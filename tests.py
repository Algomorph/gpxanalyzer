'''
Created on Mar 6, 2014

@author: algomorph
'''
import unittest
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
        input_tile = np.random.random_integers(0,255,(tile_width,tile_height))
        #input_tile = np.ones((tile_width,tile_height),dtype=np.uint8)
        true_sums = sat.cpu_sat(input_tile,cell_width,cell_height)
        #TODO: create a generic function for fetching the first device of a specific type
        gpu = cl.get_platforms()[1].get_devices()[0]
        context = cl.Context(devices=[gpu])
        ws = dev.determine_warp_size(gpu, context)
        num_sms = gpu.get_info(cl.device_info.MAX_COMPUTE_UNITS)
        determine_n_processors_per_sm = dev.determine_n_processors_per_sm(gpu)
        max_threads = num_sms * determine_n_processors_per_sm
        config = sat.SummedAreaTableConfig(cell_width,cell_height,ws,max_threads)
        sat_filter = sat.SummedAreaTableFilter(context, config)
        sums = sat_filter(input_tile)
        self.assertTrue(np.array_equal(true_sums,sums), "sat tables don't match")
        

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()