#include "dbc_lite.h"

#include <stdlib.h>
#include <string.h>

static const char *skip_ws(const char *p)
{
    while (*p == ' ' || *p == '\t') {
        p++;
    }
    return p;
}

static int parse_double(const char **pp, double *out)
{
    char *end;
    *out = strtod(*pp, &end);
    if (end == *pp) {
        return -1;
    }
    *pp = end;
    return 0;
}

static int parse_uint(const char **pp, unsigned long *out)
{
    char *end;
    *out = strtoul(*pp, &end, 10);
    if (end == *pp) {
        return -1;
    }
    *pp = end;
    return 0;
}

static int expect(const char **pp, char c)
{
    *pp = skip_ws(*pp);
    if (**pp != c) {
        return -1;
    }
    (*pp)++;
    return 0;
}

int dbc_parse_signal(const char *line, dbc_signal_t *out)
{
    if (line == NULL || out == NULL) {
        return -1;
    }
    memset(out, 0, sizeof(*out));
    const char *p = skip_ws(line);
    if (strncmp(p, "SG_", 3) != 0) {
        return -1;
    }
    p = skip_ws(p + 3);

    size_t n = 0;
    while (*p && *p != ' ' && *p != '\t' && *p != ':') {
        if (n + 1 >= DBC_NAME_MAX) {
            return -1;
        }
        out->name[n++] = *p++;
    }
    if (n == 0) {
        return -1;
    }
    out->name[n] = '\0';
    out->sig.name = out->name;

    unsigned long start, len;
    double factor, offset;
    if (expect(&p, ':') || (p = skip_ws(p), parse_uint(&p, &start)) || expect(&p, '|') ||
        parse_uint(&p, &len) || expect(&p, '@')) {
        return -1;
    }
    if (*p != '0' && *p != '1') {
        return -1;
    }
    out->sig.order = (*p == '1') ? CAN_LITTLE_ENDIAN : CAN_BIG_ENDIAN;
    p++;
    if (*p != '+' && *p != '-') {
        return -1;
    }
    out->sig.is_signed = (*p == '-');
    p++;
    if (start > 63 || len == 0 || len > 64) {
        return -1;
    }
    out->sig.start_bit = (uint8_t)start;
    out->sig.length = (uint8_t)len;

    if (expect(&p, '(') || (p = skip_ws(p), parse_double(&p, &factor)) || expect(&p, ',') ||
        (p = skip_ws(p), parse_double(&p, &offset)) || expect(&p, ')')) {
        return -1;
    }
    out->sig.factor = factor;
    out->sig.offset = offset;

    if (expect(&p, '[') || (p = skip_ws(p), parse_double(&p, &out->minimum)) || expect(&p, '|') ||
        (p = skip_ws(p), parse_double(&p, &out->maximum)) || expect(&p, ']')) {
        return -1;
    }
    if (expect(&p, '"')) {
        return -1;
    }
    n = 0;
    while (*p && *p != '"') {
        if (n + 1 >= DBC_UNIT_MAX) {
            return -1;
        }
        out->unit[n++] = *p++;
    }
    if (*p != '"') {
        return -1;
    }
    out->unit[n] = '\0';
    return 0;
}
