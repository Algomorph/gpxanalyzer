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
import gpxanalyzer.gpxanalyzer_internals as gi
from PIL import Image


class Test(unittest.TestCase):
    gpu = None
    mgr = None
    tile = None
    extr = None
    
    cell = None
    
    @classmethod
    def setUpClass(cls):
        os.environ["PYOPENCL_COMPILER_OUTPUT"] = '1'
        Test.gpu = system.get_devices_of_type(cl.device_type.GPU)[0]
        tile_width = 4096
        tile_height = 4096
        cell_width = 256
        cell_height = 256
        Test.mgr = clm.FilterCLManager.generate(Test.gpu, (tile_height, tile_width), 
                                                cell_shape=(cell_height, cell_width), verbose=True)
        n_channels = 3
        Test.tile = np.random.random_integers(0, 255, (tile_height, tile_width, n_channels)).astype(np.uint8)
        Test.extr = cs.CSDescriptorExtractor(Test.mgr)
        Test.cell = Test.tile[0:Test.mgr.cell_shape[0], 0:Test.mgr.cell_shape[1]]
        
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
        cell = Test.cell
        res_c = mp7.convert_RGB2HMMD(cell)
        mgr = Test.mgr
        ex = Test.extr
        res_cl = ex.convert_to_HMMD(cell)[:,:,0:3]
            
        self.assertTrue(np.array_equal(res_cl[:,:,0], res_c[:,:,0]), "H channel in hmmd converstions doesn't match")
        self.assertTrue(np.array_equal(res_cl[:,:,1], res_c[:,:,1]), "S channel in hmmd converstions doesn't match")
        self.assertTrue(np.array_equal(res_cl[:,:,2], res_c[:,:,2]), "D channel in hmmd converstions doesn't match")
        
    def test_quantization(self):
        cell = Test.cell
        extr = Test.extr
        hmmd_cell = mp7.convert_RGB2HMMD(cell)
        res_cl = extr.quantize_HMMD(hmmd_cell)
        res_c = mp7.quantize_HMMD(hmmd_cell)
        self.assertTrue(np.array_equal(res_cl,res_c),"HMMD quantization mismatch")
        res_cl = extr.quantize(cell)
        self.assertTrue(np.array_equal(res_cl,res_c),"HMMD quantization mismatch")
        
    def test_bitstrings(self):
        cell = Test.cell
        mgr = Test.mgr
        hmmd = mp7.convert_RGB2HMMD(cell)
        quant = mp7.quantize_HMMD(hmmd)
        extr = Test.extr
        extr._CSDescriptorExtractor__alloc_quant_buffer()
        qb = extr.quant_buffer
        output = cl.Image(mgr.context,cl.mem_flags.READ_WRITE,
                          cl.ImageFormat(cl.channel_order.RGBA,cl.channel_type.UNSIGNED_INT32),
                          shape = (mgr.cell_width, mgr.cell_height*2))
        
        res_brute = np.zeros((mgr.cell_height*2,mgr.cell_width,4),dtype=np.uint32)
        res_cache = np.zeros_like(res_brute)
        res0 = np.zeros_like(res_brute)
        rowbits_cl = np.zeros_like(res_brute)
        
        cl_evt = cl.enqueue_copy(mgr.queue, output, res0, origin = (0,0), region = output.shape)
        up_evt = cl.enqueue_copy(mgr.queue,qb,quant,origin = (0,0), region = qb.shape)
        
        ex1_evt = extr.program.csDescriptorRowBitstrings(mgr.queue,(mgr.cell_height,),(32,),
                                                         qb, output, wait_for=[up_evt])
        dl_rowbits_evt = cl.enqueue_copy(mgr.queue,rowbits_cl, output, origin = (0,0), region = output.shape)
        rowbits_py = cs.extract_row_bitstrings(quant)
        self.assertTrue(np.array_equal(rowbits_py, rowbits_cl))
        rowbits_cl_extr = extr.extract_rowbits(cell)
        self.assertTrue(np.array_equal(rowbits_py, rowbits_cl_extr))
        
        ex2_evt = extr.program.csDescriptorWindowBitstringsBrute(mgr.queue,(mgr.cell_width,),(32,), 
                                                                 output, output, wait_for=[ex1_evt])
        dl_evt = cl.enqueue_copy(mgr.queue, res_brute, output, origin = (0,0), 
                                 region = output.shape, wait_for = [ex2_evt])
        res_py = cs.extract_window_bitstrings(rowbits_py)
        self.assertTrue(np.array_equal(res_brute[:,0:249], res_py[:,0:249]),
                        "Result bitstring extraction kernel doesn't match ground truth")
        
        res_cl = extr.extract_bitstrings(cell)
        res_py = cs.reshape_bitstrings(res_py)
        self.assertTrue(np.array_equal(res_cl[0:249,:], res_py[0:249,:]),
                        "Bitstring extraction doesn't match ground truth")
        
        
        #TODO: fix bug in cache version and re-enable the tests
#         ex1_evt = extr.program.csDescriptorRowBitstrings(mgr.queue,(mgr.cell_height,),(32,),qb, output, wait_for=[up_evt])
#         ex2_evt = extr.program.csDescriptorWindowBitstringsCache(mgr.queue,(mgr.cell_width,),(32,), output, output, wait_for=[ex1_evt])
#         dl_evt = cl.enqueue_copy(mgr.queue, res_cache, output, origin = (0,0), region = output.shape, wait_for = [ex2_evt])
#         
#         self.assertTrue(np.array_equal(res_brute[:,0:249], res_cache[:,0:249]))

    def test_descriptors(self):
        cell = Test.cell
        extr = Test.extr
        bitstrings = extr.extract_bitstrings(cell)
        descr_gi = extr.extract_bistatrings_descriptor(bitstrings,0,0)
        cell_bgr = np.zeros_like(cell)
        cell_bgr[:,:,0] = cell[:,:,2]
        cell_bgr[:,:,1] = cell[:,:,1]
        cell_bgr[:,:,2] = cell[:,:,0]
        descr_mp7 = mp7.get_color_structure_descriptor(cell_bgr,256)
        self.assertTrue(np.array_equal(descr_gi, descr_mp7),
                         "Pure-Python descriptor extraction doesn't match ground truth")
        
    def test_extraction(self):
        path = "/mnt/sdb2/Data/jcb/201_chunk/0000-0000.png"
        im = Image.open(path)
        tile = np.array(im)
        mgr = clm.FilterCLManager.generate(Test.gpu, (4096, 4096), 
                                                cell_shape=(2048, 2048), verbose=True)
        extr = cs.CSDescriptorExtractor(mgr)
        #descr = extr.extract_greyscale(tile)
        
        
        
    @classmethod
    def tearDownClass(cls):
        Test.extr.release()
        

if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
