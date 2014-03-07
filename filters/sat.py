'''
Created on Feb 24, 2014

@author: algomorph
'''
import pyopencl as cl
import numpy as np
import utils.data as dm
    

class SummedAreaTableConfig:
    def __init__(self, cell_width, cell_height, warp_size, max_threads):
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.warp_size = warp_size
        self.half_warp_size = warp_size / 2
        self.n_columns = cell_width / warp_size
        self.n_rows = cell_height / warp_size
        self.max_threads = max_threads
        self.max_warps = max_threads/warp_size
        self.n_horizontal_groups = (cell_width + max_threads - 1) / max_threads
        self.n_vertical_groups = (cell_height + max_threads - 1) / max_threads
        #TODO: figure out how to auto-tune this
        self.schedule_optimized_n_warps = 5
        self.input_stride = cell_width * self.schedule_optimized_n_warps
        
    def __str_helper(self, const_name, value):
        return " -D " + const_name + "=" + str(value)
    def __str__(self):
        return self.__str_helper("WIDTH", self.cell_width) + \
            self.__str_helper("HEIGHT", self.cell_height) + \
            self.__str_helper("WARP_SIZE", self.warp_size) + \
            self.__str_helper("HALF_WARP_SIZE", self.half_warp_size) + \
            self.__str_helper("INPUT_STRIDE", self.input_stride) + \
            self.__str_helper("N_COLUMNS", self.n_columns) + \
            self.__str_helper("N_ROWS", self.n_rows)


def __cpu_sat_process_cell(cell):
    mout = np.zeros(cell.shape, dtype=cell.dtype)
    mout[0,0] = cell[0,0]
    for i_row in xrange(1,cell.shape[0]):
        mout[i_row,0] = cell[i_row,0] + mout[i_row-1,0]
    for i_col in xrange(1,cell.shape[1]):
        mout[0,i_col] = cell[0,i_col] + mout[0,i_col-1]
    
    for i_row in xrange(1,cell.shape[0]):
        for i_col in xrange(1,cell.shape[1]):
            mout[i_row,i_col] = cell[i_row,i_col] + mout[i_row-1,i_col] + mout[i_row,i_col-1] - mout[i_row-1,i_col-1]
    return mout
    
def __cpu_sat_process_channel(tile, cell_width, cell_height):
    for y in xrange(0,tile.shape[0],cell_height):
        for x in xrange(0,tile.shape[1],cell_width):
            cell = tile[y:y+cell_height,x:x+cell_height]
            np.copyto(cell,__cpu_sat_process_cell(cell))

def cpu_sat(tile, cell_width = 4096, cell_height = 4096):
    '''
    Computes summed-area tables for the given tile.
    There will be a separate table for each cell in tile.
    @type tile: 2D or 3D numpy array
    @param tile: the original image tile
    @type cell_width: int
    @param cell_width: cell_width of the cells within the tile
    @type cell_height: int
    @param cell_hegiht: height of the cells within the tile
    @return summed-area tables for cells of the whole tile, in the shape of the original tile and dtype np.uint32 
    '''
    if(len(tile.shape) > 2):
        channel_sums = []
        for i_channel in xrange(tile.shape[2]):
            channel_sums.append(__cpu_sat_process_channel(tile[:,:,i_channel].astype(np.uint32),cell_width,cell_height))
        return np.dstack(channel_sums)
    else:
        tile_copy = tile.astype(np.uint32)
        __cpu_sat_process_channel(tile_copy,cell_width,cell_height)
        return tile_copy
        
