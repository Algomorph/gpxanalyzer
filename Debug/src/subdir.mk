################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
CPP_SRCS += \
../src/Bitcounting.cpp \
../src/CSExtraction.cpp \
../src/OpenCVFilters.cpp \
../src/module.cpp 

OBJS += \
./src/Bitcounting.o \
./src/CSExtraction.o \
./src/OpenCVFilters.o \
./src/module.o 

CPP_DEPS += \
./src/Bitcounting.d \
./src/CSExtraction.d \
./src/OpenCVFilters.d \
./src/module.d 


# Each subdirectory must supply rules for building sources it contributes
src/%.o: ../src/%.cpp
	@echo 'Building file: $<'
	@echo 'Invoking: GCC C++ Compiler'
	g++ -std=c++0x -I"/home/algomorph/Factory/gpxanalyzer/include" -I/usr/local/include/python2.7 -I/usr/local/lib/python2.7/dist-packages/numpy/core/include -I/usr/include/python2.7 -O0 -g3 -Wall -c -fmessage-length=0  -fopenmp  -lgomp -fPIC -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@:%.o=%.d)" -o "$@" "$<"
	@echo 'Finished building: $<'
	@echo ' '


