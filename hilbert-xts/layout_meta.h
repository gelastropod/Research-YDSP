#ifndef LAYOUT_META_H
#define LAYOUT_META_H

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "stream_format.h"

static inline int read_layout(const char *path, Layout *layout, PixelFormat *format)
{
    FILE *meta = fopen(path, "r");
    if (!meta) {
        perror(path);
        return 0;
    }
    uint64_t original_width, original_height, width = 0, height = 0, side = 0, tiles, offset_x, offset_y;
    char axis, flag[8];
    int fields = fscanf(meta,
                        "%10" SCNu64 " %10" SCNu64 " %10" SCNu64 " %10" SCNu64
                        " %10" SCNu64 " %10" SCNu64 " %c %10" SCNu64 " %10" SCNu64,
                        &original_width, &original_height, &width, &height,
                        &side, &tiles, &axis, &offset_x, &offset_y);
    Fit fit = FIT_SHORT;
    *format = FORMAT_RGBA;
    int next = fields == 9 ? fscanf(meta, "%7s", flag) : EOF;
    if (next == 1 && strcmp(flag, "long") == 0) {
        fit = FIT_LONG;
        next = fscanf(meta, "%7s", flag);
    }
    if (next == 1 && strcmp(flag, "bc3") == 0) {
        *format = FORMAT_BC3;
        next = fscanf(meta, "%1s", flag);
    } else if (next == 1 && strcmp(flag, "ycc") == 0) {
        *format = FORMAT_YCC;
        next = fscanf(meta, "%1s", flag);
    }
    int meta_error = ferror(meta);
    fclose(meta);
    uint64_t target = fit == FIT_LONG ? (width > height ? width : height) : side;
    if (fields != 9 || next != EOF || meta_error ||
        original_width > INT_MAX || original_height > INT_MAX || target > UINT32_MAX ||
        !make_layout((uint32_t)original_width, (uint32_t)original_height, (uint32_t)target, fit, layout) ||
        width != layout->width || height != layout->height || side != layout->side || tiles != layout->tiles ||
        axis != layout->axis || offset_x != layout->offset_x || offset_y != layout->offset_y ||
        layout->side < record_edge(*format)) {
        fprintf(stderr, "%s: invalid or unsupported Hilbert layout metadata\n", path);
        return 0;
    }
    return 1;
}

#endif
