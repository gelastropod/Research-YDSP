CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra
POSIX_FLAGS = -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64

.PHONY: all test clean
all: pad_image encode decode modify_block

image_io.o: image_io.c image_io.h stb_image.h stb_image_resize2.h stb_image_write.h
	$(CC) $(CPPFLAGS) $(POSIX_FLAGS) $(CFLAGS) -c -o $@ $<

pad_image: pad_image.c image_io.o image_io.h files.h
	$(CC) $(CPPFLAGS) $(POSIX_FLAGS) $(CFLAGS) $(LDFLAGS) -o $@ $< image_io.o -lm $(LDLIBS)

encode: encode.c image_io.o image_io.h files.h hilbert.h stream_format.h stb_dxt.h ycc.h
	$(CC) $(CPPFLAGS) $(POSIX_FLAGS) $(CFLAGS) $(LDFLAGS) -o $@ $< image_io.o -lm $(LDLIBS)

decode: decode.c image_io.o image_io.h bc3.h files.h hilbert.h layout_meta.h stream_format.h ycc.h
	$(CC) $(CPPFLAGS) $(POSIX_FLAGS) $(CFLAGS) $(LDFLAGS) -o $@ $< image_io.o -lm $(LDLIBS)

modify_block: modify_block.c files.h hilbert.h image_io.h layout_meta.h stream_format.h
	$(CC) $(CPPFLAGS) $(POSIX_FLAGS) $(CFLAGS) $(LDFLAGS) -o $@ $< $(LDLIBS)

test: all
	python3 test_pipeline.py

clean:
	rm -f image_io.o pad_image encode decode modify_block
