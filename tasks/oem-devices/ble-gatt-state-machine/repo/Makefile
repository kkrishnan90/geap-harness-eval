CC      ?= clang
CFLAGS  ?= -std=c11 -Wall -Wextra -Werror -O1 -Iinclude
SRC     := $(wildcard src/*.c)
TESTS   := $(patsubst tests/%.c,build/%,$(wildcard tests/test_*.c))

.PHONY: all test clean
all: $(TESTS)

build:
	mkdir -p build

build/test_%: tests/test_%.c $(SRC) $(wildcard include/*.h) tests/unit.h | build
	$(CC) $(CFLAGS) -Itests -o $@ $< $(SRC)

test: $(TESTS)
	@set -e; for t in $(TESTS); do ./$$t; done

clean:
	rm -rf build
