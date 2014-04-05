'''
Created on Apr 3, 2014

@author: Gregory Kramida
@copyright: (c) Gregory Kramida 2014
@license: GNU v3
'''
from gpxanalyzer.utils import system
import pyopencl as cl
from gpxanalyzer.utils.data import load_string_from_file
import numpy as np
import time;

def to_hmmd_py(raster):
    out = np.zeros(raster.shape,dtype=np.int16)
    for i_row in xrange(raster.shape[0]):
        for i_col in xrange(raster.shape[1]):
            (R,G,B) = raster[i_row,i_col,0:3]
            max=R
            if(max<G): max=G
            if(max<B): max=B
        
            min=R
            if(min>G): min=G
            if(min>B): min=B
        
            if (max == min): # ( R == G == B )//exactly gray
                hue = -1.5; #hue is undefined
            else:
                #solve Hue
                if(R==max):
                    hue=((G-B)/(float)(max-min));
                elif(G==max):
                    hue=(2.0+(B-R)/(float)(max-min));
                elif(B==max):
                    hue=(4.0+(R-G)/(float)(max-min));
        
                hue*=60
                if(hue<0.0): hue+=360

            H = int(hue + 0.5)                #range [0,360]
            S = int((max + min)/2.0 + 0.5)    #range [0,255]
            D = int(max - min + 0.5)          #range [0,255]
            out[i_row,i_col,0:3] = (H,S,D)
    return out
    
def to_hmmd_cl(raster):
    in_img = None
    output = None
    context = None
    queue = None
    program = None
    try:
        shape_2d = (raster.shape[0],raster.shape[1])
        dev = system.get_devices_of_type(cl.device_type.GPU)[0]
        context = cl.Context([dev]);
        ws = system.determine_warp_size(dev, context)
        cs_cl_source = load_string_from_file("kernels/cs.cl")
        queue = cl.CommandQueue(context)
        program = cl.Program(context, cs_cl_source).build()
        convert_to_HMMD = cl.Kernel(program,"convert_to_HMMD")
        in_img = cl.Image(context,cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, 
                         cl.ImageFormat(cl.channel_order.RGBA,cl.channel_type.UNSIGNED_INT8),
                         shape_2d,hostbuf = raster)
        output = cl.Image(context,cl.mem_flags.WRITE_ONLY, cl.ImageFormat(cl.channel_order.RGBA,cl.channel_type.SIGNED_INT16),shape_2d)
        start = time.time()
        evt = convert_to_HMMD(queue,shape_2d,(32,4),in_img,output)
        runlength = time.time()-start 
        res = np.zeros(raster.shape, dtype=np.uint16)
        queue.flush()
        nanny_evt = cl.enqueue_copy(queue,res,output,wait_for = [evt], origin = (0,0), region = shape_2d)
        nanny_evt.wait()
    except MemoryError as me:
        if(input):
            input.release()
        if(output):
            output.release()
        if(context): del context
        if(queue): del queue
        if(output): del output
        if(input): del input
        if(program): del program
        raise me;
    
    input.release()
    output.release()
    del context
    del queue
    del output
    del input
    del program
    
    return res, runlength



def extract_cs_descriptor(raster, length):
    #convert to HMMD
    
    
    #quantize
    #scan
    pass