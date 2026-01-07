/*
 * Plastic Platoon - Simple JSON Parser Implementation
 *
 * Minimal JSON parser for weapon tuning profiles.
 */

#include "pp_json.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <ctype.h>

/* ============================================================================
 * MEMORY ALLOCATION
 * ============================================================================ */

static json_value_t *
json_alloc_value(void)
{
	json_value_t *val = (json_value_t *)malloc(sizeof(json_value_t));
	if (val)
	{
		memset(val, 0, sizeof(json_value_t));
	}
	return val;
}

static qboolean
json_grow_children(json_value_t *val)
{
	int new_cap;
	json_value_t *new_children;

	if (val->child_capacity == 0)
	{
		new_cap = 8;
	}
	else
	{
		new_cap = val->child_capacity * 2;
	}

	if (new_cap > JSON_MAX_CHILDREN)
	{
		new_cap = JSON_MAX_CHILDREN;
		if (val->child_count >= new_cap)
		{
			return false;
		}
	}

	new_children = (json_value_t *)realloc(val->children, new_cap * sizeof(json_value_t));
	if (!new_children)
	{
		return false;
	}

	val->children = new_children;
	val->child_capacity = new_cap;
	return true;
}

/* ============================================================================
 * PARSER HELPERS
 * ============================================================================ */

static void
json_skip_whitespace(json_parser_t *p)
{
	while (p->pos < p->len)
	{
		char c = p->text[p->pos];
		if (c == ' ' || c == '\t' || c == '\n' || c == '\r')
		{
			p->pos++;
		}
		else
		{
			break;
		}
	}
}

static char
json_peek(json_parser_t *p)
{
	json_skip_whitespace(p);
	if (p->pos >= p->len)
	{
		return '\0';
	}
	return p->text[p->pos];
}

static char
json_consume(json_parser_t *p)
{
	json_skip_whitespace(p);
	if (p->pos >= p->len)
	{
		return '\0';
	}
	return p->text[p->pos++];
}

static void
json_error(json_parser_t *p, const char *msg)
{
	if (!p->has_error)
	{
		snprintf(p->error, sizeof(p->error), "JSON error at pos %d: %s", p->pos, msg);
		p->has_error = true;
	}
}

static qboolean
json_expect(json_parser_t *p, char expected)
{
	char c = json_consume(p);
	if (c != expected)
	{
		char msg[64];
		snprintf(msg, sizeof(msg), "Expected '%c', got '%c'", expected, c);
		json_error(p, msg);
		return false;
	}
	return true;
}

/* ============================================================================
 * VALUE PARSING
 * ============================================================================ */

static json_value_t *json_parse_value(json_parser_t *p);

static qboolean
json_parse_string_into(json_parser_t *p, char *buf, int buf_size)
{
	int i = 0;
	char c;

	if (!json_expect(p, '"'))
	{
		return false;
	}

	while (p->pos < p->len && i < buf_size - 1)
	{
		c = p->text[p->pos++];

		if (c == '"')
		{
			buf[i] = '\0';
			return true;
		}

		if (c == '\\' && p->pos < p->len)
		{
			char next = p->text[p->pos++];
			switch (next)
			{
				case '"': buf[i++] = '"'; break;
				case '\\': buf[i++] = '\\'; break;
				case '/': buf[i++] = '/'; break;
				case 'b': buf[i++] = '\b'; break;
				case 'f': buf[i++] = '\f'; break;
				case 'n': buf[i++] = '\n'; break;
				case 'r': buf[i++] = '\r'; break;
				case 't': buf[i++] = '\t'; break;
				case 'u':
					/* Skip unicode escapes, just put a placeholder */
					buf[i++] = '?';
					p->pos += 4;
					break;
				default:
					buf[i++] = next;
					break;
			}
		}
		else
		{
			buf[i++] = c;
		}
	}

	buf[i] = '\0';
	json_error(p, "Unterminated string");
	return false;
}

static json_value_t *
json_parse_string(json_parser_t *p)
{
	json_value_t *val = json_alloc_value();
	if (!val)
	{
		json_error(p, "Out of memory");
		return NULL;
	}

	val->type = JSON_STRING;
	if (!json_parse_string_into(p, val->string_val, JSON_MAX_STRING))
	{
		free(val);
		return NULL;
	}

	return val;
}

