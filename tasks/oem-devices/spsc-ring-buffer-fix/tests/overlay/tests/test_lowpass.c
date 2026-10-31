#include "lowpass.h"
#include "unit.h"

TEST(first_sample_primes)
{
    lowpass_t f;
    lowpass_init(&f, 8192);
    CHECK_EQ_INT(1000, lowpass_step(&f, 1000));
}

TEST(converges_to_step)
{
    lowpass_t f;
    lowpass_init(&f, 8192); /* alpha 0.25 */
    lowpass_step(&f, 0);
    int16_t y = 0;
    for (int i = 0; i < 60; i++) {
        y = lowpass_step(&f, 4000);
    }
    CHECK(y >= 3999 && y <= 4000);
}

TEST(alpha_zero_holds)
{
    lowpass_t f;
    lowpass_init(&f, 0);
    lowpass_step(&f, -200);
    CHECK_EQ_INT(-200, lowpass_step(&f, 30000));
}

TEST(alpha_from_cutoff)
{
    /* fc = 5 Hz at 100 Hz: 31.415 / 131.415 = 0.239 -> 7834 */
    int16_t a = lowpass_alpha_q15(5000, 100);
    CHECK(a >= 7820 && a <= 7845);
    CHECK_EQ_INT(0, lowpass_alpha_q15(1000, 0));
}

int main(void)
{
    RUN("lowpass", first_sample_primes);
    RUN("lowpass", converges_to_step);
    RUN("lowpass", alpha_zero_holds);
    RUN("lowpass", alpha_from_cutoff);
    UNIT_EXIT();
}
