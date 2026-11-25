#ifndef LAYOUT_META_H
#define LAYOUT_META_H

#include <inttypes.h>
#include <stdio.h>

#include "stream_format.h"

static inline int read_metadata(const char *path, Grid *grid, PixelFormat *format)
{
    FILE *meta = fopen(path, "r");
    if (!meta) {
        perror(path);
        return 0;
    }
    uint64_t width, height;
    char name[5], extra[2];
    int fields = fscanf(meta, "%10" SCNu64 " %10" SCNu64 " %4s %1s", &width, &height, name, extra);
    int meta_error = ferror(meta);
    fclose(meta);
    if (fields != 3 || meta_error || !parse_format(name, format) || !make_grid(width, height, *format, grid)) {
        fprintf(stderr, "%s: expected valid WIDTH HEIGHT FORMAT metadata\n", path);
        return 0;
    }
    return 1;
}

#endif
