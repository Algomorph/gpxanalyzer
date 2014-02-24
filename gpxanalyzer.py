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

#command line argument parser
parser = argparse.ArgumentParser(description='''Gigapixel Image Analyzer.''')
parser.add_argument("--input_folder","-i",default="test",
                    help="path to the original gigapixel image tiles")
parser.add_argument("--output_folder","-o",default="test_output",
                    help="path to the output folder")
parser.add_argument("--device_type","-dt",default=dev.dev_type_by_name.keys()[0],
                    metavar="DEVICE_TYPE",
                    choices=dev.dev_type_by_name.keys(),
                    help="OpenCL device type, can be one of %s" % str(dev.dev_type_by_name.keys()) )
parser.add_argument("--verbose","-v",type=int,default=1,help="verbosity level")
parser.add_argument("--device_index","-di",type=int,default=0,help="index of the device to use")
parser.add_argument("--list_devices","-ld",action="store_true",default=False,help="list all available opencl devices and exit")
parser.add_argument("--combine_tiles","-ct",action="store_true",default=False,help="use with the --output_folder and --size arguments to combine small image tiles into bigger ones")
parser.add_argument("--output_tile_size","-ots",type=int,default=16384,
                    help="width/height of the resulting tiles for the --combine_tiles operation")


def run_analysis(input_folder, device_type, device_index, verbose = 0):
    tile_names = data.get_raster_names(input_folder)
    if(len(tile_names) < 0):
        raise RuntimeError("""Could not find image tiles in \"\s.\"
        Please ensure the path is correct and images have jpg/png format and extensions.""" % input_folder)
    first_tile_name = tile_names[0]
    
    #assess size of the tiles (assuming all tiles are the same size)
    (tile_height, tile_width) = img_sz.get_image_size(input_folder + os.path.sep + first_tile_name)
    if(verbose > 0):
        print "Tile Dimensions\nsize: %d, %d\n" % (tile_height,tile_width)
        
    #get device type from user's choice
    
    cl_platforms = cl.get_platforms()
    devices = []
    for platform in cl_platforms:
        try:
            devices += platform.get_devices(device_type)
        except cl.RuntimeError:
            continue
    
    if(len(devices) < 1):
        raise ValueError("No devices of type %s found on the system. Perhaps, try specifying a different device type?")
    #get device based on specified index
    device = devices[device_index]
    print "Using device \"%s\"" %device.name
    
    #create OpenCL context
    context = cl.Context(devices = [device])
    #retrieve device memory information
    global_mem = device.get_info(cl.device_info.GLOBAL_MEM_SIZE)
    local_mem = device.get_info(cl.device_info.LOCAL_MEM_SIZE)
    #retrieve warp/wavefront size (or # of hardware threads in case of CPU)
    warp_size = dev.determine_warp_size(device,context)
    #determine size of OpenCL buffers:
    #best guess for used VRAM
    avail_mem = dev.estimate_available_gpu_memory(device, verbose = verbose > 0)
    tile_size = 2**int(math.log(math.sqrt(avail_mem / 3))/math.log(2))
    print tile_size
    buf_size = tile_size*tile_size*3
    
    #determine size of memory chunks
    
    

#main entry point
if __name__ == '__main__':
    args = parser.parse_args(sys.argv[1:])
    if(args.combine_tiles):
        tilecombiner.combine_tiles(args.input_folder, args.output_folder, args.output_tile_size)
    elif(args.list_devices):
        dev.list_devices()
    else:
        input_folder = args.input_folder
        verbose = args.verbose
        device_type = dev.dev_type_by_name[args.device_type]
        device_index = args.device_index
        run_analysis(input_folder, device_type, device_index, verbose)
     
    
    
    
    
    
    
    