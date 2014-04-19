#!/usr/bin/env python
'''
Created on Mar 12, 2014

@author: Gregory Kramida
@license: GNU v3
@copyright: (c) Gregory Kramida 2014
'''

from tilecombiner import combine_tiles, get_cell_counts

from PIL import Image
import argparse
import math
import os
import re
import shutil
import sys
import time

from console import print_progress
from data import get_raster_names, find_extension
import data as dm
import image_size as imz

import tiledownloader as td


def arrange_tile_levels_into_zxy(tile_dir):
    zoom_dirs = dm.get_subfolders(tile_dir)
    coord_re = re.compile("\d\d\d\d")
    
    first_tile_name = dm.get_raster_names(tile_dir + os.path.sep + zoom_dirs[0])[0]
    
    extension = "." + find_extension(first_tile_name)
    #TODO: add progress reporting (count the files in folders initially?)
    for zoom_subfolder in zoom_dirs:
        zoom_dir = tile_dir + os.path.sep + zoom_subfolder
        tile_names = dm.get_raster_names(zoom_dir)
        for tile_name in tile_names:
            old_path = zoom_dir + os.path.sep + tile_name
            coords = [int(str_crd) for str_crd in coord_re.findall(tile_name)]
            x = coords[0]
            y = coords[1]
            x_dir = zoom_dir + os.path.sep + str(x)
            if(not os.path.isdir(x_dir)):
                os.makedirs(x_dir)
            new_path = x_dir + os.path.sep + str(y) + extension
            
            shutil.move(old_path,new_path)
            
def arrange_zxy_into_tile_levels(pyramid_dir):
    zoom_dirs = dm.get_subfolders(pyramid_dir)
    first_zm_dir = pyramid_dir + os.path.sep + zoom_dirs[0]
    first_im_dir = first_zm_dir + os.path.sep + dm.get_subfolders(first_zm_dir)[0]
    #coord_re = re.compile("\d\d\d\d")
    
    first_tile_name = dm.get_raster_names(first_im_dir)[0]
    
    extension = "." + find_extension(first_tile_name)
    #TODO: add progress reporting (count the files in folders initially?)
    for zoom_subfolder in zoom_dirs:
        zoom_dir = pyramid_dir + os.path.sep + zoom_subfolder
        x_subfolders = dm.get_subfolders(zoom_dir)[0]
        for x_subfolder in x_subfolders:
            x_dir = zoom_dir + os.path.sep + x_subfolder
            tile_names = dm.get_raster_names(x_dir)
            for tile_name in tile_names:
                old_path = x_dir + os.path.sep + tile_name
                x = int(x_subfolder)
                y = int(re.findall("\d+",tile_name)[0])
                new_name = "{0:04d}-{1:04d}.{2:s}".format(x,y,extension)
                new_path = zoom_dir + os.path.sep + new_name
                shutil.move(old_path,new_path)
            shutil.rmtree(x_dir)

