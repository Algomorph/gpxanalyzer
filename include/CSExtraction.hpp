/*
 * CSExtraction.hpp
 *
 *  Created on: Apr 22, 2014
 *      Author: Gregory Kramida
 */

#ifndef CSEXTRACTION_HPP_
#define CSEXTRACTION_HPP_
#pragma GCC diagnostic ignored "-Wunused-function"

#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include "boost/python.hpp"
#include <Python.h>
#include <numpy/ndarrayobject.h>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <omp.h>
#include <Bitcounting.hpp>
namespace bp = boost::python;//not to be confused with "British Petroleum"

#define REGION_SIZE 256
#define BASE_QUANT_SPACE 256
#define WINDOW_SIZE 8
#define REGION_CLIP (REGION_SIZE - WINDOW_SIZE + 1)
#define REGION_NORM (REGION_CLIP * REGION_CLIP)
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
void precomputeTotalLevels();
void quantAmplNonLinear(uint16_t* hist, uint8_t* histOut);
void bitstringsToHistogram(uint64_t* arr, uint16_t* hist, int width, int x, int y);
void bitstringsSlidingHistogram(uint64_t* arr, uint8_t* descriptors, int width, int height);
void bitstringsSlidingHistogramMT(uint64_t* arr, uint8_t* descriptors, int width, int height);
void bitstringsSlidingHistogramMTBasic(uint64_t* arr, uint8_t* descriptors, int width, int height);
void bitstringsSlidingHistogramMTVecExt(uint64_t* arr, uint8_t* descriptors, int width, int height);
void bitstringsSlidingHistogramMTMaskLSB(uint64_t* arr, uint8_t* descriptors, int width, int height);
void bitstringsSlidingHistogramMTMatthews(uint64_t* arr, uint8_t* descriptors, int width, int height);
void bitstringsSlidingHistogramMTFFS(uint64_t* arr, uint8_t* descriptors, int width, int height);

void bitstringsSlidingHistogramMTFP(uint64_t* arr, uint8_t* descriptors,
		void (*histAdd)(uint64_t*, uint16_t*),
		void (*histSub)(uint64_t*, uint16_t*), const int width,
		const int height);

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

static PyObject* pyBitstringsToDescriptor(PyObject* winBitstrings, int x = 0, int y = 0){
	CHECK_BITSTRINGS(winBitstrings);
	int width = shape[1];
	npy_intp dims[] = {BASE_QUANT_SPACE};
	uint16_t hist[256] = {0};
	bitstringsToHistogram((uint64_t*)PyArray_DATA(arr),hist,width,x,y);
	uint8_t histUchar[256];
	quantAmplNonLinear(hist,histUchar);
	PyObject* out = PyArray_SimpleNew(1, dims, NPY_UBYTE);
	uint8_t* histOut = (uint8_t*)PyArray_DATA((PyArrayObject*)out);
	memcpy(histOut,histUchar,sizeof(histUchar));
	return out;
}

static PyObject* pyBitstringsToHistogram(PyObject* winBitstrings, int x = 0, int y = 0){
	CHECK_BITSTRINGS(winBitstrings);
	int width = shape[1];
	npy_intp dims[] = {BASE_QUANT_SPACE};
	uint16_t hist[256] = {0};
	bitstringsToHistogram((uint64_t*)PyArray_DATA(arr),hist,width,x,y);
	PyObject* out = PyArray_SimpleNew(1, dims, NPY_USHORT);
	uint16_t* histOut = (uint16_t*)PyArray_DATA((PyArrayObject*)out);
	memcpy(histOut,hist,sizeof(hist));
	return out;
}

static PyObject* pyBitstringsToDescriptorArray(PyObject* winBitstrings){
	CHECK_BITSTRINGS(winBitstrings);
	int width = shape[1];
	int height = shape[0];
	npy_intp dims[] = {height- REGION_SIZE + 1,width - REGION_SIZE + 1,BASE_QUANT_SPACE};
	PyObject* out = PyArray_SimpleNew(3, dims, NPY_UBYTE);
	uint8_t* descrData = (uint8_t*)PyArray_DATA((PyArrayObject*)out);
	bitstringsSlidingHistogram((uint64_t*)PyArray_DATA(arr),descrData,width,height);
	return out;
}

