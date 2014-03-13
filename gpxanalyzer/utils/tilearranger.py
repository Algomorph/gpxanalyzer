#!/usr/bin/env python
'''
Created on Mar 12, 2014

@author: algomorph
'''
import argparse
import sys
import data as dm
import re
import os
import shutil

parser = argparse.ArgumentParser(description="A tool that arranges the x-y.format files into /z/x/y tile folder structure.")
parser.add_argument("--tile_directory", "-d", default="test",
                    help="path to root directory with zoom level subdirecotries")

def arrange_tiles(tile_dir):
    zoom_dirs = dm.get_subfolders(tile_dir)
    coord_re = re.compile("\d\d\d\d")
    
    ext_re = re.compile("(?<=\.)\w+")
    first_tile_name = dm.get_raster_names(tile_dir + os.path.sep + zoom_dirs[0])[0]
    extension = "." + ext_re.findall(first_tile_name)[0]
    
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

if __name__ == '__main__':
    args = parser.parse_args(sys.argv[1:])
    arrange_tiles(args.tile_directory)