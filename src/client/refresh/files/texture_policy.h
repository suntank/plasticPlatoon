/* Shared safe picmip policy for native NPOT and power-of-two uploads. */
#ifndef PP_TEXTURE_POLICY_H
#define PP_TEXTURE_POLICY_H
#include <math.h>
static inline unsigned PP_PicmipLevels(float value)
{
	if (!isfinite(value) || value <= 0) return 0;
	if (value >= 16) return 16;
	return (unsigned)value;
}
static inline int PP_TextureDimension(int dimension, unsigned levels, int maximum)
{
	if (maximum < 1) maximum = 1;
	if (dimension < 1) dimension = 1;
	while (levels-- && dimension > 1) dimension >>= 1;
	return dimension > maximum ? maximum : dimension;
}
#endif
