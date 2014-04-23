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
#define WINSIZE 8
#endif

#define WINSIZE 8
#define REGION_SIZE 256
#define CUTOFF_RS 249

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



/**
 * Determines the quant/level for the given HMMD pixel according to the provided thresholds
 * @param px - the given HMMD pixel, expressed as HSD (Hue, Sum, Difference)
 * @param diffThresh - the set of difference thresholds to determine the quant
 * @param nHueLevels - a lookup table of hue level numbers to use in quantization
 * @param nSumLevels - a lookup table of sum level numbers to use in quantization
 * @param nCumLevels - a lookup table of cumulative level numbers to use in quantization
 * @return an integer representing the quant for the HMMD pixel, in range [0,255]
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
	if (H == 360.0f)
		Hindex = 0.0f;

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
	int R, G, B;
	R = px.x;
	G = px.y;
	B = px.z;
	int4 out = convertPixelToHMMD(R,G,B);
	write_imagei(output, coord, out);
}

/**
 * Quantize the whole HMMD image
 */
__kernel
void quantize_HMMD(__read_only image2d_t input, __write_only image2d_t output,
__constant short* diffThresh, __constant uchar* nHueLevels,
		__constant uchar* nSumLevels, __constant uchar* nCumLevels){
	size_t x = get_global_id(0);
	size_t y = get_global_id(1);
	int2 dims = get_image_dim(input);
	if (x >= dims.x || y >= dims.y) {
		return;
	}
	int2 coord = (int2) (x, y);
	int4 px = read_imagei(input, sampler, coord);
	int result = quantizeHMMDPixel(px, diffThresh, nHueLevels,nSumLevels,nCumLevels);
	write_imageui(output,coord,result);
}


__kernel
void imageToHMMDQuants(__read_only image2d_t image,
		__write_only image2d_t output,
		__constant short* diffThresh, __constant uchar* nHueLevels,
		__constant uchar* nSumLevels, __constant uchar* nCumLevels){
	size_t x = get_global_id(0);
	size_t y = get_global_id(1);
	int2 dims = get_image_dim(image);
	if (x >= dims.x || y >= dims.y) {
		return;
	}
	int2 coord = (int2) (x, y);
	int4 px = read_imagei(image, sampler, coord);
	int R, G, B;
	R = px.x;
	G = px.y;
	B = px.z;
	int4 hmmd = convertPixelToHMMD(R,G,B);
	int result = quantizeHMMDPixel(hmmd, diffThresh, nHueLevels,nSumLevels,nCumLevels);
	write_imageui(output,coord,result);
}

/**
 * Faster (Image rather than buffer) version
 * reads histograms for each window-length string starting with every pixel of every row and spanning horizontally
 * TODO: any way to speed this up even further?
 */
__kernel
void csDescriptorRowBitstrings(__read_only image2d_t input, __write_only image2d_t output){
	//each thread does one row
	size_t y = get_global_id(0);
	int2 dims = get_image_dim(input);
	if(y >= dims.y){
		return;
	}
	uchar slideHist[256] = {0};
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
		slideHist[bin]++;
	}
	write_imageui(output,(int2)(y,0),(uint4)(bitstring[0],bitstring[1],bitstring[2],bitstring[3]));
	write_imageui(output,(int2)(y,1),(uint4)(bitstring[4],bitstring[5],bitstring[6],bitstring[7]));
	int x = 0;
	int ixOut;
#pragma unroll
	for(xProbe = WINSIZE; xProbe < dims.x; xProbe++){
		bin = read_imageui(input,sampler,(int2) (x, y)).x;
		if(!(--slideHist[bin])){
			idxUint = bin >> 5; //same as division by 32
			idxBit = bin - (idxUint << 5);//same as modulo division by 32
			bitstring[idxUint] &= ~(1 << idxBit);
		}
		bin = read_imageui(input,sampler,(int2) (xProbe, y)).x;
		slideHist[bin]++;
		idxUint = bin >> 5; //same as division by 32
		idxBit = bin - (idxUint << 5);//same as modulo division by 32
		bitstring[idxUint] |= (1 << idxBit);
		++x;
		ixOut = (x << 1);
		write_imageui(output,(int2)(y,ixOut),(uint4)(bitstring[0],bitstring[1],bitstring[2],bitstring[3]));
		write_imageui(output,(int2)(y,ixOut+1),(uint4)(bitstring[4],bitstring[5],bitstring[6],bitstring[7]));
	}
}

/**
 * Speedup: 20% over brute-force, TODO - figure out the bug, result doesn't completely match the brute-force version
 */