static PyObject* pyBitstringsToDescriptorArrayParallel(PyObject* winBitstrings){
	CHECK_BITSTRINGS(winBitstrings);
	int width = shape[1];
	int height = shape[0];
	npy_intp dims[] = {height- REGION_SIZE + 1,width - REGION_SIZE + 1,BASE_QUANT_SPACE};
	PyObject* out = PyArray_SimpleNew(3, dims, NPY_UBYTE);
	uint8_t* descrData = (uint8_t*)PyArray_DATA((PyArrayObject*)out);
	bitstringsSlidingHistogramMT((uint64_t*)PyArray_DATA(arr),descrData,width,height);
	return out;
}
static PyObject* pyBitstringsToDescriptorArrayParallelBasic(PyObject* winBitstrings){
	CHECK_BITSTRINGS(winBitstrings);
	int width = shape[1];
	int height = shape[0];
	npy_intp dims[] = {height- REGION_SIZE + 1,width - REGION_SIZE + 1,BASE_QUANT_SPACE};
	PyObject* out = PyArray_SimpleNew(3, dims, NPY_UBYTE);
	uint8_t* descrData = (uint8_t*)PyArray_DATA((PyArrayObject*)out);
	bitstringsSlidingHistogramMTBasic((uint64_t*)PyArray_DATA(arr),descrData,width,height);
	return out;
}
static PyObject* pyBitstringsToDescriptorArrayParallelMaskLSB(PyObject* winBitstrings){
	CHECK_BITSTRINGS(winBitstrings);
	int width = shape[1];
	int height = shape[0];
	npy_intp dims[] = {height- REGION_SIZE + 1,width - REGION_SIZE + 1,BASE_QUANT_SPACE};
	PyObject* out = PyArray_SimpleNew(3, dims, NPY_UBYTE);
	uint8_t* descrData = (uint8_t*)PyArray_DATA((PyArrayObject*)out);
	bitstringsSlidingHistogramMTMaskLSB((uint64_t*)PyArray_DATA(arr),descrData,width,height);
	return out;
}
static PyObject* pyBitstringsToDescriptorArrayParallelVecExt(PyObject* winBitstrings){
	CHECK_BITSTRINGS(winBitstrings);
	int width = shape[1];
	int height = shape[0];
	npy_intp dims[] = {height- REGION_SIZE + 1,width - REGION_SIZE + 1,BASE_QUANT_SPACE};
	PyObject* out = PyArray_SimpleNew(3, dims, NPY_UBYTE);
	uint8_t* descrData = (uint8_t*)PyArray_DATA((PyArrayObject*)out);
	bitstringsSlidingHistogramMTVecExt((uint64_t*)PyArray_DATA(arr),descrData,width,height);
	return out;
}
static PyObject* pyBitstringsToDescriptorArrayParallelMatthews(PyObject* winBitstrings){
	CHECK_BITSTRINGS(winBitstrings);
	int width = shape[1];
	int height = shape[0];
	npy_intp dims[] = {height- REGION_SIZE + 1,width - REGION_SIZE + 1,BASE_QUANT_SPACE};
	PyObject* out = PyArray_SimpleNew(3, dims, NPY_UBYTE);
	uint8_t* descrData = (uint8_t*)PyArray_DATA((PyArrayObject*)out);
	bitstringsSlidingHistogramMTMatthews((uint64_t*)PyArray_DATA(arr),descrData,width,height);
	return out;
}
static PyObject* pyBitstringsToDescriptorArrayParallelFFS(PyObject* winBitstrings){
	CHECK_BITSTRINGS(winBitstrings);
	int width = shape[1];
	int height = shape[0];
	npy_intp dims[] = {height- REGION_SIZE + 1,width - REGION_SIZE + 1,BASE_QUANT_SPACE};
	PyObject* out = PyArray_SimpleNew(3, dims, NPY_UBYTE);
	uint8_t* descrData = (uint8_t*)PyArray_DATA((PyArrayObject*)out);
	bitstringsSlidingHistogramMTFFS((uint64_t*)PyArray_DATA(arr),descrData,width,height);
	return out;
}

}//end namespace gpxa
#endif /* CSEXTRACTION_HPP_ */
