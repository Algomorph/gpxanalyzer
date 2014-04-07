'''
Created on Feb 24, 2014

@author: algomorph
'''
from filter import InPlaceFilter
import numpy as np
import pyopencl as cl
import gpxanalyzer.utils.data as dm
from gpxanalyzer.utils.oo import overrides


class SummedAreaTableFilter(InPlaceFilter):
    '''
    InPlaceFilter for computing the summed are tables on using a specific OpenCL context.
    '''
    printed = False
    def __init__(self, cl_manager, context = None):
        super(SummedAreaTableFilter,self).__init__(cl_manager,context)
        #TODO: make sure kernel works correctly on Intel/AMD CPUs and AMD graphics cards
        sat_cl_source = dm.load_string_from_file("kernels/sat.cl")
        self.program = cl.Program(context, sat_cl_source).build(options=str(cl_manager))
        
    def _process_cell(self, cell, queue, bufs):
        config = self.manager
        #upload table to device
        cell_copy = cell.copy()#have to copy to produce a contiguous array
        cl.enqueue_copy(queue, bufs.matrix, cell_copy, is_blocking=True)
        
        block_aggr_computed = self.program.compute_block_aggregates(queue,
                                              (config.cell_width,config.n_rows * config.schedule_optimized_n_warps),
                                              (config.warp_size, config.schedule_optimized_n_warps),
                                              bufs.matrix, bufs.group_column_sums, bufs.group_row_sums)

        y_groups_computed = self.program.vertical_aggregate(queue, 
                                            (config.n_sep_groups_x*config.warp_size, config.max_warps), 
                                            (config.warp_size,config.max_warps),
                                            bufs.group_column_sums,bufs.y_group_sums,
                                             wait_for=[block_aggr_computed])
        
            
        x_groups_computed = self.program.horizontal_aggregate(queue, 
                                            (config.warp_size,config.n_sep_groups_y*config.max_warps),
                                            (config.warp_size,config.max_warps),
                                            bufs.y_group_sums,bufs.group_row_sums,
                                            wait_for=[y_groups_computed])
        
        final_computed = self.program.redistribute_SAT_inplace(queue, 
                                            (config.cell_width,config.n_columns*config.schedule_optimized_n_warps),
                                            (config.warp_size,config.schedule_optimized_n_warps),
                                            bufs.matrix, bufs.group_column_sums, bufs.group_row_sums,
                                            wait_for=[x_groups_computed])
        queue.flush()
        #download table back
        cl.enqueue_copy(queue, cell_copy, bufs.matrix, wait_for=[final_computed],is_blocking=True)
        np.copyto(cell,cell_copy)

    @overrides(InPlaceFilter)  
    def _allocate_buffers(self):
        config = self.manager
        context = self.context
        mem_flags = cl.mem_flags
        #allocate buffers
        #input/output
        matrix = cl.Buffer(context,mem_flags.READ_WRITE, size = config.cell_height * config.cell_width*4)
        #group block intermediate results
        group_column_sums = cl.Buffer(context,mem_flags.READ_WRITE, size=config.n_rows*config.cell_width*4)
        group_row_sums = cl.Buffer(context,mem_flags.READ_WRITE, size=config.n_columns*config.cell_height*4)
        #these will hold aggregate 
        y_group_sums = cl.Buffer(context,mem_flags.READ_WRITE, size=config.n_columns*config.n_rows*4)
        return dm.Bunch({"matrix":matrix,
                         "group_column_sums":group_column_sums,
                         "group_row_sums":group_row_sums,
                         "y_group_sums":y_group_sums})
    
    @overrides(InPlaceFilter)    
    def _release_buffers(self,bufs):
        bufs.group_column_sums.release()
        bufs.group_row_sums.release()
        bufs.y_group_sums.release()
        bufs.matrix.release()
        

class SummedAreaTableFilterCPU(InPlaceFilter):
    '''
    InPlaceFilter for computing the summed are tables on the CPU, not using OpenCL.
    '''
    def __init__(self, cl_manager, context = None):
        super(SummedAreaTableFilterCPU,self).__init__(cl_manager,context)
        
    def _process_cell(self,cell,bufs,queue):
        #TODO: see whether it's necessary to allocate the extra array for output (in-place processing?)
        mout = np.zeros(cell.shape, dtype=cell.dtype)
        mout[0,0] = cell[0,0]
        for i_row in xrange(1,cell.shape[0]):
            mout[i_row,0] = cell[i_row,0] + mout[i_row-1,0]
        for i_col in xrange(1,cell.shape[1]):
            mout[0,i_col] = cell[0,i_col] + mout[0,i_col-1]
        
        for i_row in xrange(1,cell.shape[0]):
            for i_col in xrange(1,cell.shape[1]):
                mout[i_row,i_col] = cell[i_row,i_col] + mout[i_row-1,i_col] + mout[i_row,i_col-1] - mout[i_row-1,i_col-1]
        np.copyto(cell,mout)
            
        
        
        
        
        
        
        
