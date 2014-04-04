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
#endif

__constant sampler_t sampler = CLK_NORMALIZED_COORDS_FALSE | CLK_ADDRESS_CLAMP_TO_EDGE | CLK_FILTER_NEAREST;

__kernel
void convert_to_HMMD(__read_only image2d_t image, __write_only image2d_t output) {
	size_t x = get_global_id(0);
	size_t y = get_global_id(1);
	int2 dims = get_image_dim(image);
	if(x > dims.x || y > dims.y){
		return;
	}
	int2 coord = (int2)(x,y);
	int4 px = read_imagei(image,sampler,coord);
	int4 out;
	float hue;
	int R,G,B,a,d;
	R = px.x;
	G = px.y;
	B = px.z;
	if(R < G){
		if(G < B){
			//B is max,R is min
			a = B+R;
			d = B-R;
			hue = (4.0f+((float)(R - G))/d);
		}else{
			//G is max or G == B
			if(R < B){
				//R is min
				a = G+R;
				d = G-R;
				hue=(2.0f+((float)(B - R))/d);
			}else{
				//B is min or R == B
				a = G+B;
				d = G-B;
				hue=(2.0f+((float)(B - R))/d);

			}
		}
		hue*=60;
		if(hue<0.0){ hue+=360;}
	}else{
		if(B < R){
			//R is max or R == G
			if(B < G){
				//B is min
				a = R+B;
				d = R-B;
				hue=(((float)(G - B))/d);
			}else{
				//G is min or (B == G and R is max for sure)
				a = R+G;
				d = R-G;
				hue=(((float)(G - B))/d);

			}
			hue*=60;
			if(hue<0.0f){ hue+=360;}
		}else{
			//G <= R <= B
			if(G < B){
				//B is max or B == R
				//G is min
				a = B+G;
				d = B-G;
				hue = (4.0f+((float)(R - G))/d);
				hue*=60;
				if(hue<0.0f){ hue+=360;}
			}else{
				//G == R == B
				hue = -1.5f;//undefined
			}
		}
	}

	out.x = (int)(hue + 0.5);			//range [0,360], -1=undefined
	out.y = (int)(((a+1)>>1));			//range [0,255]
	out.z = (int)d;						//range [0,255]
	write_imagei(output,coord,out);

}
