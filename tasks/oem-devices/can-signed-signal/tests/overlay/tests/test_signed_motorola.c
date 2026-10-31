#include "candec.h"
#include "unit.h"

#define SUITE "signals"

static can_signal_t sig(uint8_t start, uint8_t len, can_byte_order_t order, bool is_signed, double f, double o)
{
    can_signal_t s = { "s", start, len, order, is_signed, f, o };
    return s;
}

/* EngineCoolantTemp-like: 16|16@1- (0.1,0): raw 0xFE70 = -400 -> -40.0 */
TEST(intel_signed_physical_negative)
{
    const uint8_t d[8] = { 0, 0, 0x70, 0xFE, 0, 0, 0, 0 };
    can_signal_t s = sig(16, 16, CAN_LITTLE_ENDIAN, true, 0.1, 0);
    double phys = 0;
    CHECK_EQ_INT(CAN_OK, can_decode_physical(d, 8, &s, &phys));
    CHECK_NEAR(-40.0, phys, 1e-9);
}

/* 8|8@1- (1,-10): raw 0x80 = -128 -> -138 */
TEST(intel_signed_physical_with_offset)
{
    const uint8_t d[8] = { 0, 0x80, 0, 0, 0, 0, 0, 0 };
    can_signal_t s = sig(8, 8, CAN_LITTLE_ENDIAN, true, 1, -10);
    double phys = 0;
    CHECK_EQ_INT(CAN_OK, can_decode_physical(d, 8, &s, &phys));
    CHECK_NEAR(-138.0, phys, 1e-9);
}

/* unsigned physical stays unsigned: 0|8@1+ raw 0xFF */
TEST(intel_unsigned_physical_high_bit)
{
    const uint8_t d[8] = { 0xFF, 0, 0, 0, 0, 0, 0, 0 };
    can_signal_t s = sig(0, 8, CAN_LITTLE_ENDIAN, false, 0.5, 0);
    double phys = 0;
    CHECK_EQ_INT(CAN_OK, can_decode_physical(d, 8, &s, &phys));
    CHECK_NEAR(127.5, phys, 1e-9);
}

/* 8|40@1- : -123456789 */
TEST(intel_signed_40bit)
{
    const uint64_t raw40 = ((uint64_t)1 << 40) - 123456789u;
    uint8_t d[8] = { 0 };
    for (int i = 0; i < 5; i++) d[1 + i] = (uint8_t)(raw40 >> (8 * i));
    can_signal_t s = sig(8, 40, CAN_LITTLE_ENDIAN, true, 1, 0);
    int64_t v = 0;
    double phys = 0;
    CHECK_EQ_INT(CAN_OK, can_decode_value(d, 8, &s, &v));
    CHECK_EQ_INT(-123456789LL, v);
    CHECK_EQ_INT(CAN_OK, can_decode_physical(d, 8, &s, &phys));
    CHECK_NEAR(-123456789.0, phys, 1e-6);
}

/* 0|33@1- all ones -> -1 */
TEST(intel_signed_33bit_minus_one)
{
    const uint8_t d[8] = { 0xFF, 0xFF, 0xFF, 0xFF, 0x01, 0, 0, 0 };
    can_signal_t s = sig(0, 33, CAN_LITTLE_ENDIAN, true, 1, 0);
    int64_t v = 0;
    CHECK_EQ_INT(CAN_OK, can_decode_value(d, 8, &s, &v));
    CHECK_EQ_INT(-1, v);
}

/* 0|64@1- : INT64_MIN and -2 */
TEST(intel_signed_64bit)
{
    const uint8_t a[8] = { 0, 0, 0, 0, 0, 0, 0, 0x80 };
    const uint8_t b[8] = { 0xFE, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF };
    can_signal_t s = sig(0, 64, CAN_LITTLE_ENDIAN, true, 1, 0);
    int64_t v = 0;
    CHECK_EQ_INT(CAN_OK, can_decode_value(a, 8, &s, &v));
    CHECK(v == INT64_MIN);
    CHECK_EQ_INT(CAN_OK, can_decode_value(b, 8, &s, &v));
    CHECK_EQ_INT(-2, v);
}