class SummedAreaTableFilter:
    printed = False
    def __init__(self, context, config):
        sat_cl_source = dm.load_string_from_file("kernels/imsat.cl")
        self.config = config
        self.context = context
        self.program = cl.Program(context, sat_cl_source).build(options=str(config))
        self.kernels = {}
        
    def _process_cell(self, cell, queue, matrix, group_column_sums, group_row_sums, y_group_sums):
        config = self.config
        #upload table to device
        cell_copy = cell.copy()#have to copy to produce a contiguous array
        cl.enqueue_copy(queue, matrix, cell_copy, is_blocking=True)
        
        block_aggr_computed = self.program.compute_block_aggregates(queue,
                                              (config.cell_width,config.n_rows * config.schedule_optimized_n_warps),
                                              (config.warp_size, config.schedule_optimized_n_warps),
                                              matrix, group_column_sums, group_row_sums)

        y_groups_computed = self.program.vertical_aggregate(queue, 
                                            (config.n_horizontal_groups*config.warp_size, config.max_warps), 
                                            (config.warp_size,config.max_warps),
                                            group_column_sums,y_group_sums,
                                             wait_for=[block_aggr_computed])
        
            
        x_groups_computed = self.program.horizontal_aggregate(queue, 
                                            (config.warp_size,config.n_vertical_groups*config.max_warps),
                                            (config.warp_size,config.max_warps),
                                            y_group_sums,group_row_sums,
                                            wait_for=[y_groups_computed])
        final_computed = self.program.redistribute_SAT_inplace(queue, 
                                            (config.cell_width,config.n_columns*config.schedule_optimized_n_warps),
                                            (config.warp_size,config.schedule_optimized_n_warps),
                                            matrix, group_column_sums, group_row_sums,
                                            wait_for=[x_groups_computed])
        queue.flush()
        #download table back
        cl.enqueue_copy(queue, cell_copy, matrix,wait_for=[final_computed],is_blocking=True)
        np.copyto(cell,cell_copy)
        
    def _process_channel(self, channel, queue, matrix, group_column_sums, group_row_sums, y_group_sums):
        config = self.config
        for y in xrange(0,channel.shape[0],config.cell_height):
                y_end = y+config.cell_height
                #traverse cell columns
                for x in xrange(0,channel.shape[1],config.cell_width):
                    x_end = x+config.cell_width
                    #slice of the tile channel
                    cell = channel[y:y_end,x:x_end]
                    #process cell in-place
                    self._process_cell(cell, queue, matrix, group_column_sums, group_row_sums, y_group_sums)
    
    def __call__(self, tile, queue = None):
        '''
        Compute summed area tables of a raster single-channel or multi-channel image tile
        '''
        context = self.context
        config = self.config
        mem_flags = cl.mem_flags
        
        #allocate buffers
        #input/output
        matrix = cl.Buffer(context,mem_flags.READ_WRITE, size = config.cell_height * config.cell_width*4)
        #group block intermediate results
        group_column_sums = cl.Buffer(context,mem_flags.READ_WRITE, size=config.n_rows*config.cell_width*4)
        group_row_sums = cl.Buffer(context,mem_flags.READ_WRITE, size=config.n_columns*config.cell_height*4)
        #these will hold aggregate 
        y_group_sums = cl.Buffer(context,mem_flags.READ_WRITE, size=config.n_columns*config.n_rows*4)
        
        #create a queue if one is needed
        if(queue is None):
            queue = cl.CommandQueue(context)
        
        if(len(tile.shape)==3):
            summed_channels = []
            #traverse channels
            for i_channel in xrange(tile.shape[2]):
                #copy channel from uint8 to uint32
                channel = tile[:,:,i_channel].astype(np.uint32)
                self._process_channel(channel, queue, matrix, group_column_sums, group_row_sums, y_group_sums)
                #aggregate summed channels in a single list
                summed_channels.append(channel)
            summed_area_tables = np.dstack(summed_channels)
        elif(len(tile.shape)==2):
            channel = tile.astype(np.uint32)
            self._process_channel(channel, queue, matrix, group_column_sums, group_row_sums, y_group_sums)
            summed_area_tables = channel
        else:
            raise ValueError("Only 2D (greyscale) or 3D (multi-channel) image tiles are supported.")
        
        #release buffers
        group_column_sums.release()
        group_row_sums.release()
        y_group_sums.release()
        matrix.release()
        #convert list of channels to a single Numpy array and return
        return summed_area_tables
        
        
        
        
        
        
        
        
        
        
