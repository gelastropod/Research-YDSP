# Build configuration for the in-memory ratcheted FDE benchmark.
#
# Common commands:
#   make                 Build build/fde_bench.
#   make test            Build and run build/fde_test.
#   make sanitize        Run the correctness suite with ASan/UBSan.
#   make sanitize-leaks  Run the sanitizer suite with leak detection enabled.
#   make quick           Run a short benchmark into results/.
#   make benchmark       Run the full benchmark into results/.

PROJECT       := fde-ratchet-bench
CC            ?= cc
PKG_CONFIG    ?= pkg-config

SRC_DIR       := src
TEST_DIR      := tests
INCLUDE_DIR   := include
BLAKE3_DIR    := third_party/blake3
OBJ_DIR       := obj
BUILD_DIR     := build
SAN_OBJ_DIR   := obj-sanitize
SAN_BUILD_DIR := build-sanitize
RESULTS_DIR   ?= results

# The vendored BLAKE3 tree contains the portable implementation only.  Disable
# dispatch entries whose SIMD implementation files are not vendored here.
BLAKE3_CPPFLAGS := \
	-DBLAKE3_NO_SSE2 \
	-DBLAKE3_NO_SSE41 \
	-DBLAKE3_NO_AVX2 \
	-DBLAKE3_NO_AVX512

# Prefer pkg-config when it is available, but keep the project buildable on a
# host where only the system libcrypto linker name is available.
OPENSSL_CFLAGS ?= $(shell $(PKG_CONFIG) --cflags openssl 2>/dev/null)
OPENSSL_LIBS   ?= $(shell $(PKG_CONFIG) --libs openssl 2>/dev/null)
ifeq ($(strip $(OPENSSL_LIBS)),)
OPENSSL_LIBS := -lcrypto
endif

CPPFLAGS += -I$(INCLUDE_DIR) -I$(BLAKE3_DIR) \
	-D_POSIX_C_SOURCE=200809L \
	$(BLAKE3_CPPFLAGS) $(OPENSSL_CFLAGS)
CFLAGS   ?= -O2 -g
CFLAGS   += -std=c11 -Wall -Wextra -Wpedantic -MMD -MP
LDFLAGS  ?=
LDLIBS   += $(OPENSSL_LIBS) -lm -pthread

LIB_SRCS := \
	$(SRC_DIR)/fde.c \
	$(BLAKE3_DIR)/blake3.c \
	$(BLAKE3_DIR)/blake3_dispatch.c \
	$(BLAKE3_DIR)/blake3_portable.c
BENCH_SRC := $(SRC_DIR)/benchmark.c
TEST_SRC  := $(TEST_DIR)/test_fde.c

LIB_OBJS   := $(patsubst %.c,$(OBJ_DIR)/%.o,$(LIB_SRCS))
BENCH_OBJ  := $(patsubst %.c,$(OBJ_DIR)/%.o,$(BENCH_SRC))
TEST_OBJ   := $(patsubst %.c,$(OBJ_DIR)/%.o,$(TEST_SRC))
DEPS       := $(LIB_OBJS:.o=.d) $(BENCH_OBJ:.o=.d) $(TEST_OBJ:.o=.d)

BENCH_BIN := $(BUILD_DIR)/fde_bench
TEST_BIN  := $(BUILD_DIR)/fde_test

SAN_CFLAGS  := $(CFLAGS) -O1 -fsanitize=address,undefined -fno-omit-frame-pointer
SAN_LDFLAGS := $(LDFLAGS) -fsanitize=address,undefined
SAN_LIB_OBJS  := $(patsubst %.c,$(SAN_OBJ_DIR)/%.o,$(LIB_SRCS))
SAN_BENCH_OBJ := $(patsubst %.c,$(SAN_OBJ_DIR)/%.o,$(BENCH_SRC))
SAN_TEST_OBJ  := $(patsubst %.c,$(SAN_OBJ_DIR)/%.o,$(TEST_SRC))
SAN_DEPS      := $(SAN_LIB_OBJS:.o=.d) $(SAN_BENCH_OBJ:.o=.d) \
	$(SAN_TEST_OBJ:.o=.d)
