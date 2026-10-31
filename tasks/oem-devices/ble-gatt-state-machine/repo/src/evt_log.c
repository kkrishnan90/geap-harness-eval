#include "evt_log.h"

#include <stdarg.h>
#include <stdio.h>

static char lines[EVT_LOG_LINES][EVT_LOG_LINE];
static size_t head, count;

void evt_log_clear(void)
{
    head = 0;
    count = 0;
}

void evt_log(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(lines[head], EVT_LOG_LINE, fmt, ap);
    va_end(ap);
    head = (head + 1) % EVT_LOG_LINES;
    if (count < EVT_LOG_LINES) {
        count++;
    }
}

size_t evt_log_count(void)
{
    return count;
}

const char *evt_log_line(size_t i)
{
    if (i >= count) {
        return NULL;
    }
    size_t oldest = (head + EVT_LOG_LINES - count) % EVT_LOG_LINES;
    return lines[(oldest + i) % EVT_LOG_LINES];
}
