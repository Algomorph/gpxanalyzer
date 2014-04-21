# coding: utf-8

get_ipython().magic(u'cd ~/Factory/gpxanalyzer/')
import libMPEG7 as mp7; import gpxanalyzer.filters.color_structure as cs; import gpxanalyzer.filters.cl_manager as clm; import numpy as np; import pyopencl as cl; gpu = cl.get_platforms()[0].get_devices()[0]; mgr = clm.FilterCLManager.generate(gpu,(4096,4096),cell_shape=(2048,2048),verbose=True)
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
dl_evt_rowbits = cl.enqueue_copy(mgr.queue,rowbits, output, origin = (0,0), region = output.shape)
res_cl = rowbits
res_cl
res_py
res0 = np.zeros_like(res_brute)
cl.enqueue_copy(mgr.queue, output, res0, origin = (0,0), region = output.shape)
ex1_evt = extr.program.csDescriptorRowBitstrings(mgr.queue,(mgr.cell_height,),(32,),qb, output, wait_for=[up_evt])
dl_evt_rowbits = cl.enqueue_copy(mgr.queue,rowbits, output, origin = (0,0), region = output.shape)
res_cl
res_py
np.array_equal(res_cl,res-Py)
np.array_equal(res_cl,res_py)
np.where(res_cl != res_py)
ixs = np.where(res_cl != res_py)
ixs[0]
res_cl[ixs[0][0],ixs[1][0],ixs[2][0])
res_cl[ixs[0][0],ixs[1][0],ixs[2][0]]
res_py[ixs[0][0],ixs[1][0],ixs[2][0]]
ixs[0][0]
ixs[1][0]
res_cl[2,0]
res_py[2,0]
cs.to_bitstring(quant[0,1:9])
cs.bitstring_vals(res_cl[2:4,0])
cs.bitstring_vals(res_py[2:4,0])
quant[0,1:9]
quant[1:9,0]
row = quant[1:9,0].copy()
row.sort()
row
cs.bitstring_vals(res_py[2:4,0])
row = quant[0,1:9].copy()
row.sort()
row
cs.bitstring_vals(res_py[2:4,0])
quant[0,1:12]
quant[0,0:12]
cs.bitstring_vals(res_cl[2:4,0])
wrong = cs.bitstring_vals(res_cl[2:4,0])
for val in wrong:
    if val not in row:
        print val
        
len(wrong)
len(cs.bitstring_vals(res_py[2:4,0]))
row = quant[0,1:9].copy()
row
right = cs.bitstring_vals(res_py[2:4,0])
right
for val in right:
    if val not in wrong:
        print val
        
row
quant[0:9,0:9]
extr.recompile()
ex1_evt = extr.program.csDescriptorRowBitstrings(mgr.queue,(mgr.cell_height,),(32,),qb, output, wait_for=[up_evt])
cs.bitstring_vals(res_cl[2:4,0])
row
58 in cs.bitstring_vals(res_cl[2:4,0])
extr.recompile()
ex1_evt = extr.program.csDescriptorRowBitstrings(mgr.queue,(mgr.cell_height,),(32,),qb, output, wait_for=[up_evt])
dl_evt_rowbits = cl.enqueue_copy(mgr.queue,rowbits, output, origin = (0,0), region = output.shape)
dl_evt_rowbits = cl.enqueue_copy(mgr.queue,res_cl, output, origin = (0,0), region = output.shape)
cs.bitstring_vals(res_cl[2:4,0])
np.array_equal(res_cl,res_py)
ex2_evt = extr.program.csDescriptorWindowBitstringsBrute(mgr.queue,(mgr.cell_width,),(32,), output, output, wait_for=[ex1_evt])
dl_evt = cl.enqueue_copy(mgr.queue, res_brute, output, origin = (0,0), region = output.shape, wait_for = [ex2_evt])
res_brute
res_cl
np.array_equal(res_cl,res_py)
res_py = cs.extract_window_bitstrings(res_py)
res_cl.transpose(1,0,2).reshape(8,-1)
res_cl.transpose(1,0,2).reshape(8,-1).shape
res_cl.transpose(1,2,0).reshape(8,-1).shape
res_cl.transpose(2,0,1).reshape(8,-1).shape
res_cl.transpose(1,0,2).reshape(-1,8)
res_cl.transpose(1,0,2).reshape(-1,8).shape
res_cl.shape
res_cl[0:2,0:8]
res_cl[0:2,0:8].transpose(1,0,2)
res_cl[0:2,0:8].transpose(1,0,2).shape
res_cl[0:2,0:8].transpose(1,0,2).reshape(8,-1)
res_cl[0:2,0:8].transpose(1,0,2).reshape(8,-1).shape
res_cl[0:2,0]
for k in res_cl[0:2,0:8].transpose(1,0,2).reshape(8,-1):
    print k
    
