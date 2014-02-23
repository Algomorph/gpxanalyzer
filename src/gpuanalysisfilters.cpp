#include <pythonPortAux.h>

#include <opencv2/stitching.hpp>
#define MODULESTR "cvgpxa"

using namespace cv;



/*====================PYTHON=METHOD=ARRAY=====================================*/
static PyMethodDef methods[] = {

    {NULL, NULL}
};
/*================END=PYTHON=METHOD=ARRAY=====================================*/


extern "C"{
	#if defined WIN32 || defined _WIN32
	__declspec(dllexport)
	#endif
	void initcvex()
	{
	  //MKTYPE2(LineIterator);
	  //MKTYPE2(Stitcher);
	  import_array();
	  PyObject* m = Py_InitModule(MODULESTR, methods);
	  PyObject* d = PyModule_GetDict(m);
	  PyDict_SetItemString(d, "__version__", PyString_FromString("0.0.5"));
	  opencv_error = PyErr_NewException((char*)MODULESTR".error", NULL, NULL);
	  PyDict_SetItemString(d, "error", opencv_error);
	  /*================MODULE=CONSTANT=PUBLISHING==================================*/
	  //PUBLISH2(GUO_HALL,cvex::GUO_HALL);
	  //PUBLISH2(ZHANG_SUEN,cvex::ZHANG_SUEN);
	  /*================MODULE=CONSTANT=PUBLISHING==================================*/
	}
}
