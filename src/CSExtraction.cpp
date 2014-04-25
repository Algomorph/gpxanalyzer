#include <CSExtraction.hpp>

namespace gpxa{
const double
amplThresh[] = {0.0, 0.000000000001, 0.037, 0.08, 0.195, 0.32};
const int
nAmplLevels[] = {1, 25, 20, 35, 35, 140};

void bitstringsToHistogram(uint64* arr, uint16* hist, int width, int x, int y){
	//pointing at the first relevant bitstring
	uint64* bitdataRowStart = arr + ((y*width + x) << 2);
	int uint64width = width << 2;
	for(int yR = 0; yR < REGION_CLIP; yR++){
		unsigned long long* rowEnd = bitdataRowStart + ((REGION_CLIP) <<2);
		for(unsigned long long* cursor = bitdataRowStart; cursor < rowEnd; cursor+=4){
			//traverse each bit of the 256-bit-long bitstring by splitting up into 4 bitsets
			std::bitset<64> a(*cursor);
			std::bitset<64> b(*(cursor+1));
			std::bitset<64> c(*(cursor+2));
			std::bitset<64> d(*(cursor+3));
			for(int bit = 0; bit < 64; bit++){
				hist[bit] += a.test(bit);
			}
			for(int bit = 0; bit < 64; bit++){
				hist[bit+64] += b.test(bit);
			}
			for(int bit = 0; bit < 64; bit++){
				hist[bit+128] += c.test(bit);
			}
			for(int bit = 0; bit < 64; bit++){
				hist[bit+192] += d.test(bit);
			}
		}
		bitdataRowStart += uint64width;
	}
}
void quantAmplNonLinear(uint16* hist, uint8* histOut){
	unsigned long iBin, iQuant;
	const int nAmplLinearRegions = sizeof(nAmplLevels)/sizeof(nAmplLevels[0]);
	int nTotalLevels = 0;

	// Calculate total levels
	for (iQuant = 0; iQuant < nAmplLinearRegions; iQuant++){
		nTotalLevels += nAmplLevels[iQuant];
	}

	// Loop through bins
	for ( iBin = 0; iBin < BASE_QUANT_SPACE; iBin ++){
		// Get bin amplitude
		double val = hist[iBin];

		// Normalize
		val /= REGION_NORM;
		assert (val>=0.0); assert (val<= 1.0);

		// Find quantization boundary and base value
		int quantValue = 0;
		for (iQuant = 0; iQuant+1 < nAmplLinearRegions; iQuant++ ){
			if (val < amplThresh[iQuant+1])
				break;
			quantValue += nAmplLevels[iQuant];
		}

		// Quantize
		double nextThresh = (iQuant+1 < nAmplLinearRegions) ? amplThresh[iQuant+1] : 1.0;
		val = floor(quantValue +
					(val - amplThresh[iQuant]) *
					(nAmplLevels[iQuant] / (nextThresh - amplThresh[iQuant])));

		// Limit (and alert), one bin contains all of histogram
		if (val == nTotalLevels){
			val = nTotalLevels - 1;
		}
		assert(val >= 0.0); assert(val < nTotalLevels);

		// Set value into histogram
		histOut[iBin]=(uint8)val;
	}
}

}//end namespace gpxa

