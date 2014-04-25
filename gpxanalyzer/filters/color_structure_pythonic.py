'''
Created on Apr 25, 2014

@author: Gregory Kramida
@copyright: (c) Gregory Kramida 2014
@license: GNU v3
'''
import gpxanalyzer.gpxanalyzer_internals as gi
import numpy as np
import sys
import math
import timeit

amplitude_thresholds = np.array([0.0, 0.000000000001, 0.037, 0.08, 0.195, 0.32],dtype=np.float64)
n_amplitude_levels = np.array([1, 25, 20, 35, 35, 140]);

difference_thresholds = np.array([
    [0, 6, 60, 110, 256, -1],
    [0, 6, 20, 60, 110, 256],
    [0, 6, 20, 60, 110, 256],
    [0, 6, 20, 60, 110, 256]], dtype=np.int16)

n_hue_levels = np.array([
    [1, 4, 4, 4, 0],
    [1, 4, 4, 8, 8],
    [1, 4, 8, 8, 8],
    [1, 4, 16, 16, 16]], dtype=np.uint8)

n_sum_levels = np.array([
    [8, 4, 1, 1, 0],
    [8, 4, 4, 2, 1],
    [16, 4, 4, 4, 4],
    [32, 8, 4, 4, 4]], dtype=np.uint8)
n_cum_levels = np.array([
    [24, 8, 4, 0, 0],
    [56, 40, 24, 8, 0],
    [112, 96, 64, 32, 0],
    [224, 192, 128, 64, 0]], dtype=np.uint8)

def reshape_bitstrings(bts):
    return bts.transpose((1,0,2)).reshape((bts.shape[1],bts.shape[1],bts.shape[2]*2))

def convert_RGB2HMMD(raster):
    out = np.zeros(raster.shape, dtype = np.int16)
    for y in xrange(raster.shape[0]):
        for x in xrange(raster.shape[1]):
            (R,G,B) = raster[y,x,:].astype(np.int32)
        
            mx=R
            if(mx<G): mx=G
            if(mx<B): mx=B
        
            mn=R
            if(mn>G): mn=G
            if(mn>B): mn=B
        
            if (mx == mn): # ( R == G == B )//exactly gray
                hue = -1; #hue is undefined
            else:
                #solve Hue
                if(R==mx):
                    hue=float(G-B)* 60.0/(mx-mn)
        
                elif(G==mx):
                    hue=120.0+float(B-R)* 60.0/(mx-mn)
        
                elif(B==mx):
                    hue=240.0+float(R-G)* 60.0/(mx-mn)
                if(hue<0.0): hue+=360.0
        
            H = int(hue + 0.5)                #range [0,360]
            S = int((mx + mn)/2.0 + 0.5)      #range [0,255]
            D = mx - mn                       #range [0,255]
            out[y,x,:] = (H,S,D)
    return out

def to_bitstring(arr):
    bts = np.zeros((8),np.uint32)
    for bn in arr:
        idxUint = bn >> 5
        idxBit = bn - (idxUint << 5)
        bts[idxUint] |= (1 << idxBit)
    return bts

def extract_row_bitstrings(quant_cell):
    bitstrings = np.zeros((quant_cell.shape[0]*2,quant_cell.shape[1],4),dtype=np.uint32)
    for ix_row in xrange(0,quant_cell.shape[0]):
        row = quant_cell[ix_row]
        for ix_bt in xrange(0, quant_cell.shape[1]-7):
            bt = to_bitstring(row[ix_bt:ix_bt+8])
            ix_ins = ix_bt<<1
            bitstrings[ix_ins,ix_row] = bt[0:4]
            bitstrings[ix_ins+1,ix_row] = bt[4:8]
    return bitstrings

def check_row_bitstrings(quant_cell,row_bitstrings, raise_exception = False):
    rb = row_bitstrings
    for ix_row in xrange(0,row_bitstrings.shape[0]- gi.WINDOW_SIZE*2 + 2,2):
        for ix_col in xrange(0,row_bitstrings.shape[1]):
            bitstring = rb[ix_row:ix_row+2,ix_col]
            x = ix_row / 2
            y = ix_col
            sample = quant_cell[y,x:x+gi.WINDOW_SIZE].copy()
            vals = bitstring_vals(bitstring)
            sample = np.unique(sample)
            sample.sort()
            vals.sort()
            if(not np.array_equal(sample, vals)):
                if(raise_exception):
                    raise ValueError("Row bitstring failure at x,y: {0:d},{1:d}".format(x,y))
                else: 
                    return False
    return True

