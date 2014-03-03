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
    def __init__(self, width, height, warp_size, max_threads):
        self.width = width
        self.height = height
        self.warp_size = warp_size
        self.half_warp_size = warp_size / 2
        self.input_stride = width * warp_size
        self.n_columns = width / warp_size
        self.n_rows = height / warp_size
        self.max_threads = max_threads
        self.max_warps = max_threads/warp_size
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
    def __init__(self, context, config):
        cl_source_file = open("kernels/sat.cl", "r")
        cl_source = cl_source_file.read()
        cl_source_file.close()
        self.config = config
        self.context = context
        self.program = cl.Program(context, cl_source).build(options=str(config))
        self.kernels = {}

        
    def compute(self, raster, queue = None):
        blue = raster
        #blue = raster[:,:,0].astype(np.float32)
        #green = raster[:,:,1].astype(np.float32)
        #red = raster[:,:,2].astype(np.float32)
        context = self.context
        config = self.config
        mem_flags = cl.mem_flags
        
        matrix = cl.Buffer(context,mem_flags.READ_WRITE | mem_flags.COPY_HOST_PTR, hostbuf = blue)
        group_column_sums = cl.Buffer(context,mem_flags.READ_WRITE, size=config.n_rows*config.width*4)
        group_row_sums = cl.Buffer(context,mem_flags.READ_WRITE, size=config.n_columns*config.height*4)
        y_group_sums = cl.Buffer(context,mem_flags.READ_WRITE, size=config.n_columns*config.n_rows*4)
        
        n_horizontal_groups = (config.width + config.max_threads - 1) / config.max_threads
        n_vertical_groups = (config.height + config.max_threads - 1) / config.max_threads
        
        if(not queue):
            queue = cl.CommandQueue(context)
        block_aggr_computed = self.program.compute_block_aggregates(queue,
                                              (config.width,config.n_columns * config.schedule_optimized_n_warps),
                                              (config.warp_size, config.schedule_optimized_n_warps),
                                              matrix, group_column_sums, group_row_sums)
        y_groups_computed = self.program.vertical_aggregate(queue, 
                                            (n_horizontal_groups*config.warp_size, config.max_warps), 
                                            (config.warp_size,config.max_warps),
                                            group_column_sums,y_group_sums,
                                             wait_for=[block_aggr_computed])
        x_groups_computed = self.program.horizontal_aggregate(queue, 
                                            (config.warp_size,n_vertical_groups*config.max_warps),
                                            (config.warp_size,config.max_warps),
                                            y_group_sums,group_row_sums,
                                            wait_for=[y_groups_computed])
        final_computed = self.program.redistribute_SAT_inplace(queue, 
                                            (config.width,config.n_columns*config.schedule_optimized_n_warps),
                                            (config.warp_size,config.schedule_optimized_n_warps),
                                            matrix, group_column_sums, group_row_sums,
                                            wait_for=[x_groups_computed])
        sum_blue = np.zeros_like(blue,dtype=np.float32)
        queue.flush()
        cl.enqueue_copy(queue, sum_blue, matrix,wait_for=[final_computed],is_blocking=True)
        group_column_sums.release()
        group_row_sums.release()
        y_group_sums.release()
        matrix.release()
        return sum_blue
        
        
        
        
        
        
        
        
