#include "candec.h"
#include "unit.h"

#define SUITE "candec"

static can_signal_t sig(uint8_t start, uint8_t len, can_byte_order_t order, bool is_signed, double f, double o)
{
    can_signal_t s = { "s", start, len, order, is_signed, f, o };
    return s;
}

/* VehicleSpeed: 0|16@1+ (0.01,0) km/h */
TEST(intel_unsigned_16bit)
{
    const uint8_t d[8] = { 0x10, 0x27, 0, 0, 0, 0, 0, 0 };
    can_signal_t s = sig(0, 16, CAN_LITTLE_ENDIAN, false, 0.01, 0);
    uint64_t raw = 0;
    double phys = 0;
    CHECK_EQ_INT(CAN_OK, can_extract_raw(d, 8, &s, &raw));
    CHECK_EQ_U64(0x2710, raw);
    CHECK_EQ_INT(CAN_OK, can_decode_physical(d, 8, &s, &phys));
    CHECK_NEAR(100.0, phys, 1e-9);
}

/* Gear: 12|3@1+ inside one byte, not byte aligned */
TEST(intel_unaligned_nibble)
{
    const uint8_t d[8] = { 0x00, 0x50, 0, 0, 0, 0, 0, 0 };
    can_signal_t s = sig(12, 3, CAN_LITTLE_ENDIAN, false, 1, 0);
    uint64_t raw = 0;
    CHECK_EQ_INT(CAN_OK, can_extract_raw(d, 8, &s, &raw));
    CHECK_EQ_U64(5, raw);
}

/* Odometer: 20|24@1+ spans four bytes */
TEST(intel_spanning_bytes)
{
    const uint8_t d[8] = { 0x00, 0x00, 0x50, 0x34, 0x12, 0x00, 0, 0 };
    can_signal_t s = sig(20, 24, CAN_LITTLE_ENDIAN, false, 1, 0);
    uint64_t raw = 0;
    CHECK_EQ_INT(CAN_OK, can_extract_raw(d, 8, &s, &raw));
    CHECK_EQ_U64(0x012345, raw);
}

/* SteeringAngleRate: 16|16@1- signed small values */
TEST(intel_signed_value)
{
    const uint8_t d[8] = { 0, 0, 0x9C, 0xFF, 0, 0, 0, 0 };
    can_signal_t s = sig(16, 16, CAN_LITTLE_ENDIAN, true, 1, 0);
    int64_t v = 0;
    CHECK_EQ_INT(CAN_OK, can_decode_value(d, 8, &s, &v));
    CHECK_EQ_INT(-100, v);
}

/* DoorState: 7|8@0+ whole first byte, Motorola */
TEST(motorola_single_byte)
{
    const uint8_t d[8] = { 0xA5, 0, 0, 0, 0, 0, 0, 0 };
    can_signal_t s = sig(7, 8, CAN_BIG_ENDIAN, false, 1, 0);
    uint64_t raw = 0;
    CHECK_EQ_INT(CAN_OK, can_extract_raw(d, 8, &s, &raw));
    CHECK_EQ_U64(0xA5, raw);
}

/* WiperMode: 21|3@0+ inside byte 2 */
TEST(motorola_bits_inside_byte)
{
    const uint8_t d[8] = { 0, 0, 0x28, 0, 0, 0, 0, 0 }; /* bits 21..19 = 101 */
    can_signal_t s = sig(21, 3, CAN_BIG_ENDIAN, false, 1, 0);
    uint64_t raw = 0;
    CHECK_EQ_INT(CAN_OK, can_extract_raw(d, 8, &s, &raw));
    CHECK_EQ_U64(5, raw);
}

TEST(argument_errors)
{
    const uint8_t d[8] = { 0 };
    uint64_t raw = 0;
    can_signal_t s = sig(0, 0, CAN_LITTLE_ENDIAN, false, 1, 0);
    CHECK_EQ_INT(CAN_ERR_LENGTH, can_extract_raw(d, 8, &s, &raw));
    s.length = 65;
    CHECK_EQ_INT(CAN_ERR_LENGTH, can_extract_raw(d, 8, &s, &raw));
    s.length = 8;
    CHECK_EQ_INT(CAN_ERR_DLC, can_extract_raw(d, 9, &s, &raw));
    CHECK_EQ_INT(CAN_ERR_NULL, can_extract_raw(NULL, 8, &s, &raw));
    CHECK_EQ_INT(CAN_ERR_NULL, can_extract_raw(d, 8, &s, NULL));
}

TEST(intel_out_of_range)
{
    const uint8_t d[8] = { 0 };
    uint64_t raw = 0;
    can_signal_t s = sig(8, 16, CAN_LITTLE_ENDIAN, false, 1, 0);
    CHECK_EQ_INT(CAN_ERR_RANGE, can_extract_raw(d, 2, &s, &raw));
    CHECK_EQ_INT(CAN_OK, can_extract_raw(d, 3, &s, &raw));
}

TEST(output_untouched_on_error)
{
    const uint8_t d[8] = { 0 };
    uint64_t raw = 0xDEAD;
    can_signal_t s = sig(60, 8, CAN_LITTLE_ENDIAN, false, 1, 0);
    CHECK_EQ_INT(CAN_ERR_RANGE, can_extract_raw(d, 8, &s, &raw));
    CHECK_EQ_U64(0xDEAD, raw);
}

int main(void)
{
    RUN(SUITE, intel_unsigned_16bit);
    RUN(SUITE, intel_unaligned_nibble);
    RUN(SUITE, intel_spanning_bytes);
    RUN(SUITE, intel_signed_value);
    RUN(SUITE, motorola_single_byte);
    RUN(SUITE, motorola_bits_inside_byte);
    RUN(SUITE, argument_errors);
    RUN(SUITE, intel_out_of_range);
    RUN(SUITE, output_untouched_on_error);
    UNIT_EXIT();
}
