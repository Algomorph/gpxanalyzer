#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
#include <numpy/ndarrayobject.h>
#include <boost/python.hpp>
#include <cstdio>
#include <bitset>
#include <CSExtraction.hpp>
#include <Bitcounting.hpp>

namespace bp = boost::python;//not to be confused with "British Petroleum"
typedef unsigned char uint8;
typedef unsigned long long uint64;


/**
 * Internal module definition
 */
BOOST_PYTHON_MODULE(gpxanalyzer_internals)
{
	using namespace boost::python;
	Py_Initialize();
	import_array();
	gpxa::setupTable();
	gpxa::precomputeTotalLevels();

	def("bitstrings_to_histogram",gpxa::pyBitstringsToHistogram,(arg("bitstrings"),arg("x") = 0,arg("y") = 0));
	def("bitstrings_to_descriptor",gpxa::pyBitstringsToDescriptor,(arg("bitstrings"),arg("x") = 0,arg("y") = 0));
	def("bitstrings_to_descriptor_array_serial",gpxa::pyBitstringsToDescriptorArray,(arg("bitstrings")));
	def("bitstrings_to_descriptor_array_parallel",gpxa::pyBitstringsToDescriptorArrayParallel,(arg("bitstrings")));
	def("bitstrings_to_descriptor_array_basic",gpxa::pyBitstringsToDescriptorArrayParallelBasic,(arg("bitstrings")));
	def("bitstrings_to_descriptor_array_mask_LSB",gpxa::pyBitstringsToDescriptorArrayParallelMaskLSB,(arg("bitstrings")));
	def("bitstrings_to_descriptor_array_vector_extensions",gpxa::pyBitstringsToDescriptorArrayParallelVecExt,(arg("bitstrings")));
	def("bitstrings_to_descriptor_array_matthews",gpxa::pyBitstringsToDescriptorArrayParallelMatthews,(arg("bitstrings")));
	def("bitstrings_to_descriptor_array_ffs",gpxa::pyBitstringsToDescriptorArrayParallelFFS,(arg("bitstrings")));
	scope().attr("REGION_SIZE") = REGION_SIZE;
	scope().attr("WINDOW_SIZE") = WINDOW_SIZE;
	scope().attr("REGION_CLIP") = REGION_CLIP;
	scope().attr("BASE_QUANT_SPACE") = BASE_QUANT_SPACE;
	scope().attr("REGION_NORM") = REGION_NORM;

}
