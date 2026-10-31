#include "fwver.h"

#include <stdio.h>

static const char *parse_u16(const char *s, uint16_t *out)
{
    uint32_t v = 0;
    const char *p = s;
    if (*p < '0' || *p > '9') {
        return NULL;
    }
    if (*p == '0' && p[1] >= '0' && p[1] <= '9') {
        return NULL; /* no leading zeros */
    }
    while (*p >= '0' && *p <= '9') {
        v = v * 10u + (uint32_t)(*p - '0');
        if (v > 65535u) {
            return NULL;
        }
        p++;
    }
    *out = (uint16_t)v;
    return p;
}

int fwver_parse(const char *s, fwver_t *out)
{
    fwver_t v = {0, 0, 0, 0};
    if (s == NULL || out == NULL) {
        return -1;
    }
    const char *p = parse_u16(s, &v.major);
    if (p == NULL || *p++ != '.') return -1;
    p = parse_u16(p, &v.minor);
    if (p == NULL || *p++ != '.') return -1;
    p = parse_u16(p, &v.patch);
    if (p == NULL) return -1;
    if (p[0] == '-' && p[1] == 'r' && p[2] == 'c') {
        p = parse_u16(p + 3, &v.rc);
        if (p == NULL || v.rc == 0) return -1;
    }
    if (*p != '\0') return -1;
    *out = v;
    return 0;
}

int fwver_compare(const fwver_t *a, const fwver_t *b)
{
    if (a->major != b->major) return a->major < b->major ? -1 : 1;
    if (a->minor != b->minor) return a->minor < b->minor ? -1 : 1;
    if (a->patch != b->patch) return a->patch < b->patch ? -1 : 1;
    if (a->rc == b->rc) return 0;
    if (a->rc == 0) return 1;  /* release sorts after its rcs */
    if (b->rc == 0) return -1;
    return a->rc < b->rc ? -1 : 1;
}

int fwver_format(const fwver_t *v, char *buf, int cap)
{
    int n;
    if (v->rc) {
        n = snprintf(buf, (size_t)cap, "%u.%u.%u-rc%u", v->major, v->minor, v->patch, v->rc);
    } else {
        n = snprintf(buf, (size_t)cap, "%u.%u.%u", v->major, v->minor, v->patch);
    }
    return (n < 0 || n >= cap) ? -1 : n;
}
