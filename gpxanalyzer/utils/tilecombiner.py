#!/usr/bin/env python
'''
Created on Mar 12, 2014

@author: Gregory Kramida
@license: GNU v3
@copyright: (c) Gregory Kramida 2014
'''
import tiledownloader

from PIL import Image
import argparse
import gc
import os
import re
import sys
import time


import data as dm
import image_size as imz
from console import OutputWrapper


#import console
overflow_modes = ["crop", "pad"]

parser = argparse.ArgumentParser(description="A tool that combines small image tiles into bigger tiles.")
parser.add_argument("--input_folder", "-i", default="test",
                    help="path to folder with the input tiles")
parser.add_argument("--image_id", "-id", type=int, default=None,
                    help="id of the image")
parser.add_argument("--output_folder", "-o", default="test_output",
                    help="path to folder for the output tiles")
parser.add_argument("--size", "-s", type=int, default=16384,
                    help="pixel width/height of the resulting tiles before resizing (if any)")
parser.add_argument("--resize", "-r", type=int, default=-1,
                    help="width/height to resize the tiles to.")
parser.add_argument("--skip_verify", "-sv", action="store_true", default=False,
                    help="don't verify the previously-combined tiles by opening them")
parser.add_argument("--data_source", "-ds", default=None,
                    metavar="DATA_SOURCE",
                    choices=tiledownloader.downloaders_by_data_source.keys(),
                    help="original data source of the tiles. Can be one of: %s" 
                    % str(tiledownloader.downloaders_by_data_source.keys()))
parser.add_argument("--overflow_mode", "-of", default=overflow_modes[0],
                    metavar="MODE",
                    choices=overflow_modes,
                    help="What to do when the output tiles at the edge are only partially spanned by the input tiles. Can be one of: %s" 
                    % str(overflow_modes))

# traverse image names and extract the x & y coordinates, thus finding out cell dimensions
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

def print_progress(i_item, n_items, elapsed, x, y):
        n_done = i_item + 1
        frac_done = float(n_done) / n_items
        total_time = elapsed / frac_done
        eta = total_time - elapsed
        hour_eta = int(eta) / 3600
        min_eta = int(eta - hour_eta * 3600) / 60
        sec_eta = int(eta - hour_eta * 3600 - min_eta * 60)
        print ('Last tile: ({7:04d},{8:04d}). {0:.3%} done ({5:0} of {6:0} tiles), elapsed: {4:0} eta: {1:0} h {2:0} m {3:0} s'
               .format(frac_done, hour_eta, min_eta, sec_eta, int(elapsed), i_item, n_items, x, y)
                ),
        sys.stdout.flush()
        print "\r",
        
def new_tile_mode_from_n_channels(num_channels):
    if(num_channels == 1):
        return 'L'
    elif(num_channels == 2):
        return 'LA'
    elif(num_channels == 3):
        return 'RGB'
    elif(num_channels == 4):
        return 'RGBA'
    else:
        raise ValueError("Unsupported number of channels for input tiles: %d" % num_channels)
    
def try_to_retrieve_cell(image_id, x,y,downloader,settings, input_folder, full_img_path):
    if(downloader is not None):
        print "Unable to open image %s. Attempting to load it from original source." % full_img_path
        if(settings is None):
            settings = downloader.retrieve_image_settings(image_id, verbose=True)
        # fetch from gigiapan
        downloader.download_tile(settings, image_id, x, y, input_folder, verbose=True)
        # re-read
        img = Image.open(full_img_path)
        return img, settings
    else:
        raise IOError("Unable to open image %s. Aborting" % full_img_path)

