# coding: utf-8

get_ipython().magic(u'cd ~/Factory/gpxanalyzer/')
import libMPEG7 as mp7; import gpxanalyzer.filters.color_structure as cs; import gpxanalyzer.filters.cl_manager as clm; import numpy as np; import pyopencl as cl; gpu = cl.get_platforms()[0].get_devices()[0]; mgr = clm.FilterCLManager.generate(gpu,(4096,4096),cell_shape=(256,256),verbose=True)
cell = np.random.random_integers(0,255,(mgr.cell_height,mgr.cell_width,3)).astype(np.uint8)
hmmd = mp7.convert_RGB2HMMD(cell)
quant = mp7.quantize_HMMD(hmmd)
res_py = cs.quantize_HMMD(hmmd)
res_py = cs.extract_row_bitstrings(res_py)
res_py = cs.extract_row_bitstrings(quant)
extr = cs.CSDescriptorExtractor(mgr)
qb = extr.quant_buffer
extr.allocate_buffers()
qb = extr.quant_buffer
output = cl.Image(mgr.context,cl.mem_flags.READ_WRITE,
                          cl.ImageFormat(cl.channel_order.RGBA,cl.channel_type.UNSIGNED_INT32),
                          shape = (mgr.cell_width, mgr.cell_height*2))
res_brute = np.zeros((mgr.cell_height*2,mgr.cell_width,4),dtype=np.uint32)
up_evt = cl.enqueue_copy(mgr.queue,qb,quant,origin = (0,0), region = mgr.cell_shape)
ex1_evt = extr.program.csDescriptorRowBitstrings(mgr.queue,(mgr.cell_height,),(32,),qb, output, wait_for=[up_evt])
rowbits = np.zeros_like(res_brute)
res_cl = rowbits
dl_evt_rowbits = cl.enqueue_copy(mgr.queue,rowbits, output, origin = (0,0), region = output.shape)
np.array_equal(res_cl,res_py)
np.where(res_cl != res_py)
ixs = np.where(res_cl != res_py)
row = quant[0,1:9].copy()
row.sort()
row = quant[0,1:9].copy()
ex1_evt = extr.program.csDescriptorRowBitstrings(mgr.queue,(mgr.cell_height,),(32,),qb, output, wait_for=[up_evt])
ex1_evt = extr.program.csDescriptorRowBitstrings(mgr.queue,(mgr.cell_height,),(32,),qb, output, wait_for=[up_evt])
dl_evt_rowbits = cl.enqueue_copy(mgr.queue,rowbits, output, origin = (0,0), region = output.shape)
dl_evt_rowbits = cl.enqueue_copy(mgr.queue,res_cl, output, origin = (0,0), region = output.shape)
cs.bitstring_vals(res_cl[2:4,0])
np.array_equal(res_cl,res_py)
ex2_evt = extr.program.csDescriptorWindowBitstringsBrute(mgr.queue,(mgr.cell_width,),(32,), output, output, wait_for=[ex1_evt])
dl_evt = cl.enqueue_copy(mgr.queue, res_brute, output, origin = (0,0), region = output.shape, wait_for = [ex2_evt])
np.array_equal(res_cl,res_py)
res_py = cs.extract_window_bitstrings(res_cl)
np.array_equal(res_py,res_brute)
ixs = np.where(res_brute != res_py)
res_brute[ixs[0][0],ixs[1][0],ixs[2][0]]
res_py[ixs[0][0],ixs[1][0],ixs[2][0]]
res_py = cs.extract_window_bitstrings(res_cl)
res_brute
res_brute[ixs[0][0],ixs[1][0],ixs[2][0]]
res_cl[ixs[0][0],ixs[1][0],ixs[2][0]]
res_brute[ixs[0][0],ixs[1][0],ixs[2][0]]
res_py[ixs[0][0],ixs[1][0],ixs[2][0]]
[249,250,251,252,253,254,255]
len([249,250,251,252,253,254,255])
res_cl[ixs[0][0],ixs[1][0],ixs[2][0]]
np.array_equal(res_py[0:249],res_brute[0:249])
np.array_equal(res_py[0:248],res_brute[0:248])
np.array_equal(res_py[:,0:249],res_brute[:,0:249])
ex1_evt = extr.program.csDescriptorRowBitstrings(mgr.queue,(mgr.cell_height,),(32,),qb, output, wait_for=[up_evt])
extr.recompile()
ex2_evt = extr.program.csDescriptorWindowBitstringsCache(mgr.queue,(mgr.cell_width,),(32,), output, output, wait_for=[ex1_evt])
res_cache = np.zeros_like(res_brute)
dl_evt = cl.enqueue_copy(mgr.queue, res_cache, output, origin = (0,0), region = output.shape, wait_for = [ex2_evt])
(res_cache[:,0:249] != res_brute[:,0:249]).sum()
res_cache.size
ixs = np.where(res_cache[:,0:249] != res_brute[:,0:249])
cs.bitstring_vals(res_cache[0:2,1])
cs.bitstring_vals(res_brute[0:2,1])
np.unique(quant[8:16,0:8])
np.unique(quant[0:8,8:16])
cs.bitstring_vals(res_py[0:2,1])
np.unique(quant[8:16,0:8])
np.unique(quant[1:9,0:8])
np.array_equal(np.unique(quant[1:9,0:8]),cs.bitstring_vals(res_brute[0:2,1])
)
np.array_equal(np.unique(quant[0:8,0:8]),cs.bitstring_vals(res_cache[0:2,0]))
np.array_equal(np.unique(quant[1:9,0:8]),cs.bitstring_vals(res_cache[0:2,1]))
kernel_bitstrings_cache = cl.Kernel(extr.program,"csDescriptorWindowBitstringsCache")
kernel_bitstrings_brute = cl.Kernel(extr.program,"csDescriptorWindowBitstringsBrute")
get_ipython().magic(u'timeit ex2_evt = kernel_bitstrings_cache(mgr.queue,(mgr.cell_width,),(32,), output, output, wait_for=[ex1_evt]); cl.wait_for_events([ex2_evt])')
get_ipython().magic(u'timeit ex2_evt = kernel_bitstrings_brute(mgr.queue,(mgr.cell_width,),(32,), output, output, wait_for=[ex1_evt]); cl.wait_for_events([ex2_evt])')
get_ipython().magic(u'timeit ex1_evt = extr.program.csDescriptorRowBitstrings(mgr.queue,(mgr.cell_height,),(32,),qb, output, wait_for=[up_evt]); cl.wait_for_events([ex1_evt])')
