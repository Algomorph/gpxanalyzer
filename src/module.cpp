#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
#include <numpy/ndarrayobject.h>
#include <boost/python.hpp>
#include <cstdio>
#include <bitset>
#include <CSExtraction.hpp>

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

	def("extract_cs_descriptor",gpxa::extractCSDescriptor,(arg("bitstrings"),arg("x"),arg("y"),arg("z")));
	scope().attr("REGION_SIZE") = REGION_SIZE;
	scope().attr("WINDOW_SIZE") = WINDOW_SIZE;
	scope().attr("REGION_CLIP") = REGION_CLIP;
	scope().attr("BASE_QUANT_SPACE") = BASE_QUANT_SPACE;
	scope().attr("REGION_NORM") = REGION_NORM;

}
