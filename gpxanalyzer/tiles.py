'''
Created on Mar 13, 2014

@author: Gregory Kramida
'''


import sqlite3
import math
from tilecloud.store.mbtiles import MBTilesTileStore
from tilecloud import TileCoord, Tile
from PIL import ImageFile
from PySide import QtGui,QtCore

full_tile_size = 256

class QTiledLayerViewer(QtGui.QWidget):
    def __init__(self):
        super(QTiledLayerViewer,self).__init__()
        self.cache = {}
        self.layers = []
        self.initUI()
        self.root = TileCoord(0, 0, 0)
        self.zoom = 0.0
        self.top_left = (0,0)
        
        
    def initUI(self):
        self.setMinimumSize(1, 30)
        self.tile_scale = 0
        self.pos = (0,0)
    
    def tile(self, index, z, x, y):
        # FIXME check ext
        root = self.root
        cache = self.cache
        tilecoord = TileCoord(z + root.z,
                              x + root.x * (1 << z),
                              y + root.y * (1 << z))
        if self.cache is not None and (index, z, x, y) in cache:
            tile = self.cache[(index, z, x, y)]
        else:
            tile = Tile(tilecoord)
            tile = self.layers[index].get_qimage(tile)
            if self.cache is not None:
                self.cache[(index, z, x, y)] = tile
        return tile
    
    def __setitem__(self,index,layer):
        self.layers[index] = layer
        
    def __getitem__(self,index,layer):
        return self.layers[index]
    
    def add_layer(self,layer):
        self.layers.append(layer)
    
    def insert_layer(self,index,layer):
        self.layers.insert(index, layer)
    
    def __iter__(self):
        for layer in self.layers:
            yield layer
            
    def get_layer_constraints(self):
        self.zoom
        
    #def draw_tile(self,index,tile_x,tile_y,tile_z,rect):
        
    def paintEvent(self,e):
        qp = QtGui.QPainter()
        qp.begin()
        self.draw_widget(qp)
        qp.end()
        
    def draw_layer(self,ix_layer,qp):
        size=self.size()
        w = size.width()
        h = size.height()
        (x_start,y_start) = self.top_left
        #get the next-higher-up whole zoom level
        tile_zoom = int(math.ceil(self.zoom))
        zoom_ratio = self.zoom % 1.0
        #if the fraction is below 1/256, use the previous whole zoom level
        if(zoom_ratio < 1.0 / full_tile_size):
            zoom_ratio = 1.0
            tile_zoom -= 1 
            
        tile_size = full_tile_size * zoom_ratio
        layer = self.layers[ix_layer]
        #calculate offsets and which tiles to skip rendering
        #get bounds at this whole zoom level
        (xbounds,ybounds) = layer.bounding_pyramid.zget(tile_zoom)
        #calculate total # of tiles in each dimension
        n_tiles_x = xbounds.stop - xbounds.start + 1
        n_tiles_y = ybounds.stop - ybounds.start + 1
        #calculate pixel coordinates if we were to render all tiles
        x_end = n_tiles_x * tile_size + x_start
        y_end = n_tiles_y * tile_size + y_start
        #figure out what size are the margins (negative if there is overflow)
        right_margin = w - x_end
        bottom_margin = h - y_end 
        #how many tiles fit into the left & top margin?
        x_tile_offset = x_start / tile_size
        y_tile_offset = y_start / tile_size
        #if the above numbers are negative, the latter coordinate will be where we actually start rendering
        x_start = max(x_start, x_start - x_tile_offset*tile_size)
        y_start = max(y_start, y_start - y_tile_offset*tile_size)
        #figure out which tiles we should actually start with
        x_tile_start = max(x_tile_offset,0)
        y_tile_start = max(y_tile_offset,0)
        #figure out which tiles we should end with
        x_tile_end = min(n_tiles_x + (-right_margin / tile_size), n_tiles_x)
        y_tile_end = min(n_tiles_y + (-bottom_margin / tile_size), n_tiles_y)
        n_tiles_x = x_tile_end - x_tile_start
        n_tiles_y = y_tile_end - y_tile_start
        
        x_end = x_start + n_tiles_x * tile_size
        y_end = y_start + n_tiles_y * tile_size
        
        x_tile = x_tile_start
        for x in xrange(x_start,x_end,tile_size):
            y_tile = y_tile_start
            for y in xrange(y_start,y_end,tile_size):
                tile = self.tile(ix_layer,tile_zoom,x_tile,y_tile)
                qp.drawImage(x,y,tile)
                y_tile +=1
            x_tile +=1
        
    
    def draw_widget(self,qp):
        #TODO - remove next line
        for ix_layer in xrange(len(self.layers)):
            self.draw_layer(ix_layer, qp)        
        

class QTileStore(MBTilesTileStore):

    def __init__(self, mbtiles_filename, **kwargs):
        '''
        Constructs a tiled image store connected to the current mbtilse sqllite database file.
        '''
        connection = sqlite3.connect(mbtiles_filename)
        super(QTileStore,self).__init__(connection,**kwargs)
        self.bounding_pyramid = self.get_bounding_pyramid()
        
        self.alpha = 255
    
    def get_raw_data(self, tile):
        try:
            data = self.tiles[tile.tilecoord]
            parser= ImageFile.Parser()
            parser.feed(data)
            image = parser.close()
            raw_data = image.tostring('raw','RGB')
        except KeyError:
            return None
        return raw_data
    
    def get_qimage(self, tile):
        try:
            data = self.tiles[tile.tilecoord]
            parser= ImageFile.Parser()
            parser.feed(data)
            image = parser.close()
            raw_data = image.tostring('raw','RGB')
            qimage = QtGui.QImage(raw_data, 256, 256, QtGui.QImage.Format_RGB888)
        except KeyError:
            return None
        return qimage
    
    def __del__(self):
        self.connection.close()