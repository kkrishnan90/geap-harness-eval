#include "e2e.h"

#define ALIVE_MODULO 15u

void alive_init(alive_monitor_t *m, uint8_t max_delta)
{
    m->seen = false;
    m->last = 0;
    m->max_delta = max_delta;
}

alive_status_t alive_check(alive_monitor_t *m, uint8_t counter)
{
    counter = (uint8_t)(counter % ALIVE_MODULO);
    if (!m->seen) {
        m->seen = true;
        m->last = counter;
        return ALIVE_INITIAL;
    }
    unsigned delta = (counter + ALIVE_MODULO - m->last) % ALIVE_MODULO;
    m->last = counter;
    if (delta == 0) {
        return ALIVE_REPEATED;
    }
    if (delta == 1) {
        return ALIVE_OK;
    }
    return delta <= m->max_delta ? ALIVE_OK_SOME_LOST : ALIVE_WRONG_SEQ;
}
