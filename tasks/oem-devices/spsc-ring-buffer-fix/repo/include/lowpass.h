#ifndef LOWPASS_H
#define LOWPASS_H

#include <stdint.h>

/* First-order IIR low-pass y += alpha * (x - y), alpha in Q15 (0..32767). */
typedef struct {
    int32_t state_q15; /* y in Q15-scaled LSB (value << 15) */
    int16_t alpha_q15;
    int primed;
} lowpass_t;

void lowpass_init(lowpass_t *f, int16_t alpha_q15);
int16_t lowpass_step(lowpass_t *f, int16_t x);

/* alpha for a cut-off frequency fc at sample rate fs, alpha = 2*pi*fc / (2*pi*fc + fs), in Q15. */
int16_t lowpass_alpha_q15(uint32_t fc_millihz, uint32_t fs_hz);

#endif
