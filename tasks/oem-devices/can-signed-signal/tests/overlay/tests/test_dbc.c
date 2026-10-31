#include <string.h>

#include "dbc_lite.h"
#include "unit.h"

#define SUITE "dbc"

TEST(parse_intel_signed)
{
    dbc_signal_t s;
    CHECK_EQ_INT(0, dbc_parse_signal(" SG_ EngineCoolantTemp : 16|16@1- (0.1,-40) [-40|215] \"degC\" ECM", &s));
    CHECK(strcmp(s.name, "EngineCoolantTemp") == 0);
    CHECK(strcmp(s.sig.name, "EngineCoolantTemp") == 0);
    CHECK_EQ_INT(16, s.sig.start_bit);
    CHECK_EQ_INT(16, s.sig.length);
    CHECK(s.sig.order == CAN_LITTLE_ENDIAN);
    CHECK(s.sig.is_signed);
    CHECK_NEAR(0.1, s.sig.factor, 1e-12);
    CHECK_NEAR(-40.0, s.sig.offset, 1e-12);
    CHECK_NEAR(215.0, s.maximum, 1e-12);
    CHECK(strcmp(s.unit, "degC") == 0);
}

TEST(parse_motorola_unsigned)
{
    dbc_signal_t s;
    CHECK_EQ_INT(0, dbc_parse_signal("SG_ BrakePressure : 7|12@0+ (0.5,0) [0|2047.5] \"bar\" ESC,BCM", &s));
    CHECK(s.sig.order == CAN_BIG_ENDIAN);
    CHECK(!s.sig.is_signed);
    CHECK_EQ_INT(7, s.sig.start_bit);
    CHECK_EQ_INT(12, s.sig.length);
}

TEST(reject_malformed)
{
    dbc_signal_t s;
    CHECK_EQ_INT(-1, dbc_parse_signal("BO_ 100 Foo: 8 ECM", &s));
    CHECK_EQ_INT(-1, dbc_parse_signal("SG_ X : 7|12@2+ (1,0) [0|1] \"\" A", &s));
    CHECK_EQ_INT(-1, dbc_parse_signal("SG_ X : 7|0@1+ (1,0) [0|1] \"\" A", &s));
    CHECK_EQ_INT(-1, dbc_parse_signal("SG_ X : 64|8@1+ (1,0) [0|1] \"\" A", &s));
    CHECK_EQ_INT(-1, dbc_parse_signal("SG_ X : 7|8@1+ (1,0) [0|1] \"unterminated", &s));
}

int main(void)
{
    RUN(SUITE, parse_intel_signed);
    RUN(SUITE, parse_motorola_unsigned);
    RUN(SUITE, reject_malformed);
    UNIT_EXIT();
}
