/* verifier probe: proves `make test` really builds and runs tests/test_*.c */
#include <stdio.h>

#include "bootcfg_build.h"

int main(void)
{
    printf("CI-PROBE-RAN BUILD_TAG=%s\n", bootcfg_build_tag());
    return 0;
}
