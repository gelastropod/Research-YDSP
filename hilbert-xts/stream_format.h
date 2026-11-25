#ifndef STREAM_FORMAT_H
#define STREAM_FORMAT_H

#include <stddef.h>

#include "hilbert.h"

typedef enum {
    FORMAT_RGBA, FORMAT_BC3, FORMAT_YCC
} PixelFormat;

enum { BLOCK_EDGE = 4, BLOCK_BYTES = 16 };

static inline uint32_t record_edge(PixelFormat format)
{
    return format == FORMAT_RGBA ? 1 : BLOCK_EDGE;
}

static inline size_t record_bytes(PixelFormat format)
{
    return format == FORMAT_RGBA ? 4 : BLOCK_BYTES;
}

static inline Layout record_grid(const Layout *canvas, PixelFormat format)
{
    uint32_t edge = record_edge(format);
    uint32_t width = canvas->canvas_width / edge, height = canvas->canvas_height / edge;
    return (Layout){
        .width = width, .height = height, .side = canvas->side / edge, .tiles = canvas->tiles,
        .canvas_width = width, .canvas_height = height, .axis = canvas->axis,
    };
}

#endif
