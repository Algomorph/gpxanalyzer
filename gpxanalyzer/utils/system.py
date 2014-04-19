'''
Created on Feb 24, 2014

@author: algomorph
'''
import platform
import psutil
import re
import subprocess

import OpenGL.GL as gl
import OpenGL.GLUT as glut
import OpenGL.extensions as gl_ext
import data as dm
import pyopencl as cl


vendor_ids={
            "NVIDIA":[4318],
            "AMD":[4130,4098]
            }
dev_type_by_name = {"gpu":cl.device_type.GPU,
                    "cpu":cl.device_type.CPU
                    }

def find_max_image_2D_size(device):
    pass

def select_device(device_type, device_index):
    '''
    Select a device of the given type based on the given index
    
    @type device_type pyopencl.device_type
    @param device_type: the type of devices from which to select
    @type device_index: int
    @param device_index: a zero-based index of the device to select from a list of all devices of the desired type
    @return device of the given type at the given index
    '''
    devices = get_devices_of_type(device_type)
    if(len(devices) < 1):
            raise ValueError("""No devices of type %s found on the system.
    Perhaps, try specifying a different device type?""")
    return devices[device_index]
    

def list_devices():
    '''
    List devices on all OpenCL platforms for types CPU and GPU to stdout
    '''
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
        
def determine_n_processors_per_sm(device):
    '''
    Determines the number of processors in each streaming multiprocessor (or analogue) on the device
    @type device: pyopencl.device
    @param device: The OpenCL device to use 
    '''
    if(device.type == cl.device_type.CPU):
        #TODO: dynamically determine this
        return 2;#assume two threads/CORE
    elif(device.type == cl.device_type.GPU and device.vendor_id in vendor_ids["NVIDIA"] or "NVIDIA" in device.vendor):
        return 8;
    elif(device.type == cl.device_type.GPU and device.vendor_id in vendor_ids["AMD"] or "AMD" in device.vendor):
        return 4;
        
def determine_warp_size(device,context = None):
    '''
    Determines the warp size / wavefront / work group suggested multiple for a given OpenCL device.
    This is critical information, since it determines how many operations can run launched by a 
    multiprocessor unit at any given moment.
    
    @type device:pyopencl.Device
    @param device: The device who's warp/wavefront size is to be determined
    @type context:pyopencl.Context
    @param context: The OpenCL context within which the device is to be used
    '''
    #TODO: spruce up the test kernel somehow to yield better results for CPUs
    src = dm.load_string_from_file("kernels/test_kernel.cl")
    del_context = False
    if(context is None):
        context = cl.Context(devices = [device])
        del_context = True
    test_prog = cl.Program(context,src).build()
    test_kernel = test_prog.all_kernels()[0]
    ws = test_kernel.get_work_group_info(cl.kernel_work_group_info.PREFERRED_WORK_GROUP_SIZE_MULTIPLE, device)
    del test_prog
    del test_kernel
    if(del_context):
        del context
    return ws

def get_devices_of_type(device_type):
    """
    Retrieve all available OpenCL devices of the specified type
    @type device_type: pyopencl.device_type
    @param device_type: the type of device to retrieve
    """
    cl_platforms = cl.get_platforms()
    devices = []
    for platform in cl_platforms:
        try:
            devices += platform.get_devices(device_type)
        except cl.RuntimeError:
            continue
    return devices


def estimate_available_cl_device_memory(device, verbose = False):
    '''
    Estimates the currently-available device global memory amount.
    Currently only gives exact result for CPUs and NVIDIA Graphics Cards.
    @type device: pyopencl.Device
    @param device: The device whose available memory amount to query
    @type verbose: bool
    @param verbose: Whether to print information messages or not.
    '''
    mb_estimated = 500
    b_in_mb = 1048576
    bytes_estimated = b_in_mb*mb_estimated
    success = False
    if(device.type == cl.device_type.CPU):
        bytes_used = psutil.avail_phymem()
        mb_used = bytes_used / b_in_mb
        success = True
    elif(device.vendor_id in vendor_ids["NVIDIA"] or "NVIDIA" in device.vendor):
        glut.glutInit()
        #window = glut.glutCreateWindow("gl_mem_info")
        GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX = 0x9049
        gl.glget.addGLGetConstant(GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX, (1,))
        if(gl_ext.hasGLExtension("GL_NVX_gpu_memory_info")):
            bytes_used = gl.glGetIntegerv(GPU_MEMORY_INFO_CURRENT_AVAILABLE_VIDMEM_NVX) * 1024
            mb_used = bytes_used / b_in_mb
            success = True
        else:
            out = None
            if(platform.system() == "Windows"):
                try:
                    p = subprocess.Popen(["C:\\Program Files\\NVIDIA Corporation\\NVSMInvidia-smi.exe", "-q","-d","MEMORY"],stdout=subprocess.PIPE)
                    out = p.communicate()[0]
                except OSError:
                    pass
            else:
                #assume Mac/Linux/Unix
                #TODO: Java python integration?
                try:
                    p = subprocess.Popen(["nvidia-smi", "-q","-d","MEMORY"],stdout=subprocess.PIPE)
                    out = p.communicate()[0]
                except OSError:
                    pass
            if(out is not None):
                mem_re = re.compile("Free\s*:\s*(\d+)\s*M(?:i)?B")
                matches = mem_re.findall(out)
                if(len(matches)>0):
                    #assume the first match will indicate free global memory
                    mb_used = int(matches[0])
                    bytes_used = mb_used * b_in_mb
                    success = True
        #glut.glutDestroyWindow(window)
        
    #TODO: determine for AMD graphics cards
    
    
    if(not success):
        print "Unable to determine availabe device memory. Asserting at: %d MiB" % mb_estimated
        return bytes_estimated
    else:
        print "Successfully determined currently available device memory: %d MiB" % mb_used
        return bytes_used