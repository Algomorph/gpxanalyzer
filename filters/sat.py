'''
Created on Feb 24, 2014

@author: algomorph
'''
import pyopencl as cl


class SummedAreaTableConfig:
    def __init__(self, width, height, warp_size):
        self.width = width
        self.height = height
        self.warp_size = warp_size
        self.input_stride = width * warp_size
        self.n_columns = width / warp_size
        self.n_rows = height / warp_size
    def __str_helper(self, const_name, value):
        return " -D " + const_name + "=" + str(value)
    def __str__(self):
        return self.__str_helper("WIDTH", self.width) + \
            self.__str_helper("HEIGHT", self.height) + \
            self.__str_helper("WARP_SIZE", self.warp_size) + \
            self.__str_helper("INPUT_STRIDE", self.input_stride) + \
            self.__str_helper("N_COLUMNS", self.n_columns) + \
            self.__str_helper("N_ROWS", self.n_rows)
    

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
        self.program = cl.Program(context, cl_source).build(options=str(config))
        self.kernels = {}
        for kernel_name in SummedAreaTableFilter.kernel_names:
            kernel = cl.Kernel(self.program, kernel_name)
            self.kernls[kernel_name] = kernel

        
    def compute(self, image):
        pass
