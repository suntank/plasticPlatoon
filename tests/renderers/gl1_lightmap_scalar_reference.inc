/* Frozen unoptimized GL1 scalar reference for byte-exact regression.
 * Original Id Software / Yamagi code, GPL-2.0-or-later.
 * Source sha256: ce5159133757a0b9ca06601d74185916134e51b14db1f0ec3f9306e3ef804307
 * Kept independent of production optimization and profiler hooks.
 */
#define REFERENCE_FTOL(value) ((long)(value))
static float reference_blocklights[34 * 34 * 3];
static void
Reference_R_AddDynamicLights(msurface_t *surf)
{
	int lnum;
	int sd, td;
	float fdist, frad, fminlight;
	vec3_t impact, local;
	int s, t;
	int i;
	int smax, tmax;
	mtexinfo_t *tex;
	dlight_t *dl;
	float *pfBL;
	float fsacc, ftacc;

	smax = (surf->extents[0] >> 4) + 1;
	tmax = (surf->extents[1] >> 4) + 1;
	tex = surf->texinfo;

	for (lnum = 0; lnum < r_newrefdef.num_dlights; lnum++)
	{
		if (!(surf->dlightbits & (1 << lnum)))
		{
			continue; /* not lit by this light */
		}

		dl = &r_newrefdef.dlights[lnum];
		frad = dl->intensity;
		fdist = DotProduct(dl->origin, surf->plane->normal) -
				surf->plane->dist;
		frad -= fabs(fdist);

		/* rad is now the highest intensity on the plane */
		fminlight = DLIGHT_CUTOFF;

		if (frad < fminlight)
		{
			continue;
		}

		fminlight = frad - fminlight;

		for (i = 0; i < 3; i++)
		{
			impact[i] = dl->origin[i] -
						surf->plane->normal[i] * fdist;
		}

		local[0] = DotProduct(impact,
				   tex->vecs[0]) + tex->vecs[0][3] - surf->texturemins[0];
		local[1] = DotProduct(impact,
				   tex->vecs[1]) + tex->vecs[1][3] - surf->texturemins[1];

		pfBL = reference_blocklights;

		for (t = 0, ftacc = 0; t < tmax; t++, ftacc += 16)
		{
			td = local[1] - ftacc;

			if (td < 0)
			{
				td = -td;
			}

			for (s = 0, fsacc = 0; s < smax; s++, fsacc += 16, pfBL += 3)
			{
				sd = REFERENCE_FTOL(local[0] - fsacc);

				if (sd < 0)
				{
					sd = -sd;
				}

				if (sd > td)
				{
					fdist = sd + (td >> 1);
				}
				else
				{
					fdist = td + (sd >> 1);
				}

				if (fdist < fminlight)
				{
					pfBL[0] += (frad - fdist) * dl->color[0];
					pfBL[1] += (frad - fdist) * dl->color[1];
					pfBL[2] += (frad - fdist) * dl->color[2];
				}
			}
		}
	}
}


