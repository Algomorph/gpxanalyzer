'''
Created on Apr 1, 2014

@author: Gregory Kramida
@copyright: (c) Gregory Kramida 2014
@license: GNU v3
'''
from gpxanalyzer.utils import tiledownloader as tdl
from gpxanalyzer.utils import tilearranger as pyr
from PySide import QtGui, QtCore
from gpxanalyzer.utils.console import OutputWrapper, print_progress
import os
import mbutil


class PyramidBuildingSlave(QtCore.QThread):
    stop_message = "stop"
    '''
    A thread that launches pyramidization process
    '''
    def __init__(self,args, parent = None):
        super(PyramidBuildingSlave,self).__init__(parent)
        self.args = args
        self.stop = False
        
    def stop_pyramid_builder(self,*args):
        print_progress(*args)
        if(self.stop):
            raise RuntimeError(self.stop_message)
        
    def run(self):
        try:
            pyr.pyramidize(*self.args,progress_callback = self.stop_pyramid_builder)
        except RuntimeError as e:
            if(e.message == self.stop_message):
                print "Execution stopped."
            else:
                #rethrow the error
                raise RuntimeError
            
class DbGenerator(QtCore.QThread):
    def __init__(self,args, parent = None):
        super(DbGenerator,self).__init__(parent)
        self.args = args
        self.stop = False
        
    def run(self):
        mbutil.disk_to_mbtiles(*self.args)
     

class ArrangeTilesDialog(QtGui.QDialog):
    def __init__(self,config,parent = None):
        self.config = config
        super(ArrangeTilesDialog, self).__init__(parent)
        self._err_color = QtCore.Qt.red
        self.initialize_components()
        self.load_config()
        self.add_components()