static json_value_t *
json_parse_number(json_parser_t *p)
{
	json_value_t *val;
	char buf[64];
	int i = 0;
	char c;

	json_skip_whitespace(p);

	while (p->pos < p->len && i < 63)
	{
		c = p->text[p->pos];
		if (isdigit(c) || c == '-' || c == '+' || c == '.' || c == 'e' || c == 'E')
		{
			buf[i++] = c;
			p->pos++;
		}
		else
		{
			break;
		}
	}
	buf[i] = '\0';

	if (i == 0)
	{
		json_error(p, "Invalid number");
		return NULL;
	}

	val = json_alloc_value();
	if (!val)
	{
		json_error(p, "Out of memory");
		return NULL;
	}

	val->type = JSON_NUMBER;
	val->number_val = atof(buf);
	return val;
}

static json_value_t *
json_parse_literal(json_parser_t *p)
{
	json_value_t *val;

	json_skip_whitespace(p);

	if (strncmp(&p->text[p->pos], "true", 4) == 0)
	{
		p->pos += 4;
		val = json_alloc_value();
		if (val)
		{
			val->type = JSON_BOOL;
			val->bool_val = true;
		}
		return val;
	}

	if (strncmp(&p->text[p->pos], "false", 5) == 0)
	{
		p->pos += 5;
		val = json_alloc_value();
		if (val)
		{
			val->type = JSON_BOOL;
			val->bool_val = false;
		}
		return val;
	}

	if (strncmp(&p->text[p->pos], "null", 4) == 0)
	{
		p->pos += 4;
		val = json_alloc_value();
		if (val)
		{
			val->type = JSON_NULL;
		}
		return val;
	}

	json_error(p, "Invalid literal");
	return NULL;
}

static json_value_t *
json_parse_array(json_parser_t *p)
{
	json_value_t *val;
	json_value_t *child;

	if (!json_expect(p, '['))
	{
		return NULL;
	}

	val = json_alloc_value();
	if (!val)
	{
		json_error(p, "Out of memory");
		return NULL;
	}
	val->type = JSON_ARRAY;

	if (json_peek(p) == ']')
	{
		json_consume(p);
		return val;
	}

	while (!p->has_error)
	{
		child = json_parse_value(p);
		if (!child)
		{
			JSON_Free(val);
			return NULL;
		}

		if (val->child_count >= val->child_capacity)
		{
			if (!json_grow_children(val))
			{
				json_error(p, "Too many array elements");
				JSON_Free(val);
				return NULL;
			}
		}

		memcpy(&val->children[val->child_count], child, sizeof(json_value_t));
		val->child_count++;
		free(child);

		if (json_peek(p) == ',')
		{
			json_consume(p);
		}
		else
		{
			break;
		}
	}

	if (!json_expect(p, ']'))
	{
		JSON_Free(val);
		return NULL;
	}

	return val;
}

static json_value_t *
json_parse_object(json_parser_t *p)
{
	json_value_t *val;
	json_value_t *child;
	char key[JSON_MAX_KEY];

	if (!json_expect(p, '{'))
	{
		return NULL;
	}

	val = json_alloc_value();
	if (!val)
	{
		json_error(p, "Out of memory");
		return NULL;
	}
	val->type = JSON_OBJECT;

	if (json_peek(p) == '}')
	{
		json_consume(p);
		return val;
	}

	while (!p->has_error)
	{
		/* Parse key */
		if (!json_parse_string_into(p, key, JSON_MAX_KEY))
		{
			JSON_Free(val);
			return NULL;
		}

		if (!json_expect(p, ':'))
		{
			JSON_Free(val);
			return NULL;
		}

		/* Parse value */
		child = json_parse_value(p);
		if (!child)
		{
			JSON_Free(val);
			return NULL;
		}

		/* Store key in child */
		Q_strlcpy(child->key, key, JSON_MAX_KEY);

		if (val->child_count >= val->child_capacity)
		{
			if (!json_grow_children(val))
			{
				json_error(p, "Too many object members");
				free(child);
				JSON_Free(val);
				return NULL;
			}
		}

		memcpy(&val->children[val->child_count], child, sizeof(json_value_t));
		val->child_count++;
		free(child);

		if (json_peek(p) == ',')
		{
			json_consume(p);
		}
		else
		{
			break;
		}
	}

	if (!json_expect(p, '}'))
	{
		JSON_Free(val);
		return NULL;
	}

	return val;
}

static json_value_t *
json_parse_value(json_parser_t *p)
{
	char c;

	if (p->has_error)
	{
		return NULL;
	}

	c = json_peek(p);

	switch (c)
	{
		case '{': return json_parse_object(p);
		case '[': return json_parse_array(p);
		case '"': return json_parse_string(p);
		case 't':
		case 'f':
		case 'n': return json_parse_literal(p);
		case '-':
		case '0':
		case '1':
		case '2':
		case '3':
		case '4':
		case '5':
		case '6':
		case '7':
		case '8':
		case '9': return json_parse_number(p);
		default:
			json_error(p, "Unexpected character");
			return NULL;
	}
}

