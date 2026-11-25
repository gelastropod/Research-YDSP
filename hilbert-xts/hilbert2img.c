#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

#include "bc3.h"
#include "files.h"
#include "layout_meta.h"
#include "ycc.h"

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

static void write_png_data(void *out, void *data, int size)
{
    fwrite(data, 1, (size_t)size, out);
}

int main(int argc, char **argv)
{
    int opaque = 0, crop = 0, arg = 1;
    for (; arg < argc && argv[arg][0] == '-'; ++arg) {
        if (strcmp(argv[arg], "--opaque") == 0)
            opaque = 1;
        else if (strcmp(argv[arg], "--crop") == 0)
            crop = 1;
        else
            break;
    }
    if (argc - arg != 3 || argv[arg][0] == '-') {
        fprintf(stderr, "Usage: %s [--crop] [--opaque] input.bin input.bin.meta output.png\n", argv[0]);
        return EXIT_FAILURE;
    }
    const char *in_path = argv[arg], *meta_path = argv[arg + 1], *out_path = argv[arg + 2];
    if (same_file(in_path, out_path) || same_file(meta_path, out_path)) {
        fprintf(stderr, "Output PNG must be different from the inputs\n");
        return EXIT_FAILURE;
    }

    Layout layout;
    PixelFormat format;
    if (!read_layout(meta_path, &layout, &format))
        return EXIT_FAILURE;

    FILE *in = fopen(in_path, "rb");
    if (!in) {
        perror(in_path);
        return EXIT_FAILURE;
    }
    uint64_t size;
    Layout grid = record_grid(&layout, format);
    uint64_t count = (uint64_t)grid.canvas_width * grid.canvas_height;
    size_t bytes = record_bytes(format);
    uint32_t edge = record_edge(format);
    if (!file_size(in, &size) || size != bytes * count) {
        fprintf(stderr, "%s: expected exactly %" PRIu64 " bytes in a regular file\n",
                in_path, bytes * count);
        fclose(in);
        return EXIT_FAILURE;
    }

    int status = EXIT_FAILURE;
    uint32_t out_width = crop ? layout.width : layout.canvas_width;
    uint32_t out_height = crop ? layout.height : layout.canvas_height;
    unsigned char *pixels = malloc(4 * (size_t)out_width * out_height);
    if (!pixels) {
        perror("malloc");
        goto cleanup;
    }
    for (uint64_t i = 0; i < count; ++i) {
        unsigned char record[BLOCK_BYTES];
        if (fread(record, 1, bytes, in) != bytes) {
            fprintf(stderr, "%s: error reading pixel data\n", in_path);
            goto cleanup;
        }
        unsigned char rgba[BLOCK_EDGE * BLOCK_EDGE * 4];
        if (format == FORMAT_BC3)
            decode_bc3(record, rgba);
        else if (format == FORMAT_YCC)
            decode_ycc(record, rgba);
        else
            memcpy(rgba, record, 4);
        uint32_t u, v;
        layout_xy(&grid, i, &u, &v);
        for (uint32_t dy = 0; dy < edge; ++dy) {
            for (uint32_t dx = 0; dx < edge; ++dx) {
                uint32_t x = u * edge + dx, y = v * edge + dy;
                if (crop) {
                    x -= layout.offset_x;
                    y -= layout.offset_y;
                }
                if (x < out_width && y < out_height) {
                    unsigned char *pixel = rgba + 4 * (dy * edge + dx);
                    if (opaque)
                        pixel[3] = 255;
                    else if (format == FORMAT_YCC && !crop && !layout_contains(&layout, x, y))
                        pixel[3] = 0;
                    memcpy(pixels + 4 * ((size_t)y * out_width + x), pixel, 4);
                }
            }
        }
    }

    FILE *out = fopen(out_path, "wb");
    if (!out) {
        perror(out_path);
        goto cleanup;
    }
    int written = stbi_write_png_to_func(write_png_data, out, (int)out_width, (int)out_height, 4,
                                         pixels, (int)(4 * out_width));
    int write_error = ferror(out);
    if (fclose(out) != 0 || !written || write_error) {
        fprintf(stderr, "%s: error writing PNG\n", out_path);
        goto cleanup;
    }
    status = EXIT_SUCCESS;

cleanup:
    fclose(in);
    free(pixels);
    return status;
}
