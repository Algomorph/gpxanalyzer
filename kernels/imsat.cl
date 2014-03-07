/***
 * @brief OpenCL kernels for recursive summed-area table filter
 * @details Based on gpufilter cuda code from code.google.com/p/gpufilter/
 * 			Reference:
 *			Nehab, D., Maximo, A., Lima, R. S., & Hoppe, H. (2011, December). GPU-efficient recursive
 *			filtering and summed-area tables. In ACM Transactions on Graphics (TOG) (Vol. 30, No. 6, p. 176). ACM.
 *
 *@author Gregory Kramida
 *@date 02/25/2013
 *@copyright GNU Public License v3.
 */

#ifdef __CDT_PARSER__
#include "OpenCLKernel.hpp"
#define WARP_SIZE 32
#define HALF_WARP_SIZE 16
#define N_COLUMNS 1
#define N_ROWS 1
#define LAST_M 1
#define LAST_N 1
#define BORDER 1
#define WIDTH 32
#define HEIGHT 32
#define INV_WIDTH 1.0F
#define INPUT_STRIDE 160
#define INV_HEIGHT 1.0F
#define NUM_CHANNELS 3
#include <gpudefs.h>
#else
#include "include/gpudefs.h"
#endif

//== IMPLEMENTATION ===========================================================
/**
 * Sampler using unnormalized coordinates (x,y pixel coordinates)
 * Discrete (int/uint) sampling supports only CLK_FILTER_NEAREST
 */
__constant sampler_t sampler = CLK_NORMALIZED_COORDS_FALSE | CLK_ADDRESS_CLAMP_TO_EDGE | CLK_FILTER_NEAREST;

/**
 * SAT stage 1: subdivide image into rows & columns of blocks.
 * Execute 1 block/group. For every block, compute the prefix sums of its rows and columns.
 * Store these intermediate results into the group_column_sums and group_row_sums buffers.
 *
 * WIDTH/WARP_SIZE blocks wide
 *
 *Groups/Block size: WARP_SIZE X SCHEDULE_OPTIMIZED_N_WARPS
 *@param input - WIDTH x HEIGHT
 *@param rowGroupCount - rowGroupCount X WIDTH
 *@param vHat - colGroupCount x HEIGHT
 */
__kernel
void compute_block_aggregates(const __global uint* input, __global uint* group_column_sums,
		__global uint* group_row_sums) {

	const size_t yLocal = get_local_id(1), xLocal = get_local_id(0);
	const size_t yGroup = get_group_id(1), xGroup = get_group_id(0);
	const size_t col = get_global_id(0),//current column (works because block width == WARP_SIZE)
				 row = get_global_id(1),//current row
				 row0 = yGroup*WARP_SIZE;//start row of current x prologue block

	//local memory to store intermediate results, size WARP_SIZE x WARP_SIZE+1
	__local uint dataBlock[WARP_SIZE][ WARP_SIZE + 1];

	//pointer to an array of uints of WARP_SIZE + 1, starting at the coordinate of the work item within
	//the sBlock
	__local uint (*dataRow)[WARP_SIZE + 1] =
			(__local uint (*)[WARP_SIZE + 1]) &dataBlock[yLocal][xLocal];

	//position the input pointer to this work-item's cell
	input += row * WIDTH + col;
	group_column_sums += yGroup * WIDTH + col;	//top->bottom output block
	group_row_sums += xGroup * WIDTH + row0 + xLocal;	//left->right output block

#pragma unroll
	//fill the local data block that's shared between work items
	for (int i = 0; i < WARP_SIZE - (WARP_SIZE % SCHEDULE_OPTIMIZED_N_WARPS);
			i++) {
		//copy WARP_SIZE+1 values over from the input
		**dataRow = *input;
		dataRow += SCHEDULE_OPTIMIZED_N_WARPS;
		input += INPUT_STRIDE;
	}
	//if we're in the last few rows of work items, finish up the remaining copying
	if (yLocal < WARP_SIZE % SCHEDULE_OPTIMIZED_N_WARPS) {
		**dataRow = *input;
	}

	barrier(CLK_LOCAL_MEM_FENCE);

	if (yLocal == 0) {

		{   // calculate per-block-row prologue (aggregate block/group vertically) -----------

			__local uint(*dataRow)[WARP_SIZE + 1] =
					(__local uint (*)[WARP_SIZE + 1]) &dataBlock[0][xLocal];

			uint prev = **dataRow;
			++dataRow;

#pragma unroll
			for (int i = 1; i < WARP_SIZE; ++i, ++dataRow)
				**dataRow = prev = **dataRow + prev;

			*group_column_sums = prev;
		}

		{   // calculate per-block-column prologue on block on results of the vertical prefix pass
			// (aggregate block/group horizontally)
			__local uint *dataRow = dataBlock[xLocal];

			uint prev = *dataRow;
			++dataRow;

#pragma unroll
			for (int i = 1; i < WARP_SIZE; ++i, ++dataRow)
				prev = *dataRow + prev;

			*group_row_sums = prev;
		}

	}
}

