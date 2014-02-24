#!/usr/bin/env python
import argparse
import cv2
import os
import re
import sys
import numpy as np

parser = argparse.ArgumentParser(description="A tool that combines 256x256 gigapan image tiles into bigger tiles.")
parser.add_argument("--input_folder","-i",default="test",
                    help="path to folder with the input tiles")
parser.add_argument("--output_folder","-o",default="test_output",
                    help="path to folder for the output tiles")
parser.add_argument("--size","-s",type=int,default=16384,
                    help="width/height of the resulting tiles")

def get_raster_names(directory):
    names = os.listdir(directory)
    names.sort()
    raster_names = []
    for name in names:
        if(re.search(r'[^.]*.jpg',name)):
            raster_names.append(name)
    return raster_names;

#traverse image names and extract the x & y coordinates, thus finding out cell dimensions
def get_cell_counts(img_names):
    img_num_regex = re.compile("\d\d\d\d")
    max_cell_x = 0
    max_cell_y = 0
    for name in img_names:
        num_str = img_num_regex.findall(name)
        cell_x = int(num_str[0])
        cell_y = int(num_str[1])
        if cell_x > max_cell_x:
            max_cell_x = cell_x 
        if cell_y > max_cell_y:
            max_cell_y = cell_y
    return max_cell_x + 1, max_cell_y + 1

if __name__ == '__main__':
    #!!>>> original small tiles are referred to as "cells"
    #!!>>> output tiles are referred to as "tiles"
    args = parser.parse_args(sys.argv[1:])
    cell_size = 256
    tile_size = args.size
    img_names = get_raster_names(args.input_folder)
    
    if(args.size % cell_size != 0):
        raise ValueError("Output tile size should be a multiple of %d" % cell_size)

    side_cell_count = tile_size / cell_size

    n_cells_x, n_cells_y = get_cell_counts(img_names)
            
    image_width = n_cells_x * cell_size
    image_height = n_cells_y * cell_size
    
    print "Cell dimensions: " + str((n_cells_x, n_cells_y))
    
    #figure out whether we need padded right and bottom tiles
    if(image_width % tile_size == 0):
        remainder_column = False
        n_tiles_x = image_width / tile_size
    else:
        remainder_column = True
        n_tiles_x = image_width / tile_size + 1
    if(image_height % tile_size == 0):
        remainder_row = False 
        n_tiles_y = image_height / tile_size
    else:
        n_tiles_y = image_height / tile_size + 1
        remainder_row = True
    
    print "Tile dimensions: " + str((n_tiles_x, n_tiles_y))

    #loop through the tiles
    start_cell_x = 0
    end_cell_x = min(side_cell_count,n_cells_x-1)
    for tile_x in range(0, n_tiles_x):
        start_cell_y = 0
        end_cell_y = min(side_cell_count,n_cells_y-1)
        for tile_y in range(0, n_tiles_y):
            #allocate tile
            tile = np.zeros(((end_cell_y - start_cell_y) * cell_size,(end_cell_x-start_cell_x) * cell_size,3),dtype=np.uint8)
            #loop through the cells
            local_x = 0
            print (end_cell_x, end_cell_y)
            for cell_x in range(start_cell_x,end_cell_x):
                local_y = 0
                for cell_y in range(start_cell_y,end_cell_y):
                    #pull up input cell
                    input_file_name = "{0:04d}-{1:04d}.jpg".format(cell_x,cell_y)
                    img = cv2.imread(args.input_folder + os.path.sep + input_file_name)
                    #fill in the corresponding pixels in the output tile
                    tile[local_y:local_y+cell_size, local_x:local_x+cell_size ,:] = img[:]
                    local_y += cell_size
                local_x += cell_size
            output_file_name = "{0:04d}-{1:04d}.png".format(tile_x,tile_y)
            #write output tile to disk
            cv2.imwrite(args.output_folder + os.path.sep + output_file_name,tile)
            start_cell_y = end_cell_y
            end_cell_y = min(side_cell_count + side_cell_count,n_cells_y-1)
        start_cell_x = end_cell_x
        end_cell_x = min(end_cell_x + side_cell_count,n_cells_x-1)
    
    
    
    
    
    
        


