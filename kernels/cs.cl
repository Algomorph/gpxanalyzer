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
#define GROUP_WIDTH 8
#define REGION_WIDTH 256
#define REGION_GROUP_COUNT 32 //REGION_WIDTH / GROUP_WIDTH
#define ITEMS_PER_QUANT_DESCR 32 //BASE_QUANT_SPACE / GROUP_WIDTH
#define REGION_HEIGHT 256
#define CUTOFF_WIDTH 249
#define CUTOFF_HEIGHT 249
#define SUBSAMPLE 3
#define WINSIZE 64
#endif

#define WINSIZE 8

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
	if (x >= CUTOFF_WIDTH|| y >=CUTOFF_HEIGHT) {
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
	if(x_window >= CUTOFF_WIDTH){
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
	for(y = SUBSAMPLE; y < CUTOFF_HEIGHT; y += SUBSAMPLE )
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
	if(x_window >= CUTOFF_WIDTH){
			return;
	}
	__local uint slideHistGroup[GROUP_WIDTH][BASE_QUANT_SPACE];

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
	for(y = SUBSAMPLE; y < CUTOFF_HEIGHT; y += SUBSAMPLE )
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



/**
 * Determines the quant/level for the given HMMD pixel according to the provided thresholds
 */
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
void convert_to_hmmd_and_quantize(__read_only image2d_t image,
		__write_only image2d_t output, __constant short* diffThresh, __constant uchar* nHueLevels,
		__constant uchar* nSumLevels, __constant uchar* nCumLevels){
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
	int4 hmmd = convertPixelToHMMD(R,G,B);
	int result = quantizeHMMDPixel(px, diffThresh, nHueLevels,nSumLevels,nCumLevels);
	write_imageui(output,coord,result);
}

uint4 histToBinDescriptor(uint* hist){
	uint4 res;
	for(int bin = 0; bin < 32; bin++, hist++){
		if(*hist > 0){
			res.x |= (long)(1 << bin);
		}
	}
	for(int bin = 0; bin < 32; bin++, hist++){
		if(*hist > 0){
			res.y |= (long)(1 << bin);
		}
	}
	for(int bin = 0; bin < 32; bin++, hist++){
		if(*hist > 0){
			res.z |= (long)(1 << bin);
		}
	}
	for(int bin = 0; bin < 32; bin++, hist++){
		if(*hist > 0){
			res.w |= (long)(1 << bin);
		}
	}
	return res;
}
/**
 * Faster (Image) version
 */
__kernel
void csDescriptorBitstringsImage(__read_only image2d_t input, __write_only image2d_t output){
	//each thread does one row
	size_t y = get_global_id(0);
	int2 dims = get_image_dim(input);
	if(y >= dims.y){
		return;
	}
	//uint slideHist[256] = {0};
	uint bitstring[8] = {0};
	//TODO: try to spead up by caching the reads, or using local memory to store intermediate result?
	//uint cache[8];
	//fill in the first window's row histogram
	int xProbe = 0;

	uint bin, idxUint, idxBit;

	//horizontal pass - compute row-wise histogram bitstrings (scan 1D horizontal areas of window-width for each pixel)
#pragma unroll
	for (; xProbe < WINSIZE; xProbe++){
		bin = read_imageui(input,sampler,(int2) (xProbe, y)).x;
		idxUint = bin >> 5;
		idxBit = bin - (idxUint << 5);
		bitstring[idxUint] |= (1 << idxBit);
	}
	write_imageui(output,(int2)(y,0),(uint4)(bitstring[0],bitstring[1],bitstring[2],bitstring[3]));
	write_imageui(output,(int2)(y,1),(uint4)(bitstring[4],bitstring[5],bitstring[6],bitstring[7]));
	int x = 0;
	int ixOut;
#pragma unroll
	for(xProbe = 8; xProbe < dims.x; xProbe++){
		bin = read_imageui(input,sampler,(int2) (x, y)).x;
		idxUint = bin >> 5; //same as division by 32
		idxBit = bin - (idxUint << 5);//same as modulo division by 32
		bitstring[idxUint] &= ~(1 << idxBit);
		bin = read_imageui(input,sampler,(int2) (xProbe, y)).x;
		idxUint = bin >> 5; //same as division by 32
		idxBit = bin - (idxUint << 5);//same as modulo division by 32
		bitstring[idxUint] |= (1 << idxBit);
		++x;
		ixOut = (x << 1);
		write_imageui(output,(int2)(y,ixOut),(uint4)(bitstring[0],bitstring[1],bitstring[2],bitstring[3]));
		write_imageui(output,(int2)(y,ixOut+1),(uint4)(bitstring[4],bitstring[5],bitstring[6],bitstring[7]));
	}
}

__kernel
void csDescriptorBitstringsWindow(__read_only image2d_t input, __write_only image2d_t output){
	//transpose thread directions
	size_t x = get_global_id(0);
	int2 dims = get_image_dim(input);
	if(x >= dims.x){
		return;
	}
	uint4 aggLower = (uint4)(0,0,0,0);
	uint4 aggUpper = (uint4)(0,0,0,0);
	uint4 upper, lower;
	uint4 bitCache[16];
#pragma unroll
	for(int y = 0; y < (WINSIZE<<1); y+=2){
		lower = read_imageui(input,sampler,(int2) (x, y));
		upper =  read_imageui(input,sampler,(int2) (x, y+1));
		bitCache[y] = lower &= ~aggLower;
		bitCache[y+1] = lower &= ~aggUpper;
		aggLower |= lower;
		aggUpper |= upper;
	}
	//write the first bitstring
	write_imageui(output,(int2)(x,0),aggLower);
	write_imageui(output,(int2)(x,1),aggUpper);
	int del_y = 0;
#pragma unroll
	for(int y = (WINSIZE<<1); y < dims.y; y+=2){

		aggLower |= read_imageui(input,sampler,(int2) (x, y));
		aggUpper |= read_imageui(input,sampler,(int2) (x, y));
		del_y+=2;
		write_imageui(output,(int2)(x,del_y),aggLower);
		write_imageui(output,(int2)(x,del_y+1),aggUpper);
	}
}/**
 * Slower (Buffer) version
 */
__kernel
void csDescriptorBitstringsBuffer(__read_only image2d_t input, __global uint* output){
	//each thread does one row
	size_t y = get_global_id(0);
	int2 dims = get_image_dim(input);
	if(y >= dims.y){
		return;
	}
	//uint slideHist[256] = {0};
	uint bitstring[8] = {0};
	//TODO: try to spead up by caching the reads, or using local memory to store intermediate result
	//uint cache[8];
	//fill in the first window's row histogram
	int xProbe = 0;
	__global uint* out = output + (dims.x << 3)*y;
	uint bin, idxUint, idxBit;
#pragma unroll
	for (; xProbe < 8; xProbe++){
		bin = read_imageui(input,sampler,(int2) (xProbe, y)).x;
		idxUint = bin >> 5;
		idxBit = bin - (idxUint << 5);
		bitstring[idxUint] |= (1 << idxBit);
	}
#pragma unroll
	for (int ixUint = 0; ixUint < 8; ixUint++){
		out[ixUint] = bitstring[ixUint];
	}
	out+=8;
	int x = 0;
	int ixOut;
	for(xProbe = 8; xProbe < dims.x; xProbe++){
		bin = read_imageui(input,sampler,(int2) (x, y)).x;
		idxUint = bin >> 5; //same as division by 32
		idxBit = bin - (idxUint << 5);//same as modulo division by 32
		bitstring[idxUint] &= ~(1 << idxBit);
		bin = read_imageui(input,sampler,(int2) (xProbe, y)).x;
		idxUint = bin >> 5; //same as division by 32
		idxBit = bin - (idxUint << 5);//same as modulo division by 32
		bitstring[idxUint] |= (1 << idxBit);
		++x;
#pragma unroll
		for (int ixUint = 0; ixUint < 8; ixUint++){
			out[ixUint] = bitstring[ixUint];
		}
		out += 8;
	}
