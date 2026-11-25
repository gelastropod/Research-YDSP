#ifndef STREAM_FORMAT_H
#define STREAM_FORMAT_H

#include <stddef.h>
#include <string.h>

#include "hilbert.h"
#include "image_io.h"

typedef enum {
    FORMAT_RGBA, FORMAT_BC3, FORMAT_YCC
} PixelFormat;

enum { BLOCK_EDGE = 4, BLOCK_BYTES = 16 };

static inline const char *format_name(PixelFormat format)
{
    return format == FORMAT_YCC ? "ycc" : format == FORMAT_BC3 ? "bc3" : "rgba";
}

static inline int parse_format(const char *name, PixelFormat *format)
{
    if (strcmp(name, "ycc") == 0)
        *format = FORMAT_YCC;
    else if (strcmp(name, "bc3") == 0)
        *format = FORMAT_BC3;
    else if (strcmp(name, "rgba") == 0)
        *format = FORMAT_RGBA;
    else
        return 0;
    return 1;
}

static inline uint32_t record_edge(PixelFormat format)
{
    return format == FORMAT_RGBA ? 1 : BLOCK_EDGE;
}

static inline size_t record_bytes(PixelFormat format)
{
    return format == FORMAT_RGBA ? 4 : BLOCK_BYTES;
}

static inline int make_grid(uint64_t width, uint64_t height, PixelFormat format, Grid *grid)
{
    if (!image_fits(width, height))
        return 0;
    uint64_t side = width < height ? width : height;
    uint64_t length = width > height ? width : height;
    if (side < BLOCK_EDGE || (side & (side - 1)) || length % side)
        return 0;
    uint32_t edge = record_edge(format);
    *grid = (Grid){(uint32_t)(width / edge), (uint32_t)(height / edge), (uint32_t)(side / edge)};
    return 1;
}

static inline uint64_t record_count(const Grid *grid)
{
    return (uint64_t)grid->width * grid->height;
}

#endif