def pyramidize(image_id, orig_tile_dir, pyramid_base_dir, data_source, arrange_in_zxy_format = False, progress_callback = None):
    tile_names = get_raster_names(orig_tile_dir)
    n_tiles_x, n_tiles_y = get_cell_counts(tile_names)
    first_tile_name = tile_names[0]
    tile_extension = find_extension(first_tile_name)
    if(tile_extension.lower() != "png"):
        conversion_necessary = True
    else:
        conversion_necessary = False
    first_tile_name = orig_tile_dir + os.path.sep + tile_names[0]
    cell_width, cell_height, n_channels = imz.get_image_info(first_tile_name)
    
    #create pyramid folder if there isn't one
    if not os.path.isdir(pyramid_base_dir):
        os.makedirs(pyramid_base_dir)
    
    base_level_size = max(n_tiles_x,n_tiles_y)
    n_levels = int(math.ceil(math.log(base_level_size,2))) + 1
    
    #create level folders
    for i_level in xrange(0,n_levels):
        level_dir = pyramid_base_dir + os.path.sep + str(i_level)
        if not os.path.exists(level_dir):
            os.makedirs(level_dir)
        
    base_level_index = n_levels - 1
    #copy base level
    print "Copying base level."
    start_time = time.time()
    n_tiles = len(tile_names)
    i_tile = 0
    
    if(progress_callback is None):
        report = print_progress 
    else:
        report = progress_callback
    
    if(conversion_necessary):
        for tile_name in tile_names:
            new_tile_path = (pyramid_base_dir + os.path.sep 
                             + str(base_level_index) + os.path.sep 
                             + tile_name.replace(tile_extension,"png"))
            if not os.path.exists(new_tile_path):
                orig_tile_path = orig_tile_dir + os.path.sep + tile_name
                im = Image.open(orig_tile_path)
                im.save(new_tile_path,"PNG")
            report(i_tile, n_tiles, start_time, "tiles")
            i_tile += 1
    else:
        for tile_name in tile_names:
            
            new_tile_path = (pyramid_base_dir + os.path.sep 
                             + str(base_level_index) + os.path.sep 
                             + tile_name)
            if not os.path.exists(new_tile_path):
                orig_tile_path = orig_tile_dir + os.path.sep + tile_name
                shutil.copy(orig_tile_path,new_tile_path)
            report(i_tile, n_tiles, start_time, "tiles")
            i_tile += 1
    
    downloader = td.downloaders_by_data_source[data_source]
    
    #traverse the levels to arrange the tiles
    for i_level in xrange(n_levels-1,0,-1):
        src_level_folder = pyramid_base_dir + os.path.sep + str(i_level)
        dst_level_folder = pyramid_base_dir + os.path.sep + str(i_level-1)
        print ""
        print "Combining & reducing level %d into level %d" % (i_level, i_level-1)
        combine_tiles(src_level_folder, dst_level_folder, cell_width*2, 
                      cell_width, image_id, downloader, verify = False, 
                      overflow_mode = "crop", 
                      progress_callback=progress_callback)
    
    if(arrange_in_zxy_format):
        print "Arrainging in /z/x/y format..."
        arrange_tile_levels_into_zxy(pyramid_base_dir)
        
ops = {"arrange_zxy":[lambda args: arrange_tile_levels_into_zxy(args.input_tile_directory),
                      """Takes the input folder with z-level subfolders by tiles named in \"x-y.ext\" 
format and re-arranges the tiles in-place to form /z/x/y folder structure."""],
       "pyramidize":[lambda args : pyramidize(args.image_id,args.input_tile_directory, args.output_tile_directory, args.data_source, True),
                     """Takes the input folder with just the base level of tiles in named in \"x-y.ext\"
format and builds a complete /z/x/y pyramid in the output folder. Does not modify the input folder."""]}

ops_help_string = "Operation to perform. Can be one of: {0:s}".format(str(ops.keys()))
for key, val in ops.itervalues():
    ops_help_string += "\n{0:s}: {1:s}".format(key,val[1])

#TODO: add verification of tiles

parser = argparse.ArgumentParser(description="A tool that arranges the x-y.format tiles into /z/x/y tile folder structure.")
parser.add_argument("--input_tile_directory", "-i", default="test",
                    help="path to the input directory")
parser.add_argument("--image_id", "-id", type=int, default=None,
                    help="id of the image")
parser.add_argument("--data_source", "-ds", default=None,
                    metavar="DATA_SOURCE",
                    choices=td.downloaders_by_data_source.keys(),
                    help="original data source of the tiles. Can be one of: %s" 
                    % str(td.downloaders_by_data_source.keys()))
parser.add_argument("--operation", "-op", default=ops.keys()[0],
                    metavar="OPERATION",
                    choices=ops.keys(),
                    help=ops_help_string)
parser.add_argument("--output_tile_directory", "-o", default=None,
                    help="path to the input directory")


if __name__ == '__main__':
    args = parser.parse_args(sys.argv[1:])
    if(args.image_id is None):
        photo_id_re = re.compile("\d+(?=_\w+$)|(?<=\/)\d+$")
        args.image_id = int(photo_id_re.findall(args.input_folder)[0])
    if(args.output_tile_directory is None):
        args.output_tile_directory = args.input_tile_directory + "_pyramid"
    ops[args.operation][0](args)