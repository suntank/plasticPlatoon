/*
 * Copyright (C) 2013 Alejandro Ricoveri
 * Copyright (C) 1997-2001 Id Software, Inc.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or (at
 * your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
 *
 * See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
 * 02111-1307, USA.
 *
 * =======================================================================
 *
 * This file implements the operating system binding of GL to QGL function
 * pointers.  When doing a port of Quake2 you must implement the following
 * two functions:
 *
 * QGL_Init() - loads libraries, assigns function pointers, etc.
 * QGL_Shutdown() - unloads libraries, NULLs function pointers
 *
 * This implementation should work for Windows and unixoid platforms,
 * other platforms may need an own implementation.
 *
 * =======================================================================
 */

#include "header/local.h"

/*
 * GL extensions
 */
void (APIENTRY *qglPointParameterf)(GLenum param, GLfloat value);
void (APIENTRY *qglPointParameterfv)(GLenum param, const GLfloat *value);
void (APIENTRY *qglColorTableEXT)(GLenum, GLenum, GLsizei, GLenum, GLenum,
		const GLvoid *);
void (APIENTRY *qglActiveTexture) (GLenum texture);
void (APIENTRY *qglClientActiveTexture) (GLenum texture);
void (APIENTRY *qglDiscardFramebufferEXT) (GLenum target,
		GLsizei numAttachments, const GLenum *attachments);

/* ========================================================================= */

void QGL_EXT_Reset ( void )
{
	qglPointParameterf     = NULL;
	qglPointParameterfv    = NULL;
	qglColorTableEXT       = NULL;
	qglActiveTexture       = NULL;
	qglClientActiveTexture = NULL;
	qglDiscardFramebufferEXT = NULL;
	qglGenBuffers = NULL; qglDeleteBuffers = NULL;
	qglBindBuffer = NULL; qglBufferData = NULL;
}

/* ========================================================================= */

void
QGL_Shutdown ( void )
{
	// Reset GL extension pointers
	QGL_EXT_Reset();
}

/* ========================================================================= */

void
QGL_Init (void)
{
	// Reset GL extension pointers
	QGL_EXT_Reset();
}


void (APIENTRY *qglGenBuffers)(GLsizei, GLuint *);
void (APIENTRY *qglDeleteBuffers)(GLsizei, const GLuint *);
void (APIENTRY *qglBindBuffer)(GLenum, GLuint);
void (APIENTRY *qglBufferData)(GLenum, ptrdiff_t, const void *, GLenum);

void R_InitBufferObjects(void)
{
	qboolean supported;
#ifdef YQ2_GL1_GLES
	/* The ES context is 1.1. Still require all entry points below. */
	supported = true;
#else
	int major = 0, minor = 0;
	sscanf(gl_config.version_string, "%d.%d", &major, &minor);
	supported = major > 1 || (major == 1 && minor >= 5) ||
		strstr(gl_config.extensions_string, "GL_ARB_vertex_buffer_object") != NULL;
#endif
	if (!supported) return;
#define PP_LOAD_BUFFER(name, signature) do { 	qgl##name = (signature)RI_GetProcAddress("gl" #name); 	if (!qgl##name) qgl##name = (signature)RI_GetProcAddress("gl" #name "ARB"); } while (0)
	PP_LOAD_BUFFER(GenBuffers, void (APIENTRY *)(GLsizei, GLuint *));
	PP_LOAD_BUFFER(DeleteBuffers, void (APIENTRY *)(GLsizei, const GLuint *));
	PP_LOAD_BUFFER(BindBuffer, void (APIENTRY *)(GLenum, GLuint));
	PP_LOAD_BUFFER(BufferData, void (APIENTRY *)(GLenum, ptrdiff_t, const void *, GLenum));
#undef PP_LOAD_BUFFER
	if (!qglGenBuffers || !qglDeleteBuffers || !qglBindBuffer || !qglBufferData)
	{
		qglGenBuffers = NULL; qglDeleteBuffers = NULL;
		qglBindBuffer = NULL; qglBufferData = NULL;
		Com_Printf(" - Persistent buffers: unavailable; using client arrays\n");
	}
	else Com_Printf(" - Persistent buffers: available\n");
}
