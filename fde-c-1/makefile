SDIR = src
TDIR = tests
IDIR = include
ODIR = obj
BDIR = build
CC = gcc
CFLAGS = -Wall -Wextra -I$(IDIR) -MMD -MP

LIBS = -lmbedcrypto

COMMON_SRC = $(shell find $(SDIR) -name '*.c')
TEST_SRC = $(shell find $(TDIR) -name '*.c')
TARGETS = $(patsubst $(TDIR)/%.c,$(BDIR)/%,$(TEST_SRC))

COMMON_OBJ=$(patsubst $(SDIR)/%.c,$(ODIR)/$(SDIR)/%.o,$(COMMON_SRC))
DEPS = $(patsubst $(SDIR)/%.c,$(ODIR)/$(SDIR)/%.d,$(COMMON_SRC)) \
       $(patsubst $(TDIR)/%.c,$(ODIR)/$(TDIR)/%.d,$(TEST_SRC))

all: $(TARGETS)

$(ODIR)/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

$(BDIR)/%: $(ODIR)/$(TDIR)/%.o $(COMMON_OBJ)
	@mkdir -p $(dir $@)
	$(CC) $(CLAGS) $< $(COMMON_OBJ) -o $@ $(LIBS)

-include $(DEPS)

.PHONY: all clean
.SECONDARY: $(COMMON_OBJ)

clean:
	rm -rf $(ODIR) $(BDIR)
