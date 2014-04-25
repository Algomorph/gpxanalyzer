'''
Created on Apr 25, 2014

@author: Gregory Kramida
@copyright: (c) Gregory Kramida 2014
@license: GNU v3
'''
import argparse
import gpxanalyzer.filters.color_structure as cs
import gpxanalyzer.filters.cl_manager as clm
parser = argparse.ArgumentParser(description="A tool for extracting MPEG-7 Color Structure descriptors for every 256x256 region of a tiled image.")


parser.add_argument("--input_folder", "-i", default=None,
                    help="path to folder with the image tiles")
parser.add_argument("--output_folder", "-o", default=None,
                    help="path to folder where to store the descriptors")

if __name__ == '__main__':
    pass