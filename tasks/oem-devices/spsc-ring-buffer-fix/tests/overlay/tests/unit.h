/* Minimal unit-test harness: each test runs in a forked child so a crash fails only that test.
 * Output: "RESULT PASS|FAIL <suite>.<test>" */
#ifndef UNIT_H
#define UNIT_H

#define _POSIX_C_SOURCE 200809L
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

static int unit_failed_;
static int unit_total_failed_;

#define CHECK(cond) do { if (!(cond)) { \
    printf("  %s:%d: CHECK(%s) failed\n", __FILE__, __LINE__, #cond); unit_failed_ = 1; } } while (0)
#define CHECK_EQ_INT(exp, act) do { long long e_ = (long long)(exp), a_ = (long long)(act); if (e_ != a_) { \
    printf("  %s:%d: expected %lld, got %lld (%s)\n", __FILE__, __LINE__, e_, a_, #act); unit_failed_ = 1; } } while (0)
#define CHECK_EQ_U64(exp, act) do { unsigned long long e_ = (exp), a_ = (act); if (e_ != a_) { \
    printf("  %s:%d: expected 0x%llx, got 0x%llx (%s)\n", __FILE__, __LINE__, e_, a_, #act); unit_failed_ = 1; } } while (0)
#define CHECK_NEAR(exp, act, tol) do { double e_ = (exp), a_ = (act); if (!(fabs(e_ - a_) <= (tol))) { \
    printf("  %s:%d: expected %.6f, got %.6f (%s)\n", __FILE__, __LINE__, e_, a_, #act); unit_failed_ = 1; } } while (0)

#define TEST(name) static void name(void)

#define RUN(suite, name) do { \
    fflush(stdout); \
    pid_t pid_ = fork(); \
    if (pid_ == 0) { unit_failed_ = 0; name(); fflush(stdout); _exit(unit_failed_ ? 1 : 0); } \
    int st_ = 0; waitpid(pid_, &st_, 0); \
    int ok_ = pid_ > 0 && WIFEXITED(st_) && WEXITSTATUS(st_) == 0; \
    if (!ok_ && pid_ > 0 && WIFSIGNALED(st_)) printf("  crashed with signal %d\n", WTERMSIG(st_)); \
    printf("RESULT %s %s.%s\n", ok_ ? "PASS" : "FAIL", suite, #name); \
    if (!ok_) unit_total_failed_++; \
} while (0)

#define UNIT_EXIT() return unit_total_failed_ ? 1 : 0

#endif
