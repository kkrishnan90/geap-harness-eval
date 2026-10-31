#ifndef EVT_LOG_H
#define EVT_LOG_H

/* Small in-RAM diagnostic log, dumped over UDS service 0x22 F1A0. Lines are truncated
 * to EVT_LOG_LINE-1 chars; the oldest line is overwritten when full. */

#include <stddef.h>

#define EVT_LOG_LINES 32
#define EVT_LOG_LINE 64

void evt_log_clear(void);
void evt_log(const char *fmt, ...);
size_t evt_log_count(void);
/* i = 0 is the oldest retained line. */
const char *evt_log_line(size_t i);

#endif
