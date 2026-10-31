#include "bootcfg.h"
#include "unit.h"

/* The decoder is given len < sizeof(buf): bytes past len must never be used. */

TEST(lone_type_byte_is_truncated)
{
    const uint8_t buf[] = {0x01, 0x01, 0x00, 0x11, 0x02, 'X', 'Y'};
    size_t rd = 0;
    bootcfg_tlv_t rec;
    CHECK_EQ_INT(BOOTCFG_OK, bootcfg_tlv_next(buf, 4, &rd, &rec));
    CHECK_EQ_INT(3, rd);
    CHECK_EQ_INT(BOOTCFG_ERR_TRUNCATED, bootcfg_tlv_next(buf, 4, &rd, &rec));
    CHECK_EQ_INT(3, rd);
}

TEST(header_only_at_end)
{
    const uint8_t buf[] = {0x10, 0x00, 0x11, 0x00};
    size_t rd = 0;
    bootcfg_tlv_t rec;
    CHECK_EQ_INT(BOOTCFG_OK, bootcfg_tlv_next(buf, 4, &rd, &rec));
    CHECK_EQ_INT(0, rec.len);
    CHECK_EQ_INT(BOOTCFG_OK, bootcfg_tlv_next(buf, 4, &rd, &rec));
    CHECK_EQ_INT(BOOTCFG_END, bootcfg_tlv_next(buf, 4, &rd, &rec));
}

TEST(verify_rejects_block_cut_inside_crc_header)
{
    uint8_t buf[32];
    size_t off = 0;
    bootcfg_tlv_put(buf, sizeof buf, &off, BOOTCFG_T_SERIAL, "SN1", 3);
    bootcfg_seal(buf, sizeof buf, &off);
    /* cut the block right after the CRC record's type byte */
    CHECK_EQ_INT(BOOTCFG_ERR_TRUNCATED, bootcfg_verify(buf, 6));
}

TEST(exact_fit_value)
{
    const uint8_t buf[] = {0x11, 0x03, 'A', 'B', 'C'};
    size_t rd = 0;
    bootcfg_tlv_t rec;
    CHECK_EQ_INT(BOOTCFG_OK, bootcfg_tlv_next(buf, 5, &rd, &rec));
    CHECK_EQ_INT(5, rd);
    CHECK_EQ_INT(BOOTCFG_ERR_TRUNCATED, bootcfg_tlv_next(buf, 4, &(size_t){0}, &rec));
}

int main(void)
{
    RUN("bounds", lone_type_byte_is_truncated);
    RUN("bounds", header_only_at_end);
    RUN("bounds", verify_rejects_block_cut_inside_crc_header);
    RUN("bounds", exact_fit_value);
    UNIT_EXIT();
}
