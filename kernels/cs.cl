/***
 * @brief MPEG-7 Color-Structure Descriptor
 * @details Reference:
 *			Messing, D. S., van Beek, P., & Errico, J. H. (2001). The mpeg-7 colour structure descriptor:
 *			Image description using colour and local spatial information.
 *			In Image Processing, 2001. Proceedings.
 *			2001 International Conference on (Vol. 1, pp. 670-673). IEEE.
 *
 *@author Gregory Kramida
 *@date 02/25/2013
 *@copyright GNU Public License v3.
 */

/**
 * Sampler using unnormalized coordinates (x,y pixel coordinates)
 * Discrete (int/uint) sampling supports only CLK_FILTER_NEAREST
 */
#ifdef __CDT_PARSER__
#include "OpenCLKernel.hpp"
#define BASE_QUANT_SPACE 256
#define GROUP_SIZE 1
#define WIDTH 2048
#define HEIGHT 2048
#define SUBSAMPLE 3
#define WINSIZE 64
#endif

__constant sampler_t sampler = CLK_NORMALIZED_COORDS_FALSE
		| CLK_ADDRESS_CLAMP_TO_EDGE | CLK_FILTER_NEAREST;

/**
 * Old routine for conversion from RGB to HMMD space - inefficient
 * @param R
 * @param G
 * @param B
 * @return
 */
int4 convertPixelToHMMD2(int R, int G, int B){
	int max, min;
	float hue;

	max=R;
	if(max<G) {max=G;}
	if(max<B) {max=B;}

	min=R;
	if(min>G) {min=G;}
	if(min>B) {min=B;}

	if (max == min) // ( R == G == B )//exactly gray
		hue = -1; //hue is undefined

	else
	{   //solve Hue
		if(R==max)
			hue=((G-B)*60.0f/(float)(max-min));

		else if(G==max)
			hue=(120.0f +(B-R)*60.0f/(float)(max-min));

		else if(B==max)
			hue=(240.0f +(R-G)*60.0f/(float)(max-min));

		//hue*=60.0f;
		if(hue<0.0f) hue+=360.0f;
	}
	return (int4)((int) (hue + 0.5f),(int)(max + min + 1) >> 1,(int)(max - min + 0.5),0);
}

/**
 * Fast routine for converting RGB pixels to HMMD colors space
 * @param R
 * @param G
 * @param B
 * @return (int4) (hue,sum,difference,0)
 */
int4 convertPixelToHMMD(int R, int G, int B){
	float hue;
	int a, D;

	if (R < G) {
		if (G < B) {
			//B is max,R is min
			a = B + R;
			D = B - R;
			hue = 240.0f + ((float) (R - G))*60.0f / D;
		} else {
			//G is max or G == B
			if (R < B) {
				//R is min
				a = G + R;
				D = G - R;
				hue = 120.0f + ((float) (B - R))*60.0f / D;
			} else {
				//B is min or R == B
				a = G + B;
				D = G - B;
				hue = 120.0f + ((float) (B - R))*60.0f / D;
			}
		}
		if (hue < 0.0f) {
			hue += 360.0f;
		}
	} else {
		if (B < R) {
			//R is max or R == G
			if (B < G) {
				//B is min
				a = R + B;
				D = R - B;
				hue = (((float) (G - B)) * 60.0f / D);
			} else {
				//G is min or (B == G and R is max for sure)
				a = R + G;
				D = R - G;
				hue = (((float) (G - B)) * 60.0f / D);
			}
			if (hue < 0.0f) {
				hue += 360.0f;
			}
		} else {
			//G <= R <= B
			if (G < B) {
				//B is max or B == R
				//G is min
				a = B + G;
				D = B - G;
				hue = (240.0f + ((float) (R - G)) * 60.0f / D);
				if (hue < 0.0f) {
					hue += 360.0f;
				}
			} else {
				//G == R == B
				return (int4)(0,(G+G+1)>>1,0,0); //hue undefined
			}
		}
	}
	return (int4)((int) (hue + 0.5f),(a + 1) >> 1,D,0);
}

__kernel
void convert_to_HMMD(__read_only image2d_t image,
		__write_only image2d_t output) {
	size_t x = get_global_id(0);
	size_t y = get_global_id(1);
	int2 dims = get_image_dim(image);
	if (x >= dims.x || y >= dims.y) {
		return;
	}
	int2 coord = (int2) (x, y);
	int4 px = read_imagei(image, sampler, coord);
	float hue;
	int R, G, B, a, d, H, S, D;
	R = px.x;
	G = px.y;
	B = px.z;
	int4 out = convertPixelToHMMD(R,G,B);
	write_imagei(output, coord, out);
}

