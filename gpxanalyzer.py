'''
Created on Mar 13, 2014

@author: Gregory Kramida
'''

#!/usr/bin/env python
import sys

from gpxanalyzer.gui import GigapixelAnalyzer
from PySide import QtGui
import os
import gpxanalyzer.config as cfg
   

# main entry point
if __name__ == '__main__':
    directory = os.path.dirname(os.path.realpath(__file__))
    config = cfg.load_config(directory, True)
    app = QtGui.QApplication(sys.argv)
    main_window = GigapixelAnalyzer(config)
    sys.exit(app.exec_())
    
    
    
    
    
    
    
