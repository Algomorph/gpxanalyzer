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
namespace bp = boost::python;//not to be confused with "British Petroleum"
typedef unsigned char uint8;
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
 * @param z - z-coordinate: predefined scale level of the region, i.e. the region size is determined as
 * REGION_SIZE * SCALE_INCREMENT_FACTOR^z TODO: currently, the SCALE_INCREMENT_FACTOR = 2, so it's just 256 << z
 * @return a 256-ushort long 1D NumPy array containing the Color Structure descriptor
 */
PyObject* extractCSDescriptor(PyObject* windowBitarrays, int x, int y, int z){
	if(!PyArray_Check(windowBitarrays)){
		std::cout << "0.1" << std::endl;
		PyErr_SetString(PyExc_ValueError,"extractCSDescriptor only accepts a 3D NumPy ndarray of type np.uint32 as an argument");
		std::cout << "0.2" << std::endl;
		bp::throw_error_already_set();
	}

	PyArrayObject* arr = (PyArrayObject*) windowBitarrays;
	int ndims = PyArray_NDIM(arr);

	if(ndims != 3){
		PyErr_SetString(PyExc_ValueError,"extractCSDescriptor only accepts a 3D NumPy ndarray of type np.uint32 as an argument");
		bp::throw_error_already_set();
	}

	int dtype = PyArray_TYPE(arr);
	if(dtype != NPY_UINT){
		PyErr_SetString(PyExc_ValueError,"extractCSDescriptor only accepts a 3D NumPy ndarray of type np.uint32 as an argument");
		bp::throw_error_already_set();
	}

	const npy_intp* shape = PyArray_DIMS(arr);
	if(shape[2] != 8){
		PyErr_SetString(PyExc_ValueError,"extractCSDescriptor: the third dimension of the argument NumPy array must be 8");
		bp::throw_error_already_set();
	}
	int height = shape[0];
	int width = shape[1];
	int bytewidth = width << 2;

	//pointing at the first relevant bitstring
	uint64* bitdataRowStart = (uint64*)PyArray_DATA(arr) + ((y*width + x) << 2);


	npy_intp dims[] = {BASE_QUANT_SPACE};
	PyObject* out = PyArray_SimpleNew(1, dims, NPY_USHORT);
	uint8* hist = (uint8*)PyArray_DATA((PyArrayObject*)out);

	for(int yR = 0; yR < REGION_CLIP; yR++){
		unsigned long long* rowEnd = bitdataRowStart + REGION_CLIP;
		for(unsigned long long* cursor = bitdataRowStart; cursor < rowEnd; cursor+=4){
			std::bitset<64> a(*cursor);
			std::bitset<64> b(*(cursor+1));
			std::bitset<64> c(*(cursor+2));
			std::bitset<64> d(*(cursor+3));
			for(int bit = 0; bit < 64; bit++){
				hist[bit] += a.test(bit);
			}
			for(int bit = 0; bit < 64; bit++){
				hist[bit+64] += b.test(bit);
			}
			for(int bit = 0; bit < 64; bit++){
				hist[bit+128] += c.test(bit);
			}
			for(int bit = 0; bit < 64; bit++){
				hist[bit+192] += d.test(bit);
			}
		}
		bitdataRowStart += bytewidth;
	}
	return out;
}

}//end namespace gpxa
#endif /* CSEXTRACTION_HPP_ */
