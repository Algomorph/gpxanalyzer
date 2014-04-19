'''
Created on Feb 24, 2014

@author: algomorph
'''
from filter import InPlaceFilter
import numpy as np
import pyopencl as cl
import gpxa.utils.data as dm
from gpxa.utils.oo import overrides


class SummedAreaTableFilter(InPlaceFilter):
    '''
    InPlaceFilter for computing the summed are tables on using a specific OpenCL context.
    '''
    printed = False
    def __init__(self, cl_manager):
        super(SummedAreaTableFilter,self).__init__(cl_manager)
        #TODO: make sure kernel works correctly on Intel/AMD CPUs and AMD graphics cards
        sat_cl_source = dm.load_string_from_file("kernels/sat.cl")
        self.program = cl.Program(cl_manager.context, sat_cl_source).build(options=str(cl_manager))
        
    def _process_cell(self, cell, bufs):
        mgr = self.manager
        #upload table to device
        cell_copy = cell.copy()#have to copy to produce a contiguous array
        queue = mgr.queue
        cl.enqueue_copy(queue, bufs.matrix, cell_copy, is_blocking=True)
        
        block_aggr_computed = self.program.compute_block_aggregates(queue,
                                              (mgr.cell_width,mgr.n_rows * mgr.schedule_optimized_n_warps),
                                              (mgr.warp_size, mgr.schedule_optimized_n_warps),
                                              bufs.matrix, bufs.group_column_sums, bufs.group_row_sums)

        y_groups_computed = self.program.vertical_aggregate(queue, 
                                            (mgr.n_sep_groups_x*mgr.warp_size, mgr.max_warps), 
                                            (mgr.warp_size,mgr.max_warps),
                                            bufs.group_column_sums,bufs.y_group_sums,
                                             wait_for=[block_aggr_computed])
        
            
        x_groups_computed = self.program.horizontal_aggregate(queue, 
                                            (mgr.warp_size,mgr.n_sep_groups_y*mgr.max_warps),
                                            (mgr.warp_size,mgr.max_warps),
                                            bufs.y_group_sums,bufs.group_row_sums,
                                            wait_for=[y_groups_computed])
        
        final_computed = self.program.redistribute_SAT_inplace(queue, 
                                            (mgr.cell_width,mgr.n_columns*mgr.schedule_optimized_n_warps),
                                            (mgr.warp_size,mgr.schedule_optimized_n_warps),
                                            bufs.matrix, bufs.group_column_sums, bufs.group_row_sums,
                                            wait_for=[x_groups_computed])
        queue.flush()
        #download table back
        cl.enqueue_copy(queue, cell_copy, bufs.matrix, wait_for=[final_computed],is_blocking=True)
        np.copyto(cell,cell_copy)

    @overrides(InPlaceFilter)  
    def _allocate_buffers(self):
        mgr = self.manager
        context = mgr.context
        mem_flags = cl.mem_flags
        #allocate buffers
        #input/output
        matrix = cl.Buffer(context,mem_flags.READ_WRITE, size = mgr.cell_height * mgr.cell_width*4)
        #group block intermediate results
        group_column_sums = cl.Buffer(context,mem_flags.READ_WRITE, size=mgr.n_rows*mgr.cell_width*4)
        group_row_sums = cl.Buffer(context,mem_flags.READ_WRITE, size=mgr.n_columns*mgr.cell_height*4)
        #these will hold aggregate 
        y_group_sums = cl.Buffer(context,mem_flags.READ_WRITE, size=mgr.n_columns*mgr.n_rows*4)
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
    def __init__(self, cl_manager):
        super(SummedAreaTableFilterCPU,self).__init__(cl_manager)
        
    def _process_cell(self,cell,bufs):
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
            
        
        
        
        
        
        
        
