'''
Created on Mar 13, 2014

@author: Gregory Kramida
@license: GNU v3
@copyright: (c) Gregory Kramida 2014
'''

from PIL import ImageFile
from PySide import QtGui,QtCore
import math
import sqlite3
from tilecloud import TileCoord, Tile
from tilecloud.store.mbtiles import MBTilesTileStore
from tilecloud.lib.sqlite3_ import query
import sys
import PySide
from collections import deque
sys.modules['PyQt4'] = PySide
from PIL import ImageQt
import gc


def PIL_to_QImage(pil_img):
#    TODO: add layer alpha support
    return ImageQt.ImageQt(pil_img)

class QTiledLayerViewer(QtGui.QWidget):
    def __init__(self, cl_manager, first_layer = None):
        super(QTiledLayerViewer,self).__init__()
        self.manager = cl_manager
        self.max_cache_size = cl_manager.system.max_tile_cache_mem
        if(first_layer != None):
            self.layers = [first_layer]
            self.full_tile_size= first_layer.tile_size
            self.half_tile_size= self.full_tile_size / 2
        else:
            self.layers = []
        self.set_up_ui()
        
    def set_up_ui(self):
        self.setMinimumSize(512,512)
        self.cache = {}
        self.cache_queue = deque()
        self.root = TileCoord(0, 0, 0)
        self.zoom = 1.0
        self.top_left = (0,0)
        self.start_x = 0
        self.start_y = 0
        self.start_mouse_x = 0
        self.start_mouse_y = 0
        self.tile_scale = 0
        self.pos = (0,0)
        self.cache_size = 0
        
    
    def tile(self, index, z, x, y, tile_size, full_tile_size):
        #TODO: add layer alpha support
        root = self.root
        cache = self.cache
        tilecoord = TileCoord(z + root.z,
                              x + root.x * (1 << z),
                              y + root.y * (1 << z))
        if (index, z, x, y) in cache:
            image = self.cache[(index, z, x, y)]
        else:
            tile = Tile(tilecoord)
            image = self.layers[index].get_PIL_image(tile)
            if self.cache is not None and image is not None:
                coord = (index, z, x, y)
                self.cache[coord] = image
                self.cache_queue.append(coord)
                self.cache_size += image.size[0]*image.size[1]*len(image.getbands())
                #if the cache size exceeds limit, delete some of the tiles added earlier
                #TODO: it seems that it's better to delete tiles that are "far away" - farthest in 
                #the layer_ix, x,y,z coordinates instead of just removing the ones added first, i.e.
                #user could be doing more panning after coming back to some earlier zoom level
                while(self.cache_size > self.max_cache_size):
                    coord = self.cache_queue.popleft()
                    del self.cache[coord]
                    gc.collect()
                
                
        if image is not None:
            if(tile_size != full_tile_size):
                new_size = (int(float(image.size[0]) / self.full_tile_size* tile_size),
                            int(float(image.size[1]) / self.full_tile_size* tile_size))
                image = image.resize(new_size)
            return PIL_to_QImage(image)
        return None
    
    def __setitem__(self,index,layer):
        if(len(self.layers) > index):
            self.empty_cache()
        self.__check_layer_size(layer)
        self.layers[index] = layer
        
    def __getitem__(self,index,layer):
        return self.layers[index]
    
    def __check_layer_size(self,layer):
        if(len(self.layers) == 0):
            self.full_tile_size = layer.tile_size
            self.half_tile_size = self.full_tile_size / 2
        else:
            if(layer.tile_size != self.full_tile_size):
                raise ValueError("Layers with different tile sizes are not supported.")
            
    def empty_cache(self):
        self.cache = {}
        self.cache_queue=deque()
        self.cache_size = 0
        gc.collect()
    
    def add_layer(self,layer):
        self.__check_layer_size(layer)
        self.layers.append(layer)
        self.repaint()
    
    def insert_layer(self,index,layer):
        self.__check_layer_size(layer)
        self.layers.insert(index, layer)
        self.repaint()
        
    def switch_base_layer(self,layer):
        if(len(self.layers) == 0):
            self.layers.append(layer)
        else:
            self.layers[0] = layer
        self.full_tile_size = layer.tile_size
        self.half_tile_size = self.full_tile_size / 2
        self.empty_cache()
        self.repaint()
        
    
    def __iter__(self):
        for layer in self.layers:
            yield layer
            
    def __tile_size_by_zoom(self,zoom):
        #get the next-higher-up whole zoom level
        tile_zoom = int(math.ceil(zoom))
        zoom_ratio = zoom % 1.0
        if(zoom_ratio == 0.0):
            tile_size = self.full_tile_size
        #if the fraction is below 1/256, use the previous whole zoom level
        elif(zoom_ratio < 1.0 / self.full_tile_size):
            tile_zoom -= 1
            tile_size = self.full_tile_size
        else:
            tile_size = int(self.half_tile_size+ self.half_tile_size* zoom_ratio)
        return tile_size, tile_zoom
            
    def __size_by_zoom(self,zoom):
        tile_size, tile_zoom = self.__tile_size_by_zoom(zoom)
        tiles_per_side = 2**tile_zoom
        return tile_size * tiles_per_side
    
    def zoom_by(self,val, pt):
        last_zoom = self.zoom
        self.zoom = max(0.0,self.zoom + val)
        x, y = pt.x(), pt.y()
        last_offset_x = self.top_left[0] - x
        last_offset_y = self.top_left[1] - y
        size_ratio = float(self.__size_by_zoom(self.zoom)) / self.__size_by_zoom(last_zoom)        
        new_offset_x = int(last_offset_x * size_ratio)
        new_offset_y = int(last_offset_y * size_ratio)
        self.top_left = (x + new_offset_x, y + new_offset_y)
        print self.zoom 
        self.repaint()
        
    def wheelEvent(self,event):
        #TODO: smooth zoom animations, as in gigapan.com
        numDegrees = float(event.delta()) / 8
        numSteps = numDegrees / 15
        self.zoom_by(numSteps / 4, event.pos())
        
    def zoom_in_smoothly(self):
        zoom_step = 0.02
        pt = self.mapFromGlobal(QtGui.QCursor.pos())
        while self.zoom < 8.7:
            self.zoom_by(zoom_step, pt)
        
    def paintEvent(self,event):
        qp = QtGui.QPainter()
        qp.begin(self)
        self.draw_widget(qp)
        qp.end()
        
    def mousePressEvent(self,event):
        if(event.button() == QtCore.Qt.MiddleButton):
            pt = event.pos()
            (self.start_mouse_x, self.start_mouse_y) = (pt.x(),pt.y()) 
            (self.start_x, self.start_y) = self.top_left
            
    def mouseMoveEvent(self,event):
        #TODO: smooth mouse animations, as in gigapan.com
        if(event.buttons() == QtCore.Qt.MiddleButton):
            pt = event.pos()
            x,y = pt.x(), pt.y()
            self.top_left = (self.start_x + (x - self.start_mouse_x), self.start_y + (y - self.start_mouse_y))
            self.repaint()
            
    def mouseReleaseEvent(self, event):
        if(event.button() == QtCore.Qt.MiddleButton):
            pt = event.pos()
            x,y = pt.x(), pt.y()
            self.top_left = (self.start_x + (x - self.start_mouse_x), self.start_y + (y - self.start_mouse_y))
            self.repaint()
        
    def draw_layer(self,ix_layer,qp):     
        tile_size,tile_zoom = self.__tile_size_by_zoom(self.zoom)
        layer = self.layers[ix_layer]
        size = self.size()
        w = size.width()
        h = size.height()
        if TileCoord(tile_zoom,0,0) in layer.bounding_pyramid:
            #get bounds at this whole zoom level
            (xbounds,ybounds) = layer.bounding_pyramid.zget(tile_zoom)
            
            #calculate total # of tiles in each dimension
            n_tiles_x = xbounds.stop - xbounds.start
            n_tiles_y = ybounds.stop - ybounds.start
            

            (x_start,y_start) = self.top_left
            
            #arbitrary pixel bounds
            end_x = x_start + n_tiles_x * tile_size
            end_y = y_start + n_tiles_y * tile_size
            
            if(x_start > w or y_start > h or end_x < 0 or end_y < 0):
                return
            
            start_tile_x = 0
            start_tile_y = 0
            end_tile_x = n_tiles_x
            end_tile_y = n_tiles_y
            #crop the tile bounds if need be
            if(x_start < 0):
                start_tile_x += -x_start / tile_size
                x_start += start_tile_x * tile_size
            if(y_start < 0):
                start_tile_y += -y_start / tile_size
                y_start += start_tile_y * tile_size
            if(end_x > w):
                end_tile_x -= (end_x - w) / tile_size
            if(end_y > h):
                end_tile_y -= (end_y - h) / tile_size
            
            tiles_drawn = 0
            x = x_start
            for x_tile in xrange(start_tile_x,end_tile_x):
                y = y_start
                for y_tile in xrange(start_tile_y,end_tile_y):
                    tile = self.tile(ix_layer,tile_zoom,x_tile,y_tile,tile_size,self.full_tile_size)
                    if(tile is not None):
                        qp.drawImage(x,y,tile)
                    tiles_drawn += 1
                    y += tile.height()
                x_tile +=1
                x += tile.width()
            
    def minimumSizeHint(self):
        return QtCore.QSize(512,512)
    
    def sizeHint(self):
        return QtCore.QSize(1024,1024)
    
    def draw_widget(self,qp):
        for ix_layer in xrange(len(self.layers)):
            self.draw_layer(ix_layer, qp)
            
        

