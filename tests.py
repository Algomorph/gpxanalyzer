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
        num_channels = 3
        #input_tile = np.random.random_integers(0,255,(tile_width,tile_height,num_channels))
        input_tile = np.ones((tile_width,tile_height,num_channels),dtype=np.uint8)
        true_sums = sat.cpu_sat(input_tile)
        #TODO: create a generic function for fetching the first device of a specific type
        gpu = cl.get_platforms()[1].get_devices()[0]
        context = cl.Context(devices=[gpu])
        ws = dev.determine_warp_size(gpu, context)
        num_sms = gpu.get_info(cl.device_info.MAX_COMPUTE_UNITS)
        determine_n_processors_per_sm = dev.determine_n_processors_per_sm(gpu)
        max_threads = num_sms * determine_n_processors_per_sm
        config = sat.SummedAreaTableConfig(tile_width/2,tile_height/2,ws,max_threads)
        sat_filter = sat.SummedAreaTableFilter(context, config)
        sums = sat_filter(input_tile)
       
        print "\n==================================\n"
        print sums[0:8,0:8,0]
        print true_sums[0:8,0:8,0]
        print np.array_equal(true_sums[0:32,0:32,0], sums[0:32,0:32,0])
        print np.array_equal(true_sums[0:32,32:,0], sums[0:32,32:,0])
        print np.array_equal(true_sums[32:,0:32,0], sums[32:,0:32,0])
        print np.array_equal(true_sums[32:,32:,0], sums[32:,32:,0])
        self.assertTrue(np.array_equal(true_sums,sums), "sat tables don't match")

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()