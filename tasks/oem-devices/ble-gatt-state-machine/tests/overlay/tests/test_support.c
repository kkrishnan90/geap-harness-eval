#include <string.h>

#include "adv_data.h"
#include "bond_store.h"
#include "evt_log.h"
#include "unit.h"

TEST(bond_lru_replacement)
{
    bond_store_clear();
    uint8_t a[6] = {1, 2, 3, 4, 5, 0};
    for (int i = 0; i < BOND_STORE_MAX; i++) {
        a[5] = (uint8_t)i;
        bond_store_add(a);
    }
    CHECK_EQ_INT(BOND_STORE_MAX, bond_store_count());
    a[5] = 0;
    bond_store_add(a); /* refresh #0, so #1 is now the LRU */
    a[5] = 99;
    bond_store_add(a);
    a[5] = 1;
    CHECK(!bond_store_contains(a));
    a[5] = 0;
    CHECK(bond_store_contains(a));
    CHECK(bond_store_remove(a));
    CHECK(!bond_store_remove(a));
}

TEST(adv_payload_fits_name)
{
    adv_payload_t p;
    CHECK_EQ_INT(0, adv_build_key_service(&p, "DKM2-7F3A", 0xFFF0));
    const uint8_t expect[] = {0x02, 0x01, 0x06, 0x03, 0x03, 0xF0, 0xFF, 0x0A, 0x09,
                              'D', 'K', 'M', '2', '-', '7', 'F', '3', 'A'};
    CHECK_EQ_INT(sizeof expect, p.len);
    CHECK(memcmp(expect, p.data, sizeof expect) == 0);
}

TEST(adv_payload_shortens_long_name)
{
    adv_payload_t p;
    CHECK_EQ_INT(0, adv_build_key_service(&p, "DKM2 Digital Key Module Rear Left", 0xFFF0));
    CHECK_EQ_INT(31, p.len);
    CHECK_EQ_INT(AD_TYPE_NAME_SHORT, p.data[8]);
}

TEST(evt_log_wraps)
{
    evt_log_clear();
    for (int i = 0; i < EVT_LOG_LINES + 5; i++) {
        evt_log("line %d", i);
    }
    CHECK_EQ_INT(EVT_LOG_LINES, evt_log_count());
    CHECK(strcmp(evt_log_line(0), "line 5") == 0);
    CHECK(evt_log_line(EVT_LOG_LINES) == NULL);
}

int main(void)
{
    RUN("support", bond_lru_replacement);
    RUN("support", adv_payload_fits_name);
    RUN("support", adv_payload_shortens_long_name);
    RUN("support", evt_log_wraps);
    UNIT_EXIT();
}