/* ============================================================================
 * PUBLIC API
 * ============================================================================ */

json_value_t *
JSON_Parse(const char *text, char *error_out, int error_size)
{
	json_parser_t parser;
	json_value_t *result;

	if (!text)
	{
		if (error_out)
		{
			Q_strlcpy(error_out, "NULL input", error_size);
		}
		return NULL;
	}

	memset(&parser, 0, sizeof(parser));
	parser.text = text;
	parser.len = strlen(text);

	result = json_parse_value(&parser);

	if (parser.has_error)
	{
		if (error_out)
		{
			Q_strlcpy(error_out, parser.error, error_size);
		}
		if (result)
		{
			JSON_Free(result);
		}
		return NULL;
	}

	return result;
}

void
JSON_Free(json_value_t *val)
{
	int i;

	if (!val)
	{
		return;
	}

	/* Free children recursively */
	if (val->children)
	{
		for (i = 0; i < val->child_count; i++)
		{
			/* Children have inline storage, but may have their own children */
			if (val->children[i].children)
			{
				JSON_Free(&val->children[i]);
			}
		}
		free(val->children);
	}

	/* Only free the root allocation */
	free(val);
}

json_value_t *
JSON_GetMember(json_value_t *obj, const char *key)
{
	int i;

	if (!obj || obj->type != JSON_OBJECT || !key)
	{
		return NULL;
	}

	for (i = 0; i < obj->child_count; i++)
	{
		if (strcmp(obj->children[i].key, key) == 0)
		{
			return &obj->children[i];
		}
	}

	return NULL;
}

json_value_t *
JSON_GetIndex(json_value_t *arr, int index)
{
	if (!arr || arr->type != JSON_ARRAY)
	{
		return NULL;
	}

	if (index < 0 || index >= arr->child_count)
	{
		return NULL;
	}

	return &arr->children[index];
}

qboolean
JSON_GetBool(json_value_t *val, qboolean default_val)
{
	if (!val || val->type != JSON_BOOL)
	{
		return default_val;
	}
	return val->bool_val;
}

double
JSON_GetNumber(json_value_t *val, double default_val)
{
	if (!val || val->type != JSON_NUMBER)
	{
		return default_val;
	}
	return val->number_val;
}

int
JSON_GetInt(json_value_t *val, int default_val)
{
	if (!val || val->type != JSON_NUMBER)
	{
		return default_val;
	}
	return (int)val->number_val;
}

float
JSON_GetFloat(json_value_t *val, float default_val)
{
	if (!val || val->type != JSON_NUMBER)
	{
		return default_val;
	}
	return (float)val->number_val;
}

const char *
JSON_GetString(json_value_t *val, const char *default_val)
{
	if (!val || val->type != JSON_STRING)
	{
		return default_val;
	}
	return val->string_val;
}

json_value_t *
JSON_GetPath(json_value_t *root, const char *path)
{
	char segment[JSON_MAX_KEY];
	const char *p = path;
	const char *dot;
	json_value_t *current = root;
	int len;

	if (!root || !path)
	{
		return NULL;
	}

	while (*p && current)
	{
		dot = strchr(p, '.');
		if (dot)
		{
			len = dot - p;
			if (len >= JSON_MAX_KEY)
			{
				len = JSON_MAX_KEY - 1;
			}
			strncpy(segment, p, len);
			segment[len] = '\0';
			p = dot + 1;
		}
		else
		{
			Q_strlcpy(segment, p, JSON_MAX_KEY);
			p += strlen(p);
		}

		if (current->type == JSON_OBJECT)
		{
			current = JSON_GetMember(current, segment);
		}
		else if (current->type == JSON_ARRAY)
		{
			int idx = atoi(segment);
			current = JSON_GetIndex(current, idx);
		}
		else
		{
			return NULL;
		}
	}

	return current;
}

qboolean
JSON_IsObject(json_value_t *val)
{
	return val && val->type == JSON_OBJECT;
}

qboolean
JSON_IsArray(json_value_t *val)
{
	return val && val->type == JSON_ARRAY;
}

qboolean
JSON_IsString(json_value_t *val)
{
	return val && val->type == JSON_STRING;
}

qboolean
JSON_IsNumber(json_value_t *val)
{
	return val && val->type == JSON_NUMBER;
}

qboolean
JSON_IsBool(json_value_t *val)
{
	return val && val->type == JSON_BOOL;
}
