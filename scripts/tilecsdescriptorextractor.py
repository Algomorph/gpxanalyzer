'''
Created on Apr 25, 2014

@author: Gregory Kramida
@copyright: (c) Gregory Kramida 2014
@license: GNU v3
'''
import argparse
import gpxanalyzer.filters.color_structure as cs
import gpxanalyzer.filters.cl_manager as clm
import gpxanalyzer.utils.system as system
import gpxanalyzer.gpxanalyzer_internals as gi
import numpy as np
import pyopencl as cl
import sys
from PIL import Image

parser = argparse.ArgumentParser(description="A tool for extracting MPEG-7 Color Structure descriptors for every 256x256 region of a tiled image.")


parser.add_argument("--input_image", "-i", default=None,
                    help="path to the image whose descriptor to compute")
parser.add_argument("--output_folder", "-o", default=None,
                    help="path to folder where to store the descriptors")

if __name__ == '__main__':
    args = parser.parse_args(sys.argv[1:])
    device = system.get_devices_of_type(cl.device_type.GPU)[0]
    mgr = clm.FilterCLManager.generate(device, (0,0), cell_shape=(2048,2048), verbose = True)
    extr = cs.CSDescriptorExtractor(mgr)
    im = Image.open(args.input_image)
    (width,height) = im.size
    #descriptors = np.zeros((width-gi.REGION_SIZE+1,height-gi.REGION_SIZE+1,256),dtype=np.uint8)
    bitstrings = np.zeros((height-gi.WINDOW_SIZE+1,width-gi.WINDOW_SIZE+1,8),dtype=np.uint32)
    for y in xrange(0,height,mgr.cell_height-gi.WINDOW_SIZE+1):
        for x in xrange(0,width,mgr.cell_width-gi.WINDOW_SIZE+1):
            right = min(x+mgr.cell_width, width)
            bottom = min(y+mgr.cell_height,height)
            cell = np.array(im.crop((x,y,right,bottom)))
            
            bitcell = extr.extract_bitstrings(cell)
            
            bit_bottom = y+mgr.cell_height
            bit_right = x+mgr.cell_width
            if(bit_bottom > bitstrings.shape[0]):
                bit_height = mgr.cell_height - (bit_bottom - bitstrings.shape[0]) 
                bit_bottom = bitstrings.shape[0]
                bitcell = bitcell[0:bit_height]
            
            if(bit_right > bitstrings.shape[1]):
                bit_width = mgr.cell_width - (bit_right - bitstrings.shape[1]) 
                bit_right = bitstrings.shape[1]
                bitcell = bitcell[:,0:bit_width]

            np.copyto(bitstrings[y:bit_bottom,x:bit_right],bitcell)
            
    