'''
Created on Mar 31, 2014

@author: Gregory Kramida
@copyright: (c) Gregory Kramida 2014
@license: GNU v3
'''

import gpxanalyzer.utils.tilecombiner as tc
from PySide import QtCore,QtGui
from gpxanalyzer.utils.console import OutputWrapper
import os

from gpxanalyzer.utils import tilecombiner

class ComboWorker(QtCore.QThread):
    stop_message = "stop"
    
    def __init__(self,args, parent = None):
        super(ComboWorker,self).__init__(parent)
        self.args = args
        self.stop = False
        
    def stop_pyramid_builder(self,*args):
        tilecombiner.print_progress(*args)
        if(self.stop):
            raise RuntimeError(self.stop_message)
        
    def run(self):
        try:
            tilecombiner.combine_tiles(*self.args,progress_callback = self.stop_pyramid_builder)
        except RuntimeError as e:
            if(e.message == self.stop_message):
                print "Execution stopped."
            else:
                #rethrow the error
                raise RuntimeError    
            
class Pow2SpinBox(QtGui.QSpinBox):
    def __init__(self,parent = None):
        allowed_values = [2,4,8,16,32,64,128,256,512,1024,2048,4096,8192,16384,32768,65536,131072,262144,524288,1048576]
        super(Pow2SpinBox,self).__init__(parent)
        self.setRange(allowed_values[0],allowed_values[len(allowed_values)-1])
        self.allowed_vals = allowed_values
        
    def stepBy(self,steps):
        cur = self.value()
        if(cur not in self.allowed_vals):
            for ix_cur in xrange(0,len(self.allowed_vals)):
                closest = self.allowed_vals[ix_cur]
                if(cur < closest):
                    if(ix_cur > 0 and cur - self.allowed_vals[ix_cur-1] < closest - cur):
                        closest = self.allowed_vals[ix_cur-1]
                    break
            cur = closest
        idx = self.allowed_vals.index(cur)
        idx += steps;
        if idx >= len(self.allowed_vals): idx = len(self.allowed_vals) - 1
        elif idx < 0: idx = 0
        self.setValue(self.allowed_vals[idx])

class CombineTilesDialog(QtGui.QDialog):
    stop_requested = QtCore.Signal()
    def __init__(self, cl_manager, parent = None):
        self.manager = cl_manager
        super(CombineTilesDialog, self).__init__(parent)
        self._err_color = QtCore.Qt.red
        self.initialize_components()
        self.load_config()
        self.add_components()
        
    def load_config(self):
        config = self.manager.tilecombiner
        if(os.path.exists(config.output_folder)):
            self.output_dir_line.setText(config.output_folder)
        if(os.path.exists(config.input_folder)):
            self.input_dir_line.setText(config.input_folder)
        self.comb_size_spinbox.setValue(config.size)
        self.resize_check_box.setChecked(config.resize)
        self.resize_size_spinbox.setValue(config.resize_size)
        self.data_source_dropdown.setCurrentIndex(tc.tiledownloader.downloaders_by_data_source.keys().index(config.data_source))
        self.overflow_mode_dropdown.setCurrentIndex(tc.overflow_modes.index(config.overflow_mode))
        self.image_id_spinbox.setValue(config.image_id)
        self.verify_check_box.setChecked(config.verify)
        
###############CONFIG SAVING FUNCTIONS############################
    def save_image_id(self):
        self.manager.tilecombiner.image_id = self.image_id_spinbox.value()
    def save_resize(self):
        self.manager.tilecombiner.resize = self.resize_check_box.isChecked()
    def save_verify(self):
        self.manager.tilecombiner.resize = self.verify_check_box.isChecked()
    def save_overflow_mode(self):
        self.manager.tilecombiner.overflow_mode = self.overflow_mode_dropdown.currentText()
    def save_data_source(self):
        self.manager.tilecombiner.data_source = self.data_source_dropdown.currentText()
    def save_size(self):
        self.manager.tilecombiner.size = self.comb_size_spinbox.value()
    def save_resize_size(self):
        self.manager.tilecombiner.resize_size = self.resize_size_spinbox.value()
    def save_input_directory(self):
        self.manager.tilecombiner.input_folder = self.input_dir_line.text()
    def save_output_directory(self):
        self.manager.tilecombiner.output_folder = self.output_dir_line.text()
        
