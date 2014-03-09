#!/usr/bin/env python
import os
import sys
import argparse
import cv2
import pyopencl as cl
import math
import utils.data as data
import utils.dev as dev
import utils.image_size as img_sz


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
     
    
    
    
    
    
    
    