//-- Algorithm SAT Stage 2 ----------------------------------------------------
/**
 * Aggregates the horizontal block-row-wise block column sums into column/block sums along the whole image
 * @param[in] yBar [rowGroupCount x WIDTH] - sums of columns in each block row
 * @param[out] ySum [colGroupCount x rowGroupCount] - sums of rows and columns for each block
 */
__kernel
void vertical_aggregate(__global uint *yBar, __global uint *ySum) {

	const size_t yLocal = get_local_id(1), xLocal = get_local_id(0), xGroup = get_group_id(
			0), col0 = xGroup * MAX_WARPS + yLocal, col = col0*WARP_SIZE+xLocal;

	if (col >= WIDTH)
		return;

	yBar += col;
	uint y = *yBar;
	int ln = HALF_WARP_SIZE + xLocal;

	if (xLocal == WARP_SIZE - 1)
		ySum += col0;

	volatile __local uint dataBlock[ MAX_WARPS][ HALF_WARP_SIZE + WARP_SIZE + 1];

	if (xLocal < HALF_WARP_SIZE)
		dataBlock[yLocal][xLocal] = 0.f;
	else
		dataBlock[yLocal][ln] = 0.f;

	for (int n = 1; n < N_ROWS; ++n) {

		// calculate ysum -----------------------
		//TODO: can't we just do inner loop unroll here? I mean, how do we know to stop at ln - 16?
		dataBlock[yLocal][ln] = y;

		dataBlock[yLocal][ln] += dataBlock[yLocal][ln - 1];
		dataBlock[yLocal][ln] += dataBlock[yLocal][ln - 2];
		dataBlock[yLocal][ln] += dataBlock[yLocal][ln - 4];
		dataBlock[yLocal][ln] += dataBlock[yLocal][ln - 8];
		dataBlock[yLocal][ln] += dataBlock[yLocal][ln - 16];

		if (xLocal == WARP_SIZE - 1) {
			*ySum = dataBlock[yLocal][ln];
			ySum += N_COLUMNS;
		}

		//TODO:??? fix ybar -> y ??? (left over from original code)-------------------------

		yBar += WIDTH;
		y = *yBar += y;

	}

}

//-- Algorithm SAT Stage 3 ----------------------------------------------------
/**
 * Aggregates the horizontal block-row-wise block column sums into column/block sums along the whole image
 * @param[in] yBar [rowGroupCount x WIDTH] - sums of columns in each block row
 * @param[out] ySum [colGroupCount x rowGroupCount] - sums of rows and columns for each block
 */
__kernel
void horizontal_aggregate(const __global uint *ySum, __global uint *vHat) {

	const size_t xWorkItem = get_local_id(0), yWorkItem = get_local_id(1), yGroup = get_group_id(
			1), row0 = yGroup * MAX_WARPS + yWorkItem, row = row0 * WARP_SIZE + xWorkItem;

	if (row >= HEIGHT)
		return;

	vHat += row;
	uint y = 0.f, v = 0.f;

	if (row0 > 0)
		ySum += (row0 - 1) * N_COLUMNS;

	for (int m = 0; m < N_COLUMNS; ++m) {

		// fix vhat -> v -------------------------

		if (row0 > 0) {
			y = *ySum;
			ySum += 1;
		}

		v = *vHat += v + y;
		vHat += HEIGHT;

	}

}

//-- Algorithm SAT Stage 4 ----------------------------------------------------

