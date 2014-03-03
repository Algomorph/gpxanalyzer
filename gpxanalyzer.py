#!/usr/bin/env python
import os
import sys
import argparse
import numpy as np
import cv2
import pyopencl as cl
import math
import utils.data as data
import utils.dev as dev
import utils.image_size as img_sz
import utils.tilecombiner as tilecombiner

# command line argument parser
parser = argparse.ArgumentParser(description='''Gigapixel Image Analyzer.''')
parser.add_argument("--input_folder", "-i", default="test",
                    help="path to the original gigapixel image tiles")
parser.add_argument("--output_folder", "-o", default="test_output",
                    help="path to the output folder")
parser.add_argument("--device_type", "-dt", default=dev.dev_type_by_name.keys()[0],
                    metavar="DEVICE_TYPE",
                    choices=dev.dev_type_by_name.keys(),
                    help="OpenCL device type, can be one of %s" % str(dev.dev_type_by_name.keys()))
parser.add_argument("--verbose", "-v", type=int, default=1, help="verbosity level")
parser.add_argument("--device_index", "-di", type=int, default=0, help="index of the device to use")
parser.add_argument("--list_devices", "-ld", action="store_true", default=False, help="list all available opencl devices and associate indexes, then exit")
parser.add_argument("--combine_tiles", "-ct", action="store_true", default=False, help="use with the --output_folder and --size arguments to combine small image tiles into bigger ones")
parser.add_argument("--output_tile_size", "-ots", type=int, default=16384,
                    help="width/height of the resulting tiles for the --combine_tiles operation")


def run_analysis(input_folder, device_type, device_index, verbose=0):
    '''
    Runs analysis on the Gigapixel image using the specified OpenCL device.
    @type input_folder: String
    @param input_folder: folder from where the gigapixel tile images will be loaded from
    @type device_type: pyopencl.device_type
    @param device_type: type of OpenCL device to use
    @type device_index: int
    @param device_index: a non-negative index of the device to use. To view device indices, user must
    run the program with the --list_devices argument.
    @type verbose: int
    @param verbose: verbosity level
    '''
    tile_names = data.get_raster_names(input_folder)
    
    
    num_image_channels = 3
    # avail_memory_divisor determines the fraction of available memory to use for buffer
    # we want the fraction to be smaller in case of CPU, because we're then basically using the same 
    # memory twice -- on the device and on the host
    if(device_type == cl.device_type.CPU):
        avail_memory_divisor = 4
    else:
        avail_memory_divisor = 2
    if(len(tile_names) < 0):
        raise RuntimeError("""Could not find image tiles in \"\s.\"
Please ensure the path is correct and images have jpg/png format and extensions.""" 
        % input_folder)
    first_tile_name = tile_names[0]
    
    # assess size of the tiles (assuming all tiles are the same size)
    (tile_height, tile_width) = img_sz.get_image_size(input_folder + os.path.sep + first_tile_name)
    if(verbose > 0):
        print "Tile Dimensions\nsize: %d, %d" % (tile_height, tile_width)
    tile_size = max(tile_height,tile_width)
    
    devices = dev.get_devices_of_type(device_type)
    
    if(len(devices) < 1):
        raise ValueError("""No devices of type %s found on the system.
Perhaps, try specifying a different device type?""")
    # get device based on specified index
    device = devices[device_index]
    print "Using device \"%s\"" % device.name
    
    bytes_in_mb = (1024 ** 2)  # ==2**20
    # create OpenCL context
    context = cl.Context(devices=[device])
    # retrieve device memory information
    global_mem = device.global_mem_size
    local_mem = device.local_mem_size
    wg_size = device.get_info(cl.device_info.MAX_WORK_GROUP_SIZE)
    num_sms = device.get_info(cl.device_info.MAX_COMPUTE_UNITS)
    processors_per_sm = dev.processors_per_sm(device)
    max_threads = processors_per_sm * num_sms
    
    
    # retrieve warp/wavefront size (or # of hardware threads in case of CPU)
    warp_size = dev.determine_warp_size(device, context)
    if(verbose > 0):
        print """\nDevice Information
  Global Memory Size: {0:0d} MiB
  Local/Workgroup Memory Size: {1:0d} KiB
  Warp/Wavefront: {2:0d}
  Number of Streaming Multiprocessors: {3:0d}
  Best guess for number of processors per SM: {4:0d}
  Best guess for maximum concurrent execution paths: {5:0d}"""\
        .format(global_mem / bytes_in_mb, local_mem / 1024, warp_size, num_sms, processors_per_sm, max_threads)
        
    # determine size of OpenCL buffers
    # best guess for used VRAM
    avail_mem = dev.estimate_available_device_memory(device, verbose=verbose > 0)
    
    #>>HENCEFORTH in the code, all the tiles for the OpenCL device are referred to as "cells"
    #>>The tiles loaded into memory are still called "tiles"
    #>>Printed information messages use "tiles" but are more explicit about which ones.
    
    #the reason num_image_channels is multiplied by 4 is that we need intermediate buffers of int4 size for each channel
    cell_size = 2 ** int(math.log(math.sqrt(avail_mem / (num_image_channels + num_image_channels*4) / avail_memory_divisor)) / math.log(2))
    input_buf_size = cell_size * cell_size * num_image_channels
    if(verbose > 0):
        print "Limiting tile size for device to {0:0d} x {0:0d} pixels ({1:0d} MiB input buffer)."\
        .format(cell_size, input_buf_size / bytes_in_mb)
    
    #TODO: for now, convert to floats and run old sat.cl. Later, switch up the kernels to load the texture instead.
    #traverse the file tiles
    for tile_name in tile_names:
        full_path = input_folder + os.path.sep + tile_name
        #load tile into main memory
        tile = cv2.imread(full_path)
        n_cells_y = tile.shape[0] / cell_size
        n_cells_x = tile.shape[1] / cell_size
        #extract smaller cells one-by-one
        x_start = 0;
        x_end = cell_size
        for cell_x in xrange(n_cells_x):
            y_start = 0;
            y_end = cell_size
            for cell_y in xrange(n_cells_y):
                
                y_start = y_end
                y_end += cell_size
            x_start = x_end
            x_end+=cell_size

# main entry point
if __name__ == '__main__':
    args = parser.parse_args(sys.argv[1:])
    if(args.combine_tiles):
        tilecombiner.combine_tiles(args.input_folder, args.output_folder, args.output_tile_size)
    elif(args.list_devices):
        dev.list_devices()
    else:
        input_folder = args.input_folder
        verbose = args.verbose
        # get device type from user's choice
        device_type = dev.dev_type_by_name[args.device_type]
        device_index = args.device_index
        run_analysis(input_folder, device_type, device_index, verbose)
     
    
    
    
    
    
    
    
