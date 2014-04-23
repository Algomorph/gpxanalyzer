'''
Created on Apr 3, 2014

@author: Gregory Kramida
@copyright: (c) Gregory Kramida 2014
@license: GNU v3
'''
from gpxanalyzer.utils import system
import pyopencl as cl
from gpxanalyzer.utils.data import load_string_from_file
import numpy as np
import gpxanalyzer.filters.cl_manager as clm
import libMPEG7 as mp7
import math;
from numpy import dtype

cqt256_064 = np.array([
 0,  0,  0,  0,  0,  0,  0,  0,  1,  1,  1,  1,  1,  1,  1,  1,
 2,  2,  2,  2,  2,  2,  2,  2,  3,  3,  3,  3,  3,  3,  3,  3,
 4,  4,  4,  4,  4,  4,  4,  4,  5,  5,  5,  5,  5,  5,  5,  5,
 6,  6,  6,  6,  6,  6,  6,  6,  7,  7,  7,  7,  7,  7,  7,  7,
 8,  8,  9,  9,  8,  8,  9,  9, 10, 10, 11, 11, 10, 10, 11, 11,
12, 12, 13, 13, 12, 12, 13, 13, 14, 14, 15, 15, 14, 14, 15, 15,
16, 16, 17, 17, 16, 16, 17, 17, 18, 18, 19, 19, 18, 18, 19, 19,
20, 20, 21, 21, 20, 20, 21, 21, 22, 22, 23, 23, 22, 22, 23, 23,
24, 25, 26, 27, 24, 25, 26, 27, 24, 25, 26, 27, 24, 25, 26, 27,
28, 29, 30, 31, 28, 29, 30, 31, 28, 29, 30, 31, 28, 29, 30, 31,
32, 33, 34, 35, 32, 33, 34, 35, 32, 33, 34, 35, 32, 33, 34, 35,
36, 37, 38, 39, 36, 37, 38, 39, 36, 37, 38, 39, 36, 37, 38, 39,
40, 40, 41, 41, 42, 42, 43, 43, 44, 44, 45, 45, 46, 46, 47, 47,
48, 48, 49, 49, 50, 50, 51, 51, 52, 52, 53, 53, 54, 54, 55, 55,
56, 56, 56, 56, 57, 57, 57, 57, 58, 58, 58, 58, 59, 59, 59, 59,
60, 60, 60, 60, 61, 61, 61, 61, 62, 62, 62, 62, 63, 63, 63, 63 ],dtype=np.uint8)

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
    for bin in arr:
        idxUint = bin >> 5
        idxBit = bin - (idxUint << 5)
        bts[idxUint] |= (1 << idxBit)
    return bts

def extract_row_bitstrings(cell):
    bitstrings = np.zeros((cell.shape[0]*2,cell.shape[1],4),dtype=np.uint32)
    for ix_row in xrange(0,cell.shape[0]):
        row = cell[ix_row]
        for ix_bt in xrange(0, cell.shape[1]-7):
            bt = to_bitstring(row[ix_bt:ix_bt+8])
            ix_ins = ix_bt<<1
            bitstrings[ix_ins,ix_row] = bt[0:4]
            bitstrings[ix_ins+1,ix_row] = bt[4:8]
    return bitstrings


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