def agg_bitstrings(bitstring_arr):
    if(len(bitstring_arr.shape) > 2):
        bitstring_arr = bitstring_arr.transpose(1,0,2).reshape((8,-1))
    agg = np.array([0,0,0,0,0,0,0,0],dtype=np.uint32)
    for bitstring in bitstring_arr:
        agg |= bitstring
    return agg

def extract_window_bitstrings(row_bitstrings):
    bitstrings = np.zeros_like(row_bitstrings)
    for ix_row in xrange(0,row_bitstrings.shape[0],2):
        for ix_col in xrange(0,row_bitstrings.shape[1]-7):
            chunk = row_bitstrings[ix_row:ix_row+2,ix_col:ix_col+8]
            bitstring = agg_bitstrings(chunk)
            bitstrings[ix_row,ix_col] = bitstring[0:4]
            bitstrings[ix_row+1,ix_col] = bitstring[4:8]
    return bitstrings

def check_window_bitstrings(quant_cell,window_bitstrings, raise_exception = False):
    wb = window_bitstrings
    for ix_row in xrange(0,window_bitstrings.shape[0]-gi.WINDOW_SIZE+1):
        for ix_col in xrange(0,window_bitstrings.shape[1]-gi.WINDOW_SIZE+1):
            bitstring = wb[ix_row,ix_col]
            y = ix_row
            x = ix_col
            sample = np.unique(quant_cell[y:y+gi.WINDOW_SIZE,x:x+gi.WINDOW_SIZE])
            vals = bitstring_vals(bitstring)
            if(not np.array_equal(sample, vals)):
                if(raise_exception):
                    raise ValueError("Window bitstring failure at x,y: {0:d},{1:d}".format(x,y))
                else: 
                    return False
    return True

def extract_histogram(quant_cell, x, y, verbose = False, first_n_cols = None, first_n_rows = None):
    region = quant_cell[x:x+gi.REGION_SIZE,y:y+gi.REGION_SIZE]
    descr = np.zeros((gi.BASE_QUANT_SPACE,),dtype=np.uint16)
    stop_at_col = gi.REGION_CLIP
    if first_n_cols != None:
        stop_at_col = first_n_cols
    stop_at_row = gi.REGION_CLIP
    if first_n_rows != None:
        stop_at_row = first_n_rows
    for ix_col in xrange(0,stop_at_col):
        hist = np.zeros((gi.BASE_QUANT_SPACE,),dtype=np.int32)
        for ix_row in xrange(0,gi.WINDOW_SIZE):
            for ix_wincol in xrange(ix_col,ix_col + gi.WINDOW_SIZE):
                hist[region[ix_row,ix_wincol]]+=1
        for ix in xrange(0,gi.BASE_QUANT_SPACE):
            descr[ix] += int(hist[ix] > 0)
        for ix_row in xrange(gi.WINDOW_SIZE,stop_at_row + gi.WINDOW_SIZE-1):
            ix_row_sub = ix_row - gi.WINDOW_SIZE
            for ix_wincol in xrange(ix_col,ix_col + gi.WINDOW_SIZE):
                hist[region[ix_row_sub,ix_wincol]]-=1
                hist[region[ix_row,ix_wincol]]+=1
            for ix in xrange(0,gi.BASE_QUANT_SPACE):
                descr[ix] += int(hist[ix] > 0)
        if(verbose):
            print "Finished column {0:d} out of {1:d}".format(ix_col+1, stop_at_col),
            sys.stdout.flush()
            print "\r",
    return descr

def quantize_amplitude(descriptor):
    des = descriptor
    norm = gi.REGION_NORM
    n_total_levels = n_amplitude_levels.sum()
    des_out = np.zeros(des.shape,dtype=np.uint8)
    for i_bin in xrange(0,des.size):
        val = float(des[i_bin]) / norm
        quant_val = 0
        i_quant = 0
        while (i_quant+1 < amplitude_thresholds.size and val >= amplitude_thresholds[i_quant+1]):
            quant_val += n_amplitude_levels[i_quant]
            i_quant+=1
            
        next_thresh = amplitude_thresholds[i_quant+1] if i_quant+1 < n_amplitude_levels.size else 1.0
        val = int(quant_val + 
                 (val - amplitude_thresholds[i_quant]) * 
                 (n_amplitude_levels[i_quant] / (next_thresh - amplitude_thresholds[i_quant])))
        if(val == n_total_levels):
            val = n_total_levels - 1
        des_out[i_bin] = val
    return des_out
        

