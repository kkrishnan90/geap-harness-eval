#include <string.h>

#include "bootcfg.h"
#include "unit.h"

TEST(put_and_iterate)
{
    uint8_t buf[64];
    size_t off = 0;
    uint8_t slot = 1;
    uint8_t count[4] = {3, 0, 0, 0};
    CHECK_EQ_INT(BOOTCFG_OK, bootcfg_tlv_put(buf, sizeof buf, &off, BOOTCFG_T_ACTIVE_SLOT, &slot, 1));
    CHECK_EQ_INT(BOOTCFG_OK, bootcfg_tlv_put(buf, sizeof buf, &off, BOOTCFG_T_BOOT_COUNT, count, 4));
    CHECK_EQ_INT(BOOTCFG_OK, bootcfg_tlv_put(buf, sizeof buf, &off, BOOTCFG_T_FW_VERSION, "4.2.0", 5));
    CHECK_EQ_INT(3 + 6 + 7, off);

    size_t rd = 0;
    bootcfg_tlv_t rec;
    CHECK_EQ_INT(BOOTCFG_OK, bootcfg_tlv_next(buf, off, &rd, &rec));
    CHECK_EQ_INT(BOOTCFG_T_ACTIVE_SLOT, rec.type);
    CHECK_EQ_INT(1, rec.value[0]);
    CHECK_EQ_INT(BOOTCFG_OK, bootcfg_tlv_next(buf, off, &rd, &rec));
    CHECK_EQ_INT(4, rec.len);
    CHECK_EQ_INT(BOOTCFG_OK, bootcfg_tlv_next(buf, off, &rd, &rec));
    CHECK(memcmp(rec.value, "4.2.0", 5) == 0);
    CHECK_EQ_INT(BOOTCFG_END, bootcfg_tlv_next(buf, off, &rd, &rec));
}

TEST(pad_bytes_skipped)
{
    const uint8_t buf[] = {0x00, 0x00, 0x01, 0x01, 0x00, 0x00};
    size_t rd = 0;
    bootcfg_tlv_t rec;
    CHECK_EQ_INT(BOOTCFG_OK, bootcfg_tlv_next(buf, sizeof buf, &rd, &rec));
    CHECK_EQ_INT(BOOTCFG_T_ACTIVE_SLOT, rec.type);
    CHECK_EQ_INT(0, rec.value[0]);
    CHECK_EQ_INT(BOOTCFG_END, bootcfg_tlv_next(buf, sizeof buf, &rd, &rec));
}

TEST(value_truncated)
{
    const uint8_t buf[] = {0x10, 0x05, 'a', 'b'};
    size_t rd = 0;
    bootcfg_tlv_t rec;
    CHECK_EQ_INT(BOOTCFG_ERR_TRUNCATED, bootcfg_tlv_next(buf, sizeof buf, &rd, &rec));
}

TEST(put_out_of_space)
{
    uint8_t buf[4];
    size_t off = 0;
    CHECK_EQ_INT(BOOTCFG_ERR_SPACE, bootcfg_tlv_put(buf, sizeof buf, &off, BOOTCFG_T_SERIAL, "ABC", 3));
    CHECK_EQ_INT(0, off);
}

TEST(seal_and_verify)
{
    uint8_t buf[64];
    size_t off = 0;
    bootcfg_tlv_put(buf, sizeof buf, &off, BOOTCFG_T_SERIAL, "GW7-000123", 10);
    CHECK_EQ_INT(BOOTCFG_OK, bootcfg_seal(buf, sizeof buf, &off));
    CHECK_EQ_INT(BOOTCFG_OK, bootcfg_verify(buf, off));
    buf[3] ^= 0x20u;
    CHECK_EQ_INT(BOOTCFG_ERR_CRC, bootcfg_verify(buf, off));
}

int main(void)
{
    RUN("tlv", put_and_iterate);
    RUN("tlv", pad_bytes_skipped);
    RUN("tlv", value_truncated);
    RUN("tlv", put_out_of_space);
    RUN("tlv", seal_and_verify);
    UNIT_EXIT();
}
