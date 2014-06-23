#!/usr/bin/env python

import argparse
import sys
from PIL import Image
import os
import re

parser = argparse.ArgumentParser(description="A script for converting all grayscale 16-bit tiff images in a folder into grayscale 8-bit png images in the same grey range")
parser.add_argument("--folder", "-f", default=None,
                    help="path to the folder with the images")
parser.add_argument("--verbose", "-v", action='store_true',
                    help="verbose output",default=False)

def get_raster_names(directory):
    names = os.listdir(directory)
    names.sort()
    raster_names = []
    for name in names:
        if(re.search(r"[^.]*.(?:tif|TIF)",name)):
            raster_names.append(name)
    return raster_names;

if __name__ == '__main__':
    args = parser.parse_args(sys.argv[1:])
    names = get_raster_names(args.folder)
    (imin,imax) = (sys.maxint,0)
    for name in names:
        if(args.verbose):
            print "Checking range on image \"{0:s}\"".format(name)
        path = args.folder + os.path.sep + name
        img = Image.open(path).convert("I")
        extrema = img.getextrema()
        del img
        if(imin > extrema[0]):
            imin = extrema[0]
        if(imax < extrema[1]):
            imax = extrema[1]
        if(args.verbose):
            print "Current range: {0:0d} - {1:0d}".format(imin,imax)
            
    ix_img =0
    irange = float(imax - imin)
    scale = 256.0 / irange
    offset =  - imin / irange
    for name in names:
        path = args.folder + os.path.sep + name
        if(args.verbose):
            print "Converting image {0:s}".format(name)
        img = Image.open(path)
        img.mode = "I"
        new_path = os.path.splitext(path)[0] + ".png"
        
        img.point(lambda i: i * scale + offset).convert('L').save(new_path, 'PNG')
        del img
        ix_img+=1