class TileLayer(MBTilesTileStore):
    
    def __init__(self, mbtiles_filepath, **kwargs):
        '''
        Constructs a tiled image store connected to the current mbtilse sqllite database file.
        '''
        self.__file_path = mbtiles_filepath
        connection = sqlite3.connect(mbtiles_filepath)
        super(TileLayer,self).__init__(connection,**kwargs)
        if (u'tile_size' in self.metadata):
            self.tile_size = int(self.metadata[u'tile_size'])
        else:
            data = self.tiles[TileCoord(0,0,0)]
            parser= ImageFile.Parser()
            parser.feed(data)
            image = parser.close()
            self.tile_size = image.size[0]
            self.metadata[u'tile_size'] = unicode(self.tile_size)
        self.bounding_pyramid = self.get_bounding_pyramid()
        self.alpha = 255
    
    @property
    def file_path(self):
        return self.__file_path
    
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
    
    def get_PIL_image(self,tile):
        try:
            data = self.tiles[tile.tilecoord]
            parser= ImageFile.Parser()
            parser.feed(data)
            image = parser.close()
        except KeyError:
            return None
        return image
    
    def get_qimage(self, tile):
        try:
            data = self.tiles[tile.tilecoord]
            parser= ImageFile.Parser()
            parser.feed(data)
            image = parser.close()
            qimage = PIL_to_QImage(image)
        except KeyError:
            return None
        return qimage
    
    def __del__(self):
        self.connection.close()