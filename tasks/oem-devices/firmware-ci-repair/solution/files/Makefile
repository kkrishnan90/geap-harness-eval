# bootcfg-tools build. `make ci` is what the Jenkins pipeline runs (ci/Jenkinsfile).
CC       := clang
SRC_DIR  := src
INC_DIR  := include
BUILD    := build
OBJ_DIR  := $(BUILD)/obj

CPPFLAGS := -I$(INC_DIR)
CFLAGS   := -std=c11 -Wall -Wextra -Werror -O2
DEPFLAGS  = -MMD -MP
ARFLAGS  := rcs

SRCS      := $(wildcard $(SRC_DIR)/*.c)
OBJS      := $(patsubst $(SRC_DIR)/%.c,$(OBJ_DIR)/%.o,$(SRCS))
LIB       := $(BUILD)/libbootcfg.a
TEST_SRCS := $(wildcard tests/test_*.c)
TEST_BINS := $(patsubst tests/%.c,$(BUILD)/%,$(TEST_SRCS))
DEPS      := $(OBJS:.o=.d) $(TEST_BINS:=.d)

.PHONY: all test ci clean

all: $(LIB)

$(OBJ_DIR):
	mkdir -p $@

$(OBJ_DIR)/%.o: $(SRC_DIR)/%.c | $(OBJ_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(DEPFLAGS) -c $< -o $@

$(LIB): $(OBJS)
	rm -f $@
	$(AR) $(ARFLAGS) $@ $^

$(BUILD)/test_%: tests/test_%.c $(LIB) | $(OBJ_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -MMD -MP -MF $@.d -Itests $< $(LIB) -o $@

test: $(TEST_BINS)
	@set -e; for t in $(TEST_BINS); do echo "== $$t"; ./$$t; done
	@echo "all tests passed"

ci:
	$(MAKE) clean
	$(MAKE) all
	$(MAKE) test

clean:
	rm -rf $(BUILD)

-include $(DEPS)
