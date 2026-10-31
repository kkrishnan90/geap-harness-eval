#include "lowpass.h"

void lowpass_init(lowpass_t *f, int16_t alpha_q15)
{
    f->state_q15 = 0;
    f->alpha_q15 = alpha_q15 < 0 ? 0 : alpha_q15;
    f->primed = 0;
}

int16_t lowpass_step(lowpass_t *f, int16_t x)
{
    if (!f->primed) {
        /* seed with the first sample to avoid a start-up transient */
        f->state_q15 = (int32_t)x * 32768;
        f->primed = 1;
        return x;
    }
    int64_t err = (int64_t)x * 32768 - f->state_q15;
    f->state_q15 += (int32_t)((err * f->alpha_q15) / 32768);
    int32_t y = f->state_q15 >= 0 ? (f->state_q15 + 16384) / 32768 : -((-f->state_q15 + 16384) / 32768);
    if (y > 32767) {
        y = 32767;
    } else if (y < -32768) {
        y = -32768;
    }
    return (int16_t)y;
}

int16_t lowpass_alpha_q15(uint32_t fc_millihz, uint32_t fs_hz)
{
    if (fs_hz == 0u) {
        return 0;
    }
    /* 2*pi ~= 6283/1000 */
    uint64_t w = (uint64_t)fc_millihz * 6283u / 1000u;      /* millirad/s */
    uint64_t denom = w + (uint64_t)fs_hz * 1000u;
    uint64_t a = (w * 32768u + denom / 2u) / denom;
    return (int16_t)(a > 32767u ? 32767u : a);
}
