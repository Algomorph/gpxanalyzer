'''
Created on Jul 28, 2013

@author: Gregory Kramida
'''

def enum(**enums):
    '''
    A function for initializing enumerated-constant-like structures
    '''
    return type('Enum', (), enums)