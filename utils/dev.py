'''
Created on Feb 24, 2014

@author: algomorph
'''
import psutil
import pyopencl as cl
import OpenGL.GL as gl
import OpenGL.extensions as gl_ext
import platform
import subprocess
import re


vendor_ids={
            "NVIDIA":[4318],
            "AMD":[4130,4098]
            }
dev_type_by_name = {"gpu":cl.device_type.GPU,
                    "cpu":cl.device_type.CPU
                    }

def list_devices():
    cl_platforms = cl.get_platforms()
    devices = []
    for platform in cl_platforms:
        try:
            devices += platform.get_devices(cl.device_type.GPU)
        except cl.RuntimeError:
            continue
        
    print "GPU devices:"
    ix = 0
    for device in devices:
        print "%d: %s" % (ix,device)
        ix += 1
    devices = []
    for platform in cl_platforms:
        try:
            devices += platform.get_devices(cl.device_type.CPU)
        except cl.RuntimeError:
            continue
    print "CPU devices:"
    ix = 0
    for device in devices:
        print "%d: %s" % (ix,device)
        ix += 1
        
def determine_warp_size(device,context):
    if(device.type == cl.device_type.GPU):
        src = ""
        with open("kernels/test_kernel.cl","r") as src_file:
            src = src_file.read()
        test_prog = cl.Program(context,src).build()
        test_kernel = test_prog.all_kernels()[0]
        return test_kernel.get_work_group_info(cl.kernel_work_group_info.PREFERRED_WORK_GROUP_SIZE_MULTIPLE, device)
    elif(device.device_type == cl.device_type.CPU):
        return psutil.NUM_CPUS
    else:
        return 1


def estimate_available_gpu_memory(device, verbose = False):
    if(device.vendor_id in vendor_ids["NVIDIA"] or "NVIDIA" in device.vendor):
        if(gl_ext.hasGLExtension("GL_NVX_gpu_memory_info")):
            GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX = 0x9049
            gl.glget.addGLGetConstant(GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX, (1,))
            return gl.glGetIntegerv(GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX) * 1024
        else:
            out = None
            if(platform.system() == "Windows"):
                try:
                    p = subprocess.Popen(["C:\\Program Files\\NVIDIA Corporation\\NVSMInvidia-smi.exe", "-q","-d","MEMORY"],stdout=subprocess.PIPE)
                    out, err = p.communicate()
                except OSError:
                    pass
            else:
                #assume Mac/Linux/Unix
                #TODO: Java python integration?
                try:
                    p = subprocess.Popen(["nvidia-smi", "-q","-d","MEMORY"],stdout=subprocess.PIPE)
                    out, err = p.communicate()
                except OSError:
                    pass
            if(out):
                mem_re = re.compile("Free\s*:\s*(\d+)\s*MiB")
                matches = mem_re.findall(out)
                if(len(matches)>0):
                    #assume the first match will indicate free global memory
                    mb_used = int(matches[0])
                    bytes_used= mb_used * 1024**2
                    if(verbose):
                        print "Determined currently available device memory: %d b" % bytes_used
                    return bytes_used
    #TODO: determine for AMD and Intel devices
    bytes_estimated = (1024**2)*500
    if(verbose):
        print "Unable to determine availabe device memory. Asserting at: %d b" % bytes_estimated
    return bytes_estimated