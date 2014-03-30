'''
Created on Mar 13, 2014

@author: Gregory Kramida
@license: GNU v3
@copyright: (c) Gregory Kramida 2014
'''

from PySide import QtCore, QtGui

import gpxanalyzer.tiles as tiles
import os

class GigapixelAnalyzer(QtGui.QMainWindow):
    def __init__(self, config):
        super(GigapixelAnalyzer, self).__init__()
        self.config = config
        self.init_gui()

    def init_gui(self):
        self.printer = QtGui.QPrinter()
        #self.setSizePolicy(QtGui.QSizePolicy.Ignored,QtGui.QSizePolicy.Ignored)
        self.setBackgroundRole(QtGui.QPalette.Dark)
        
        #startup = "/mnt/sdb2/Data/mbtiles/immunogold-colored/255_reduced.mbtiles"
        startup = "/media/algomorph/Data/mbtiles/king_penguins_8192/db.sqlite"
        #startup = "/media/algomorph/Data/mbtiles/king_penguins/db.sqlite"
        self.image_area = tiles.QTiledLayerViewer(tiles.TileLayer(startup))
        self.image_area.setBackgroundRole(QtGui.QPalette.Base)
        self.image_area.setSizePolicy(QtGui.QSizePolicy.Ignored,QtGui.QSizePolicy.Ignored)

        self.setCentralWidget(self.image_area)
        

        self.createActions()
        self.createMenus()

        self.setWindowTitle("Gigapixel Analyzer")
        self.resize(800,600)
        self.show()
        #self.showMaximized()


    def open(self):
        file_path = QtGui.QFileDialog.getOpenFileName(self, "Open File",
                QtCore.QDir.currentPath())[0]
        if file_path:
            layer = tiles.TileLayer(file_path)
            self.image_area.add_layer(layer)

    def print_(self):
        dialog = QtGui.QPrintDialog(self.printer, self)
        if dialog.exec_():
            painter = QtGui.QPainter(self.printer)
            rect = painter.viewport()
            size = self.imageLabel.pixmap().size()
            size.scale(rect.size(), QtCore.Qt.KeepAspectRatio)
            painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
            painter.setWindow(self.imageLabel.pixmap().rect())
            painter.drawPixmap(0, 0, self.imageLabel.pixmap())

    def zoomIn(self):
        self.scaleImage(1.25)

    def zoomOut(self):
        self.scaleImage(0.8)

    def normalSize(self):
        self.scaleFactor = 1.0

    def fitToWindow(self):
        fitToWindow = self.fitToWindowAct.isChecked()
        self.scroll_area.setWidgetResizable(fitToWindow)
        if not fitToWindow:
            self.normalSize()

        self.updateActions()

    def about(self):
        QtGui.QMessageBox.about(self, "About Gigapixel Analyzer",
                "<p>The <b>Gigapixel Analyzer</b>  is a really cool app still under development.</p>")

    def createActions(self):
        self.openAct = QtGui.QAction("&Open...", self, shortcut="Ctrl+O",
                triggered=self.open)

        self.printAct = QtGui.QAction("&Print...", self, shortcut="Ctrl+P",
                enabled=False, triggered=self.print_)

        self.exitAct = QtGui.QAction("E&xit", self, shortcut="Ctrl+Q",
                triggered=self.close)

        self.zoomInAct = QtGui.QAction("Zoom &In (25%)", self,
                shortcut="Ctrl++", enabled=False, triggered=self.zoomIn)

        self.zoomOutAct = QtGui.QAction("Zoom &Out (25%)", self,
                shortcut="Ctrl+-", enabled=False, triggered=self.zoomOut)

        self.normalSizeAct = QtGui.QAction("&Normal Size", self,
                shortcut="Ctrl+S", enabled=False, triggered=self.normalSize)

        self.fitToWindowAct = QtGui.QAction("&Fit to Window", self,
                enabled=False, checkable=True, shortcut="Ctrl+F",
                triggered=self.fitToWindow)

        self.aboutAct = QtGui.QAction("&About", self, triggered=self.about)

        self.aboutQtAct = QtGui.QAction("About &Qt", self,
                triggered=QtGui.qApp.aboutQt)

    def createMenus(self):
        self.fileMenu = QtGui.QMenu("&File", self)
        self.fileMenu.addAction(self.openAct)
        self.fileMenu.addAction(self.printAct)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exitAct)

        self.viewMenu = QtGui.QMenu("&View", self)
        self.viewMenu.addAction(self.zoomInAct)
        self.viewMenu.addAction(self.zoomOutAct)
        self.viewMenu.addAction(self.normalSizeAct)
        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.fitToWindowAct)

        self.helpMenu = QtGui.QMenu("&Help", self)
        self.helpMenu.addAction(self.aboutAct)
        self.helpMenu.addAction(self.aboutQtAct)

        self.menuBar().addMenu(self.fileMenu)
        self.menuBar().addMenu(self.viewMenu)
        self.menuBar().addMenu(self.helpMenu)

    def updateActions(self):
        self.zoomInAct.setEnabled(not self.fitToWindowAct.isChecked())
        self.zoomOutAct.setEnabled(not self.fitToWindowAct.isChecked())
        self.normalSizeAct.setEnabled(not self.fitToWindowAct.isChecked())

    def scaleImage(self, factor):
        self.scaleFactor *= factor

        self.adjustScrollBar(self.scroll_area.horizontalScrollBar(), factor)
        self.adjustScrollBar(self.scroll_area.verticalScrollBar(), factor)

        self.zoomInAct.setEnabled(self.scaleFactor < 3.0)
        self.zoomOutAct.setEnabled(self.scaleFactor > 0.333)

    def adjustScrollBar(self, scrollBar, factor):
        scrollBar.setValue(int(factor * scrollBar.value()
                                 + ((factor - 1) * scrollBar.pageStep()/2)))