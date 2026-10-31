/* verifier probe: a failing test must make the build fail */
#include <stdio.h>

int main(void)
{
    printf("CI-FAIL-PROBE-RAN\n");
    return 3;
}