__kernel
void csDescriptorWindowBitstringsCache(__read_only image2d_t input, __write_only image2d_t output){
	//transpose thread directions (x refers to horizontal direction in original image)
	size_t x = get_global_id(0);
	int2 dims = get_image_dim(input);
	if(x >= dims.y){
		return;
	}
	size_t x_lower = x << 1;
	size_t x_upper = x_lower + 1;
	uint4 aggLower = (uint4)(0,0,0,0);
	uint4 aggUpper = (uint4)(0,0,0,0);
	uint4 upper, lower;
	uint4 lBitCache[WINSIZE];
	uint4 uBitCache[WINSIZE];
	int cacheIns;
#pragma unroll
	for(int y = 0; y < WINSIZE; y++){
		lower = read_imageui(input,sampler,(int2) (y, x_lower));
		upper = read_imageui(input,sampler,(int2) (y, x_upper));
		lBitCache[y] = lower;
		uBitCache[y] = upper;
		aggLower |= lower;
		aggUpper |= upper;
	}
	//write the first bitstring
	write_imageui(output,(int2)(x,0),aggLower);
	write_imageui(output,(int2)(x,1),aggUpper);

	int yIns = 1;

#pragma unroll
	for(int y = WINSIZE; y < dims.x; y++,yIns++){
		aggLower = (uint4)(0,0,0,0);
		aggUpper = (uint4)(0,0,0,0);
		cacheIns = y%WINSIZE;
		lBitCache[cacheIns] = read_imageui(input,sampler,(int2) (y, x_lower));
		uBitCache[cacheIns] = read_imageui(input,sampler,(int2) (y, x_upper));

		for(int row = 0; row < WINSIZE; row ++){
			aggLower |= lBitCache[row];
			aggUpper |= uBitCache[row];
		}
		write_imageui(output,(int2)(yIns,x_lower),aggLower);
		write_imageui(output,(int2)(yIns,x_upper),aggUpper);
	}
}

__kernel
void csDescriptorWindowBitstringsBrute(__read_only image2d_t input, __write_only image2d_t output){
	//transpose thread directions
	size_t x = get_global_id(0);
	int2 dims = get_image_dim(input);
	if(x >= dims.y){
		return;
	}
	size_t x_lower = x << 1;
	size_t x_upper = x_lower + 1;
	uint4 aggLower, aggUpper;
	int gStopAt = dims.x - WINSIZE;
	//gStopAt = 4;
#pragma unroll
	for(int yg = 0; yg <= gStopAt; yg++){
		int stopBefore = yg+WINSIZE;
		aggLower = (uint4)(0,0,0,0);
		aggUpper = (uint4)(0,0,0,0);
		for(int y = yg; y < stopBefore; y++){
			aggLower |= read_imageui(input,sampler,(int2) (y, x_lower));
			aggUpper |= read_imageui(input,sampler,(int2) (y, x_upper));
		}
		write_imageui(output,(int2)(yg,x_lower),aggLower);
		write_imageui(output,(int2)(yg,x_upper),aggUpper);
	}
}


void bitstringToHist(ushort* slideHist,uint4 lower,uint4 upper){
	for (int ixBit = 0; ixBit < 32; ixBit++){
		slideHist[ixBit] += (lower.x >> ixBit) & 1;
	}
	for (int ixBit = 0; ixBit < 32; ixBit++){
		slideHist[ixBit+32] += (lower.y >> ixBit) & 1;
	}
	for (int ixBit = 0; ixBit < 32; ixBit++){
		slideHist[ixBit+64] += (lower.z >> ixBit) & 1;
	}
	for (int ixBit = 0; ixBit < 32; ixBit++){
		slideHist[ixBit+96] += (lower.w >> ixBit) & 1;
	}
	for (int ixBit = 0; ixBit < 32; ixBit++){
		slideHist[ixBit+128] += (upper.x >> ixBit) & 1;
	}
	for (int ixBit = 0; ixBit < 32; ixBit++){
		slideHist[ixBit+160] += (upper.y >> ixBit) & 1;
	}
	for (int ixBit = 0; ixBit < 32; ixBit++){
		slideHist[ixBit+192] += (upper.z >> ixBit) & 1;
	}
	for (int ixBit = 0; ixBit < 32; ixBit++){
		slideHist[ixBit+224] += (upper.w >> ixBit) & 1;
	}
}




__kernel
void csDescriptorsBrute(__read_only image2d_t input, __global ushort* output){
	//y direction of input, x coordinate of the upper-left corner of the region in original image
	size_t x_region = get_global_id(0);
	int2 dimsBitstrings = get_image_dim(input);
	int width = dimsBitstrings.x >> 1;
	int height = dimsBitstrings.y;
	uint4 lower, upper;

	ushort slideHist[256] = {0};
	int xStartWidth = x_region << 1;
	int xStopAt = (x_region + CUTOFF_RS) << 1;
	__global ushort* histAt = output + x_region * width;

	for(int y = 0; y < CUTOFF_RS; y++){
		for(int x = xStartWidth; x < xStopAt; x+=2){
			lower = read_imageui(input,sampler,(int2) (y, x));
			upper = read_imageui(input,sampler,(int2) (y, x+1));
			bitstringToHist(slideHist,lower,upper);
		}

	}

}



