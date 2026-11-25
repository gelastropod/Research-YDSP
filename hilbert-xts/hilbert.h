#ifndef HILBERT_H
#define HILBERT_H

#include <limits.h>
#include <stdint.h>

typedef struct {
    uint32_t width, height, side, tiles, offset_x, offset_y;
    uint32_t canvas_width, canvas_height;
    char axis;
} Layout;

static inline int layout_contains(const Layout *layout, uint32_t x, uint32_t y)
{
    return x - layout->offset_x < layout->width && y - layout->offset_y < layout->height;
}

typedef enum {
    FIT_SHORT, FIT_LONG
} Fit;

static inline uint32_t ceil_power_of_two(uint32_t dimension)
{
    uint32_t side = 1;
    while (side < dimension)
        side *= 2;
    return side;
}

static inline uint32_t nearest_power_of_two(uint32_t dimension)
{
    uint32_t side = ceil_power_of_two(dimension);
    uint32_t lower = side / 2;
    return lower && dimension - lower < side - dimension ? lower : side;
}

static inline int make_layout(uint32_t width, uint32_t height, uint32_t target, Fit fit, Layout *l)
{
    if (!width || !height || !target || (target & (target - 1)))
        return 0;
    int horizontal = width >= height;
    uint32_t short_edge = horizontal ? height : width;
    uint32_t long_edge = horizontal ? width : height;
    uint32_t scaled_short, side;
    uint64_t scaled_long, padded_long;
    if (fit == FIT_LONG) {
        scaled_long = padded_long = target;
        scaled_short = (uint32_t)(((uint64_t)short_edge * target + long_edge / 2) / long_edge);
        if (!scaled_short)
            scaled_short = 1;
        side = ceil_power_of_two(scaled_short);
    } else {
        scaled_short = side = target;
        scaled_long = ((uint64_t)long_edge * target + short_edge / 2) / short_edge;
        padded_long = (scaled_long + side - 1) / side * side;
    }
    uint64_t canvas_width = horizontal ? padded_long : side;
    uint64_t canvas_height = horizontal ? side : padded_long;
    if (canvas_width > (INT_MAX / 2 - 1) / 4 ||
        canvas_height > (uint64_t)(INT_MAX / 2) / (4 * canvas_width + 1))
        return 0;
    uint32_t long_offset = (uint32_t)((padded_long - scaled_long) / 2);
    uint32_t short_offset = (side - scaled_short) / 2;
    *l = (Layout){
        .width = horizontal ? (uint32_t)scaled_long : scaled_short,
        .height = horizontal ? scaled_short : (uint32_t)scaled_long,
        .side = side,
        .tiles = (uint32_t)(padded_long / side),
        .offset_x = horizontal ? long_offset : short_offset,
        .offset_y = horizontal ? short_offset : long_offset,
        .canvas_width = (uint32_t)canvas_width,
        .canvas_height = (uint32_t)canvas_height,
        .axis = horizontal ? 'H' : 'V',
    };
    return 1;
}

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

static inline void layout_xy(const Layout *l, uint64_t index, uint32_t *x, uint32_t *y)
{
    uint64_t area = (uint64_t)l->side * l->side;
    uint32_t u, v;
    hilbert_xy(l->side, index % area, &u, &v);
    u += (uint32_t)(index / area) * l->side;
    *x = l->axis == 'H' ? u : v;
    *y = l->axis == 'H' ? v : u;
}

static inline uint64_t layout_index(const Layout *l, uint32_t x, uint32_t y)
{
    uint32_t u = l->axis == 'H' ? x : y;
    uint32_t v = l->axis == 'H' ? y : x;
    uint64_t index = (uint64_t)(u / l->side) * l->side * l->side;
    for (uint32_t scale = l->side / 2; scale; scale /= 2) {
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
