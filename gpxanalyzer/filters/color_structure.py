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

def to_hmmd_py(raster):
    out = np.zeros(raster.shape, dtype=np.int16)
    for i_row in xrange(raster.shape[0]):
        for i_col in xrange(raster.shape[1]):
            (R, G, B) = raster[i_row, i_col, 0:3]
            max = R
            if(max < G): max = G
            if(max < B): max = B
        
            min = R
            if(min > G): min = G
            if(min > B): min = B
        
            if (max == min):  # ( R == G == B )//exactly gray
                hue = -1.5;  # hue is undefined
            else:
                # solve Hue
                if(R == max):
                    hue = ((G - B) / (float)(max - min));
                elif(G == max):
                    hue = (2.0 + (B - R) / (float)(max - min));
                elif(B == max):
                    hue = (4.0 + (R - G) / (float)(max - min));
        
                hue *= 60
                if(hue < 0.0): hue += 360

            H = int(hue + 0.5)  # range [0,360]
            S = int((max + min) / 2.0 + 0.5)  # range [0,255]
            D = int(max - min + 0.5)  # range [0,255]
            out[i_row, i_col, 0:3] = (H, S, D)
    return out
    
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
    
    def __init__(self, cl_manager):
        self.manager = cl_manager
        self.source_image_map = clm.ImageCLMap(cl_manager, cl_manager.image_uint8_format)
        self.hmmd_buffer = cl.Image(cl_manager.context, cl.mem_flags.READ_WRITE, 
                                    cl_manager.image_int16_format, cl_manager.cell_shape)
        self.quant_buffer = cl.Image(cl_manager.context, cl.mem_flags.READ_WRITE,
                                     cl.ImageFormat(cl.channel_order.A, cl.channel_type.UNSIGNED_INT8),
                                     cl_manager.cell_shape)
        cs_cl_source = load_string_from_file("kernels/cs.cl")
        self.program = cl.Program(cl_manager.context, cs_cl_source).build()
        self.hmmd_group_dims = (32, 4)
        self.diff_thresh_buff = cl.Buffer(cl_manager.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf=difference_thresholds)
        self.hue_levels_buff = cl.Buffer(cl_manager.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf=n_hue_levels)
        self.sum_levels_buff = cl.Buffer(cl_manager.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf= n_sum_levels)
        self.cum_levels_buff = cl.Buffer(cl_manager.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                          hostbuf= n_cum_levels)
        
    
    def release(self):
        self.hmmd_buffer.release()
        self.source_image_map.release()

    def extract(self, tile, length):
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
#     if(slideHeight % subSample == 0) {
#         moduloSlideHeight = slideHeight;
#     }
#     else {
#         moduloSlideHeight = slideHeight +
#           (subSample - slideHeight % subSample);
#     }
                log_area = math.log(float(cell.size),2)
                scale_power = max(int(0.5 * log_area - 8 + 0.5),0)
                sub_sample = 1 << scale_power
                slide_width = 8 * sub_sample
                slide_height = 8 * sub_sample
                
                mod_width = cell.shape[1] - (slide_width - 1)
                mod_height = cell.shape[0] - (slide_height - 1)
                if(slide_height % sub_sample == 0):
                    mod_slide_height = slide_height
                else:
                    mod_slide_height = slide_height + (sub_sample - slide_height % sub_sample)
                    
                
                
                x_start = x_end
            y_start = y_end
        
