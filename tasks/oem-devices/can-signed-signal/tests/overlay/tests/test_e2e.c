#include <string.h>

#include "e2e.h"
#include "unit.h"

#define SUITE "e2e"

TEST(crc8_check_value)
{
    const char *msg = "123456789";
    CHECK_EQ_INT(0x4B, crc8_sae_j1850((const uint8_t *)msg, strlen(msg)));
    const uint8_t zeros[4] = { 0 };
    CHECK_EQ_INT(0x59, crc8_sae_j1850(zeros, 4));
}

TEST(alive_sequence)
{
    alive_monitor_t m;
    alive_init(&m, 2);
    CHECK_EQ_INT(ALIVE_INITIAL, alive_check(&m, 13));
    CHECK_EQ_INT(ALIVE_OK, alive_check(&m, 14));
    CHECK_EQ_INT(ALIVE_OK, alive_check(&m, 0));
    CHECK_EQ_INT(ALIVE_REPEATED, alive_check(&m, 0));
    CHECK_EQ_INT(ALIVE_OK_SOME_LOST, alive_check(&m, 2));
    CHECK_EQ_INT(ALIVE_WRONG_SEQ, alive_check(&m, 6));
}

int main(void)
{
    RUN(SUITE, crc8_check_value);
    RUN(SUITE, alive_sequence);
    UNIT_EXIT();
}
