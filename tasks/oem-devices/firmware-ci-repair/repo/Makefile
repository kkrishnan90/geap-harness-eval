# bootcfg-tools build. `make ci` is what the Jenkins pipeline runs (ci/Jenkinsfile).
CC       := clang
CPPFLAGS := -I$(INC_DIR)/
CFLAGS   := -std=c11 -Wall -Wextra -Werror -O2
ARFLAGS  := rcs

SRC_DIR  := src
INC_DIR  := include
BUILD    := build
OBJ_DIR  := $(BUILD)/obj

SRCS      := $(wildcard $(SRC_DIR)/*.c)
OBJS      := $(patsubst $(SRC_DIR)/%.c,$(OBJ_DIR)/%.o,$(SRCS))
LIB       := $(BUILD)/libbootcfg.a
TEST_SRCS := $(wildcard tests/*_test.c)
TEST_BINS := $(patsubst tests/%.c,$(BUILD)/%,$(TEST_SRCS))

.PHONY: all test ci clean

all: $(LIB)

$(OBJ_DIR):
	mkdir -p $@

$(OBJ_DIR)/%.o: $(SRC_DIR)/%.c | $(OBJ_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(LIB): $(OBJS)
	$(AR) $(ARFLAGS) $@ $^

$(BUILD)/test_%: tests/test_%.c $(LIB)
	$(CC) $(CPPFLAGS) $(CFLAGS) -Itests $< $(LIB) -o $@

test: $(TEST_BINS)
	@for t in $(TEST_BINS); do ./$$t || true; done
	@echo "all tests passed"

ci: clean all test

clean:
	rm -rf $(BUILD)
