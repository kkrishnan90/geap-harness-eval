CC      ?= clang
CFLAGS  ?= -std=c11 -Wall -Wextra -Werror -O1 -Iinclude
SRC     := $(wildcard src/*.c)
TESTS   := $(patsubst tests/%.c,build/%,$(wildcard tests/test_*.c))

.PHONY: all test clean
all: build/libcandec.a

build:
	mkdir -p build

build/libcandec.a: $(SRC) | build
	$(CC) $(CFLAGS) -c $(SRC)
	mv *.o build/
	ar rcs $@ build/*.o

build/test_%: tests/test_%.c $(SRC) tests/unit.h | build
	$(CC) $(CFLAGS) -Itests -o $@ $< $(SRC) -lm

test: $(TESTS)
	@set -e; for t in $(TESTS); do ./$$t; done

clean:
	rm -rf build