###############CONFIG SAVING FUNCTIONS############################
    def save_image_id(self):
        self.config.tilearranger.image_id = self.image_id_spinbox.value()
    def save_arrange_xyz(self):
        self.config.tilearranger.resize = self.arrange_xyz_check_box.isChecked()
    def save_overflow_mode(self):
        self.config.tilearranger.overflow_mode = self.overflow_mode_dropdown.currentText()
    def save_data_source(self):
        self.config.tilearranger.data_source = self.data_source_dropdown.currentText()
    def save_input_directory(self):
        self.config.tilearranger.input_folder = self.input_dir_line.text()
    def save_output_directory(self):
        self.config.tilearranger.output_folder = self.output_dir_line.text()
    def save_db_filename(self):
        self.config.tilearranger.db_filename = self.db_file_name_line.text()
        
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
        
        #download source stuff
        self.data_source_label = QtGui.QLabel("Original data source: ")
        data_source_dropdown = QtGui.QComboBox(self)
        data_source_dropdown.insertItems(0,tdl.downloaders_by_data_source.keys())
        data_source_dropdown.currentIndexChanged.connect(self.save_data_source)
        self.data_source_dropdown = data_source_dropdown
        self.image_id_label = QtGui.QLabel("Id of the image at the data source: ")
        image_id_spinbox = QtGui.QSpinBox(self)
        image_id_spinbox.setMinimum(0)
        image_id_spinbox.setMaximum(1000000000)
        image_id_spinbox.valueChanged.connect(self.save_image_id)
        self.image_id_spinbox = image_id_spinbox
        
        #arranging style stuff
        self.arrange_xyz_check_box = QtGui.QCheckBox("Arrange the output in z/x/y structure right away")
        self.arrange_xyz_check_box.stateChanged.connect(self.save_arrange_xyz)
        
        #pyramidize button
        self.pyramidize_btn = QtGui.QPushButton("Pyramidize",self)
        self.pyramidize_btn.clicked.connect(self.launch_pyramidization)
        
        self.halt_btn = QtGui.QPushButton("Halt Pyramidization",self)
        self.halt_btn.clicked.connect(self.halt)
        
        #sqlite database stuff
        self.db_file_name_label = QtGui.QLabel("SQLite database file name: ")
        self.db_file_name_line = QtGui.QLineEdit(self)
        self.db_file_name_line.textChanged.connect(self.save_db_filename)
        self.generate_db_btn = QtGui.QPushButton("Generate Database", self)
        self.generate_db_btn.setToolTip("Generate the sqlite mbtiles file.\n This can only be done \
when the output folder contains the entire image pyramid using the z/x/y structure.")
        self.generate_db_btn.clicked.connect(self.generate_db)
        
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
        
    def handle_output(self, text, stdout):
        '''
        Duplicates stdout to the console.
        '''
        #TODO:fix last-line erasing
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
    
    def launch_pyramidization(self):
        args = (self.image_id_spinbox.value(), 
                self.input_dir_line.text(), 
                self.output_dir_line.text(), 
                self.data_source_dropdown.currentText(), 
                self.arrange_xyz_check_box.isChecked())
        aw = PyramidBuildingSlave(args,self)
        aw.start()
        self.worker = aw
        
    def generate_db(self):
        args = (self.output_dir_line.text(),
                self.output_dir_line.text() + os.path.sep + self.db_file_name_line.text(),
                {"format":"png",
                 "scheme":"xyz"}
                )
        dbw = DbGenerator(args,self)
        dbw.start()
        self.db_worker = dbw
        
    
    def browse_input(self):
        '''
        Triggered by Browse.. button under source directory.
        Opens up a FileDialog allowing the user to choose a folder where the input tiles are located. 
        Stores the result in the config as well as shows it in the GUI.
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
        Opens up a FileDialog allowing the user to choose a folder where the output tile pyramid is going
        to be saved. Stores the result in the config as well as shows it in the GUI.
        '''
        dialog = QtGui.QFileDialog(self, caption="Specify Destination...")
        dialog.setFileMode(QtGui.QFileDialog.Directory)
        dialog.setOption(QtGui.QFileDialog.ShowDirsOnly, True)
        dialog.exec_()
        if(len(dialog.selectedFiles()) > 0):
            path = dialog.selectedFiles()[0]
            self.config.tilecombiner.output_folder = path
            self.output_dir_line.setText(path)
    
    def load_config(self):
        config = self.config.tilearranger
        if(os.path.exists(config.output_folder)):
            self.output_dir_line.setText(config.output_folder)
        if(os.path.exists(config.input_folder)):
            self.input_dir_line.setText(config.input_folder)
        self.data_source_dropdown.setCurrentIndex(tdl.downloaders_by_data_source.keys().index(config.data_source))
        self.image_id_spinbox.setValue(config.image_id)
        self.arrange_xyz_check_box.setChecked(config.arrange_xyz)
        self.db_file_name_line.setText(config.db_filename)
    
    def add_components(self):
        main_layout = QtGui.QGridLayout(self)
        #add all to controls_layout in this order
        main_layout.addWidget(self.input_dir_label,0,0)
        main_layout.addWidget(self.input_dir_line,1,0)
        main_layout.addWidget(self.browse_input_btn,2,0)
        
        main_layout.addWidget(self.output_dir_label,3,0)
        main_layout.addWidget(self.output_dir_line, 4, 0)
        main_layout.addWidget(self.browse_output_btn, 5, 0)
        
        main_layout.addWidget(self.data_source_label, 6, 0)
        main_layout.addWidget(self.data_source_dropdown, 7, 0)
        main_layout.addWidget(self.image_id_label, 8, 0)
        main_layout.addWidget(self.image_id_spinbox, 9, 0)
        
        main_layout.addWidget(self.arrange_xyz_check_box, 10, 0)
        
        main_layout.addWidget(self.pyramidize_btn, 11, 0)
        main_layout.addWidget(self.halt_btn,12,0)
        main_layout.addWidget(self.db_file_name_label,13,0)
        main_layout.addWidget(self.db_file_name_line,14,0)
        main_layout.addWidget(self.generate_db_btn,15,0)
        
        main_layout.addWidget(self.console_label,0,1,1,3)
        main_layout.addWidget(self.console,1,1,15,3)
        main_layout.setColumnStretch(0,1)
        main_layout.setColumnStretch(1,5)
        self.setLayout(main_layout)