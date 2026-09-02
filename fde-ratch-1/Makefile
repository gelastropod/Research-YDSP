CC ?= cc
CFLAGS ?= -O3 -std=c11 -Wall -Wextra -Wpedantic
CPPFLAGS += -D_POSIX_C_SOURCE=200809L -Iinclude -Ithird_party/blake3 \
	-DBLAKE3_NO_SSE2 -DBLAKE3_NO_SSE41 -DBLAKE3_NO_AVX2 -DBLAKE3_NO_AVX512 \
	$(shell pkg-config --cflags openssl 2>/dev/null)
LDLIBS += $(shell pkg-config --libs openssl 2>/dev/null || printf '%s' -lcrypto) \
	-lm -pthread

BUILD_DIR := build
BLAKE3_SRC := third_party/blake3/blake3.c \
	third_party/blake3/blake3_dispatch.c \
	third_party/blake3/blake3_portable.c
COMMON_SRC := src/fde.c $(BLAKE3_SRC)

.PHONY: all clean test sanitize benchmark graphs

all: $(BUILD_DIR)/fde_bench $(BUILD_DIR)/test_fde

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/fde_bench: src/benchmark.c $(COMMON_SRC) include/fde.h | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) src/benchmark.c $(COMMON_SRC) $(LDLIBS) -o $@

$(BUILD_DIR)/test_fde: tests/test_fde.c $(COMMON_SRC) include/fde.h | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_fde.c $(COMMON_SRC) $(LDLIBS) -o $@

test: $(BUILD_DIR)/test_fde
	./$(BUILD_DIR)/test_fde

sanitize: CFLAGS := -O1 -g -std=c11 -Wall -Wextra -Wpedantic \
	-fsanitize=address,undefined -fno-omit-frame-pointer
sanitize: clean $(BUILD_DIR)/test_fde
	ASAN_OPTIONS=detect_leaks=0 ./$(BUILD_DIR)/test_fde

.PHONY: sanitize-leaks
sanitize-leaks: CFLAGS := -O1 -g -std=c11 -Wall -Wextra -Wpedantic \
	-fsanitize=address,undefined -fno-omit-frame-pointer
sanitize-leaks: clean $(BUILD_DIR)/test_fde
	ASAN_OPTIONS=detect_leaks=1 ./$(BUILD_DIR)/test_fde

benchmark: $(BUILD_DIR)/fde_bench
	./scripts/capture_environment.sh results
	./$(BUILD_DIR)/fde_bench --all results

graphs:
	python3 scripts/plot_results.py results figures

clean:
	rm -rf $(BUILD_DIR)
