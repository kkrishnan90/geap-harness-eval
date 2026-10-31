#ifndef DBC_LITE_H
#define DBC_LITE_H

#include "candec.h"

#define DBC_NAME_MAX 32
#define DBC_UNIT_MAX 16

typedef struct {
    can_signal_t sig;        /* sig.name points into name[] */
    char name[DBC_NAME_MAX];
    char unit[DBC_UNIT_MAX];
    double minimum;
    double maximum;
} dbc_signal_t;

/*
 * Parse one signal line, e.g.
 *   SG_ EngineCoolantTemp : 16|16@1- (0.1,-40) [-40|215] "degC" ECM
 * Returns 0 on success, -1 on syntax error.
 */
int dbc_parse_signal(const char *line, dbc_signal_t *out);

#endif
