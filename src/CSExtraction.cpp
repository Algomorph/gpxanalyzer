#include <CSExtraction.hpp>

namespace gpxa {
const double amplThresh[] = { 0.0, 0.000000000001, 0.037, 0.08, 0.195, 0.32 };
const int nAmplLevels[] = { 1, 25, 20, 35, 35, 140 };
static int nTotalLevels = 0;

void precomputeTotalLevels(){
	const int nAmplLinearRegions = sizeof(nAmplLevels) / sizeof(nAmplLevels[0]);
	// Calculate total levels
	for (int iQuant = 0; iQuant < nAmplLinearRegions; iQuant++) {
		nTotalLevels += nAmplLevels[iQuant];
	}
}

void bitstringsToHistogram(uint64_t* arr, uint16_t* hist, int width, int x,
		int y) {
	//pointing at the first relevant bitstring
	uint64_t* bitdataRowStart = arr + ((y * width + x) << 2);
	const int uint64_twidth = width << 2;
	for (int yR = 0; yR < REGION_CLIP; yR++) {
		uint64_t* rowEnd = bitdataRowStart + ((REGION_CLIP) << 2);
		for (uint64_t* cursor = bitdataRowStart; cursor < rowEnd; cursor += 4) {
			//traverse each bit of the 256-bit-long bitstring by splitting up into 4 bitsets
			std::bitset<64> a(*cursor);
			std::bitset<64> b(*(cursor + 1));
			std::bitset<64> c(*(cursor + 2));
			std::bitset<64> d(*(cursor + 3));
			for (int bit = 0; bit < 64; bit++) {
				hist[bit] += a.test(bit);
			}
			for (int bit = 0; bit < 64; bit++) {
				hist[bit + 64] += b.test(bit);
			}
			for (int bit = 0; bit < 64; bit++) {
				hist[bit + 128] += c.test(bit);
			}
			for (int bit = 0; bit < 64; bit++) {
				hist[bit + 192] += d.test(bit);
			}
		}
		bitdataRowStart += uint64_twidth;
	}
}
void quantAmplNonLinear(uint16_t* hist, uint8_t* histOut) {
	unsigned long iBin, iQuant;
	const int nAmplLinearRegions = sizeof(nAmplLevels) / sizeof(nAmplLevels[0]);

	// Loop through bins
	for (iBin = 0; iBin < BASE_QUANT_SPACE; iBin++) {
		// Get bin amplitude
		double val = hist[iBin];

		// Normalize
		val /= REGION_NORM;

		// Find quantization boundary and base value
		int quantValue = 0;
		for (iQuant = 0; iQuant + 1 < nAmplLinearRegions; iQuant++) {
			if (val < amplThresh[iQuant + 1])
				break;
			quantValue += nAmplLevels[iQuant];
		}

		// Quantize
		double nextThresh =
				(iQuant + 1 < nAmplLinearRegions) ?
						amplThresh[iQuant + 1] : 1.0;
		val = floor(
				quantValue
						+ (val - amplThresh[iQuant])
								* (nAmplLevels[iQuant]
										/ (nextThresh - amplThresh[iQuant])));

		// Limit (and alert), one bin contains all of histogram
		if (val == nTotalLevels) {
			val = nTotalLevels - 1;
		}

		// Set value into histogram
		histOut[iBin] = (uint8_t) val;
	}
}

void bitstringsSlidingHistogram(uint64_t* arr, uint8_t* descriptors,
		const int width, const int height) {
	//pointing at the first relevant bitstring

	const int uint64_twidth = width << 2;
	const int stopAtY = height - REGION_SIZE + 1;
	const int stopAtX = width - REGION_SIZE + 1;
	const int histShift = (const int) log((float) BASE_QUANT_SPACE) / log(2)
			+ 1;
	const int histsWidth = stopAtX << histShift;

	for (int xR = 0; xR < stopAtX; xR++) {
		/*clean out the sliding histogram at the top of each column*/
		uint16_t slidingHist[BASE_QUANT_SPACE] = { 0 };
		uint64_t* bitdataRowStart = arr + (xR << 2);
		uint64_t* bitdataRowSubStart = bitdataRowStart;
		uint64_t* stopAtRow = bitdataRowStart + REGION_CLIP * uint64_twidth;
		/*first histogram in this column*/
		for (; bitdataRowStart < stopAtRow; bitdataRowStart += uint64_twidth) {
			uint64_t* rowEnd = bitdataRowStart + ((REGION_CLIP) << 2);
			for (uint64_t* cursor = bitdataRowStart; cursor < rowEnd; cursor +=
					4) {
				histAddFromBits(cursor, slidingHist);
			}
		}
		//determine location of descriptor
		uint8_t* descrAt = descriptors + (xR << histShift);
		quantAmplNonLinear(slidingHist, descrAt);
		//determine stopping row
		stopAtRow = bitdataRowStart + (stopAtY - 1) * uint64_twidth;

		descrAt += histsWidth;
		//slide over the rest of the rows, removing the first row and adding the next one

		for (; bitdataRowStart < stopAtRow;
				bitdataRowStart += uint64_twidth, bitdataRowSubStart +=
						uint64_twidth, descrAt += histsWidth) {
			uint64_t* rowEnd = bitdataRowStart + ((REGION_CLIP) << 2);
			for (uint64_t* cursorAdd = bitdataRowStart, *cursorSub =
					bitdataRowSubStart; cursorAdd < rowEnd;
					cursorAdd += 4, cursorSub += 4) {
				histAddFromBits(cursorAdd, slidingHist);
				histSubtractFromBits(cursorSub, slidingHist);
			}
			quantAmplNonLinear(slidingHist, descrAt);
		}
	}
}
void bitstringsSlidingHistogramMT(uint64_t* arr, uint8_t* descriptors,
		const int width, const int height) {
	//pointing at the first relevant bitstring

	int uint64_twidth = width << 2;

	const int stopAtY = height - REGION_SIZE + 1;
	const int stopAtX = width - REGION_SIZE + 1;
	const int histShift = (const int) log((float) BASE_QUANT_SPACE) / log(2)
			+ 1;
	const int histsWidth = stopAtX << histShift;
#pragma omp parallel for
	for (int xR = 0; xR < stopAtX; xR++) {

		/*clean out the sliding histogram at the top of each column*/
		uint16_t slidingHist[BASE_QUANT_SPACE] = { 0 };
		uint64_t* bitdataRowStart = arr + (xR << 2);

		uint64_t* bitdataRowSubStart = bitdataRowStart;
		uint64_t* stopAtRow = bitdataRowStart + REGION_CLIP * uint64_twidth;
		/*first histogram in this column*/
		for (; bitdataRowStart < stopAtRow; bitdataRowStart += uint64_twidth) {
			uint64_t* rowEnd = bitdataRowStart + ((REGION_CLIP) << 2);
			for (uint64_t* cursor = bitdataRowStart; cursor < rowEnd; cursor +=
					4) {
				histAddFromBits(cursor, slidingHist);
			}
		}
		//determine location of descriptor
		uint8_t* descrAt = descriptors + (xR << histShift);
		quantAmplNonLinear(slidingHist, descrAt);
		//determine stopping row
		stopAtRow = bitdataRowStart + (stopAtY - 1) * uint64_twidth;

		descrAt += histsWidth;
		//slide over the rest of the rows, removing the first row and adding the next one

		for (; bitdataRowStart < stopAtRow;
				bitdataRowStart += uint64_twidth, bitdataRowSubStart +=
						uint64_twidth, descrAt += histsWidth) {
			uint64_t* rowEnd = bitdataRowStart + ((REGION_CLIP) << 2);
			for (uint64_t* cursorAdd = bitdataRowStart, *cursorSub =
					bitdataRowSubStart; cursorAdd < rowEnd;
					cursorAdd += 4, cursorSub += 4) {
				histAddFromBits(cursorAdd, slidingHist);
				histSubtractFromBits(cursorSub, slidingHist);
			}
			quantAmplNonLinear(slidingHist, descrAt);
		}
	}
}

void bitstringsSlidingHistogramMTFP(uint64_t* arr, uint8_t* descriptors,
		void (*histAdd)(uint64_t*, uint16_t*),
		void (*histSub)(uint64_t*, uint16_t*), const int width,
		const int height) {
	//pointing at the first relevant bitstring

	int uint64_twidth = width << 2;

	const int stopAtY = height - REGION_SIZE + 1;
	const int stopAtX = width - REGION_SIZE + 1;
	const int histShift = (const int) log((float) BASE_QUANT_SPACE) / log(2)
			+ 1;
	const int histsWidth = stopAtX << histShift;
#pragma omp parallel for
	for (int xR = 0; xR < stopAtX; xR++) {

		/*clean out the sliding histogram at the top of each column*/
		uint16_t slidingHist[BASE_QUANT_SPACE] = { 0 };
		uint64_t* bitdataRowStart = arr + (xR << 2);

		uint64_t* bitdataRowSubStart = bitdataRowStart;
		uint64_t* stopAtRow = bitdataRowStart + REGION_CLIP * uint64_twidth;
		/*first histogram in this column*/
		for (; bitdataRowStart < stopAtRow; bitdataRowStart += uint64_twidth) {
			uint64_t* rowEnd = bitdataRowStart + ((REGION_CLIP) << 2);
			for (uint64_t* cursor = bitdataRowStart; cursor < rowEnd; cursor +=
					4) {
				histAdd(cursor, slidingHist);
			}
		}
		//determine location of descriptor
		uint8_t* descrAt = descriptors + (xR << histShift);
		quantAmplNonLinear(slidingHist, descrAt);
		//determine stopping row
		stopAtRow = bitdataRowStart + (stopAtY - 1) * uint64_twidth;

		descrAt += histsWidth;
		//slide over the rest of the rows, removing the first row and adding the next one

		for (; bitdataRowStart < stopAtRow;
				bitdataRowStart += uint64_twidth, bitdataRowSubStart +=
						uint64_twidth, descrAt += histsWidth) {
			uint64_t* rowEnd = bitdataRowStart + ((REGION_CLIP) << 2);
			for (uint64_t* cursorAdd = bitdataRowStart, *cursorSub =
					bitdataRowSubStart; cursorAdd < rowEnd;
					cursorAdd += 4, cursorSub += 4) {
				histAdd(cursorAdd, slidingHist);
				histSub(cursorSub, slidingHist);
			}
			quantAmplNonLinear(slidingHist, descrAt);
		}
	}
}
void bitstringsSlidingHistogramMTBasic(uint64_t* arr, uint8_t* descriptors,
		const int width, const int height){
	bitstringsSlidingHistogramMTFP(arr, descriptors,&histAddFromBits,&histSubtractFromBits,width,height);
}
void bitstringsSlidingHistogramMTMaskLSB(uint64_t* arr, uint8_t* descriptors,
		const int width, const int height){
	bitstringsSlidingHistogramMTFP(arr, descriptors,&histAddFromBitsMaskLSB,&histSubtractFromBitsMaskLSB,width,height);
}
void bitstringsSlidingHistogramMTVecExt(uint64_t* arr, uint8_t* descriptors,
		const int width, const int height){
	bitstringsSlidingHistogramMTFP(arr, descriptors,&histAddFromBitsVecExt,&histSubtractFromBitsVecExt,width,height);
}
void bitstringsSlidingHistogramMTMatthews(uint64_t* arr, uint8_t* descriptors,
		const int width, const int height){
	bitstringsSlidingHistogramMTFP(arr, descriptors,&histAddFromBitsMatthews,&histSubtractFromBitsMatthews,width,height);
}
void bitstringsSlidingHistogramMTFFS(uint64_t* arr, uint8_t* descriptors,
		const int width, const int height){
	bitstringsSlidingHistogramMTFP(arr, descriptors,&histAddFromBitsFFS,&histSubtractFromBitsFFS,width,height);
}


} //end namespace gpxa