__kernel
void window_hist_cumo(__read_only image2d_t input, __global uint* descriptor){
	size_t x_thread = get_global_id(0);
	size_t y_thread = get_global_id(1);
	size_t x = x_thread * SUBSAMPLE;
	size_t y = y_thread * SUBSAMPLE;
	if (x >= WIDTH|| y >= HEIGHT) {
		return;
	}
	__global uint *descrRow = descriptor + (y_thread*249+x_thread)*BASE_QUANT_SPACE;
	uint hist[BASE_QUANT_SPACE] = {0};
	size_t stop_x = x + WINSIZE;
	size_t stop_y = y + WINSIZE;
	for(size_t loc_x = x; loc_x < stop_x; loc_x+=SUBSAMPLE){
		for(size_t loc_y = y; loc_y < stop_y; loc_y+=SUBSAMPLE){
			int2 coord = (int2) (loc_x, loc_y);
			hist[read_imagei(input,sampler,coord).x] ++;
		}
	}
	for(int pos = 0; pos < BASE_QUANT_SPACE; pos++){
		descrRow[pos] += hist[pos] > 0;
	}
}

__kernel
void window_hist_p(__read_only image2d_t input, __global uint* descriptor){
	//size_t row = get_global_id(1);
	size_t x_thread = get_global_id(0);
	size_t x_window = x_thread * SUBSAMPLE;
	//size_t group_row = get_group_id(1);
	size_t colWithinGroup = get_local_id(0);
	if(x_window >= WIDTH){
		return;
	}
	__global uint *descrRow = descriptor + x_thread*BASE_QUANT_SPACE;
	uint slideHist[BASE_QUANT_SPACE];

	for(int ix = 0; ix < BASE_QUANT_SPACE; ix++){
		slideHist[ix] = 0;
	}
	size_t y, x, stop_at, add_y, del_y;
	int2 add_coord, del_coord;
	stop_at = x_window + WINSIZE;

	//fill in the first (top of image) full sliding window histograms
	for( y = 0; y < WINSIZE; y += SUBSAMPLE ){
		for(x = x_window; x < stop_at; x++){
			add_coord = (int2) (x,y);
			slideHist[read_imagei(input,sampler,add_coord).x] ++;
		}
	}

	// update histogram from first sliding window histograms
	for (int index = 0; index < BASE_QUANT_SPACE; index ++){
		descrRow[index] += slideHist[index] > 0;
	}

	// slide the window down the rest of the rows
	for(y = SUBSAMPLE; y < HEIGHT; y += SUBSAMPLE )
	{
		for(x = x_window; x < stop_at; x++){
			del_y = y - SUBSAMPLE;
			add_y = y + WINSIZE - SUBSAMPLE;
			del_coord = (int2) (x,del_y);
			add_coord = (int2) (x,add_y);
			slideHist[read_imagei(input,sampler,add_coord).x] ++;
			slideHist[read_imagei(input,sampler,del_coord).x] --;
		}

		// update histogram from sliding window histogram
		for (int index = 0; index < BASE_QUANT_SPACE; index ++){
			descrRow[index] += slideHist[index] > 0;
		}
	}
}

__kernel
void window_hist(__read_only image2d_t input, __global uint* descriptor){
	//size_t row = get_global_id(1);
	size_t x_thread = get_global_id(0);
	size_t x_window = x_thread * SUBSAMPLE;
	//size_t group_row = get_group_id(1);
	size_t colWithinGroup = get_local_id(0);
	int2 dims = get_image_dim(input);
	if(x_window >= WIDTH){
			return;
	}
	__local uint slideHistGroup[GROUP_SIZE][BASE_QUANT_SPACE];

	//__local uint descrGroup[GROUP_SIZE][BASE_QUANT_SPACE];
//	__local uint *slideHist = (__local uint *) slideHistGroup[colWithinGroup];
	__local uint *slideHist = ((__local uint *) slideHistGroup) + colWithinGroup*BASE_QUANT_SPACE;
	__global uint *descrRow = descriptor + x_thread*BASE_QUANT_SPACE;
	//uint slideHist[BASE_QUANT_SPACE];
	for(int ix = 0; ix < BASE_QUANT_SPACE; ix++){
		slideHist[ix] = 0;
	}
	size_t y, x, stop_at, add_y, del_y;
	int2 add_coord, del_coord;
	stop_at = x_window + WINSIZE;

	//fill in the first (top of image) full sliding window histograms
	for( y = 0; y < WINSIZE; y += SUBSAMPLE ){
		for(x = x_window; x < stop_at; x++){
			add_coord = (int2) (x,y);
			slideHist[read_imagei(input,sampler,add_coord).x] ++;
		}
	}

	// update histogram from first sliding window histograms
	for (int index = 0; index < BASE_QUANT_SPACE; index ++){
		descrRow[index] += slideHist[index] > 0;
	}

	// slide the window down the rest of the rows
	for(y = SUBSAMPLE; y < HEIGHT; y += SUBSAMPLE )
	{
		for(x = x_window; x < stop_at; x++){
			del_y = y - SUBSAMPLE;
			add_y = y + WINSIZE - SUBSAMPLE;
			del_coord = (int2) (x,del_y);
			add_coord = (int2) (x,add_y);
			slideHist[read_imagei(input,sampler,add_coord).x] ++;
			slideHist[read_imagei(input,sampler,del_coord).x] --;
		}

		// update histogram from sliding window histogram
		for (int index = 0; index < BASE_QUANT_SPACE; index ++){
			descrRow[index] += slideHist[index] > 0;
		}
	}
}

