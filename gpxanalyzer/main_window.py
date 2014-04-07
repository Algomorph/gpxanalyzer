'''
Created on Mar 13, 2014

@author: Gregory Kramida
@license: GNU v3
@copyright: (c) Gregory Kramida 2014
'''

from gpxanalyzer.gui.combiner_gui import CombineTilesDialog
from gpxanalyzer.gui.arranger_gui import ArrangeTilesDialog
from PySide import QtCore, QtGui
import os
import gpxanalyzer.tiles as tiles
import config as cfg


class GigapixelAnalyzer(QtGui.QMainWindow):
    def __init__(self, cl_manager, startup_dir):
        super(GigapixelAnalyzer, self).__init__()
        self.manager = cl_manager
        self.startup_dir = startup_dir
        self.init_gui()

    def init_gui(self):
        self.setWindowIcon(QtGui.QIcon('icon.png'))
        self.printer = QtGui.QPrinter()
        #self.setSizePolicy(QtGui.QSizePolicy.Ignored,QtGui.QSizePolicy.Ignored)
        self.setBackgroundRole(QtGui.QPalette.Dark)
        
        #startup = "/mnt/sdb2/Data/mbtiles/immunogold-colored/255_reduced.mbtiles"
        #startup = "/media/algomorph/Data/mbtiles/king_penguins_8192/db.sqlite"
        #startup = "/media/algomorph/Data/mbtiles/king_penguins/db.sqlite"
        if (hasattr(self.manager.system, "startup_file_path") and os.path.exists(self.manager.system.startup_file_path)):
            self.image_area = tiles.QTiledLayerViewer(self.manager,tiles.TileLayer(self.manager.system.startup_file_path))
        else:
            self.image_area = tiles.QTiledLayerViewer(self.manager)
            
        self.image_area.setBackgroundRole(QtGui.QPalette.Base)
        self.image_area.setSizePolicy(QtGui.QSizePolicy.Ignored,QtGui.QSizePolicy.Ignored)

        self.setCentralWidget(self.image_area)

        self.create_actions()
        self.create_menus()

        self.setWindowTitle("Gigapixel Analyzer")
        self.resize(800,600)
        self.show()
        #self.showMaximized()
        
    def save_config(self):
        cfg.save_config(self.startup_dir, self.manager, True)

    def closeEvent(self,event):
        self.save_config()


    def open(self):
        file_path = str(QtGui.QFileDialog.getOpenFileName(self, "Open File",
                QtCore.QDir.currentPath())[0])
        if file_path is not None:
            layer = tiles.TileLayer(file_path)
            self.image_area.switch_base_layer(layer)
    
    #TODO figure out a way (Tabs, perhaps, or QThreads?) to 
    #get multiple tools AND the main interface usable at the same time.
    def open_tile_combiner(self):
        dialog = CombineTilesDialog(self.manager,self)
        dialog.resize(1024,600)
        dialog.exec_()
        
    def open_tile_arranger(self):
        dialog = ArrangeTilesDialog(self.manager,self)
        dialog.resize(1024,400)
        dialog.exec_()

    def about(self):
        QtGui.QMessageBox.about(self, "About Gigapixel Analyzer",
                "<p>The <b>Gigapixel Analyzer</b>  is a really cool app still under development.</p>")

    def create_actions(self):
        self.about_action = QtGui.QAction("&About", self, triggered=self.about)

        self.about_Qt_action = QtGui.QAction("About &Qt", self,
                triggered=QtGui.qApp.aboutQt)
        
        self.exit_action = QtGui.QAction("E&xit", self, shortcut="Ctrl+Q",
                triggered=self.close)

        self.open_action = QtGui.QAction("&Open...", self, shortcut="Ctrl+O",
                triggered=self.open)
        
        self.open_combiner_tool_action = QtGui.QAction("&Combine Tiles...", self, shortcut="Ctrl+Shift+C",
                triggered=self.open_tile_combiner)
    
        self.open_arranger_tool_action = QtGui.QAction("&Pyramidize Tiles...", self, shortcut="Ctrl+Shift+P",
                    triggered=self.open_tile_arranger)
        
        self.set_startup_file_action = QtGui.QAction("&Set Startup File...",self,shortcut="Ctrl+Shift+F",
                                               triggered=self.set_startup_file)
        
    def set_startup_file(self):
        layer_paths = []
        for layer in self.image_area:
            layer_paths.append(layer.file_path)
        dialog = SetStartupDialog(layer_paths,self)
        retval = dialog.exec_()
        path = layer_paths[retval]
        self.manager.system.startup_file_path = path
        cfg.save_config(self.startup_dir, self.manager, True)
         

    def create_menus(self):
        self.fileMenu = QtGui.QMenu("&File", self)
        self.fileMenu.addAction(self.open_action)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.set_startup_file_action)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exit_action)

        self.viewMenu = QtGui.QMenu("&View", self)
        self.viewMenu.addSeparator()

        self.toolsMenu = QtGui.QMenu("&Tools",self)
        self.toolsMenu.addAction(self.open_combiner_tool_action)
        self.toolsMenu.addAction(self.open_arranger_tool_action)
        
        self.helpMenu = QtGui.QMenu("&Help", self)
        self.helpMenu.addAction(self.about_action)
        self.helpMenu.addAction(self.about_Qt_action)

        self.menuBar().addMenu(self.fileMenu)
        self.menuBar().addMenu(self.viewMenu)
        self.menuBar().addMenu(self.toolsMenu)
        self.menuBar().addMenu(self.helpMenu)
        
class SetStartupDialog(QtGui.QDialog):
    def __init__(self,file_list, parent = None):
        super(SetStartupDialog, self).__init__(parent)
        self.file_list = file_list
        layout = QtGui.QVBoxLayout()
        
        list_view = QtGui.QListWidget(self)
        for path in file_list:
            list_view.addItem(QtGui.QListWidgetItem(path))
        
        list_view.itemClicked.connect(self.item_select)
        
        layout.addWidget(list_view)
        self.list_view = list_view
        self.setLayout(layout)
        
        
    
    def item_select(self,item):
        sel = str(item.text())
        self.setResult(self.file_list.index(sel))
        self.close()
