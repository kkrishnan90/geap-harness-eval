#include <string.h>

#include "fwver.h"
#include "unit.h"

TEST(parse_release_and_rc)
{
    fwver_t v;
    CHECK_EQ_INT(0, fwver_parse("4.12.3", &v));
    CHECK_EQ_INT(4, v.major);
    CHECK_EQ_INT(12, v.minor);
    CHECK_EQ_INT(3, v.patch);
    CHECK_EQ_INT(0, v.rc);
    CHECK_EQ_INT(0, fwver_parse("5.0.0-rc2", &v));
    CHECK_EQ_INT(2, v.rc);
}

TEST(parse_rejects)
{
    fwver_t v;
    const char *bad[] = {"", "4", "4.1", "4.1.", "04.1.0", "4.1.0-rc0", "4.1.0-beta", "4.1.65536", "4.1.0 "};
    for (size_t i = 0; i < sizeof bad / sizeof bad[0]; i++) {
        CHECK_EQ_INT(-1, fwver_parse(bad[i], &v));
    }
}

TEST(compare_orders_rc_before_release)
{
    fwver_t a, b, c;
    fwver_parse("5.0.0-rc1", &a);
    fwver_parse("5.0.0-rc10", &b);
    fwver_parse("5.0.0", &c);
    CHECK(fwver_compare(&a, &b) < 0);
    CHECK(fwver_compare(&b, &c) < 0);
    CHECK(fwver_compare(&c, &a) > 0);
    CHECK_EQ_INT(0, fwver_compare(&c, &c));
}

TEST(format_roundtrip)
{
    fwver_t v;
    char buf[32];
    fwver_parse("12.0.7-rc3", &v);
    CHECK_EQ_INT(10, fwver_format(&v, buf, sizeof buf));
    CHECK(strcmp(buf, "12.0.7-rc3") == 0);
    CHECK_EQ_INT(-1, fwver_format(&v, buf, 5));
}

int main(void)
{
    RUN("fwver", parse_release_and_rc);
    RUN("fwver", parse_rejects);
    RUN("fwver", compare_orders_rc_before_release);
    RUN("fwver", format_roundtrip);
    UNIT_EXIT();
}
