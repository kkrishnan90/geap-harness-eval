#ifndef FWVER_H
#define FWVER_H

#include <stdint.h>

/* MAJOR.MINOR.PATCH with optional -rcN; each number 0..65535. */
typedef struct {
    uint16_t major, minor, patch;
    uint16_t rc; /* 0 = release; rc builds sort before the release */
} fwver_t;

int fwver_parse(const char *s, fwver_t *out); /* 0 or -1 */
int fwver_compare(const fwver_t *a, const fwver_t *b); /* <0, 0, >0 */
int fwver_format(const fwver_t *v, char *buf, int cap); /* chars written (excl. NUL) or -1 */

#endif