def combine_tiles(input_folder, output_folder, tile_size, tile_to_size, image_id, downloader, verify, 
                  overflow_mode, progress_callback = None):
    # !!>>> original small tiles are referred to as "cells"
    # !!>>> output tiles are referred to as "tiles"
    # load one file to assess the cell size
    #TODO: redistribute the code into smaller subroutines
    
    img_names = dm.get_raster_names(input_folder)
    first_cell_path = input_folder + os.path.sep + img_names[0]
    ext_re = re.compile("(?<=\.)\w+")
    cell_extension = ext_re.findall(img_names[0])[0]
    cell_width, cell_height, n_channels = imz.get_image_info(first_cell_path)    
    #TODO: support non-square rectangular tiles & cells
    if(cell_width != cell_height):
        raise ValueError("Only square input tiles of equal size supported! Found tile at %d x %d px." 
                         % (cell_width, cell_height))
    cell_size = cell_width
    
    print "Cell shape: %s\nNumber of channels: %d" % (str((cell_size, cell_size)), n_channels)
    
    if(tile_size % cell_size != 0):
        raise ValueError("Output tile size should be a multiple of %d" % cell_size)

    side_cell_count = tile_size / cell_size

    n_cells_x, n_cells_y = get_cell_counts(img_names)
            
    image_width = n_cells_x * cell_size
    image_height = n_cells_y * cell_size
    
    print "Cell dimensions (x,y): " + str((n_cells_x, n_cells_y))
    
    # figure out whether we need padded right and bottom tiles
    if(image_width % tile_size == 0):
        n_tiles_x = image_width / tile_size
    else:
        n_tiles_x = image_width / tile_size + 1
    if(image_height % tile_size == 0):
        n_tiles_y = image_height / tile_size
    else:
        n_tiles_y = image_height / tile_size + 1
    
    print "Tile dimensions (x,y): " + str((n_tiles_x, n_tiles_y))
    
    # create the output folder if it's not there yet
    if(not os.path.exists(output_folder)):
        os.makedirs(output_folder)

    settings = None
    start = time.time()
    i_cell = 0
    n_cells = n_cells_x * n_cells_y
    
    #
    new_tile_mode = new_tile_mode_from_n_channels(n_channels)
    
    resize = lambda img: img
    exp_size = lambda size: size
    if(tile_to_size > 0):
        resize = lambda img: img.resize((int(float(img.size[0]) / tile_size * tile_to_size),
                                            int(float(img.size[1]) / tile_size * tile_to_size)))
        exp_size = lambda size: (int(float(size[0]) / tile_size * tile_to_size),
                                 int(float(size[1]) / tile_size * tile_to_size))
        
    size_func_hash = {overflow_modes[0]: lambda arg: ((arg[1] - arg[0]) * cell_size,
                                     (arg[3] - arg[2]) * cell_size),  # crop
                      overflow_modes[1]: lambda arg: (tile_size, tile_size)  # pad
                      }
    size_func = size_func_hash[overflow_mode]
        
    # loop through the tiles
    start_cell_x = 0
    end_cell_x = min(side_cell_count, n_cells_x)
    
    
    if(progress_callback is None):
        report = print_progress 
    else:
        report = progress_callback
    
    print overflow_mode
    print report
    
    for tile_x in range(0, n_tiles_x):
        start_cell_y = 0
        end_cell_y = min(side_cell_count, n_cells_y)
        for tile_y in range(0, n_tiles_y):
            output_file_name = "{0:04d}-{1:04d}.png".format(tile_x, tile_y)
            output_tile_path = output_folder + os.path.sep + output_file_name
            tile_shape = size_func((start_cell_x,end_cell_x,start_cell_y,end_cell_y))
            exp_shape = exp_size(tile_shape)
            if os.path.isfile(output_tile_path) and (not verify or dm.check_image(output_tile_path,exp_shape,True)):
                print "Skipping output tile %s, previously done and verified." % output_file_name,
                sys.stdout.flush(),
                print "\r",
                n_cells -= (end_cell_y - start_cell_y) * (end_cell_x - start_cell_x)
            else:
                tile = Image.new(new_tile_mode, tile_shape)
                # loop through the cells
                local_x = 0
                for cell_x in range(start_cell_x, end_cell_x):
                    local_y = 0
                    for cell_y in range(start_cell_y, end_cell_y):
                        # pull up input cell
                        input_file_name = "{0:04d}-{1:04d}.{2:s}".format(cell_x, cell_y, cell_extension)
                        full_img_path = input_folder + os.path.sep + input_file_name
                        # print full_img_path
                        try:
                            img = Image.open(full_img_path)
                        except IOError:
                            img = None
                        # if there's no image, try to reload it
                        if(img is None):
                            img,settings = try_to_retrieve_cell(image_id, cell_x,cell_y,downloader,settings,
                                                                input_folder, full_img_path)
                            
                        # fill in the corresponding pixels in the output tile
                        box = (local_x, local_y, local_x + img.size[0], local_y + img.size[1])
                        tile.paste(img, box)
                        report(i_cell, n_cells, time.time() - start, cell_x, cell_y) 
                        i_cell += 1
                        local_y += cell_size
                        
                    local_x += cell_size
                    
                # end cell loop
                # write output tile to disk
                
                tile = resize(tile)
                tile.save(output_tile_path, "PNG")
                del tile
                gc.collect()
            start_cell_y = end_cell_y
            end_cell_y = min(end_cell_y + side_cell_count, n_cells_y)
        start_cell_x = end_cell_x
        end_cell_x = min(end_cell_x + side_cell_count, n_cells_x)
    print "\nDone"


if __name__ == '__main__':
    args = parser.parse_args(sys.argv[1:])
    verify = not args.skip_verify
    if(args.image_id is None):
        photo_id_re = re.compile("\d+(?=_\w+$)|(?<=\/)\d+$")
        args.image_id = int(photo_id_re.findall(args.input_folder)[0])
    if(args.data_source is not None):
        downloader = tiledownloader.downloaders_by_data_source[args.data_source]
    else:
        downloader = None 
    combine_tiles(args.input_folder, args.output_folder,
                  args.size, args.resize, args.image_id, downloader, verify, args.overflow_mode)
        
    
    
    
    
    
        


