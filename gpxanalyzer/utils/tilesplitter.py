'''
Created on Mar 14, 2014

@author: Gregory Kramida
'''
from PIL import Image
import argparse
import os


parser = argparse.ArgumentParser(description="A tool for splitting larger tiles into multiple smaller tiles.")
parser.add_argument("--input_folder", "-i", default="test",
                    help="path to folder with the input tiles")
parser.add_argument("--output_folder", "-o", default="test_output",
                    help="path to folder for the output tiles")

def chunk_up(im,size,start_coord,dir):
    w = im.size[0]
    h = im.size[1]
    w_c = size[0]
    h_c = size[1]
    cell_x = start_coord[0]
    cell_y = start_coord[1]
    for x in xrange(0,w,w_c):
        till_x = x + w_c
        for y in xrange(0,h,h_c):
            till_y = y + h_c
            cell = im.crop((x,y,till_x,till_y))
            cell.save(dir + os.path.sep + "%04d-%04d.png"%(cell_x,cell_y),'PNG')
            cell_y += 1
        cell_x += 1
