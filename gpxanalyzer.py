#!/usr/bin/env python
'''
Created on Mar 13, 2014

@author: Gregory Kramida
'''


from PySide import QtGui
import os
import sys

import gpxanalyzer.config as cfg
from gpxanalyzer.gui import GigapixelAnalyzer


# main entry point
if __name__ == '__main__':
    directory = os.path.dirname(os.path.realpath(__file__))
    config = cfg.load_config(directory, True)
    app = QtGui.QApplication(sys.argv)
    main_window = GigapixelAnalyzer(config)
    sys.exit(app.exec_())
    
    
    
    
    
    
    
