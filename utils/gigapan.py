#!/usr/bin/env python

#usage: python downloadGigaPan.py <photoid>
# http://gigapan.org/gigapans/<photoid>>


from xml.dom.minidom import *
from urllib2 import *
from urllib import *
import sys,os,math

base_gigapan_url = "http://www.gigapan.org"

def getText(nodelist):
    rc = ""
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc = rc + node.data
    return rc

def find_element_value(e,name):
    nodelist = [e]
    while len(nodelist) > 0 :
        node = nodelist.pop()
        if node.nodeType == node.ELEMENT_NODE and node.localName == name:
            return getText(node.childNodes)
        else:
            nodelist += node.childNodes

    return None


def set_up_sizes(dom):
    height=int(find_element_value(dom.documentElement, "maxHeight"))
    width=int(find_element_value(dom.documentElement, "maxWidth"))
    tile_size=int(find_element_value(dom.documentElement, "tileSize"))
    return height, width, tile_size

def set_up_retrieval(photo_id, verbose = False):
    base_gigapan_url = "http://www.gigapan.org"
    
    # read the kml file
    h = urlopen(base_gigapan_url+"/gigapans/%d.kml"%(photo_id))
    photo_kml=h.read()
    
    # find the width and height, level 
    dom = parseString(photo_kml)
    
    height, width, tile_size = set_up_sizes(dom)
    if(verbose):
        print "Gigapan image characteristics\nwidth: %d\nheight: %d\ntile size: %d" %(width,height,tile_size)
    maxlevel = max(math.ceil(width/tile_size), math.ceil(height/tile_size))
    maxlevel = int(math.ceil(math.log(maxlevel)/math.log(2.0)))
    wt = int(math.ceil(width/tile_size))+1
    ht = int(math.ceil(height/tile_size))+1
    if (verbose):
        print "Tile dimensions: %d x %d" %(wt,ht)
        print "Maximum zoom level: %d" % maxlevel 
    return wt, ht, maxlevel

def fetch_tile(output_folder, photo_id, maxlevel, x, y, verbose = False):
    filename = "%04d-%04d.jpg"%(x,y)
    url = "%s/get_ge_tile/%d/%d/%d/%d"%(base_gigapan_url,photo_id, maxlevel,y,x)
    print "Fetching tile %s from %s" % (filename,url)
    h = urlopen(url)
    fout = open(output_folder+os.path.sep+filename,"wb")
    fout.write(h.read())
    fout.close()

#main
if __name__ == '__main__':
    photo_id = int(sys.argv[1])
    
    #create output folder if such doesn't exist
    if not os.path.exists(str(photo_id)):
        os.makedirs(str(photo_id))

    wt, ht, maxlevel = set_up_retrieval(photo_id, verbose = True)
    #loop around to get every tile
    for y in xrange(ht):
        for x in xrange(wt):
            fetch_tile(str(photo_id),photo_id,maxlevel,x,y,verbose=True)
