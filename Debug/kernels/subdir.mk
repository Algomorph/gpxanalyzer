################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
CL_SRCS += \
../kernels/cs.cl 

OBJS += \
./kernels/cs.o 

CL_DEPS += \
./kernels/cs.d 


# Each subdirectory must supply rules for building sources it contributes
kernels/%.o: ../kernels/%.cl
	@echo 'Building file: $<'
	@echo 'Invoking: GCC C++ Compiler'
	g++ -I"/home/algomorph/Factory/gpxanalyzer/include" -I/usr/include/python2.7 -O0 -g3 -Wall -c -fmessage-length=0 -std=c++0x -fPIC -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@:%.o=%.d)" -o "$@" "$<"
	@echo 'Finished building: $<'
	@echo ' '


