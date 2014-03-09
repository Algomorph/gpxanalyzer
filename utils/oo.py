'''
Created on Mar 9, 2014

@author: Gregory Kramida
'''
def overrides(interface_class):
    def overrider(method):
        assert(method.__name__ in dir(interface_class))
        return method
    return overrider