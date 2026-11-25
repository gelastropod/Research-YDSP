#ifndef HILBERT_H
#define HILBERT_H

#include <stdint.h>

typedef struct {
    uint32_t width, height, side;
} Grid;

static inline void hilbert_xy(uint32_t side, uint64_t index, uint32_t *x, uint32_t *y)
{
    *x = *y = 0;
    for (uint32_t scale = 1; scale < side; scale *= 2, index >>= 2) {
        uint32_t rx = (uint32_t)(index >> 1) & 1;
        uint32_t ry = ((uint32_t)index ^ rx) & 1;
        if (!ry) {
            if (rx) {
                *x = scale - 1 - *x;
                *y = scale - 1 - *y;
            }
            uint32_t swap = *x;
            *x = *y;
            *y = swap;
        }
        *x += scale * rx;
        *y += scale * ry;
    }
}

static inline void grid_xy(const Grid *grid, uint64_t index, uint32_t *x, uint32_t *y)
{
    uint64_t area = (uint64_t)grid->side * grid->side;
    uint32_t u, v;
    hilbert_xy(grid->side, index % area, &u, &v);
    u += (uint32_t)(index / area) * grid->side;
    int horizontal = grid->width >= grid->height;
    *x = horizontal ? u : v;
    *y = horizontal ? v : u;
}

static inline uint64_t grid_index(const Grid *grid, uint32_t x, uint32_t y)
{
    int horizontal = grid->width >= grid->height;
    uint32_t u = horizontal ? x : y;
    uint32_t v = horizontal ? y : x;
    uint64_t index = (uint64_t)(u / grid->side) * grid->side * grid->side;
    for (uint32_t scale = grid->side / 2; scale; scale /= 2) {
        uint32_t rx = (u & scale) != 0;
        uint32_t ry = (v & scale) != 0;
        index += (uint64_t)scale * scale * ((3 * rx) ^ ry);
        u &= scale - 1;
        v &= scale - 1;
        if (!ry) {
            if (rx) {
                u = scale - 1 - u;
                v = scale - 1 - v;
            }
            uint32_t swap = u;
            u = v;
            v = swap;
        }
    }
    return index;
}

#endif
