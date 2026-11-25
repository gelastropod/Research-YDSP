CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra
POSIX_FLAGS = -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64

.PHONY: all test clean
all: img2hilbert hilbert2img modify_block pad_image

image_prep.o: image_prep.c image_prep.h hilbert.h stream_format.h stb_image.h stb_image_resize2.h
	$(CC) $(CPPFLAGS) $(POSIX_FLAGS) $(CFLAGS) -c -o $@ $<

img2hilbert: img2hilbert.c image_prep.o image_prep.h files.h hilbert.h stream_format.h stb_dxt.h ycc.h
	$(CC) $(CPPFLAGS) $(POSIX_FLAGS) $(CFLAGS) $(LDFLAGS) -o $@ $< image_prep.o -lm $(LDLIBS)

pad_image: pad_image.c image_prep.o image_prep.h files.h hilbert.h stream_format.h stb_image_write.h
	$(CC) $(CPPFLAGS) $(POSIX_FLAGS) $(CFLAGS) $(LDFLAGS) -o $@ $< image_prep.o -lm $(LDLIBS)

hilbert2img: hilbert2img.c bc3.h files.h hilbert.h layout_meta.h stream_format.h stb_image_write.h ycc.h
	$(CC) $(CPPFLAGS) $(POSIX_FLAGS) $(CFLAGS) $(LDFLAGS) -o $@ $< -lm $(LDLIBS)

modify_block: modify_block.c files.h hilbert.h layout_meta.h stream_format.h
	$(CC) $(CPPFLAGS) $(POSIX_FLAGS) $(CFLAGS) $(LDFLAGS) -o $@ $< $(LDLIBS)

xts_blocks: xts_blocks.c files.h
	$(CC) $(CPPFLAGS) $(POSIX_FLAGS) $(CFLAGS) $(LDFLAGS) -o $@ $< -lcrypto $(LDLIBS)

test_resize: test_resize.c stb_image.h stb_image_resize2.h stb_image_write.h
	$(CC) $(CPPFLAGS) $(POSIX_FLAGS) $(CFLAGS) $(LDFLAGS) -o $@ $< -lm $(LDLIBS)

test: all test_resize xts_blocks
	python3 test_demo.py

clean:
	rm -f image_prep.o img2hilbert hilbert2img modify_block pad_image xts_blocks test_resize
