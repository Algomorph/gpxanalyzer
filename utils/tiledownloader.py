'''
Created on Mar 7, 2014

@author: algomorph
'''

from gevent import monkey; monkey.patch_all()
import gevent
from data import Bunch
import abc
from xml.dom.minidom import parseString
import sys
import math
import os
import urllib2
import json
import psutil

import time
import cv2
import console
#import argparse



class TileDownloader:
    '''
    Abstract tile downloader
    '''
    __metaclass__ = abc.ABCMeta
    
    @abc.abstractmethod
    def retrieve_image_settings(self, image_id, verbose = False):
        pass
    @abc.abstractmethod
    def download_tiles(self,image_id, output_folder,tile_range=None, settings = None, verbose = False):
        pass
    @abc.abstractmethod
    def download_tile(self,settings, image_id, x, y, output_folder,verbose = False):
        pass
    def set_up_range_and_settings(self, settings, tile_range, image_id, verbose = False):
        if(settings is None):
            settings = self.retrieve_image_settings(image_id, verbose)
        if(tile_range is None):
            tile_range = [0,settings.n_cells_x,0,settings.n_cells_y]
        return settings, tile_range

class GigapanTileDownloader(TileDownloader):
    base_url = "http://www.gigapan.org"

    def getText(self,nodelist):
        rc = ""
        for node in nodelist:
            if node.nodeType == node.TEXT_NODE:
                rc = rc + node.data
        return rc
    
    def find_element_value(self,e,name):
        nodelist = [e]
        while len(nodelist) > 0 :
            node = nodelist.pop()
            if node.nodeType == node.ELEMENT_NODE and node.localName == name:
                return self.getText(node.childNodes)
            else:
                nodelist += node.childNodes
    
        return None
    
    def set_up_sizes(self,dom):
        height=int(self.find_element_value(dom.documentElement, "maxHeight"))
        width=int(self.find_element_value(dom.documentElement, "maxWidth"))
        tile_size=int(self.find_element_value(dom.documentElement, "tileSize"))
        return height, width, tile_size
    
    def retrieve_image_settings(self, image_id, verbose = False):
        # read the kml file
        h = urllib2.urlopen(GigapanTileDownloader.base_url+"/gigapans/%d.kml"%(image_id))
        photo_kml=h.read()
        
        # find the width and height, level 
        dom = parseString(photo_kml)
        
        height, width, tile_size = self.set_up_sizes(dom)
        if(verbose):
            print "Gigapan image characteristics\nwidth: %d\nheight: %d\ntile size: %d" %(width,height,tile_size)
        maxlevel = max(math.ceil(width/tile_size), math.ceil(height/tile_size))
        maxlevel = int(math.ceil(math.log(maxlevel)/math.log(2.0)))
        n_cells_x = int(math.ceil(width/tile_size))+1
        n_cells_y = int(math.ceil(height/tile_size))+1
        if (verbose):
            print "Tile dimensions: %d x %d" %(n_cells_x,n_cells_y)
            print "Maximum zoom level: %d" % maxlevel 
        return Bunch({"n_cells_x":n_cells_x, "n_cells_y":n_cells_y, "maxlevel":maxlevel})
    
    def download_tile(self, settings, image_id, x, y, output_folder,verbose = False):
        filename = "%04d-%04d.jpg"%(x,y)
        url = "%s/get_ge_tile/%d/%d/%d/%d"%(GigapanTileDownloader.base_url,image_id, settings.maxlevel,y,x)
        if(verbose):
            print "Fetching tile %s from %s" % (filename,url)
        h = urllib2.urlopen(url)
        fout = open(output_folder+os.path.sep+filename,"wb")
        fout.write(h.read())
        fout.close()
        
    def download_tiles(self,image_id, output_folder,tile_range=None, settings = None, verbose = False):
        settings, tile_range = self.set_up_range_and_settings(settings, tile_range, image_id, verbose)
        for y in xrange(tile_range[2],tile_range[3]):
            for x in xrange(tile_range[0],tile_range[1]):
                self.download_tile(settings, image_id, x, y, output_folder,verbose)
#=========END CLASS GigapanTileDownloader====================================


