'''
Created on Mar 9, 2014

@author: Gregory Kramida
'''
from abc import abstractmethod
import abc

import numpy as np
import pyopencl as cl


class InPlaceFilter():
    '''
    A generic abstract image filter
    '''
    __metaclass__ = abc.ABCMeta
    
    def __init__(self, cl_manager):
        self.manager = cl_manager
        if(cl_manager.n_channels > 1):
            self._process = self._process_multi_channel
        else:
            self._process = self._process_single_channel
        
    @abstractmethod    
    def _process_cell(self, cell, bufs):
        """
        Applies filter to a single cell.
        """
        pass
    
    def _process_channel(self,channel,bufs):
        """
        Applies filter to all cells within the channel in-place.
        """
        (cell_height,cell_width) = (self.manager.cell_shape)
        #traverse cell rows
        for y in xrange(0,channel.shape[0],cell_height):
                y_end = y+cell_height
                #traverse cell columns
                for x in xrange(0,channel.shape[1],cell_width):
                    x_end = x+cell_width
                    #slice of the tile channel
                    cell = channel[y:y_end,x:x_end]
                    #process cell in-place
                    self._process_cell(cell, bufs)
    
    def _process_single_channel(self, tile, bufs):
        """
        Applies filter to a single-channel tile.
        Does not modify the original tile.
        """
        channel = tile.astype(np.uint32)
        self._process_channel(channel, bufs)
        return channel

    def _process_multi_channel(self, tile, bufs):
        """
        Applies filter to a multi-channel tile.
        Does not modify the original tile.
        """
        result_channels = []
        for i_channel in xrange(tile.shape[2]):
            #copy channel from uint8 to uint32
            channel = tile[:,:,i_channel].astype(np.uint32)
            self._process_channel(channel, bufs)
            #aggregate summed channels in a single list
            result_channels.append(channel)
        result_raster = np.dstack(result_channels)
        return result_raster
    
    def _allocate_buffers(self):
        return None
    
    def _release_buffers(self,bufs):
        pass

    
    def __call__(self, tile):
        '''
        Applies the filter to each cell within the the given tile.
        Does not modify the original tile.
        @type tile: 2D or 3D numpy array
        @param tile: the original image tile
        @return summed-area tables for cells of the whole tile, in the shape of the original tile and dtype np.uint32 
        '''
        bufs = self._allocate_buffers()
        summed_area_tables = self._process(tile,bufs)
        
        #release buffers
        self._release_buffers(bufs)
        #convert list of channels to a single Numpy array and return
        return summed_area_tables
    
        