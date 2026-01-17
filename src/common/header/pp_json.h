/*
 * Plastic Platoon - Simple JSON Parser
 *
 * Minimal JSON parser for weapon tuning profiles.
 * Shared between game and client.
 */

#ifndef PP_JSON_H
#define PP_JSON_H

#include "shared.h"

/* ============================================================================
 * JSON VALUE TYPES
 * ============================================================================ */

typedef enum {
	JSON_NULL = 0,
	JSON_BOOL,
	JSON_NUMBER,
	JSON_STRING,
	JSON_ARRAY,
	JSON_OBJECT
} json_type_t;

/* ============================================================================
 * JSON VALUE STRUCTURE
 * ============================================================================ */

#define JSON_MAX_STRING 256
#define JSON_MAX_CHILDREN 64
#define JSON_MAX_KEY 64

typedef struct json_value_s json_value_t;

struct json_value_s {
	json_type_t type;

	/* Value storage */
	union {
		qboolean bool_val;
		double number_val;
		char string_val[JSON_MAX_STRING];
	};

	/* For objects and arrays */
	char key[JSON_MAX_KEY];          /* Key name (for object members) */
	json_value_t *children;          /* Array of children */
	int child_count;
	int child_capacity;
};

/* ============================================================================
 * PARSER STATE
 * ============================================================================ */

typedef struct {
	const char *text;
	int pos;
	int len;
	char error[256];
	qboolean has_error;
} json_parser_t;

/* ============================================================================
 * API FUNCTIONS
 * ============================================================================ */

/* Parse JSON text into a value tree. Returns NULL on error. */
json_value_t *JSON_Parse(const char *text, char *error_out, int error_size);

/* Free a parsed JSON value tree */
void JSON_Free(json_value_t *val);

/* Access helpers */
json_value_t *JSON_GetMember(json_value_t *obj, const char *key);
json_value_t *JSON_GetIndex(json_value_t *arr, int index);

/* Type-checked value getters (return default on type mismatch) */
qboolean JSON_GetBool(json_value_t *val, qboolean default_val);
double JSON_GetNumber(json_value_t *val, double default_val);
int JSON_GetInt(json_value_t *val, int default_val);
float JSON_GetFloat(json_value_t *val, float default_val);
const char *JSON_GetString(json_value_t *val, const char *default_val);

/* Nested access with dot notation: "meta.name" or "weapons.SMG.damage" */
json_value_t *JSON_GetPath(json_value_t *root, const char *path);

/* Validation helpers */
qboolean JSON_IsObject(json_value_t *val);
qboolean JSON_IsArray(json_value_t *val);
qboolean JSON_IsString(json_value_t *val);
qboolean JSON_IsNumber(json_value_t *val);
qboolean JSON_IsBool(json_value_t *val);

#endif /* PP_JSON_H */