##################################################################
    def initialize_components(self):
        
        
        #input & output directory stuff
        self.input_dir_label = QtGui.QLabel("Input Directory:",self)
        input_dir_line = QtGui.QLineEdit(self)
        input_dir_line.textChanged.connect(self.save_input_directory)
        self.input_dir_line = input_dir_line
       
        browse_input_btn = QtGui.QPushButton("Browse..",self)
        browse_input_btn.setToolTip("Browse for the source directory.")
        browse_input_btn.clicked.connect(self.browse_input)
        self.browse_input_btn = browse_input_btn
        
        self.output_dir_label = QtGui.QLabel("Output Directory:",self)
        output_dir_line = QtGui.QLineEdit()
        output_dir_line.textChanged.connect(self.save_output_directory)
        self.output_dir_line = output_dir_line
        
        browse_output_btn = QtGui.QPushButton("Browse..",self)
        browse_output_btn.setToolTip("Browse for the destination directory.")
        browse_output_btn.clicked.connect(self.browse_output)
        self.browse_output_btn = browse_output_btn
        
        #combine size
        self.comb_size_label = QtGui.QLabel("Combined tile size (before resizing): ")
        comb_size_spinbox = Pow2SpinBox(self)
        comb_size_spinbox.valueChanged.connect(self.save_size)
        self.comb_size_spinbox = comb_size_spinbox
        
        #resize stuff & crop
        resize_check_box = QtGui.QCheckBox("Resize combined tiles")
        resize_check_box.setChecked(False)
        resize_check_box.stateChanged.connect(self.configure_resize)
        self.resize_check_box = resize_check_box
        self.resize_size_label = QtGui.QLabel("Resize to: ")
        resize_size_spinbox = Pow2SpinBox(self)
        resize_size_spinbox.setEnabled(False)
        resize_size_spinbox.valueChanged.connect(self.save_resize_size)
        self.resize_size_spinbox = resize_size_spinbox
        self.overflow_mode_label = QtGui.QLabel("Overflow mode: ")
        self.overflow_mode_label.setToolTip("How to deal with tiles at the bottom row and right column that cannot be fully filled.")
        overflow_mode_dropdown = QtGui.QComboBox(self)
        overflow_mode_dropdown.insertItems(0,tc.overflow_modes)
        overflow_mode_dropdown.currentIndexChanged.connect(self.save_overflow_mode)
        self.overflow_mode_dropdown = overflow_mode_dropdown
        
        #download source stuff
        self.data_source_label = QtGui.QLabel("Original data source: ")
        data_source_dropdown = QtGui.QComboBox(self)
        data_source_dropdown.insertItems(0,tc.tiledownloader.downloaders_by_data_source.keys())
        data_source_dropdown.currentIndexChanged.connect(self.save_data_source)
        self.data_source_dropdown = data_source_dropdown
        self.image_id_label = QtGui.QLabel("Id of the image at the data source: ")
        image_id_spinbox = QtGui.QSpinBox(self)
        image_id_spinbox.setMinimum(0)
        image_id_spinbox.setMaximum(1000000000)
        image_id_spinbox.valueChanged.connect(self.save_image_id)
        self.image_id_spinbox = image_id_spinbox
        
        #verification stuff
        self.verify_check_box = QtGui.QCheckBox("Verify combined tiles")
        self.verify_check_box.stateChanged.connect(self.save_verify)
        
        #combine button
        self.combine_btn = QtGui.QPushButton("Combine",self)
        self.combine_btn.clicked.connect(self.combine)
        
        self.halt_btn = QtGui.QPushButton("Halt",self)
        self.halt_btn.clicked.connect(self.halt)
        
        #console stuff
        self.console_label = QtGui.QLabel("Console:",self)
        console = QtGui.QTextBrowser(self)
        console.setMinimumWidth(500)
        console.setReadOnly(True)
        console.setBackgroundRole(QtGui.QPalette.Dark)
        console.setSizePolicy(QtGui.QSizePolicy.Ignored,QtGui.QSizePolicy.Ignored)
        console.setOverwriteMode(True)
        self.console = console

        #set up output wrapping
        stdout = OutputWrapper(self, True, False)
        stdout.outputWritten.connect(self.handle_output)
        stderr = OutputWrapper(self, False, False)
        stderr.outputWritten.connect(self.handle_output)
        
    def add_components(self):
        main_layout = QtGui.QGridLayout(self)
        #add all to controls_layout in this order
        main_layout.addWidget(self.input_dir_label,0,0)
        main_layout.addWidget(self.input_dir_line,1,0)
        main_layout.addWidget(self.browse_input_btn,2,0)
        
        main_layout.addWidget(self.output_dir_label,3,0)
        main_layout.addWidget(self.output_dir_line, 4, 0)
        main_layout.addWidget(self.browse_output_btn, 5, 0)
        
        main_layout.addWidget(self.comb_size_label, 6, 0)
        main_layout.addWidget(self.comb_size_spinbox, 7, 0)
        
        main_layout.addWidget(self.resize_check_box, 8, 0)
        main_layout.addWidget(self.resize_size_label, 9, 0)
        main_layout.addWidget(self.resize_size_spinbox, 10, 0)
        main_layout.addWidget(self.overflow_mode_label, 11, 0)
        main_layout.addWidget(self.overflow_mode_dropdown, 12, 0)
        
        main_layout.addWidget(self.data_source_label, 13, 0)
        main_layout.addWidget(self.data_source_dropdown, 14, 0)
        main_layout.addWidget(self.image_id_label, 15, 0)
        main_layout.addWidget(self.image_id_spinbox, 16, 0)
        
        main_layout.addWidget(self.verify_check_box, 17, 0)
        
        main_layout.addWidget(self.combine_btn, 18, 0)
        main_layout.addWidget(self.halt_btn, 19, 0)
        
        main_layout.addWidget(self.console_label,0,1,1,3)
        main_layout.addWidget(self.console,1,1,18,3)
        main_layout.setColumnStretch(0,1)
        main_layout.setColumnStretch(1,5)
        self.setLayout(main_layout)
        
    
    def sizeHint(self):
        return QtCore.QSize(1024,768)
        
    def handle_output(self, text, stdout):
        '''
        Duplicates stdout to the console.
        '''
        #TODO:fix last-line erasing
        #TODO: fix output handling so that two different tools with consoles can run at the same time
        color = self.console.textColor()
       
        self.console.setTextColor(color if stdout else self._err_color)
        self.console.moveCursor(QtGui.QTextCursor.End)
        self.console.insertPlainText(text)
        self.console.setTextColor(color)
        if(self.console.document().lineCount() > 300):
            self.console.moveCursor(QtGui.QTextCursor.Start,QtGui.QTextCursor.MoveAnchor),
            self.console.moveCursor(QtGui.QTextCursor.EndOfLine,QtGui.QTextCursor.MoveAnchor)
            self.console.moveCursor(QtGui.QTextCursor.Start,QtGui.QTextCursor.KeepAnchor)
            self.console.textCursor().removeSelectedText()
            self.console.moveCursor(QtGui.QTextCursor.End)
        
        
    
    def halt(self):
        if(self.worker):
            self.worker.stop = True
        
    def combine(self):
        '''
        Main tilecombiner routine. Reads off the settings and tries to combine the tiles,
        outputing progress and other stuff things to the console.
        '''
        if self.resize_check_box.isChecked():
            resize_to = self.resize_size_spinbox.value()
        else:
            resize_to = None
        downloader = tc.tiledownloader.downloaders_by_data_source[self.data_source_dropdown.currentText()]
        args = (self.input_dir_line.text(), 
                self.output_dir_line.text(), 
                self.comb_size_spinbox.value(), 
                resize_to, 
                self.image_id_spinbox.value(), 
                downloader, 
                self.verify_check_box.isChecked(), 
                self.overflow_mode_dropdown.currentText())
        cw = ComboWorker(args,self)
        cw.start()
        self.worker = cw
            
    def configure_resize(self):
        '''
        Enables/disables the resize spinbox based on whether the checkbox above it is marked.
        '''
        self.save_resize()
        if(self.resize_check_box.isChecked()):
            self.resize_size_spinbox.setEnabled(True)
        else:
            self.resize_size_spinbox.setEnabled(False)
    
    def browse_input(self):
        '''
        Triggered by Browse.. button under source directory.
        Opens up a FileDialog allowing the user to choose a folder where the input tiles are located. 
        Stores the result in the manager as well as shows it in the GUI.
        '''
        dialog = QtGui.QFileDialog(self, caption="Specify Source...")
        dialog.setFileMode(QtGui.QFileDialog.Directory)
        dialog.setOption(QtGui.QFileDialog.ShowDirsOnly, True)
        dialog.exec_();
        if(len(dialog.selectedFiles()) > 0):
            path = dialog.selectedFiles()[0]
            self.input_dir_line.setText(path)
    
    def browse_output(self):
        '''
        Triggered by Browse.. button under destination directory.
        Opens up a FileDialog allowing the user to choose a folder where the output tiles are going
        to be saved. Stores the result in the manager as well as shows it in the GUI.
        '''
        dialog = QtGui.QFileDialog(self, caption="Specify Destination...")
        dialog.setFileMode(QtGui.QFileDialog.Directory)
        dialog.setOption(QtGui.QFileDialog.ShowDirsOnly, True)
        dialog.exec_()
        if(len(dialog.selectedFiles()) > 0):
            path = dialog.selectedFiles()[0]
            self.manager.tilecombiner.output_folder = path
            self.output_dir_line.setText(path)