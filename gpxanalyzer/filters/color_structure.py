'''
Created on Apr 3, 2014

@author: Gregory Kramida
@copyright: (c) Gregory Kramida 2014
@license: GNU v3
'''
import pyopencl as cl
from gpxanalyzer.utils.data import load_string_from_file
import gpxanalyzer.filters.cl_manager as clm
from color_structure_pythonic import *


class CSDescriptorExtractor:
    BASE_QUANT_SPACE = 256
    REGION_SIZE = gi.REGION_SIZE
    REGION_CLIP = gi.REGION_CLIP
    WINDOW_SIZE = gi.WINDOW_SIZE
    COMPILE_STRING = "-D REGION_SIZE={0:d} -D REGION_CLIP={1:d} -D WINDOW_SIZE={2:d} -D BASE_QUANT_SPACE={3:d}"
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
                                          .format(CSDescriptorExtractor.REGION_SIZE,
                                                  CSDescriptorExtractor.REGION_CLIP,
                                                  CSDescriptorExtractor.WINDOW_SIZE,
                                                  CSDescriptorExtractor.BASE_QUANT_SPACE,))
        self.kernel_convert_to_HMMD = cl.Kernel(self.program, "convert_to_HMMD")
        self.kernel_quantize_HMMD = cl.Kernel(self.program, "quantize_HMMD")
        self.kernel_image_to_HMMD_quants = cl.Kernel(self.program, "imageToHMMDQuants")
        self.kernel_zero_out_image = cl.Kernel(self.program,"zeroOutImage")
        self.kernel_cs_descriptor_row_bitstrings = cl.Kernel(self.program, "csDescriptorRowBitstrings")           
        self.kernel_cs_descriptor_window_bitstrings = cl.Kernel(self.program, "csDescriptorWindowBitstringsBrute")
        
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
                                          hostbuf=n_sum_levels[idx])
            self.cum_levels_buff = cl.Buffer(mgr.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                             hostbuf=n_cum_levels[idx])
    
    def __alloc_bitstring_buffer(self):
        if(self.bitstring_buffer is None):
            mgr = self.manager
            self.bitstring_buffer = cl.Image(mgr.context,cl.mem_flags.READ_WRITE,
                          mgr.image_uint32_format,
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
        for buf in self.buffers:
            if buf is not None:
                buf.release()
                
    
    def __del__(self):
        self.release()
############################SUBROUTINES#################################################################################
    def __convert_to_HMMD_no_check(self,cell):
        mgr = self.manager
        if(cell.shape[2] == 3 and not mgr.supports_3channel_images):
            cell = np.append(cell,np.zeros((mgr.cell_shape[0],mgr.cell_shape[1],1),dtype=np.uint8),axis=2)
        
        self.source_image_map.write(cell)
        evt = self.kernel_convert_to_HMMD(mgr.queue, mgr.cell_shape, self.pixelwise_group_dims, 
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
            
        cl.enqueue_copy(mgr.queue,self.hmmd_buffer,hmmd_cell,origin=(0,0),region=mgr.cell_shape)
        evt = self.kernel_quantize_HMMD(mgr.queue,mgr.cell_shape, self.pixelwise_group_dims,
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
        self.source_image_map.write(cell)
        evt = self.kernel_image_to_HMMD_quants(mgr.queue,mgr.cell_shape, self.pixelwise_group_dims,
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
    
    def __extract_rowbits_no_check(self,cell):
        mgr = self.manager
        if(cell.shape[2] == 3 and not mgr.supports_3channel_images):
            cell = np.append(cell,np.zeros((mgr.cell_shape[0],mgr.cell_shape[1],1),dtype=np.uint8),axis=2)
        up_evt = self.source_image_map.write(cell)
        cl_evt = self.kernel_zero_out_image(mgr.queue,self.bitstring_buffer.shape,self.pixelwise_group_dims,self.bitstring_buffer)
        evt1 = self.kernel_image_to_HMMD_quants(mgr.queue,mgr.cell_shape, self.pixelwise_group_dims,
                              self.source_image_map.image_dev,self.quant_buffer,self.diff_thresh_buff,
                              self.hue_levels_buff,self.sum_levels_buff,self.cum_levels_buff, wait_for = [up_evt,cl_evt])
        evt2 = self.kernel_cs_descriptor_row_bitstrings(mgr.queue,(mgr.cell_height,),(mgr.warp_size,),self.quant_buffer, 
                                         self.bitstring_buffer, wait_for=[evt1])
        out = np.zeros((mgr.cell_height*2,mgr.cell_width,4),dtype=np.uint32)
        cl.enqueue_copy(mgr.queue, out, self.bitstring_buffer, origin = (0,0), 
                                 region = self.bitstring_buffer.shape, wait_for = [evt2])
        return out
    
    def extract_rowbits(self,cell):
        self.__alloc_source_map()
        self.__alloc_quant_buffer()
        self.__alloc_thresholds()
        self.__alloc_bitstring_buffer()
        self.extract_rowbits=self.__extract_rowbits_no_check
        return self.__extract_rowbits_no_check(cell)
    
    def __extract_bitstrings_no_check(self,cell):
        mgr = self.manager
        if(cell.shape[0] != mgr.cell_height or cell.shape[1] != cell.cell_width()):
            n_channels = 3 if mgr.supports_3channel_images else 4
            padded = np.zeros((mgr.cell_height,mgr.cell_width,n_channels),dtype=np.uint8)
            if(cell.shape[2] == 3):
                np.copyto(padded[0:cell.shape[0],0:cell.shape[1],0:3],cell)
            else:
                np.copyto(padded[0:cell.shape[0],0:cell.shape[1]],cell)
            cell = padded
        if(cell.shape[2] == 3 and not mgr.supports_3channel_images):
            cell = np.append(cell,np.zeros((mgr.cell_shape[0],mgr.cell_shape[1],1),dtype=np.uint8),axis=2)
        
        up_evt = self.source_image_map.write(cell)
        
        cl_evt = self.kernel_zero_out_image(mgr.queue,self.bitstring_buffer.shape,self.pixelwise_group_dims,self.bitstring_buffer)
        evt1 = self.kernel_image_to_HMMD_quants(mgr.queue,mgr.cell_shape, self.pixelwise_group_dims,
                              self.source_image_map.image_dev,self.quant_buffer,self.diff_thresh_buff,
                              self.hue_levels_buff,self.sum_levels_buff,self.cum_levels_buff, wait_for = [up_evt,cl_evt])
        evt2 = self.kernel_cs_descriptor_row_bitstrings(mgr.queue,(mgr.cell_height,),(mgr.warp_size,),self.quant_buffer, 
                                         self.bitstring_buffer, wait_for=[evt1])
        evt3 = self.kernel_cs_descriptor_window_bitstrings(mgr.queue,(mgr.cell_height,),(mgr.warp_size,),self.bitstring_buffer, 
                                            self.bitstring_buffer, wait_for=[evt2])
        out = np.zeros((mgr.cell_height*2,mgr.cell_width,4),dtype=np.uint32)
        cl.enqueue_copy(mgr.queue, out, self.bitstring_buffer, origin = (0,0), 
                                 region = self.bitstring_buffer.shape, wait_for = [evt3])
        return out.transpose((1,0,2)).reshape((out.shape[1],out.shape[1],out.shape[2]*2))

    def extract_bitstrings(self,cell):
        self.__alloc_source_map()
        self.__alloc_quant_buffer()
        self.__alloc_thresholds()
        self.__alloc_bitstring_buffer()
        self.extract_bitstrings=self.__extract_bitstrings_no_check
        return self.__extract_bitstrings_no_check(cell)
    
    def __extract_quant_bitstrings_no_check(self,quant_cell):
        mgr = self.manager
        qb = self.quant_buffer
        up_evt = cl.enqueue_copy(mgr.queue,qb,quant_cell,origin = (0,0), region = qb.shape)
        cl_evt = self.kernel_zero_out_image(mgr.queue,self.bitstring_buffer.shape,self.pixelwise_group_dims,self.bitstring_buffer)
        evt1 = self.kernel_cs_descriptor_row_bitstrings(mgr.queue,(mgr.cell_height,),(mgr.warp_size,),self.quant_buffer, 
                                         self.bitstring_buffer, wait_for = [up_evt,cl_evt])
        evt2 = self.kernel_cs_descriptor_window_bitstrings(mgr.queue,(mgr.cell_height,),(mgr.warp_size,),self.bitstring_buffer, 
                                            self.bitstring_buffer, wait_for=[evt1])
        out = np.zeros((mgr.cell_height*2,mgr.cell_width,4),dtype=np.uint32)
        cl.enqueue_copy(mgr.queue, out, self.bitstring_buffer, origin = (0,0), 
                                 region = self.bitstring_buffer.shape, wait_for = [evt2])
        return out.transpose((1,0,2)).reshape((out.shape[1],out.shape[1],out.shape[2]*2))

    def extract_quant_bitstrings(self, quant_cell):
        self.__alloc_quant_buffer()
        self.__alloc_bitstring_buffer()
        self.extract_quant_bitstrings=self.__extract_quant_bitstrings_no_check
        return self.__extract_quant_bitstrings_no_check(quant_cell)
    
    def extract_descriptor(self,cell,x,y):
        return gi.bitstrings_to_descriptor(cell,x,y)
        
