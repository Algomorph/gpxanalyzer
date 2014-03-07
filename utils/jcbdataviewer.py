#!/usr/bin/env python

#usage: python downloadGigaPan.py <photoid>
# http://gigapan.org/gigapans/<photoid>>


import urllib2
import json
import sys,os
import psutil
import gevent
from gevent import monkey
import time
import argparse
import cv2
import console
monkey.patch_all()

base_jcb_url = "http://v.jcb-dataviewer.glencoesoftware.com/webclient/"

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

def set_up_retrieval(image_id, verbose = False):  
    # read the kml file
    h = urllib2.urlopen(base_jcb_url+"imgData/%d"%(image_id))
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
    wt = width/tile_width
    ht = height/tile_height
    if (verbose):
        print "Tile dimensions: %d x %d" %(wt,ht)
    return wt, ht, tile_width, tile_height, color

color_strings = {True:"1|0:255$FF0000,2|0:255$00FF00,3|0:255$0000FF&m=c",
                 False:"1|0:255$FF0000&m=g"}

def fetch_tile(output_folder, image_id, zoom, x, y, tile_width, tile_height, color = False, verbose = False):
    success = False
    col_str = color_strings[color]
    while(not success):
        try:
            filename = "%04d-%04d.jpg"%(x,y)
            url = "%srender_image_region/%d/0/0/?c=%s&p=normal&ia=0&q=0.9&zm=%d&x=0&y=0&tile=0,%d,%d,%d,%d"%(base_jcb_url,image_id,col_str, zoom,x,y, tile_width, tile_height)
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

def save_file(output_folder,data,x,y):
    filename = "%04d-%04d.jpg"%(x,y)
    fout = open(output_folder+os.path.sep+filename,"wb")
    fout.write(data)
    fout.close()
    
def print_progress(i_tile, n_tiles, elapsed):
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

def gen_file_path(x,y,folder):
    filename = "%04d-%04d.jpg"%(x,y)
    return folder+os.path.sep+filename

def check_what_is_done(width, start_y, end_y, output_folder):
    print "Checking progress..."
    #check what's ready
    check_next_row = True
    x = 0; y = start_y
    for y in xrange(start_y,end_y):
        for x in xrange(width):
            path = gen_file_path(x,y,output_folder)
            if(not os.path.isfile(path)):
                check_next_row = False
                break
        if(not check_next_row):
            break
    return x, y

def check_what_is_done_and_verify(width, start_y, end_y, output_folder):
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
            path = gen_file_path(x,y,output_folder)
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

def handle_jobs(jobs):
    gevent.joinall(jobs,timeout=20)
    success = True
    for job in jobs:
        if not job.ready():
            success = False
            job.kill()
    return success

def run_batch(xs,y,output_folder, image_id, scale, tile_width, tile_height, color, verbose):
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
        jobs = [gevent.spawn(fetch_tile, output_folder, image_id, scale, x, y, tile_width, tile_height, color, verbose) for x in xs]
        success = handle_jobs(jobs)
        if not success: 
            print "\nTimeout, retrying batch"
    return True

parser = argparse.ArgumentParser(description="A tool that retrieves color/greyscale 256x256 from the jcb (Journal of Cell Biology) website.")
parser.add_argument("--output_folder", "-o", default=None,
                    help="path to folder for the downloaded tiles")
parser.add_argument("--image_id", "-id", type=int, default=201,
                    help="id of the image to retrieve")
parser.add_argument("--start_row", "-s", type=int, default=-1,
                    help="tile row to start with")
parser.add_argument("--end_row", "-e", type=int, default=-1,
                    help="tile row to end with")
parser.add_argument("--verify", "-V", action="store_true", default=False, 
                    help="verify the already-loaded tiles by opening them")

#main
if __name__ == '__main__':
    args = parser.parse_args(sys.argv[1:])
    image_id = args.image_id
    verify = args.verify
    
    if args.start_row < 0:
        start_y=0
    else:
        start_y = args.start_row
    
    if args.end_row < 0:
        end_y=sys.maxint
    else:
        end_y=args.end_row
    if(args.output_folder is None):
        output_folder = str(image_id)
    else:
        output_folder = args.output_folder
    #create output folder if such doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    wt, ht, tile_width, tile_height, color = set_up_retrieval(image_id, verbose = True)
    
    
    #exclusive bound
    end_y +=1
    end_y = min(ht, end_y)
    
    redownload = False
    bad_tiles = []
    
    if not verify:
        start_x, start_y = check_what_is_done(wt, start_y, end_y, output_folder)
    else:
        start_x, start_y, bad_tiles = check_what_is_done_and_verify(wt, start_y, end_y, output_folder)    
        if(len(bad_tiles) > 0):
            redownload = console.query_yes_no("Found %d bad tiles. Re-download now (y/n)?" % len(bad_tiles))
        else:
            print "Tiles verified and no bad tiles found."
    
    if redownload:
        for (x,y) in bad_tiles:
            fetch_tile(output_folder, image_id, 100, x, y, tile_width, tile_height, color, False)
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
    print "Starting from tile %04d-%04d.jpg" % (start_x, start_y)
    print "Ending on tile %04d-%04d.jpg" % (wt-1, end_y-1)
    #loop to get the first row
    y = start_y
    
    run_batch_local = lambda xs, y: run_batch(xs, y, output_folder, image_id, 100, 
                                              tile_width, tile_height, color, False)
    for x_range in xrange(start_batch,n_batches):
        xs = range(x_range*batch_size, (x_range+1)*batch_size)
        run_batch_local(xs, y)
        i_tile += batch_size
        print_progress(i_tile, n_tiles, time.time() - start)
    if do_extra_batch is True:
        xs = range(remainder_start,wt)
        run_batch_local(xs, y)
        i_tile += len(xs)
        print_progress(i_tile, n_tiles, time.time() - start)
    #loop around to get every tile
    for y in xrange(start_y+1,end_y):
        for x_range in xrange(0,n_batches):
            xs = range(x_range*batch_size, (x_range+1)*batch_size)
            run_batch_local(xs, y)
            i_tile += batch_size
            print_progress(i_tile, n_tiles, time.time() - start)
        if do_extra_batch is True:
            xs = range(remainder_start,wt)
            run_batch_local(xs, y)
            i_tile += len(xs)
            print_progress(i_tile, n_tiles, time.time() - start)
    print "\nDone."
            
        
                
            
