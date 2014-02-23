#!/usr/bin/env python
import os
import sys
import argparse
import numpy as np
import cv2
import scripts.data_management as dm
import pyopencl as cl
import math
import psutil

dev_type_by_name = {"gpu":cl.device_type.GPU,
                    "cpu":cl.device_type.CPU
                    }

#command line argument parser
parser = argparse.ArgumentParser(description='''Gigapixel Image Analyzer.''')
parser.add_argument("--input_folder","-i",default="test",
                    help="path to gigapixel image tiles")
parser.add_argument("--device_type","-dt",default=dev_type_by_name.keys()[0],
                    metavar="DEVICE_TYPE",
                    choices=dev_type_by_name.keys(),
                    help="OpenCL device type, can be one of %s" % str(dev_type_by_name.keys()) )
parser.add_argument("--verbose","-v",type=int,default=1,help="verbosity level")
parser.add_argument("--device_index","-d",type=int,default=0,help="index of the device to use")
parser.add_argument("--list_devices","-l",action="store_true",default=False,help="list all available opencl devices and exit")


def list_devices():
    cl_platforms = cl.get_platforms()
    devices = []
    for platform in cl_platforms:
        try:
            devices += platform.get_devices(cl.device_type.GPU)
        except cl.RuntimeError:
            continue
        
    print "GPU devices:"
    ix = 0
    for device in devices:
        print "%d: %s" % (ix,device)
        ix += 1
    devices = []
    for platform in cl_platforms:
        try:
            devices += platform.get_devices(cl.device_type.CPU)
        except cl.RuntimeError:
            continue
    print "CPU devices:"
    ix = 0
    for device in devices:
        print "%d: %s" % (ix,device)
        ix += 1
        
def determine_warp_size(device,context):
    if(device.device_type == cl.device_type.GPU):
        src = ""
        with open("kernels/test_kernel.cl","r") as src_file:
            src = src_file.read()
        test_prog = cl.Program(context,src).build()
        test_kernel = test_prog.all_kernels()[0]
        return test_kernel.get_work_group_info(cl.kernel_work_group_info.PREFERRED_WORK_GROUP_SIZE_MULTIPLE, device)
    elif(device.device_type == cl.device_type.CPU):
         import multiprocessing as mp
         return mp.cpu_count()
    else:
        return 1
    

def run_analysis(args):
    tile_names = get_raster_names(args.input_folder)
    first_tile_name = tile_names[0]
    #assess size of the tiles (assuming all tiles are the same size)
    img = cv2.imread(args.input_folder + os.path.sep + first_tile_name)
    (tile_height, tile_width) = img.shape
    
    #get device type from user's choice
    device_type = dev_type_by_name[args.device_type]
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
    device = devices[args.device_index]
    #create OpenCL context
    context = cl.Context(devices = [device])
    #retrieve device memory information
    global_mem = device.get_info(cl.device_info.GLOBAL_MEM_SIZE)
    local_mem = device.get_info(cl.device_info.LOCAL_MEM_SIZE)
    #retrieve warp/wavefront size (or # of hardware threads in case of CPU)
    warp_size = determine_warp_size(device,context)
    #determine size of OpenCL buffers:
    avail_mem = (global_mem - (1024**2)*500) / 2#best guess for used VRAM: 500mb
    tile_size = 2**int(math.log(math.sqrt(avail_mem / 3))/math.log(2))
    buf_size = tile_size*tile_size*3
    
    #determine size of memory chunks
    
    

#main entry point
if __name__ == '__main__':
    args = parser.parse_args(sys.argv[1:])
    if(args.list_devices):
        list_devices()
    else:
        run_analysis(args)
     
    
    
    
    
    
    
    