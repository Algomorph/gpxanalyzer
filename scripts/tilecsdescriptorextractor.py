#!/usr/bin/env python
'''
Created on Apr 25, 2014

@author: Gregory Kramida
@copyright: (c) Gregory Kramida 2014
@license: GNU v3
'''
import argparse
import gpxanalyzer.filters.color_structure as cs
import gpxanalyzer.filters.cl_manager as clm
import gpxanalyzer.utils.system as system
import gpxanalyzer.gpxanalyzer_internals as gi
import gpxanalyzer.utils.image_size as imz
from scipy.cluster.vq import kmeans
import numpy as np
import pyopencl as cl
import sys
import os
import math
import gpxanalyzer.utils.console as console
from PIL import Image


parser = argparse.ArgumentParser(description="A tool for extracting MPEG-7 Color Structure descriptors"+
                                 " for every 256x256 region of a single 2048x2048 image.")
parser.add_argument('-w', '--channel_clusters', nargs='+', type=int,
                    help="Distance to which of the cluster means"+
                    " to represent as R,G,B colors in a mean distance image",default=[1,2,3])
parser.add_argument("--cluster", "-c",action='store_true',
                    help="generate and save cluster means",default=False)
parser.add_argument("--mean_distance_image", "-m",action='store_true',
                    help="generate mean-distance image",default=False)
parser.add_argument("--segmented_image", "-s", action='store_true',
                    help="generate segmented image",default=False)
parser.add_argument("--number_of_clusters", "-k", type=int,default=3,
                    help="number of clusters to generate")

parser.add_argument("--input_path", "-i", default=None,
                    help="path to the image whose descriptor to compute")
parser.add_argument("--output_path", "-o", default=None,
                    help="path to folder where to store the descriptors and output images")
parser.add_argument("--verbose", "-v", action='store_true',
                    help="generate mean-distance image",default=False)

def find_dists(means,rowwise):
    dists = np.zeros((len(rowwise),len(means)),dtype=np.uint16)
    for i in xrange(0,len(means)):
        dists[:,i] = np.sum((means[i] - rowwise)**2,axis=1)
    return dists

def save_dists_image(dists,path,name,which):
    n_means = dists.shape[1]
    save_path = path+os.path.sep + name + \
    "_{0:0d}_means_distances-{1:0d}-{2:0d}-{3:0d}.png".format(n_means,which[0],which[1],which[2])
    
    if(os.path.isfile(save_path)):
        if not console.query_yes_no("File at {0:s} already exists. Overwrite?".format(save_path), "no"):
            return
    
    if(len(which)!= 3 or len(np.intersect1d(which, np.arange(n_means), True)) < len(which)):
        raise ValueError("which should contain indexes of means distances to which to represent as"+
                         " each of the three channels. It should be a length 3 array of indexes.")
    #normalize
    maxes = dists.max(axis=0)
    dists_norm = dists.astype(np.float32) / maxes
    out_size = int(math.sqrt(dists.shape[0]))
    raster_dists = dists_norm.reshape((out_size,out_size,n_means))[:,:,which]
    Image.fromarray(raster_dists).save(save_path,"PNG")

palette = np.array([[230,174,44],
                    [245,241,22],
                    [168,219,105],
                    [135,208,212],
                    [139,132,184],
                    [173,34,12],
                    [105,72,12],
                    [49,125,2],
                    [2,125,123],
                    [117,98,122],
                    [227,16,44]],dtype=np.uint8)

    
def save_segment_image(dists, path, name):
    n_means = dists.shape[1]
    save_path = path+os.path.sep + name + "_{0:0d}_segments.png".format(n_means)
    if(os.path.isfile(save_path)):
        if not console.query_yes_no("File at {0:s} already exists. Overwrite?".format(save_path), "no"):
            return
    out_size = int(math.sqrt(dists.shape[0]))
    
    classes = np.argmin(dists,axis=1).reshape(out_size,out_size)
    segmented = np.zeros((out_size,out_size,3),dtype=np.uint8)

    for y in xrange(0,classes.shape[0]):
        for x in xrange(0,classes.shape[1]):
            segmented[y,x] = palette[classes[y,x]]
    Image.fromarray(segmented).save(save_path,"PNG")

def extract_descriptors(path, n_channels):
    device = system.get_devices_of_type(cl.device_type.GPU)[0]
    mgr = clm.FilterCLManager.generate(device, (0,0), cell_shape=(2048,2048), verbose = True)
    extr = cs.CSDescriptorExtractor(mgr)
    cell = np.array(Image.open(path))
    if(n_channels == 1):
        descr = extr.extract_greyscale(cell)
    else:
        descr = extr.extract(cell)
    return descr

def cluster(path, name, k,rowwise):
    clusters_path = args.output_path + os.path.sep + name + "_{0:0d}_means.npz".format(k)
    if(os.path.isfile(clusters_path)):
        cluster_file = np.load(out_descriptor_path)
        means = descr_file["descriptors"]
        cluster_file.close()
    else:
        means = kmeans(rowwise, k, iter=1)[0]
        np.savez_compressed(clusters_path,descriptors = descr)
    return means

if __name__ == '__main__':
    args = parser.parse_args(sys.argv[1:])
    #check whether the image has proper dimensions
    width, height, n_channels = imz.get_image_info(args.input_path)
    name = os.path.splitext(os.path.split(args.input_path)[1])[0]
    
    if(width != 2048 or height != 2048):
        raise ValueError("Improper input image dimensions, expecting 2048 x 2048,"+
                         " got {0:0d} x {1:0d}.".format(width,height))
    out_descriptor_path = args.output_path + os.path.sep + name + "_descriptors.npz"
    if(os.path.isfile(out_descriptor_path)):
        if(args.verbose):
            print "Found descriptor file at {0:s}, loading.".format(out_descriptor_path)
        descr_file = np.load(out_descriptor_path)
        descr = descr_file["descriptors"]
        descr_file.close()
    else:
        if(args.verbose):
            print "Generating descriptor file at {0:s}.".format(out_descriptor_path)
        descr = extract_descriptors(args.input_path, n_channels)
        np.savez_compressed(out_descriptor_path,descriptors = descr)
    k = args.number_of_clusters
    rowwise = descr.reshape((-1,gi.BASE_QUANT_SPACE))
    which = args.channel_clusters
    
    if(args.cluster or args.mean_distance_image or args.segmented_image):
        if(args.verbose):
            print "Computing & saving cluster centroids / means."
        means = cluster(args.output_path,name,k,rowwise)    
    
    if(args.mean_distance_image or args.segmented_image):
        if(args.verbose):
            print "Computing distance of every descriptor to each of the cluster means."
        dists = find_dists(means, rowwise)
    
    if(args.mean_distance_image):
        if(args.verbose):
            print "Computing distance of every descriptor to each of the cluster means."
        save_dists_image(dists, args.output_path, name, which)
    
    if(args.segmented_image):
        save_segment_image(dists, args.output_path, name)
    
    
    
    
            
    