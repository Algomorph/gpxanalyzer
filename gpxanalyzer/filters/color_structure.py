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
import cl_manager as clm
import math;

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

class ColorStructureDescriptorExtractor:
    COMPILE_STRING = "-D WIDTH={0:d} -D HEIGHT={1:d} -D SUBSAMPLE={2:d} -D WINSIZE={3:d}"+\
                                          " -D BASE_QUANT_SPACE=256 -D GROUP_SIZE={4:d}"
    @staticmethod
    def calc_winsize(cell_size):
        log_area = math.log(float(cell_size*cell_size),2)
        scale_power = max(int(math.floor(0.5 * log_area - 8 + 0.5)),0)
        subsample = 1 << scale_power
        winsize = 8 * subsample
        return winsize,subsample
    
    def __init__(self, cl_manager, quant_index = 3):
        self.manager = cl_manager
        self.wg_size = 8
        self.quant_index = 3;
        
        cs_cl_source = load_string_from_file("kernels/cs.cl")
        
        mgr = cl_manager
        winsize,subsample= ColorStructureDescriptorExtractor.calc_winsize(mgr.cell_height)
        self.winsize = winsize
        self.subsample = subsample
        
        mod_width = mgr.cell_width - (winsize - 1)
        mod_height = mgr.cell_height - (winsize - 1)
        self.mod_width = mod_width
        self.mod_height = mod_height

        self.program = cl.Program(cl_manager.context, 
                                  cs_cl_source
                                  ).build(ColorStructureDescriptorExtractor.COMPILE_STRING
                                          .format(mod_width,mod_height,subsample,winsize,self.wg_size))
        
        
        self.hmmd_group_dims = (32, 4)
        self.hist_global_dims =(mgr.cell_width / subsample,)
        self.hist_group_dims = (self.wg_size,)
        
        self.buffers_allocated = False
        
    def recompile(self):
        self.program = cl.Program(self.manager.context, 
                                  load_string_from_file("kernels/cs.cl")
                                  ).build(ColorStructureDescriptorExtractor.COMPILE_STRING
                                          .format(self.mod_width,self.mod_height,self.subsample,
                                                  self.winsize,self.wg_size))
        
    def allocate_buffers(self):
        if(not self.buffers_allocated):
            cl_manager = self.manager
            self.source_image_map = clm.ImageCLMap(cl_manager, cl.mem_flags.READ_ONLY, cl_manager.image_uint8_format)
            self.hmmd_buffer = cl.Image(cl_manager.context, cl.mem_flags.READ_WRITE, 
                                        cl_manager.image_int16_format, cl_manager.cell_shape)
            self.quant_buffer = cl.Image(cl_manager.context, cl.mem_flags.READ_WRITE,
                                         cl.ImageFormat(cl.channel_order.A, cl.channel_type.UNSIGNED_INT8),
                                         cl_manager.cell_shape)
            idx = self.quant_index
            self.diff_thresh_buff = cl.Buffer(cl_manager.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf=difference_thresholds[idx])
            self.hue_levels_buff = cl.Buffer(cl_manager.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf=n_hue_levels[idx])
            self.sum_levels_buff = cl.Buffer(cl_manager.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf= n_sum_levels[idx])
            self.cum_levels_buff = cl.Buffer(cl_manager.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf= n_cum_levels[idx])
            self.buffers_allocated = True
    
    def release(self):
        if(self.buffers_allocated):
            self.hmmd_buffer.release()
            self.source_image_map.release()
            self.buffers_allocated = False
    
    def __del__(self):
        self.release()
        
    def convert_cell_to_HMMD(self,cell):
        convert_to_HMMD = cl.Kernel(self.program, "convert_to_HMMD")
        mgr = self.manager
        if(not self.buffers_allocated):
            self.allocate_buffers()
        self.source_image_map.write(cell)
        evt = convert_to_HMMD(mgr.queue, mgr.cell_shape, self.hmmd_group_dims, 
                                    self.source_image_map.image_dev, self.hmmd_buffer)
        out = np.zeros(cell.shape,dtype=np.int16)
        cl.enqueue_copy(mgr.queue, out, self.hmmd_buffer, origin = (0,0), region = mgr.cell_shape, wait_for = [evt])
        return out
        
        

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
                convert_to_HMMD(mgr.queue, mgr.cell_shape, self.hmmd_group_dims, 
                                self.source_image_map.image_dev, self.hmmd_buffer)
                quantize_HMMD(mgr.queue,mgr.cell_shape, self.hmmd_group_dims,
                              self.hmmd_buffer,self.quant_buffer,self.diff_thresh_buff,
                              self.hue_levels_buff,self.sum_levels_buff,self.cum_levels_buff)    
                
                
                
                x_start = x_end
            y_start = y_end
        
