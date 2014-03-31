'''
Created on Mar 13, 2014

@author: Gregory Kramida
'''
import ConfigParser
import os
import re


from utils.data import Bunch

default_setting_hash = {"system":
                            {"max_tile_mem":"4096MB",
                             "startup_file_path":"/mnt/sdb2/Data/mbtiles/immunogold-colored/255.mbtiles"
                             },
                        }

byte_sizes = {"B":1,
              "KB":1024,
              "MB":1048576,
              "GB":1073741824,}


CONFIG_FILE_NAME = "gpxanalyzer.cfg"

#TODO: make these recursive instead and define the bunch-to-hash inside the Bunch class
def setting_hash_to_bunch(setting_hash):
    interim = {}
    for key, section_hash in setting_hash.items():
        interim[key] = Bunch(section_hash)
    return Bunch(interim)

def setting_hash_to_parser(setting_hash):
    config = AutoConfigParser()
    for section, section_hash in setting_hash.items():
        config.add_section(section)
        for key, val in section_hash.items():
            config.set(section,key,val)
    return config

def setting_bunch_to_hash(setting_bunch):
    setting_hash = {}
    for key, section_bunch in setting_bunch.__dict__.items():
        setting_hash[key] = section_bunch.__dict__
    return setting_hash

class AutoConfigParser(ConfigParser.ConfigParser):
    
#     def __init__(self,defaults = None, dict_type = None, allow_no_value = None):
#         """
#         Builds an AutoConfigParser
#         """
#         super(AutoConfigParser,self).__init__(defaults, dict_type, allow_no_value)
        
    def _parse_byte_size(self,str_opt):
        designators = re.findall('\d+(\w*)',str_opt, re.IGNORECASE)
        number = int(re.findall('\d+',str_opt)[0])
        if(len(designators) == 0):
            return number
        else:
            designator = designators[0].upper()
            return byte_sizes[designator] * number
        
    def getbytesize(self,section,option):
        str_opt = self.get(section, option)
        return self._parse_byte_size(str_opt)
        
        
    def parse_option(self,section,option):
        str_opt = self.get(section, option)
        if(re.match("^\d+$",str_opt)):
            return int(str_opt)
        elif(re.match("^\d+\.\d*$",str_opt)):
            return float(str_opt)
        elif(re.match("^\d+\s*(?:KB|B|MB|GB)$",str_opt,re.IGNORECASE)):
            return self._parse_byte_size(str_opt)
        else:
            return str_opt
        
    def to_bunch(self):
        """
        converts the config to a namespace / Bunch
        """
        config_hash = {}
        for section in self.sections():
            section_hash = {}
            for option in self.options(section):
                section_hash[option] = self.parse_option(section,option)
            config_hash[section] = section_hash
        return setting_hash_to_bunch(config_hash)
    
def load_config(directory, verbose = False):
    path = directory + os.path.sep + CONFIG_FILE_NAME
    if os.path.isfile(path):
        config = setting_hash_to_parser(default_setting_hash)
        config.read(path)
        if(verbose):
            print "Configuration loaded from file {0:s}".format(path)
        return config.to_bunch()
    else:
        config = setting_hash_to_parser(default_setting_hash)
        conf_file = open(path, "w")
        config.write(conf_file)
        if(verbose):
            print "Written configuration to {0:s}".format(path)
        conf_file.close()
    return config.to_bunch()
        
    