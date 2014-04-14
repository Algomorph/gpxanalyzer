'''
Created on Mar 6, 2014

@author: algomorph
'''
import os
import unittest

import gpxanalyzer.filters.cl_manager as clm
#import gpxanalyzer.filters.sat as sat
import gpxanalyzer.filters.color_structure as cs
import numpy as np
import pyopencl as cl
import gpxanalyzer.utils.system as system
import libMPEG7 as mp7


class Test(unittest.TestCase):
    gpu = None
    mgr = None
    tile = None
    extr = None
    
    def setUp(self):
        unittest.TestCase.setUp(self)
        os.environ["PYOPENCL_COMPILER_OUTPUT"] = '1'
        Test.gpu = system.get_devices_of_type(cl.device_type.GPU)[0]
        tile_width = 512
        tile_height = 512
        cell_width = 256
        cell_height = 256
        Test.mgr = clm.FilterCLManager.generate(Test.gpu, (tile_height, tile_width), 
                                                cell_shape=(cell_height, cell_width), verbose=True)
        n_channels = 3
        Test.tile = np.random.random_integers(0, 255, (tile_height, tile_width, n_channels)).astype(np.uint8)
        
        
# TODO: adapt SAT to use image type
#     def test_sat_filter_simple(self):
#         cpu_sat = sat.SummedAreaTableFilterCPU(Test.mgr)
#         gpu_sat = sat.SummedAreaTableFilter(Test.mgr)        
#         true_sums = cpu_sat(Test.tile)
#         sums = gpu_sat(Test.tile)
#         # TODO: create a generic function for fetching the first device of a specific type
#         # print sums[0:16,0:16,0]
#         self.assertTrue(np.array_equal(true_sums, sums), "sat tables don't match")
        
    def test_hmmd_conversion(self):
        mgr = Test.mgr
        if(Test.extr is None):
            Test.extr = cs.ColorStructureDescriptorExtractor(mgr)
        cell = Test.tile[0:mgr.cell_shape[0], 0:mgr.cell_shape[1]]
        res_c = mp7.convert_RGB2HMMD(cell)
        res_py = cs.convert_RGB2HMMD(cell)
        ix = res_py[:,:,0] != res_c[:,:,0]
        self.assertTrue(np.array_equal(res_py[:,:,0], res_c[:,:,0]), "H channel in hmmd converstions doesn't match")
        self.assertTrue(np.array_equal(res_py[:,:,0], res_c[:,:,0]), "H channel in hmmd converstions doesn't match")
        self.assertTrue(np.array_equal(res_py[:,:,1], res_c[:,:,1]), "S channel in hmmd converstions doesn't match")
        
        cell4 = np.append(cell,np.zeros((mgr.cell_shape[0],mgr.cell_shape[1],1),dtype=np.uint8),axis=2)
        ex = Test.extr
        res_cl = ex.convert_cell_to_HMMD(cell4)[:,:,0:3]
            
        self.assertTrue(np.array_equal(res_cl[:,:,0], res_c[:,:,0]), "H channel in hmmd converstions doesn't match")
        self.assertTrue(np.array_equal(res_cl[:,:,1], res_c[:,:,1]), "S channel in hmmd converstions doesn't match")
        self.assertTrue(np.array_equal(res_cl[:,:,2], res_c[:,:,2]), "D channel in hmmd converstions doesn't match")
        
        
        
    
    def tearDown(self):
        unittest.TestCase.tearDown(self)
        if(Test.extr is not None):
            Test.extr.release()
        

if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