__kernel
void redistribute_SAT_inplace( __global uint *matrix, __global const uint *yBar,
		__global const uint *vHat) {

	const size_t xLocal = get_local_id(0), yLocal = get_local_id(1), xBlock = get_group_id(
			0), yBlock = get_group_id(1), col = get_global_id(0), blockRow0 = yBlock
			* WARP_SIZE;

	__local uint block[ WARP_SIZE][ WARP_SIZE + 1];

	__local uint (*blockRow)[WARP_SIZE + 1] =
			(__local uint (*)[WARP_SIZE + 1]) &block[yLocal][xLocal];

	matrix += (blockRow0 + yLocal) * WIDTH + col;
	if (yBlock > 0)
		yBar += (yBlock - 1) * WIDTH + col;
	if (xBlock > 0)
		vHat += (xBlock - 1) * HEIGHT + blockRow0 + xLocal;

#pragma unroll
	//-----copy the assigned block into local memory---------
	for (int i = 0; i < WARP_SIZE - (WARP_SIZE % SCHEDULE_OPTIMIZED_N_WARPS);
			i += SCHEDULE_OPTIMIZED_N_WARPS) {
		**blockRow = *matrix;
		blockRow += SCHEDULE_OPTIMIZED_N_WARPS;
		matrix += INPUT_STRIDE;
	}
	//finish copying - some threads handling remaining rows
	if (yLocal < WARP_SIZE % SCHEDULE_OPTIMIZED_N_WARPS) {
		**blockRow = *matrix;
	}
	//--------------end copying to local memory---------------
	barrier(CLK_LOCAL_MEM_FENCE);//resynch

	//for threads at the top of the block
	if (yLocal == 0) {
		{   // calculate y -----------------------
			//point at the row at the top
			__local uint(*blockRow)[WARP_SIZE + 1] = (__local uint (*)[WARP_SIZE
					+ 1]) &block[0][xLocal];

			uint prev;
			if (yBlock > 0)
				prev = *yBar;
			else
				prev = 0;//for the first block, there is no y prologue

#pragma unroll
			//go up to warp size, add the previous item (item above)
			for (int i = 0; i < WARP_SIZE; ++i, ++blockRow)
				**blockRow = prev = **blockRow + prev;
		}

		{   // calculate x -----------------------
			__local uint *bdata = block[xLocal];

			uint prev;
			if (xBlock > 0)
				prev = *vHat;
			else
				prev = 0;

#pragma unroll
			for (int i = 0; i < WARP_SIZE; ++i, ++bdata)
				*bdata = prev = *bdata + prev;
		}

	}

	barrier(CLK_LOCAL_MEM_FENCE);

	//--------copy results back from local memory into the global in/out matrix----
	blockRow = (__local uint (*)[WARP_SIZE + 1]) &block[yLocal][xLocal];

	matrix -= (WARP_SIZE - (WARP_SIZE % SCHEDULE_OPTIMIZED_N_WARPS))
			* WIDTH;

#pragma unroll
	for (int i = 0; i < WARP_SIZE - (WARP_SIZE % SCHEDULE_OPTIMIZED_N_WARPS);
			i += SCHEDULE_OPTIMIZED_N_WARPS) {
		*matrix = **blockRow;
		blockRow += SCHEDULE_OPTIMIZED_N_WARPS;
		matrix += SCHEDULE_OPTIMIZED_N_WARPS * WIDTH;
	}
	if (yLocal < WARP_SIZE % SCHEDULE_OPTIMIZED_N_WARPS) {
		*matrix = **blockRow;
	}

}


//-- Algorithm SAT Stage 4 (not-in-place) -------------------------------------

__kernel
void redistribute_SAT_not_inplace( __global uint *g_out,
		__global const uint *g_in, __global const uint *g_y,
		__global const uint *g_v) {

	const size_t tx = get_local_id(0), ty = get_local_id(1), bx = get_group_id(
			0), by = get_group_id(1), col = bx * WARP_SIZE + tx, row0 = by
			* WARP_SIZE;
	__local uint s_block[ WARP_SIZE][ WARP_SIZE + 1];

	__local uint (*dataBlock)[WARP_SIZE + 1] =
			(__local uint (*)[WARP_SIZE + 1]) &s_block[ty][tx];

	g_in += (row0 + ty) * WIDTH + col;
	if (by > 0)
		g_y += (by - 1) * WIDTH + col;
	if (bx > 0)
		g_v += (bx - 1) * HEIGHT + row0 + tx;

#pragma unroll
	for (int i = 0; i < WARP_SIZE - (WARP_SIZE % SCHEDULE_OPTIMIZED_N_WARPS);
			i += SCHEDULE_OPTIMIZED_N_WARPS) {
		**dataBlock = *g_in;
		dataBlock += SCHEDULE_OPTIMIZED_N_WARPS;
		g_in += SCHEDULE_OPTIMIZED_N_WARPS * WIDTH;
	}
	if (ty < WARP_SIZE % SCHEDULE_OPTIMIZED_N_WARPS) {
		**dataBlock = *g_in;
	}

	barrier(CLK_LOCAL_MEM_FENCE);

	if (ty == 0) {

		{   // calculate y -----------------------
			__local uint(*dataBlock)[WARP_SIZE + 1] = (__local uint (*)[WARP_SIZE
					+ 1]) &s_block[0][tx];

			uint prev;
			if (by > 0)
				prev = *g_y;
			else
				prev = 0;

#pragma unroll
			for (int i = 0; i < WARP_SIZE; ++i, ++dataBlock)
				**dataBlock = prev = **dataBlock + prev;
		}

		{   // calculate x -----------------------
			__local uint *bdata = s_block[tx];

			uint prev;
			if (bx > 0)
				prev = *g_v;
			else
				prev = 0;

#pragma unroll
			for (int i = 0; i < WARP_SIZE; ++i, ++bdata)
				*bdata = prev = *bdata + prev;
		}

	}

	barrier(CLK_LOCAL_MEM_FENCE);

	dataBlock = (__local uint (*)[WARP_SIZE + 1]) &s_block[ty][tx];

	g_out += (row0 + ty) * WIDTH + col;

#pragma unroll
	for (int i = 0; i < WARP_SIZE - (WARP_SIZE % SCHEDULE_OPTIMIZED_N_WARPS);
			i += SCHEDULE_OPTIMIZED_N_WARPS) {
		*g_out = **dataBlock;
		dataBlock += SCHEDULE_OPTIMIZED_N_WARPS;
		g_out += SCHEDULE_OPTIMIZED_N_WARPS * WIDTH;
	}
	if (ty < WARP_SIZE % SCHEDULE_OPTIMIZED_N_WARPS) {
		*g_out = **dataBlock;
	}

}
