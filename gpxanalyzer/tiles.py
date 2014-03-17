'''
Created on Mar 13, 2014

@author: Gregory Kramida
'''

from gevent import monkey
monkey.patch_all()
import gevent

import sqlite3
from tilecloud.store.mbtiles import MBTilesTileStore
from tilecloud import TileCoord
from PIL import ImageFile
from PySide import QtGui,QtCore



class QTiledImage(QtGui.QWidget):
    def __init__(self):
        super(QTiledImage,self).__init__()
        self.initUI()
        
    def initUI(self):
        self.setMinimumSize(1, 30)
        self.tile_scale = 0
        self.pos = (0,0)
        self.cached_tiles = []
        self.tile_store = None
        
    @property
    def tile_store(self):
        return self.tile_store
    
    @tile_store.setter
    def tile_store(self, tile_store_filename):
        self.tile_store = QTileStore(tile_store_filename)
        self.bounding_pyramid = self.tile_store.get_cheap_bounding_pyramid()
    
    @tile_store.deleter
    def tile_store(self):
        del self.tile_store
        del self.bounding_pyramid
        
    def draw_tile(self,tile_x,tile_y,tile_zoom,rect):
    
    def paintEvent(self,e):
        qp = QtGui.QPainter()
        qp.begin()
        self.drawWidget(qp)
        qp.end()
    
    def drawWidget(self,qp):
        #TODO - remove next line
        qp = QtGui.QPainter()
        
        size=self.size()
        w = size.width()
        h = size.height()
        
        
        

class QTileStore(MBTilesTileStore):
    
    '''
    A tiled image.
    '''

    def __init__(self, mbtiles_filename, **kwargs):
        '''
        Constructs a TiledImage connected to the current mbtilse sqllite database file.
        '''
        connection = sqlite3.connect(mbtiles_filename)
        super(QTileStore,self).__init__(connection,**kwargs)
    
    def get_raw_data(self, x, y, z):
        try:
            data = self.tiles[TileCoord(z, x, y)]
            parser= ImageFile.Parser()
            parser.feed(data)
            image = parser.close()
            raw_data = image.tostring('raw','RGB')
        except KeyError:
            return None
        return raw_data
    
    def get_qimage(self, x, y, z):
        try:
            data = self.tiles[TileCoord(z, x, y)]
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