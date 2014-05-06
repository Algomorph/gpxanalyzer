'''
Created on Mar 7, 2014

@author: algomorph
'''

import gpxanalyzer.utils.tilecombiner as tc
import gpxanalyzer.utils.data as dm
import gpxanalyzer.filters.cl_manager as clm
import gpxanalyzer.filters.color_structure as cs
import gpxanalyzer.utils.system as system
import pyopencl as cl
import libMPEG7 as mp7
import timeit
import unittest
import numpy as np
import os
from PIL import Image

class Test(unittest.TestCase):


    def setUp(self):
        pass


    def tearDown(self):
        pass

    

    def testCSspeed(self):
        gpu = system.get_devices_of_type(cl.device_type.GPU)
        mgr = clm.FilterCLManager.generate(gpu, (4096, 4096), cell_shape=(256,256),verbose=True)
        extr = cs.CSDescriptorExtractor(mgr)
        cells256_folder = "/mnt/sdb2/Data/gigapan/107000"
        img_names = dm.get_raster_names(cells256_folder)
        tiles_x, tiles_y = tc.get_cell_counts(img_names)
        tiles = []
        for name in img_names:
            tiles.append(np.array(Image.open(cells256_folder + os.path.sep + name)))
        
        


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()