static void
Reference_R_BuildLightMap(msurface_t *surf, byte *dest, int stride)
{
	int smax, tmax;
	int r, g, b, a, max;
	int i, j, size;
	byte *lightmap;
	float scale[4];
	int nummaps;
	float *bl;

	if (surf->texinfo->flags &
		(SURF_SKY | SURF_TRANS33 | SURF_TRANS66 | SURF_WARP))
	{
		Com_Error(ERR_DROP, "%s called for non-lit surface", __func__);
	}

	smax = (surf->extents[0] >> 4) + 1;
	tmax = (surf->extents[1] >> 4) + 1;
	size = smax * tmax;

	if (size > (sizeof(reference_blocklights) >> 4))
	{
		Com_Error(ERR_DROP, "%s: Bad reference_blocklights size", __func__);
	}

	/* set to full bright if no light data */
	if (!surf->samples)
	{
		for (i = 0; i < size * 3; i++)
		{
			reference_blocklights[i] = 255;
		}

		goto store;
	}

	/* count the # of maps */
	for (nummaps = 0; nummaps < MAXLIGHTMAPS && surf->styles[nummaps] != 255;
		 nummaps++)
	{
	}

	lightmap = surf->samples;

	/* add all the lightmaps */
	if (nummaps == 1)
	{
		int maps;

		for (maps = 0; maps < MAXLIGHTMAPS && surf->styles[maps] != 255; maps++)
		{
			bl = reference_blocklights;

			for (i = 0; i < 3; i++)
			{
				scale[i] = r_modulate->value *
						   r_newrefdef.lightstyles[surf->styles[maps]].rgb[i];
			}

			if ((scale[0] == 1.0F) &&
				(scale[1] == 1.0F) &&
				(scale[2] == 1.0F))
			{
				for (i = 0; i < size; i++, bl += 3)
				{
					bl[0] = lightmap[i * 3 + 0];
					bl[1] = lightmap[i * 3 + 1];
					bl[2] = lightmap[i * 3 + 2];
				}
			}
			else
			{
				for (i = 0; i < size; i++, bl += 3)
				{
					bl[0] = lightmap[i * 3 + 0] * scale[0];
					bl[1] = lightmap[i * 3 + 1] * scale[1];
					bl[2] = lightmap[i * 3 + 2] * scale[2];
				}
			}

			lightmap += size * 3; /* skip to next lightmap */
		}
	}
	else
	{
		int maps;

		memset(reference_blocklights, 0, sizeof(reference_blocklights[0]) * size * 3);

		for (maps = 0; maps < MAXLIGHTMAPS && surf->styles[maps] != 255; maps++)
		{
			bl = reference_blocklights;

			for (i = 0; i < 3; i++)
			{
				scale[i] = r_modulate->value *
						   r_newrefdef.lightstyles[surf->styles[maps]].rgb[i];
			}

			if ((scale[0] == 1.0F) &&
				(scale[1] == 1.0F) &&
				(scale[2] == 1.0F))
			{
				for (i = 0; i < size; i++, bl += 3)
				{
					bl[0] += lightmap[i * 3 + 0];
					bl[1] += lightmap[i * 3 + 1];
					bl[2] += lightmap[i * 3 + 2];
				}
			}
			else
			{
				for (i = 0; i < size; i++, bl += 3)
				{
					bl[0] += lightmap[i * 3 + 0] * scale[0];
					bl[1] += lightmap[i * 3 + 1] * scale[1];
					bl[2] += lightmap[i * 3 + 2] * scale[2];
				}
			}

			lightmap += size * 3; /* skip to next lightmap */
		}
	}

	/* add all the dynamic lights */
	if (surf->dlightframe == r_framecount)
	{
		Reference_R_AddDynamicLights(surf);
	}

store:

	stride -= (smax << 2);
	bl = reference_blocklights;

	for (i = 0; i < tmax; i++, dest += stride)
	{
		for (j = 0; j < smax; j++)
		{
			r = REFERENCE_FTOL(bl[0]);
			g = REFERENCE_FTOL(bl[1]);
			b = REFERENCE_FTOL(bl[2]);

			/* catch negative lights */
			if (r < 0)
			{
				r = 0;
			}

			if (g < 0)
			{
				g = 0;
			}

			if (b < 0)
			{
				b = 0;
			}

			/* determine the brightest of the three color components */
			if (r > g)
			{
				max = r;
			}
			else
			{
				max = g;
			}

			if (b > max)
			{
				max = b;
			}

			/* alpha is ONLY used for the mono lightmap case. For this
			   reason we set it to the brightest of the color components
			   so that things don't get too dim. */
			a = max;

			/* rescale all the color components if the
			   intensity of the greatest channel exceeds
			   1.0 */
			if (max > 255)
			{
				float t = 255.0F / max;

				r = r * t;
				g = g * t;
				b = b * t;
				a = a * t;
			}

			if (gl_state.minlight_set)
			{
				r = minlight[r];
				g = minlight[g];
				b = minlight[b];
			}

			dest[0] = gammatable[r];
			dest[1] = gammatable[g];
			dest[2] = gammatable[b];
			dest[3] = a;

			bl += 3;
			dest += 4;
		}
	}
}

#undef REFERENCE_FTOL
