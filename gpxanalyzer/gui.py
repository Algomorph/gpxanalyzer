from PySide import QtGui

class GigapixelAnalyzer(QtGui.QMainWindow):
    def __init__(self,config):
        super(GigapixelAnalyzer, self).__init__()
        self.config = config
        self.initUI()
        
    def initUI(self):        
        
        self.statusBar().showMessage('Ready')
        self.setGeometry(300, 300, 1024, 768)
        self.setWindowTitle('Gigapixel Analyzer')
        self.showMaximized()