class JCBTileDownloader(TileDownloader):
    base_url = "http://v.jcb-dataviewer.glencoesoftware.com/webclient/"
    color_strings = {True:"1|0:255$FF0000,2|0:255$00FF00,3|0:255$0000FF&m=c",
                     False:"1|0:255$FF0000&m=g"}
    
    def __init__(self,verify_files_on_disk = False):
        self.verify = verify_files_on_disk
    
    def retrieve_image_settings(self, image_id, verbose = False):  
        # read the kml file
        h = urllib2.urlopen(JCBTileDownloader.base_url+"imgData/%d"%(image_id))
        image_meta_str=h.read()
        
        # find the width and height, level 
        image_info = json.loads(image_meta_str)
        height = image_info["size"]["height"]
        width = image_info["size"]["width"]
        tile_width = image_info["tile_size"]["width"]
        tile_height = image_info["tile_size"]["height"]
        color = image_info["rdefs"]["model"] == "color"
        if(verbose):
            print ("JSB Dataviewer image characteristics\nwidth: %d\nheight: %d\ntile size: %s\nmode: %s"
            % (width,height,str((tile_width, tile_height)), image_info["rdefs"]["model"]))
        n_cells_x = width/tile_width
        n_cells_y = height/tile_height
        zoom = 100 #default zoom: max
        if (verbose):
            print "Tile dimensions: %d x %d" %(n_cells_x,n_cells_y)
        return Bunch({"n_cells_x":n_cells_x, 
                      "n_cells_y":n_cells_y, 
                      "tile_width":tile_width, 
                      "tile_height":tile_width, 
                      "color":color,
                      "zoom":100}) 
    
    def download_tile(self, settings, image_id, x, y, output_folder, verbose = False):
        success = False
        col_str = JCBTileDownloader.color_strings[settings.color]
        while(not success):
            try:
                filename = "%04d-%04d.jpg"%(x,y)
                url = ("%srender_image_region/%d/0/0/?c=%s&p=normal&ia=0&q=0.9&zm=%d&x=0&y=0&tile=0,%d,%d,%d,%d"
                       %(JCBTileDownloader.base_url,
                         image_id,col_str, 
                         settings.zoom, x,y, 
                         settings.tile_width, 
                         settings.tile_height))
                if(verbose):
                    print "Fetching tile %s from %s" % (filename,url)
                h = urllib2.urlopen(url)
                fout = open(output_folder+os.path.sep+filename,"wb")
                fout.write(h.read())
                fout.close()
                success = True
            except Exception:
                print "\nConnection Error, retrying batch"
                continue
        
    def print_progress(self,i_tile, n_tiles, elapsed):
        n_done = i_tile+1
        frac_done = float(n_done) / n_tiles
        total_time = elapsed / frac_done
        eta = total_time - elapsed
        hour_eta = int(eta) / 3600
        min_eta = int(eta-hour_eta*3600) / 60
        sec_eta = int(eta-hour_eta*3600-min_eta*60)
        print '{0:.3%} done ({5:0} of {6:0} tiles), elapsed: {4:0} eta: {1:0} h {2:0} m {3:0} s'.format(frac_done,hour_eta,min_eta,sec_eta, int(elapsed), i_tile, n_tiles),
        sys.stdout.flush()
        print "\r",
    
    def __gen_file_path(self,x,y,folder):
        filename = "%04d-%04d.jpg"%(x,y)
        return folder+os.path.sep+filename
    
    #TODO: check methods should be generic for all TileDownloaders - include in abastract base class
    def check_what_is_done(self, width, start_y, end_y, output_folder):
        print "Checking progress..."
        #check what's ready
        check_next_row = True
        x = 0; y = start_y
        for y in xrange(start_y,end_y):
            for x in xrange(width):
                path = self.__gen_file_path(x,y,output_folder)
                if(not os.path.isfile(path)):
                    check_next_row = False
                    break
            if(not check_next_row):
                break
        return x, y
    
    def check_what_is_done_and_verify(self, width, start_y, end_y, output_folder):
        '''
        Checks the progress up to this point (in terms of which files exist)
        For every file that exists, checks whether it can be loaded as an image by opencv.
        If not, then adds that to the bad_tiles list.
        @return: x, y, bad_tiles - where x and y are coorinates of the last tile it found, and bad_tiles
        are existing tiles which couldn't be opened 
        '''
        print "Verifying downloaded tiles..."
        check_next_row = True
        x = 0; y = start_y
        bad_tiles = []
        for y in xrange(start_y,end_y):
            for x in xrange(width):
                path = self.gen_file_path(x,y,output_folder)
                if(not os.path.isfile(path)):
                    check_next_row = False
                    break
                else:
                    img = cv2.imread(path)
                    if img is None:
                        print "Failed to open image %s. Adding to re-download list." % path
                        bad_tiles.append((x,y))
            if(not check_next_row):
                break
        return x, y, bad_tiles
    
    def handle_jobs(self,jobs):
        gevent.joinall(jobs,timeout=20)
        success = True
        for job in jobs:
            if not job.ready():
                success = False
                job.kill()
        return success
    
    def run_batch(self, settings, image_id, xs, y, output_folder, verbose = False):
        '''
        Run a single batch of tile downloads
        @type xs: list of int 
        @param xs: xs are the x coordinates for each tile in the batch
        @type y: int
        @param y: The y coordinate for every tile in the batch
        @type output_folder: str
        @param output_folder: path where to save the tiles
        @type image_id: int
        @param image_id: numeric id of the image
        '''
        success = False
        while(not success):
            jobs = [gevent.spawn(self.download_tile, self, 
                                 settings, image_id, x, y, output_folder,
                                 verbose= False) for x in xs]
            success = self.handle_jobs(jobs)
            if not success: 
                print "\nTimeout, retrying batch"
        return True
    
    def download_tiles(self,image_id, output_folder,tile_range=None, settings = None, verbose = False):
        settings, tile_range = self.set_up_range_and_settings(settings, tile_range, image_id, verbose)
        verify = self.verify
        
        start_y=tile_range[2]
        end_y=tile_range[3]
        
        #TODO: add support for x ranges
        if(tile_range[0] != 0 or tile_range[1] != 0):
            print "Warning: x range is not yet supported by the JCBTileDownloader"
        
        if(output_folder is None):
            output_folder = str(image_id)
        
        #create output folder if such doesn't exist
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            
        wt = settings.n_cells_x
        ht = settings.n_cells_y
        
        #exclusive bound
        end_y +=1
        end_y = min(ht, end_y)
        
        redownload = False
        bad_tiles = []
        
        if not verify:
            start_x, start_y = self.check_what_is_done(wt, start_y, end_y, output_folder)
        else:
            start_x, start_y, bad_tiles = self.check_what_is_done_and_verify(wt, start_y, end_y, output_folder)    
            if(len(bad_tiles) > 0):
                redownload = console.query_yes_no("Found %d bad tiles. Re-download now (y/n)?" % len(bad_tiles))
            else:
                if(verbose):
                    print "Tiles verified and no bad tiles found."
        
        if redownload:
            for (x,y) in bad_tiles:
                self.download_tile(self, settings, image_id, x, y, output_folder, verbose = False)
            if(verbose):
                print "Bad tiles re-downloaded."
                
            
        
        batch_size = psutil.NUM_CPUS*2
        do_extra_batch = False
        
        n_batches = wt / batch_size
        
        if(wt % batch_size != 0):
            do_extra_batch = True
            remainder_start = wt - (wt % batch_size)
            
        #scroll back a bit to ensure proper bounds and re-load the entire last batch * 2
        start_x = max(start_x - (start_x % batch_size) - batch_size*2,0)
        start_batch = start_x / batch_size
        
        
        n_tiles = wt*end_y - (start_y * wt + start_x)
        i_tile = 0
        start = time.time()
        if(verbose):
            print "Starting from tile %04d-%04d.jpg" % (start_x, start_y)
            print "Ending on tile %04d-%04d.jpg" % (wt-1, end_y-1)
        #loop to get the first row
        y = start_y
        
        run_batch_local = lambda xs, y: self.run_batch(settings, image_id, xs, y, output_folder, verbose)
        for x_range in xrange(start_batch,n_batches):
            xs = range(x_range*batch_size, (x_range+1)*batch_size)
            run_batch_local(xs, y)
            i_tile += batch_size
            self.print_progress(i_tile, n_tiles, time.time() - start)
        if do_extra_batch is True:
            xs = range(remainder_start,wt)
            run_batch_local(xs, y)
            i_tile += len(xs)
            self.print_progress(i_tile, n_tiles, time.time() - start)
        #loop around to get every tile
        for y in xrange(start_y+1,end_y):
            for x_range in xrange(0,n_batches):
                xs = range(x_range*batch_size, (x_range+1)*batch_size)
                run_batch_local(xs, y)
                i_tile += batch_size
                self.print_progress(i_tile, n_tiles, time.time() - start)
            if do_extra_batch is True:
                xs = range(remainder_start,wt)
                run_batch_local(xs, y)
                i_tile += len(xs)
                self.print_progress(i_tile, n_tiles, time.time() - start)
        if(verbose):
            print "\nDone."
