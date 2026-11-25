#ifndef HILBERT_H
#define HILBERT_H

#include <stdint.h>

typedef struct {
    uint32_t width, height, side;
} Grid;

static inline void grid_xy(const Grid *grid, uint64_t index, uint32_t *x, uint32_t *y)
{
    *x = (uint32_t)(index % grid->width);
    *y = (uint32_t)(index / grid->width);
}

static inline uint64_t grid_index(const Grid *grid, uint32_t x, uint32_t y)
{
    return (uint64_t)y * grid->width + x;
}

#endif
