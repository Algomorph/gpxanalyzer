#!/usr/bin/env python

'''
Created on May 7, 2014

@author: Gregory Kramida
'''
import argparse
import gpxanalyzer.utils.data as dm
from PIL import Image
import sys
import os

parser = argparse.ArgumentParser(description="A script for converting all RBG images in a folder into grayscale images with the same names (overwriting the original files)")
parser.add_argument("--folder", "-f", default=None,
                    help="path to the folder with the images")
parser.add_argument("--verbose", "-v", action='store_true',
                    help="generate mean-distance image",default=False)
if __name__ == '__main__':
    args = parser.parse_args(sys.argv[1:])
    names = dm.get_raster_names(args.folder)
    for name in names:
        path = args.folder + os.path.sep + name
        if(args.verbose):
            print "Processing image {0:s}...".format(name)
        img = Image.open(path)
        if(img.mode != 'L'):
            converted = img.convert('L')
            converted.save(path.replace("jpg","png"),"PNG",options="optimize")
        
    