'''
Created on Mar 9, 2014

@author: Gregory Kramida
'''

import utils.dev as dev
import utils.data as data
import utils.image_size as img_sz
import pyopencl as cl
import os
import math

class FilterConfig(object):
    """
    Configuration object that can be used for any of the filters interchangeably.
    It contains data that are converted to #define directives when OpenCL kernel is computed.
    The data include meta-information based on image and the device characteristics, which
    is used directly to fine-tune parallelism during kernel execution.
    """
    def __init__(self, tile_shape, cell_shape, warp_size, max_threads):
        """
        @param warp_size: number of threads/work items that can be synchronously launched by a block/work group at any given moment.
        @param max_threads: maximum number of threads / concurrent execution paths
        """
        (cell_height,cell_width) = cell_shape
        
        self.cell_shape = cell_shape
        self.tile_shape = tile_shape
        if(len(self.tile_shape) == 2):
            self.n_channels = 1
        else:
            self.n_channels = self.tile_shape[2]
        
        self.sep_group_dims = ((cell_height + max_threads - 1) / max_threads,(cell_width + max_threads - 1) / max_threads)
        self.block_dims = (cell_height / warp_size, cell_width / warp_size)
        
        self.warp_size = warp_size
        self.half_warp_size = warp_size / 2
        
        self.max_threads = max_threads
        #TODO: ensure this is the correct way to auto-tune this
        self.max_warps = max_threads / warp_size 
        #TODO: figure out how to auto-tune this
        self.schedule_optimized_n_warps = self.max_warps-1
        self.input_stride = cell_width * self.schedule_optimized_n_warps
        
    @property
    def n_rows(self):
        """
        used to determine the number of group rows for per-block processing
        """
        return self.block_dims[0]
    @property
    def n_columns(self):
        """
        used to determine the number of group columns for per-block processing
        """
        return self.block_dims[1]
    @property
    def n_sep_groups_x(self):
        """
        used to determine the number of groups for separable filters during the horizontall pass
        """
        return self.sep_group_dims[1]
    @property
    def n_sep_groups_y(self):
        """
        used to determine the number of groups for separable filters during the vertical pass
        """
        return self.sep_group_dims[0]
    @property
    def tile_width(self):
        return self.tile_shape[1]
    @property
    def tile_height(self):
        return self.tile_shape[0]
    @property
    def cell_width(self):
        return self.cell_shape[1]
    @property
    def cell_height(self):
        return self.cell_shape[0]
    @staticmethod
    def generate(device, tile_shape, tile_dir = None, cell_shape = None, verbose = False):
        """
        Generate filter configuration automatically, either based on the provided tile width, tile height, and channel
        count, or reading off these properties automatically from the first image encountered in the provided tile_dir
        @type tile_dir: str
        @param tile_dir: the directory where tiles that will be processed by the filters reside
        @type tile_width: int
        @param tile_width: width of the tiles that will be processed by the filters
        @type tile_height: int
        @param tile_height: height of the tiles that will be processed by the filters
        @return a FilterConfig object with appropriate settings
        """
        if(tile_dir is None and tile_shape is None):
            raise ValueError("If the tile_dir argument is None / not provided, tile_shape has to be specified.")
        
        if(tile_dir is not None):
            tile_names = data.get_raster_names(tile_dir)
            # avail_memory_divisor determines the fraction of available memory to use for buffer
            # we want the fraction to be smaller in case of CPU, because we're then basically using the same 
            # memory twice -- on the device and on the host
            
            if(len(tile_names) < 0):
                raise RuntimeError("""Could not find image tiles in \"\s.\"
        Please ensure the path is correct and images have jpg/png format and extensions.""" 
                % tile_dir)
            first_tile_name = tile_names[0]
            
            # assess size of the tiles (assuming all tiles are the same size)
            (tile_height, tile_width, n_channels) = img_sz.get_image_size(tile_dir + os.path.sep + first_tile_name)
            tile_shape = (tile_height, tile_width, n_channels)
                
            if(verbose):
                print "Tile Dimensions\nsize: %d, %d" % (tile_height, tile_width)
        
        if(device.type == cl.device_type.CPU):
            avail_memory_divisor = 4
        else:
            avail_memory_divisor = 2
        
        if(verbose):
            print "Using device \"%s\"" % device.name
        
        bytes_in_mb = 1048576  # ==2**20
        # create temporary OpenCL context
        context = cl.Context(devices=[device])
        # retrieve device memory information
        global_mem = device.global_mem_size
        local_mem = device.local_mem_size
        wg_size = device.get_info(cl.device_info.MAX_WORK_GROUP_SIZE)
        num_sms = device.get_info(cl.device_info.MAX_COMPUTE_UNITS)
        determine_n_processors_per_sm = dev.determine_n_processors_per_sm(device)
        max_threads = determine_n_processors_per_sm * num_sms
        
        
        # retrieve warp/wavefront size (or # of hardware threads in case of CPU)
        warp_size = dev.determine_warp_size(device, context)
        
        if(verbose):
            print """\nDevice Information
Global Memory Size: {0:0d} MiB
Local/Workgroup Memory Size: {1:0d} KiB
Warp/Wavefront: {2:0d}
Max Workgroup Size: {3:0d}
Number of Streaming Multiprocessors: {4:0d}
Best guess for number of processors per SM: {5:0d}
Best guess for maximum concurrent execution paths: {6:0d}"""\
            .format(global_mem / bytes_in_mb, 
                    local_mem / 1024, warp_size,
                    wg_size,
                    num_sms, 
                    determine_n_processors_per_sm,
                    max_threads)
            
        # determine size of OpenCL buffers
        # best guess for used VRAM
        avail_mem = dev.estimate_available_cl_device_memory(device, verbose=verbose > 0)
        
        #>>In this code, all the tiles for the OpenCL device are referred to as "cells"
        #>>The tiles loaded into memory are still called "tiles"
        #>>Printed information messages use "tiles" but are more explicit about which ones.
        #the divisior '4' signifies 4 bytes / uint32, since computations will be done in uint32
        if(cell_shape is None):
            cell_size = 2 ** int(math.log(math.sqrt(avail_mem / avail_memory_divisor / 4)) / math.log(2))
            input_buf_size = cell_size * cell_size * 4 #TODO: is this needed
            if(verbose > 0):
                print "Limiting tile size for device to {0:0d} x {0:0d} pixels ({1:0d} MiB input buffer)."\
                .format(cell_size, input_buf_size / bytes_in_mb)
            cell_shape = (cell_size,cell_size)
            
            
        return FilterConfig(tile_shape, cell_shape, warp_size, max_threads)
            
        
    def __str_helper(self, const_name, value):
        return " -D " + const_name + "=" + str(value)
    def __str__(self):
        return (self.__str_helper("WIDTH", self.cell_width) + 
            self.__str_helper("HEIGHT", self.cell_height) + 
            self.__str_helper("WARP_SIZE", self.warp_size) + 
            self.__str_helper("HALF_WARP_SIZE", self.half_warp_size) + 
            self.__str_helper("INPUT_STRIDE", self.input_stride) + 
            self.__str_helper("N_COLUMNS", self.n_columns) + 
            self.__str_helper("N_ROWS", self.n_rows) + 
            self.__str_helper("SCHEDULE_OPTIMIZED_N_WARPS", self.schedule_optimized_n_warps) +
            self.__str_helper("MAX_WARPS", self.max_warps))
    