class CSDescriptorExtractor:
    BASE_QUANT_SPACE = 256
    REGION_SIZE = 256
    COMPILE_STRING = "-D CUTOFF_WIDTH={0:d} -D CUTOFF_HEIGHT={1:d} -D SUBSAMPLE={2:d} -D WINSIZE={3:d}"+\
                                          " -D BASE_QUANT_SPACE={4:d} -D GROUP_WIDTH={5:d}"+\
                                          " -D REGION_WIDTH={6:d} -D REGION_HEIGHT={6:d} -D REGION_GROUP_COUNT={7:d}"+\
                                          " -D ITEMS_PER_QUANT_DESCR={8:d}"
    descr_size_by_index ={0:32,
                          1:64,
                          2:128,
                          3:BASE_QUANT_SPACE
                          }
    @staticmethod
    def calc_winsize(cell_size):
        log_area = math.log(float(cell_size*cell_size),2)
        scale_power = max(int(math.floor(0.5 * log_area - 8 + 0.5)),0)
        subsample = 1 << scale_power
        winsize = 8 * subsample
        return winsize,subsample
    
    def __init__(self, cl_manager, quant_index = 3):
        self.manager = cl_manager
        mgr = cl_manager
        dev = mgr.context.devices[0]
        mem_per_descriptor= 4*CSDescriptorExtractor.BASE_QUANT_SPACE
        #leave half for registers and other junk
        #we need a single group to fit a number of descriptors in local memory
        self.group_width = dev.local_mem_size / 2 / mem_per_descriptor 
        self.quant_index = 3;
        
        winsize,subsample= CSDescriptorExtractor.calc_winsize(self.REGION_SIZE)
        self.winsize = winsize
        self.subsample = subsample
        
        mod_width = mgr.cell_width - (winsize - 1)
        mod_height = mgr.cell_height - (winsize - 1)
        self.mod_width = mod_width
        self.mod_height = mod_height

        self.recompile()
        
        
        self.pixelwise_group_dims = (mgr.warp_size, 4)
        self.hist_global_dims =(mgr.cell_width / subsample,)
        self.hist_group_dims = (self.group_width,)
        
        #buffers - all set to None
        self.source_image_map = None
        self.hmmd_buffer = None
        self.quant_buffer = None
        self.bitstring_buffer = None
        self.diff_thresh_buff = None
        self.sum_levels_buff = None
        self.hue_levels_buff = None
        self.cum_levels_buff = None
        self.buffers = [self.source_image_map, self.hmmd_buffer, self.quant_buffer, self.bitstring_buffer,
                        self.diff_thresh_buff,self.sum_levels_buff,self.hue_levels_buff,self.cum_levels_buff]
        
        
    def recompile(self):
        self.program = cl.Program(self.manager.context, 
                                  load_string_from_file("kernels/cs.cl")
                                  ).build(CSDescriptorExtractor.COMPILE_STRING
                                          .format(self.mod_width,self.mod_height,self.subsample,
                                                  self.winsize,self.BASE_QUANT_SPACE,self.group_width,
                                                  self.REGION_SIZE, self.REGION_SIZE / self.group_width, 
                                                  self.BASE_QUANT_SPACE / self.group_width))
#############CL BUFFER/IMAGE ALLOCATIONS################################################################################
    def __alloc_hmmd_buffer(self):
        if(self.hmmd_buffer is None):
            mgr = self.manager
            self.hmmd_buffer = cl.Image(mgr.context, cl.mem_flags.READ_WRITE, 
                                        mgr.image_int16_format, mgr.cell_shape)
            
    def __alloc_thresholds(self):
        if(self.diff_thresh_buff is None):
            idx = self.quant_index
            mgr = self.manager
            self.diff_thresh_buff = cl.Buffer(mgr.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf=difference_thresholds[idx])
            self.hue_levels_buff = cl.Buffer(mgr.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf=n_hue_levels[idx])
            self.sum_levels_buff = cl.Buffer(mgr.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf= n_sum_levels[idx])
            self.cum_levels_buff = cl.Buffer(mgr.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                             hostbuf= n_cum_levels[idx])
    
    def __alloc_bitstring_buffer(self):
        if(self.bitstring_buffer is None):
            mgr = self.manager
            self.bitstring_buffer = cl.Image(mgr.context,cl.mem_flags.READ_WRITE,
                          cl.ImageFormat(cl.channel_order.RGBA,cl.channel_type.UNSIGNED_INT32),
                          shape = (mgr.cell_width, mgr.cell_height*2))
        
        
    def __alloc_source_map(self):
        if(self.source_image_map is None):
            mgr = self.manager
            self.source_image_map = clm.ImageCLMap(mgr, cl.mem_flags.READ_ONLY, mgr.image_uint8_format)
           
           
    def __alloc_quant_buffer(self):
        if(self.quant_buffer is None):
            mgr = self.manager
            self.quant_buffer = cl.Image(mgr.context, cl.mem_flags.READ_WRITE,
                                         cl.ImageFormat(cl.channel_order.R, cl.channel_type.UNSIGNED_INT8),
                                         mgr.cell_shape)