/* 0|1@1- : a 1-bit signed signal is 0 or -1 */
TEST(intel_signed_1bit)
{
    const uint8_t d[8] = { 0x01, 0, 0, 0, 0, 0, 0, 0 };
    can_signal_t s = sig(0, 1, CAN_LITTLE_ENDIAN, true, 1, 0);
    int64_t v = 0;
    CHECK_EQ_INT(CAN_OK, can_decode_value(d, 8, &s, &v));
    CHECK_EQ_INT(-1, v);
}

/* EngineSpeed: 7|16@0+ (0.25,0): bytes 0x1F 0x40 -> 0x1F40 = 8000 -> 2000 rpm */
TEST(motorola_unsigned_16bit)
{
    const uint8_t d[8] = { 0x1F, 0x40, 0, 0, 0, 0, 0, 0 };
    can_signal_t s = sig(7, 16, CAN_BIG_ENDIAN, false, 0.25, 0);
    uint64_t raw = 0;
    double phys = 0;
    CHECK_EQ_INT(CAN_OK, can_extract_raw(d, 8, &s, &raw));
    CHECK_EQ_U64(0x1F40, raw);
    CHECK_EQ_INT(CAN_OK, can_decode_physical(d, 8, &s, &phys));
    CHECK_NEAR(2000.0, phys, 1e-9);
}

/* 7|16@0+ in a 2-byte frame must fit exactly */
TEST(motorola_fits_short_frame)
{
    const uint8_t d[2] = { 0x12, 0x34 };
    can_signal_t s = sig(7, 16, CAN_BIG_ENDIAN, false, 1, 0);
    uint64_t raw = 0;
    CHECK_EQ_INT(CAN_OK, can_extract_raw(d, 2, &s, &raw));
    CHECK_EQ_U64(0x1234, raw);
}

/* YawRate: 3|12@0- (0.5,0): byte0 low nibble = MSBs, byte1 = LSBs. 0xF9C = -100 -> -50.0 */
TEST(motorola_signed_12bit_crossing)
{
    const uint8_t d[8] = { 0xAF, 0x9C, 0, 0, 0, 0, 0, 0 };
    can_signal_t s = sig(3, 12, CAN_BIG_ENDIAN, true, 0.5, 0);
    uint64_t raw = 0;
    int64_t v = 0;
    double phys = 0;
    CHECK_EQ_INT(CAN_OK, can_extract_raw(d, 8, &s, &raw));
    CHECK_EQ_U64(0xF9C, raw);
    CHECK_EQ_INT(CAN_OK, can_decode_value(d, 8, &s, &v));
    CHECK_EQ_INT(-100, v);
    CHECK_EQ_INT(CAN_OK, can_decode_physical(d, 8, &s, &phys));
    CHECK_NEAR(-50.0, phys, 1e-9);
}

/* LatAccel: 39|24@0- spanning bytes 4..6, value -2 */
TEST(motorola_signed_24bit)
{
    const uint8_t d[8] = { 0, 0, 0, 0, 0xFF, 0xFF, 0xFE, 0x11 };
    can_signal_t s = sig(39, 24, CAN_BIG_ENDIAN, true, 0.001, 0);
    int64_t v = 0;
    double phys = 0;
    CHECK_EQ_INT(CAN_OK, can_decode_value(d, 8, &s, &v));
    CHECK_EQ_INT(-2, v);
    CHECK_EQ_INT(CAN_OK, can_decode_physical(d, 8, &s, &phys));
    CHECK_NEAR(-0.002, phys, 1e-12);
}

/* 7|64@0- : whole frame big endian */
TEST(motorola_signed_64bit)
{
    const uint8_t d[8] = { 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x85 };
    can_signal_t s = sig(7, 64, CAN_BIG_ENDIAN, true, 1, 0);
    int64_t v = 0;
    CHECK_EQ_INT(CAN_OK, can_decode_value(d, 8, &s, &v));
    CHECK_EQ_INT(-123, v);
}

