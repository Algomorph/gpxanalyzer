/*
 * CSExtraction.hpp
 *
 *  Created on: Apr 22, 2014
 *      Author: Gregory Kramida
 */

#ifndef CSEXTRACTION_HPP_
#define CSEXTRACTION_HPP_

#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include "boost/python.hpp"
#include <Python.h>
#include <numpy/ndarrayobject.h>
#include <bitset>
#include <cstdio>
#include <cstring>
namespace bp = boost::python;//not to be confused with "British Petroleum"

typedef unsigned char uint8;
typedef unsigned short uint16;
typedef unsigned long long uint64;

#define REGION_SIZE 256
#define BASE_QUANT_SPACE 256
#define WINDOW_SIZE 8
#define REGION_CLIP REGION_SIZE - WINDOW_SIZE + 1
#define REGION_NORM REGION_CLIP * REGION_CLIP
#define SCALE_INCREMENT_FACTOR 2.0

namespace gpxa{
/**
 * Extract a single region MPEG7 Color Structure descriptor from the pre-computed 8x8 window bit-arrays at the
 * given coordinate.
 * @param windowBitarrays - a NumPy array of bitarrays for each pixel of the original image, having shape
 * (h,w,8), where w & h are width and height of the original image, and type unsigned int. Within, the bitarray for
 * pixel (y,x) is spread over 8 uints at y,x,0-7. The bitarray for a pixel represents,
 * for 256 values, whether that value occurred within the 8x8 pixel window with top-left corner at that pixel.
 * @param x - x-coordinate for the top-left corner of the region whose descriptor to retrieve
 * @param y - y-coordinate for the top-right corner of the region whose descriptor to retrieve
 * REGION_SIZE * SCALE_INCREMENT_FACTOR^z
 * @return a 256-ushort long 1D NumPy array containing the Color Structure descriptor
 */
void bitstringsToHistogram(uint64* arr, uint16* hist, int width, int x, int y);
void quantAmplNonLinear(uint16* hist, uint8* histOut);

#define CHECK_BITSTRINGS(winBitstrings) \
	if(!PyArray_Check(winBitstrings)){\
		std::cout << "0.1" << std::endl;\
		PyErr_SetString(PyExc_ValueError,"Bitstring array can only be a 3D NumPy ndarray of type np.uint32");\
		std::cout << "0.2" << std::endl;\
		bp::throw_error_already_set();\
	}\
	PyArrayObject* arr = (PyArrayObject*) winBitstrings;\
	int ndims = PyArray_NDIM(arr);\
	if(ndims != 3){\
		PyErr_SetString(PyExc_ValueError,"Bitstring array can only be a 3D NumPy ndarray of type np.uint32");\
		bp::throw_error_already_set();\
	}\
	int dtype = PyArray_TYPE(arr);\
	if(dtype != NPY_UINT){\
		PyErr_SetString(PyExc_ValueError,"Bitstring array can only be a 3D NumPy ndarray of type np.uint32");\
		bp::throw_error_already_set();\
	}\
	const npy_intp* shape = PyArray_DIMS(arr);\
	if(shape[2] != 8){\
		PyErr_SetString(PyExc_ValueError,"The third dimension of the bitstring NumPy array must be 8.");\
		bp::throw_error_already_set();\
	}

static PyObject* pyBitstringsToDescriptor(PyObject* winBitstrings, int x, int y){
	CHECK_BITSTRINGS(winBitstrings);
	int width = shape[1];
	npy_intp dims[] = {BASE_QUANT_SPACE};
	uint16 hist[256] = {0};
	bitstringsToHistogram((uint64*)PyArray_DATA(arr),hist,width,x,y);
	uint8 histUchar[256];
	quantAmplNonLinear(hist,histUchar);
	PyObject* out = PyArray_SimpleNew(1, dims, NPY_UBYTE);
	uint8* histOut = (uint8*)PyArray_DATA((PyArrayObject*)out);
	memcpy(histOut,histUchar,sizeof(histUchar));
	return out;
}

static PyObject* pyBitstringsToHistogram(PyObject* winBitstrings, int x, int y){
	CHECK_BITSTRINGS(winBitstrings);
	int width = shape[1];
	npy_intp dims[] = {BASE_QUANT_SPACE};
	uint16 hist[256] = {0};
	bitstringsToHistogram((uint64*)PyArray_DATA(arr),hist,width,x,y);
	PyObject* out = PyArray_SimpleNew(1, dims, NPY_USHORT);
	uint16* histOut = (uint16*)PyArray_DATA((PyArrayObject*)out);
	memcpy(histOut,hist,sizeof(hist));
	return out;
}

}//end namespace gpxa
#endif /* CSEXTRACTION_HPP_ */