########################################################################################################################    
    def release(self):
        for buffer in self.buffers:
            if buffer is not None:
                buffer.release()
                
    
    def __del__(self):
        self.release()
############################SUBROUTINES#################################################################################
    def __convert_to_HMMD_no_check(self,cell):
        mgr = self.manager
        #TODO: make accept 3-channel cell
        if(cell.shape[2] == 3 and not mgr.supports_3channel_images):
            cell = np.append(cell,np.zeros((mgr.cell_shape[0],mgr.cell_shape[1],1),dtype=np.uint8),axis=2)
        convert_to_HMMD = cl.Kernel(self.program, "convert_to_HMMD")
        
        self.source_image_map.write(cell)
        evt = convert_to_HMMD(mgr.queue, mgr.cell_shape, self.pixelwise_group_dims, 
                                    self.source_image_map.image_dev, self.hmmd_buffer)
        out = np.zeros(cell.shape,dtype=np.int16)
        cl.enqueue_copy(mgr.queue, out, self.hmmd_buffer, origin = (0,0), region = mgr.cell_shape, wait_for = [evt])
        return out
        
    def convert_to_HMMD(self,cell):
        self.__alloc_source_map()
        self.__alloc_hmmd_buffer()
        self.convert_to_HMMD = self.__convert_to_HMMD_no_check
        return self.__convert_to_HMMD_no_check(cell)
        
    def __quantize_HMMD_no_check(self,hmmd_cell):
        mgr = self.manager
        if(hmmd_cell.shape[2] == 3 and not mgr.supports_3channel_images):
            hmmd_cell = np.append(hmmd_cell,np.zeros((mgr.cell_shape[0],mgr.cell_shape[1],1),dtype=np.int16),axis=2)
            
        quantize_HMMD = cl.Kernel(self.program, "quantize_HMMD")
        cl.enqueue_copy(mgr.queue,self.hmmd_buffer,hmmd_cell,origin=(0,0),region=mgr.cell_shape)
        evt = quantize_HMMD(mgr.queue,mgr.cell_shape, self.pixelwise_group_dims,
                              self.hmmd_buffer,self.quant_buffer,self.diff_thresh_buff,
                              self.hue_levels_buff,self.sum_levels_buff,self.cum_levels_buff)
        out = np.zeros(mgr.cell_shape,dtype=np.uint8)
        cl.enqueue_copy(mgr.queue, out, self.quant_buffer, origin = (0,0), region = mgr.cell_shape, wait_for = [evt])
        return out
    
    def quantize_HMMD(self,hmmd_cell):
        self.__alloc_hmmd_buffer()
        self.__alloc_quant_buffer()
        self.__alloc_thresholds()
        self.quantize_HMMD = self.__quantize_HMMD_no_check
        return self.__quantize_HMMD_no_check(hmmd_cell)
    
    def __quantize_no_check(self,cell):
        mgr = self.manager
        if(cell.shape[2] == 3 and not mgr.supports_3channel_images):
            cell = np.append(cell,np.zeros((mgr.cell_shape[0],mgr.cell_shape[1],1),dtype=np.uint8),axis=2)
        imageToHMMDQuants = cl.Kernel(self.program, "imageToHMMDQuants")
        self.source_image_map.write(cell)
        evt = imageToHMMDQuants(mgr.queue,mgr.cell_shape, self.pixelwise_group_dims,
                              self.source_image_map.image_dev,self.quant_buffer,self.diff_thresh_buff,
                              self.hue_levels_buff,self.sum_levels_buff,self.cum_levels_buff)
        out = np.zeros(mgr.cell_shape,dtype=np.uint8)
        cl.enqueue_copy(mgr.queue, out, self.quant_buffer, origin = (0,0), region = mgr.cell_shape, wait_for = [evt])
        return out
        
    def quantize(self,cell):
        self.__alloc_source_map()
        self.__alloc_quant_buffer()
        self.__alloc_thresholds()
        self.quantize = self.__quantize_no_check
        return self.__quantize_no_check(cell)
    
    def __extract_bitstrings_no_check(self,cell):
        mgr = self.manager
        if(cell.shape[2] == 3 and not mgr.supports_3channel_images):
            cell = np.append(cell,np.zeros((mgr.cell_shape[0],mgr.cell_shape[1],1),dtype=np.uint8),axis=2)
        imageToHMMDQuants = cl.Kernel(self.program, "imageToHMMDQuants")
        csDescriptorRowBitstrings = cl.Kernel(self.program, "csDescriptorRowBitstrings")
        csDescriptorWindowBitstrings = cl.Kernel(self.program, "csDescriptorWindowBitstringsBrute")
        
        up_evt = self.source_image_map.write(cell)
        evt1 = imageToHMMDQuants(mgr.queue,mgr.cell_shape, self.pixelwise_group_dims,
                              self.source_image_map.image_dev,self.quant_buffer,self.diff_thresh_buff,
                              self.hue_levels_buff,self.sum_levels_buff,self.cum_levels_buff, wait_for = [up_evt])
        evt2 = csDescriptorRowBitstrings(mgr.queue,(mgr.cell_height,),(mgr.warp_size,),self.quant_buffer, 
                                         self.bitstring_buffer, wait_for=[evt1])
        evt3 = csDescriptorWindowBitstrings(mgr.queue,(mgr.cell_height,),(mgr.warp_size,),self.bitstring_buffer, 
                                            self.bitstring_buffer, wait_for=[evt2])
        out = np.zeros((mgr.cell_height*2,mgr.cell_width,4),dtype=np.uint32)
        dl_evt = cl.enqueue_copy(mgr.queue, out, self.bitstring_buffer, origin = (0,0), 
                                 region = self.bitstring_buffer.shape, wait_for = [evt3])
        return out
        
    
    def extract_bitstrings(self,cell):
        self.__alloc_source_map()
        self.__alloc_quant_buffer()
        self.__alloc_thresholds()
        self.__alloc_bitstring_buffer()
        self.extract_bitstrings=self.__extract_bitstrings_no_check
        return self.__extract_bitstrings_no_check(cell)
########################################################################################################################


    def extract(self, tile, length):
        self.allocate_buffers()
        mgr = self.manager
        y_start = 0
        convert_to_HMMD = cl.Kernel(self.program, "convert_to_HMMD")
        quantize_HMMD = cl.Kernel(self.program,"quantize_HMMD")
        for y_end in xrange(mgr.cell_height, tile.shape[0] + 1, mgr.cell_height):
            x_start = 0 
            for x_end in xrange(mgr.cell_width, tile.shape[1] + 1, mgr.cell_width):
                cell = tile[y_start:y_end, x_start:x_end, :]
                self.source_image_map.write(cell)
                convert_to_HMMD(mgr.queue, mgr.cell_shape, self.pixelwise_group_dims, 
                                self.source_image_map.image_dev, self.hmmd_buffer)
                quantize_HMMD(mgr.queue,mgr.cell_shape, self.pixelwise_group_dims,
                              self.hmmd_buffer,self.quant_buffer,self.diff_thresh_buff,
                              self.hue_levels_buff,self.sum_levels_buff,self.cum_levels_buff)    
                
                
                
                x_start = x_end
            y_start = y_end
        