def bitstrings_to_histogram(window_bitstrings,x,y, verbose = False):
    chunk = window_bitstrings[y:y+gi.REGION_CLIP,x:x+gi.REGION_CLIP];
    descr = np.zeros((gi.BASE_QUANT_SPACE),dtype=np.uint16)
    i_row = 0
    for row in chunk:
        for bitstring in row:
            vals = bitstring_vals(bitstring)
            for val in vals:
                descr[val]+=1
        if verbose:
            i_row+=1
            print "Finished column {0:d} out of {1:d}".format(i_row, gi.REGION_CLIP),
            sys.stdout.flush()
            print "\r",
    return descr
        

def bitstring_vals(bitstring_arr):
    if(len(bitstring_arr.shape) > 1):
        bitstring_arr = bitstring_arr.flatten()
    vals = []
    
    for ix_uint in range(0,8):
        uint = bitstring_arr[ix_uint]
        addend = (ix_uint << 5)
        for bit_ix in range(0,32):
            if(uint & (1 << bit_ix)):
                vals.append(addend + bit_ix)
    return np.uint8(vals)


def tune_group_size(stmt):
    for x in xrange(0,9):
        y = 0
        while((2**x)*(2**y) <= 512):
            size_x = 2**x
            size_y = 2**y
            stmt = "evt = extr.program.zeroOutImage(mgr.queue,extr.bitstring_buffer.shape,({0:d},{1:d})"+\
",extr.bitstring_buffer); cl.wait_for_events([evt])".format(size_x,size_y)
            timeit.timeit(stmt)
            y+=1

def hist_bin(raster):
    log_area = math.log(float(raster.size),2)
    scale_power = max(int(0.5 * log_area - 8 + 0.5),0)
    subsample = 1 << scale_power
    window_width = 8 * subsample
    window_height = 8 * subsample
                
    mod_width = raster.shape[1] - (window_width - 1)
    mod_height = raster.shape[0] - (window_height - 1)


    hist = np.zeros((256),dtype=np.uint64)
    descr = np.zeros((256),dtype=np.uint64)
    for col in xrange(0,mod_width,subsample):
        hist[:] = 0
        stop_at = col + window_width
        for row in xrange(0,window_height,subsample):
            for loc in xrange(col,stop_at,subsample):
                val = raster[row,loc]
                hist[val]+=1
        for ix in xrange(0,len(hist)):
            if(hist[ix]):
                descr[ix] +=1
        for row in xrange(subsample,mod_height,subsample):
            del_row = row - subsample
            add_row = row + window_height - subsample
            for loc in xrange(col,stop_at,subsample):
                del_val = raster[del_row,loc]
                add_val = raster[add_row,loc]
                hist[del_val]-=1
                hist[add_val]+=1
            
            for ix in xrange(0,len(hist)):
                if(hist[ix]):
                    descr[ix] +=1
    return descr

def quantize_HMMD(raster):
    out = np.zeros((raster.shape[0],raster.shape[1]), dtype = np.uint8)
    N = 3
    for y in xrange(raster.shape[0]):
        for x in xrange(raster.shape[1]):
            (H,S,D) = raster[y,x]
            iSub = 0
            while(difference_thresholds[N,iSub + 1] <= D):
                iSub +=1
        
            Hindex = int((H / 360.0) * n_hue_levels[N,iSub]);
            if (H == 360):
                Hindex = 0
        
            Sindex = int(math.floor((S - 0.5*difference_thresholds[N,iSub])
                                    * n_sum_levels[N,iSub]
                                    / (255 - difference_thresholds[N,iSub])))
            if Sindex >= n_sum_levels[N,iSub]:
                Sindex   = n_sum_levels[N,iSub] - 1
        
            px = n_cum_levels[N,iSub] + Hindex*n_sum_levels[N,iSub] + Sindex
            out[y,x] = px
    return out