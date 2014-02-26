'''
Created on Feb 24, 2014

@author: algomorph
'''
import pyopencl as cl
import numpy as np

def __str_helper(const_name, value):
        return " -D " + const_name + "=" + str(value)

def gen_config(width, height, warp_size):
    input_stride = width * warp_size
    n_columns = width / warp_size
    n_rows = height / warp_size
    half_warp_size = warp_size / 2
    return __str_helper("WIDTH", width) + \
            __str_helper("HEIGHT", height) + \
            __str_helper("WARP_SIZE", warp_size) + \
            __str_helper("HALF_WARP_SIZE", half_warp_size) + \
            __str_helper("INPUT_STRIDE", input_stride) + \
            __str_helper("N_COLUMNS", n_columns) + \
            __str_helper("N_ROWS", n_rows)
    

class SummedAreaTableConfig:
    def __init__(self, width, height, warp_size):
        self.width = width
        self.height = height
        self.warp_size = warp_size
        self.half_warp_size = warp_size / 2
        self.input_stride = width * warp_size
        self.n_columns = width / warp_size
        self.n_rows = height / warp_size
        #todo: figure out how to auto-tune this
        self.schedule_optimized_n_warps = 5
    def __str_helper(self, const_name, value):
        return " -D " + const_name + "=" + str(value)
    def __str__(self):
        return self.__str_helper("WIDTH", self.width) + \
            self.__str_helper("HEIGHT", self.height) + \
            self.__str_helper("WARP_SIZE", self.warp_size) + \
            self.__str_helper("HALF_WARP_SIZE", self.half_warp_size) + \
            self.__str_helper("INPUT_STRIDE", self.input_stride) + \
            self.__str_helper("N_COLUMNS", self.n_columns) + \
            self.__str_helper("N_ROWS", self.n_rows)
            
        
    
def cpu_sat(mat):
    mout = np.zeros(mat.shape, dtype=np.int64)
    for i_row in xrange(mat.shape[0]):
        for i_col in xrange(mat.shape[1]):
            mout[i_row,i_col] = mat[i_row,0:i_col].sum() + mat[0:i_row,i_col].sum() + mat[i_row,i_col]
    return mout


class SummedAreaTableFilter:
    
    kernel_names = ["computeBlockAggregates",
                    "horizontalAggregate",
                    "verticalAggregate",
                    "redistributeSAT_not_inplace",
                    "redistributeSAT_inplace"]
    def __init__(self, context, config):
        cl_source_file = open("kernels/sat.cl", "r")
        cl_source = cl_source_file.read()
        cl_source_file.close()
        self.config = config
        self.context = context
        self.program = cl.Program(context, cl_source).build(options=str(config))
        self.kernels = {}
        for kernel_name in SummedAreaTableFilter.kernel_names:
            kernel = cl.Kernel(self.program, kernel_name)
            self.kernels[kernel_name] = kernel

        
    def compute(self, raster, queue = None):
        blue = raster[:,:,0].astype(np.float32)
        green = raster[:,:,1].astype(np.float32)
        red = raster[:,:,2].astype(np.float32)
        context = self.context
        config = self.config
        mem_flags = cl.mem_flags
        
        matrix = cl.Buffer(context,mem_flags.READ_WRITE | mem_flags.COPY_HOST_PTR, hostbuf = blue)
        yHat = cl.Buffer(context,mem_flags.READ_WRITE, size=config.n_rows*config.width*4)
        vBar = cl.Buffer(context,mem_flags.READ_WRITE, size=config.n_columns*config.height*4)
        ySum = cl.Buffer(context,mem_flags.READ_WRITE, size=config.n_columns*config.n_rows*4)
        
        if(not queue):
            queue = cl.CommandQueue(context)
        self.program.computeBlockAggregates(queue,
                                            (config.width,config.n_columns * config.schedule_optimized_n_warps),
                                            (config.warp_size, config.schedule_optimized_n_warps),
                                            matrix, yHat, vBar)
        
        
        
        
        