/* 0|2@0+ : MSB at byte0 bit0, LSB at byte1 bit7 */
TEST(motorola_start_at_bit0)
{
    const uint8_t d[8] = { 0x01, 0x80, 0, 0, 0, 0, 0, 0 };
    can_signal_t s = sig(0, 2, CAN_BIG_ENDIAN, false, 1, 0);
    uint64_t raw = 0;
    CHECK_EQ_INT(CAN_OK, can_extract_raw(d, 2, &s, &raw));
    CHECK_EQ_U64(3, raw);
}

/* signal that runs past the payload must be rejected, output untouched */
TEST(motorola_out_of_range)
{
    const uint8_t d[8] = { 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF };
    can_signal_t s = sig(0, 2, CAN_BIG_ENDIAN, false, 1, 0);
    uint64_t raw = 0x77;
    CHECK_EQ_INT(CAN_ERR_RANGE, can_extract_raw(d, 1, &s, &raw));
    CHECK_EQ_U64(0x77, raw);
    s = sig(63, 16, CAN_BIG_ENDIAN, false, 1, 0); /* 63..56 then runs off byte 7 */
    CHECK_EQ_INT(CAN_ERR_RANGE, can_extract_raw(d, 8, &s, &raw));
    s = sig(23, 16, CAN_BIG_ENDIAN, false, 1, 0); /* bytes 2..3 need dlc >= 4 */
    CHECK_EQ_INT(CAN_ERR_RANGE, can_extract_raw(d, 3, &s, &raw));
    CHECK_EQ_INT(CAN_OK, can_extract_raw(d, 4, &s, &raw));
}

/* Regression guards (already correct). */
TEST(intel_signed_positive_unchanged)
{
    const uint8_t d[8] = { 0, 0, 0x90, 0x01, 0, 0, 0, 0 };
    can_signal_t s = sig(16, 16, CAN_LITTLE_ENDIAN, true, 0.1, 0);
    double phys = 0;
    CHECK_EQ_INT(CAN_OK, can_decode_physical(d, 8, &s, &phys));
    CHECK_NEAR(40.0, phys, 1e-9);
}

TEST(intel_unsigned_64bit)
{
    const uint8_t d[8] = { 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF };
    can_signal_t s = sig(0, 64, CAN_LITTLE_ENDIAN, false, 1, 0);
    uint64_t raw = 0;
    CHECK_EQ_INT(CAN_OK, can_extract_raw(d, 8, &s, &raw));
    CHECK_EQ_U64(0xFFFFFFFFFFFFFFFFull, raw);
}

TEST(motorola_single_byte_signed)
{
    const uint8_t d[8] = { 0, 0, 0, 0xF6, 0, 0, 0, 0 };
    can_signal_t s = sig(31, 8, CAN_BIG_ENDIAN, true, 1, 0);
    int64_t v = 0;
    CHECK_EQ_INT(CAN_OK, can_decode_value(d, 8, &s, &v));
    CHECK_EQ_INT(-10, v);
}

int main(void)
{
    RUN(SUITE, intel_signed_physical_negative);
    RUN(SUITE, intel_signed_physical_with_offset);
    RUN(SUITE, intel_unsigned_physical_high_bit);
    RUN(SUITE, intel_signed_40bit);
    RUN(SUITE, intel_signed_33bit_minus_one);
    RUN(SUITE, intel_signed_64bit);
    RUN(SUITE, intel_signed_1bit);
    RUN(SUITE, motorola_unsigned_16bit);
    RUN(SUITE, motorola_fits_short_frame);
    RUN(SUITE, motorola_signed_12bit_crossing);
    RUN(SUITE, motorola_signed_24bit);
    RUN(SUITE, motorola_signed_64bit);
    RUN(SUITE, motorola_start_at_bit0);
    RUN(SUITE, motorola_out_of_range);
    RUN(SUITE, intel_signed_positive_unchanged);
    RUN(SUITE, intel_unsigned_64bit);
    RUN(SUITE, motorola_single_byte_signed);
    UNIT_EXIT();
}
