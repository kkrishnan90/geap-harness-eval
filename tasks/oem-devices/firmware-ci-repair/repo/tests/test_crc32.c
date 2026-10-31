#include "crc32.h"
#include "unit.h"

TEST(check_value)
{
    CHECK_EQ_U64(0xCBF43926u, crc32_ieee("123456789", 9));
}

TEST(empty)
{
    CHECK_EQ_U64(0u, crc32_ieee("", 0));
}

TEST(incremental_matches_oneshot)
{
    uint32_t c = crc32_ieee_update(0u, "12345", 5);
    c = crc32_ieee_update(c, "6789", 4);
    CHECK_EQ_U64(0xCBF43926u, c);
}

int main(void)
{
    RUN("crc32", check_value);
    RUN("crc32", empty);
    RUN("crc32", incremental_matches_oneshot);
    UNIT_EXIT();
}