SAN_TEST_BIN  := $(SAN_BUILD_DIR)/fde_test

.DEFAULT_GOAL := all

.PHONY: all test sanitize sanitize-leaks clean rebuild \
	quick benchmark bench rq1 rq2 rq3 rq4 capture results run-all help

all: $(BENCH_BIN)

test: $(TEST_BIN)
	$(TEST_BIN)

sanitize: $(SAN_TEST_BIN)
	ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
		$(SAN_TEST_BIN)

sanitize-leaks: $(SAN_TEST_BIN)
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
		$(SAN_TEST_BIN)

$(BENCH_BIN): $(BENCH_OBJ) $(LIB_OBJS)
	@mkdir -p $(@D)
	$(CC) $(LDFLAGS) -o $@ $^ $(LDLIBS)

$(TEST_BIN): $(TEST_OBJ) $(LIB_OBJS)
	@mkdir -p $(@D)
	$(CC) $(LDFLAGS) -o $@ $^ $(LDLIBS)

$(OBJ_DIR)/%.o: %.c
	@mkdir -p $(@D)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(SAN_BUILD_DIR)/fde_test: $(SAN_TEST_OBJ) $(SAN_LIB_OBJS)
	@mkdir -p $(@D)
	$(CC) $(SAN_LDFLAGS) -o $@ $^ $(LDLIBS)

$(SAN_OBJ_DIR)/%.o: %.c
	@mkdir -p $(@D)
	$(CC) $(CPPFLAGS) $(SAN_CFLAGS) -c $< -o $@

quick: $(BENCH_BIN)
	$(BENCH_BIN) --quick $(RESULTS_DIR)

benchmark bench: $(BENCH_BIN)
	$(BENCH_BIN) --all $(RESULTS_DIR)

rq1: $(BENCH_BIN)
	$(BENCH_BIN) --rq1 $(RESULTS_DIR)

rq2: $(BENCH_BIN)
	$(BENCH_BIN) --rq2 $(RESULTS_DIR)

rq3: $(BENCH_BIN)
	$(BENCH_BIN) --rq3 $(RESULTS_DIR)

rq4: $(BENCH_BIN)
	$(BENCH_BIN) --rq4 $(RESULTS_DIR)

capture:
	sh scripts/capture_environment.sh $(RESULTS_DIR)

results: $(BENCH_BIN)
	sh scripts/capture_environment.sh $(RESULTS_DIR)
	$(BENCH_BIN) --all $(RESULTS_DIR)

run-all:
	sh scripts/run_all.sh

rebuild:
	$(MAKE) clean
	$(MAKE) all

clean:
	$(RM) -r $(OBJ_DIR) $(BUILD_DIR) $(SAN_OBJ_DIR) $(SAN_BUILD_DIR)

help:
	@printf '%s\n' \
		'$(PROJECT) build targets:' \
		'  all (default)    Build the benchmark executable.' \
		'  test             Build and run the correctness suite.' \
		'  sanitize         Run AddressSanitizer and UndefinedBehaviorSanitizer.' \
		'  sanitize-leaks   Run sanitizers with leak detection enabled.' \
		'  quick            Run the short benchmark profile.' \
		'  benchmark        Run the full benchmark profile.' \
		'  rq1 ... rq4      Run one research-question benchmark.' \
		'  capture          Capture environment metadata only.' \
		'  results          Capture metadata and run the full benchmark.' \
		'  run-all          Run scripts/run_all.sh.' \
		'  clean            Remove generated objects and binaries.'

-include $(DEPS) $(SAN_DEPS)

.SECONDARY: $(LIB_OBJS) $(BENCH_OBJ) $(TEST_OBJ) \
	$(SAN_LIB_OBJS) $(SAN_BENCH_OBJ) $(SAN_TEST_OBJ)
