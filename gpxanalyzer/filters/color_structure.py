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
import time;
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
n_cum_levels = np.array(
    [[24, 8, 4, 0, 0],
    [56, 40, 24, 8, 0],
    [112, 96, 64, 32, 0],
    [224, 192, 128, 64, 0]], dtype=np.uint8)

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

    
def to_hmmd_cl(raster, context, queue):
    in_img = None
    output = None
    try:
        shape_2d = (raster.shape[0], raster.shape[1])
        cs_cl_source = load_string_from_file("kernels/cs.cl")
        program = cl.Program(context, cs_cl_source).build()
        convert_to_HMMD = cl.Kernel(program, "convert_to_HMMD")
        in_img = cl.Image(context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                         cl.ImageFormat(cl.channel_order.RGBA, cl.channel_type.UNSIGNED_INT8),
                         shape_2d, hostbuf=raster)
        output = cl.Image(context, cl.mem_flags.WRITE_ONLY,
                          cl.ImageFormat(cl.channel_order.RGBA, cl.channel_type.SIGNED_INT16), shape_2d)
        evt = convert_to_HMMD(queue, shape_2d, (32, 4), in_img, output)
        res = np.zeros(raster.shape, dtype=np.uint16)
        queue.flush()
        nanny_evt = cl.enqueue_copy(queue, res, output, wait_for=[evt], origin=(0, 0), region=shape_2d)
        nanny_evt.wait()
    except MemoryError as me:
        if(in_img):
            in_img.release()
        if(output):
            output.release()
        raise me;
    
    in_img.release()
    output.release()
    
    return res

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
    
    def __init__(self, cl_manager):
        self.manager = cl_manager
        self.wg_size = 8
        
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
        self.diff_thresh_buff = cl.Buffer(cl_manager.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf=difference_thresholds)
        self.hue_levels_buff = cl.Buffer(cl_manager.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf=n_hue_levels)
        self.sum_levels_buff = cl.Buffer(cl_manager.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf= n_sum_levels)
        self.cum_levels_buff = cl.Buffer(cl_manager.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf= n_cum_levels)
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
            self.buffers_allocated = True
    
    def release(self):
        if(self.buffers_allocated):
            self.hmmd_buffer.release()
            self.source_image_map.release()
            self.buffers_allocated = False
    
    def __del__(self):
        self.release()

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
        
