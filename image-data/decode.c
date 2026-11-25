#include <stdlib.h>

#include "bc3.h"
#include "files.h"
#include "layout_meta.h"
#include "ycc.h"

static int read_records(FILE *in, unsigned char *pixels, const Grid *grid, PixelFormat format)
{
    uint32_t edge = record_edge(format);
    size_t stride = 4 * (size_t)grid->width * edge;
    size_t bytes = record_bytes(format);
    for (uint64_t i = 0; i < record_count(grid); ++i) {
        unsigned char record[BLOCK_BYTES];
        if (fread(record, 1, bytes, in) != bytes)
            return 0;
        uint32_t x, y;
        grid_xy(grid, i, &x, &y);
        unsigned char *dst = pixels + (size_t)y * edge * stride + (size_t)x * edge * 4;
        if (format == FORMAT_RGBA) {
            memcpy(dst, record, 4);
        } else {
            unsigned char rgba[BLOCK_EDGE * BLOCK_EDGE * 4];
            if (format == FORMAT_BC3)
                decode_bc3(record, rgba);
            else
                decode_ycc(record, rgba);
            for (size_t row = 0; row < BLOCK_EDGE; ++row)
                memcpy(dst + row * stride, rgba + row * 4 * BLOCK_EDGE, 4 * BLOCK_EDGE);
        }
    }
    return 1;
}

int main(int argc, char **argv)
{
    if (argc != 4) {
        fprintf(stderr, "Usage: %s in.bin in.bin.meta out.png\n", argv[0]);
        return EXIT_FAILURE;
    }
    const char *input = argv[1], *metadata = argv[2], *output = argv[3];
    if (same_file(input, output) || same_file(metadata, output)) {
        fprintf(stderr, "Output PNG must be different from the inputs\n");
        return EXIT_FAILURE;
    }
    Grid grid;
    PixelFormat format;
    if (!read_metadata(metadata, &grid, &format))
        return EXIT_FAILURE;
    FILE *in = fopen(input, "rb");
    if (!in) {
        perror(input);
        return EXIT_FAILURE;
    }
    uint64_t size, expected = record_bytes(format) * record_count(&grid);
    if (!file_size(in, &size) || size != expected) {
        fprintf(stderr, "%s: expected exactly %" PRIu64 " bytes in a regular file\n", input, expected);
        fclose(in);
        return EXIT_FAILURE;
    }
    uint32_t edge = record_edge(format);
    uint32_t width = grid.width * edge, height = grid.height * edge;
    unsigned char *pixels = malloc(4 * (size_t)width * height);
    if (!pixels) {
        perror("malloc");
        fclose(in);
        return EXIT_FAILURE;
    }
    int valid = read_records(in, pixels, &grid, format);
    fclose(in);
    if (!valid)
        fprintf(stderr, "%s: error reading binary data\n", input);
    int success = valid && write_png(output, pixels, (int)width, (int)height);
    free(pixels);
    return success ? EXIT_SUCCESS : EXIT_FAILURE;
}