int quantizeHMMDPixel(int4 px,
__constant short* diffThresh, __constant uchar* nHueLevels,
		__constant uchar* nSumLevels, __constant uchar* nCumLevels){
	int H = px.x;
	int S = px.y;
	int D = px.z;
	// Note: lower threshold boundary is inclusive,
	// i.e. diffThresh[..][m] <= (D of subspace m) < diffThresh[..][m+1]

	// Quantize the Difference component, find the Subspace
	int iSub = 0;
	//TODO: optimize
	while (diffThresh[iSub + 1] <= D)
		iSub++;
	//write_imageui(output,coord,D);


	// Quantize the Hue component
	int Hindex = (int) ((H / 360.0f) * nHueLevels[iSub]);
	//TODO: swap 0 and 360 in HMMD conversion or just subtract 1 instead of doing the check
	if (H == 360)
		Hindex = 0;

	short curDiffThresh = diffThresh[iSub];
	uchar curSumLevel = nSumLevels[iSub];

	// Quantize the Sum component
	// The min value of Sum in a subspace is 0.5*diffThresh (see HMMD slice)
	int Sindex = (int)(((float)S - 0.5f * curDiffThresh)
						* curSumLevel
						/ (255.0f - curDiffThresh));
	if (Sindex >= curSumLevel)
		Sindex = curSumLevel - 1;

	/* The following quantization of Sum is more uniform and doesn't require the bounds check
	 int Sindex = (int)floor((S - 0.5*diffThresh[quant_index][iSub])
	 * nSumLevels[quant_index][iSub]
	 / (256 - diffThresh[quant_index][iSub]));
	 */

	return nCumLevels[iSub] + Hindex * curSumLevel + Sindex;
}

__kernel
void quantize_HMMD(__read_only image2d_t input, __write_only image2d_t output,
__constant short* diffThresh, __constant uchar* nHueLevels,
		__constant uchar* nSumLevels, __constant uchar* nCumLevels) {
	size_t x = get_global_id(0);
	size_t y = get_global_id(1);
	int2 dims = get_image_dim(input);
	if (x >= dims.x || y >= dims.y) {
		return;
	}
	int2 coord = (int2) (x, y);
	int4 px = read_imagei(input, sampler, coord);
	int result = quantizeHMMDPixel(px,diffThresh,nHueLevels,nSumLevels,nCumLevels);
	write_imageui(output,coord,result);
}

__kernel
void quantize_HMMD2(__read_only image2d_t input, __write_only image2d_t output,
__constant short* diffThresh, __constant uchar* nHueLevels,
		__constant uchar* nSumLevels, __constant uchar* nCumLevels) {
	size_t x = get_global_id(0);
	size_t y = get_global_id(1);
	int2 dims = get_image_dim(input);
	if (x >= dims.x || y >= dims.y) {
		return;
	}
	int2 coord = (int2) (x, y);
	int4 px = read_imagei(input, sampler, coord);
	int H = px.x;
	int S = px.y;
	int D = px.z;
	// Note: lower threshold boundary is inclusive,
	// i.e. diffThresh[..][m] <= (D of subspace m) < diffThresh[..][m+1]

	// Quantize the Difference component, find the Subspace
	int iSub = 0;
	//TODO: optimize
	while (diffThresh[iSub + 1] <= D)
		iSub++;
	//write_imageui(output,coord,D);


	// Quantize the Hue component
	int Hindex = (int) (((float)H / 360.0f) * nHueLevels[iSub]);
	//TODO: swap 0 and 360 in HMMD conversion or just subtract 1 instead of doing the check
	if (H == 360)
		Hindex = 0;

	short curDiffThresh = diffThresh[iSub];
	uchar curSumLevel = nSumLevels[iSub];

	// Quantize the Sum component
	// The min value of Sum in a subspace is 0.5*diffThresh (see HMMD slice)
	int Sindex = (int)(((float)S - 0.5f * curDiffThresh)
						* curSumLevel
					    / (255.0f - curDiffThresh));
	if (Sindex >= curSumLevel)
		Sindex = curSumLevel - 1;

	/* The following quantization of Sum is more uniform and doesn't require the bounds check
	 int Sindex = (int)floor((S - 0.5*diffThresh[quant_index][iSub])
	 * nSumLevels[quant_index][iSub]
	 / (256 - diffThresh[quant_index][iSub]));
	 */

	int result = nCumLevels[iSub] + Hindex * curSumLevel + Sindex;
	write_imageui(output,coord,result);
}