for k in res_cl[0:2,0:8].transpose(1,0,2).reshape(8,-1):
    print k.shape
    
res_py = cs.extract_window_bitstrings(res_py)
reload(cs)
res_py = cs.extract_window_bitstrings(res_py)
res_py
res_py = cs.extract_window_bitstrings(res_cl)
res_py
reload(cs)
res_py = cs.extract_window_bitstrings(res_cl)
res_py
res_brute
np.array_equal(res_py,res_brute)
ixs = np.where(res_brute != res_py)
res_brute[ixs[0][0],ixs[1][0],ixs[2][0]]
res_py[ixs[0][0],ixs[1][0],ixs[2][0]]
ixs[0][0]
ixs[1][0]
ixs[2][0]
reload(cs)
res_py = cs.extract_window_bitstrings(res_cl)
reload(cs)
res_brute
res_brute[ixs[0][0],ixs[1][0],ixs[2][0]]
res_cl
ixs[1,0]
ixs[1][0]
row[0:4]
row[4:8]
res_cl[ixs[0][0],ixs[1][0],ixs[2][0]]
res_brute[ixs[0][0],ixs[1][0],ixs[2][0]]
res_py[ixs[0][0],ixs[1][0],ixs[2][0]]
256-7
256-7
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
res_cache[:,0:249] != res_brute[:,0:249]
(res_cache[:,0:249] != res_brute[:,0:249]).sum()
res_cache.size
ixs = np.where(res_cache[:,0:249] != res_brute[:,0:249])
ixs
ixs[0][0]
ixs[1][0]
ixs[2][0]
res_cache[0,1,0]
res_brute[0,1,0]
res_cache[0:0,1,0]
res_cache[0:2,1,0]
res_cache[0:2,1]
res_brute[0:2,1]
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
get_ipython().magic(u'timeit kernel_bitstrings_cache(mgr.queue,(mgr.cell_width,),(32,), output, output, wait_for=[ex1_evt]); cl.wait_for_events([ex2_evt])')
kernel_bitstings_brute = cl.Kernel(extr.program,"csDescriptorWindowBitstringsBrute")
get_ipython().magic(u'timeit ex2_evt = kernel_bitstrings_cache(mgr.queue,(mgr.cell_width,),(32,), output, output, wait_for=[ex1_evt]); cl.wait_for_events([ex2_evt])')
get_ipython().magic(u'timeit ex2_evt = kernel_bitstrings_brute(mgr.queue,(mgr.cell_width,),(32,), output, output, wait_for=[ex1_evt]); cl.wait_for_events([ex2_evt])')
get_ipython().magic(u'timeit ex2_evt = kernel_bitstings(mgr.queue,(mgr.cell_width,),(32,), output, output, wait_for=[ex1_evt]); cl.wait_for_events([ex2_evt])')
get_ipython().magic(u'timeit ex2_evt = kernel_bitstings_brute(mgr.queue,(mgr.cell_width,),(32,), output, output, wait_for=[ex1_evt]); cl.wait_for_events([ex2_evt])')
get_ipython().magic(u'timeit ex2_evt = kernel_bitstings_brute(mgr.queue,(mgr.cell_width,),(32,), output, output, wait_for=[ex1_evt]); cl.wait_for_events([ex2_evt])')
get_ipython().magic(u'timeit ex2_evt = kernel_bitstings_brute(mgr.queue,(mgr.cell_width,),(64,), output, output, wait_for=[ex1_evt]); cl.wait_for_events([ex2_evt])')
kernel_bitstrings_brute = kernel_bitstings_brute
get_ipython().magic(u'timeit ex2_evt = kernel_bitstrings_cache(mgr.queue,(mgr.cell_width,),(32,), output, output, wait_for=[ex1_evt]); cl.wait_for_events([ex2_evt])')
get_ipython().magic(u'timeit ex2_evt = kernel_bitstrings_brute(mgr.queue,(mgr.cell_width,),(32,), output, output, wait_for=[ex1_evt]); cl.wait_for_events([ex2_evt])')
get_ipython().magic(u'timeit ex1_evt = extr.program.csDescriptorRowBitstrings(mgr.queue,(mgr.cell_height,),(32,),qb, output, wait_for=[up_evt]); cl.wait_for_events([ex1_evt])')
