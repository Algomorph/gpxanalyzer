'''
Created on Mar 6, 2014

@author: algomorph
'''
import os
import unittest

from filters.config import FilterConfig
import filters.sat as sat
import numpy as np
import pyopencl as cl
import utils.dev as dev


class Test(unittest.TestCase):
    def test_sat_filter_simple(self):
        tile_width = 64
        tile_height = 64
        cell_width = 32
        cell_height = 32
        n_channels = 3
        input_tile = np.random.random_integers(0,255,(tile_width,tile_height,n_channels))
        os.environ["PYOPENCL_COMPILER_OUTPUT"] = '1'
        
        gpu = dev.get_devices_of_type(cl.device_type.CPU)[0]
        config = FilterConfig.generate(gpu, input_tile.shape, cell_shape=(cell_width,cell_height), verbose=True)
        context = cl.Context(devices=[gpu])
        cpu_sat = sat.SummedAreaTableFilterCPU(config)
        gpu_sat = sat.SummedAreaTableFilter(config,context)
        
        #input_tile = np.ones((tile_width,tile_height),dtype=np.uint8)
        true_sums = cpu_sat(input_tile)
        sums = gpu_sat(input_tile)
        #TODO: create a generic function for fetching the first device of a specific type
        print sums[0:16,0:16,0]
        self.assertTrue(np.array_equal(true_sums,sums), "sat tables don't match")
        

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()