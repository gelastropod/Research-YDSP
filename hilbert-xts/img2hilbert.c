#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

#include "files.h"
#include "image_prep.h"
#include "ycc.h"

#define STB_DXT_IMPLEMENTATION
#include "stb_dxt.h"

int main(int argc, char **argv)
{
    uint32_t target;
    Fit fit;
    PixelFormat format;
    const char *input, *output;
    if (!image_arguments(argc, argv, "output.bin", &target, &fit, &format, &input, &output))
        return EXIT_FAILURE;

    size_t length = strlen(output);
    char *meta_path = malloc(length + sizeof ".meta");
    if (!meta_path) {
        perror("malloc");
        return EXIT_FAILURE;
    }
    memcpy(meta_path, output, length);
    memcpy(meta_path + length, ".meta", sizeof ".meta");

    int status = EXIT_FAILURE;
    PreparedImage image = {0};
    if (same_file(input, output) || same_file(input, meta_path) || same_file(output, meta_path)) {
        fprintf(stderr, "Input, output and metadata must be different files\n");
        goto cleanup;
    }
    if (!prepare_image(input, target, fit, &image))
        goto cleanup;

    const Layout *layout = &image.layout;
    if (layout->side < record_edge(format)) {
        fprintf(stderr, "BC3 and YCC require a Hilbert tile side of at least 4 pixels\n");
        goto cleanup;
    }
    Layout grid = record_grid(layout, format);
    size_t bytes = record_bytes(format);
    uint64_t count = (uint64_t)grid.canvas_width * grid.canvas_height;
    FILE *out = fopen(output, "wb");
    if (!out) {
        perror(output);
        goto cleanup;
    }
    uint64_t i;
    for (i = 0; i < count; ++i) {
        uint32_t x, y;
        layout_xy(&grid, i, &x, &y);
        unsigned char block[BLOCK_BYTES];
        const unsigned char *data;
        if (format != FORMAT_RGBA) {
            unsigned valid = 0;
            unsigned char rgba[BLOCK_EDGE * BLOCK_EDGE * 4];
            for (uint32_t dy = 0; dy < BLOCK_EDGE; ++dy) {
                for (uint32_t dx = 0; dx < BLOCK_EDGE; ++dx) {
                    uint32_t px = x * BLOCK_EDGE + dx, py = y * BLOCK_EDGE + dy;
                    unsigned j = dy * BLOCK_EDGE + dx;
                    memcpy(rgba + 4 * j, prepared_pixel(&image, px, py), 4);
                    if (format == FORMAT_YCC && layout_contains(layout, px, py))
                        valid |= 1u << j;
                }
            }
            if (format == FORMAT_BC3)
                stb_compress_dxt_block(block, rgba, 1, STB_DXT_HIGHQUAL);
            else
                encode_ycc(block, rgba, valid);
            data = block;
        } else {
            data = prepared_pixel(&image, x, y);
        }
        if (fwrite(data, 1, bytes, out) != bytes)
            break;
    }
    if (fclose(out) != 0 || i != count) {
        fprintf(stderr, "%s: error writing pixel data\n", output);
        goto cleanup;
    }

    FILE *meta = fopen(meta_path, "w");
    if (!meta) {
        perror(meta_path);
        goto cleanup;
    }
    char record[128];
    snprintf(record, sizeof record,
             "%d %d %" PRIu32 " %" PRIu32 " %" PRIu32 " %" PRIu32 " %c %" PRIu32 " %" PRIu32 "%s%s\n",
             image.width, image.height, layout->width, layout->height, layout->side, layout->tiles,
             layout->axis, layout->offset_x, layout->offset_y, fit == FIT_LONG ? " long" : "",
             format == FORMAT_BC3 ? " bc3" : format == FORMAT_YCC ? " ycc" : "");
    int written = fputs(record, meta);
    if (fclose(meta) != 0 || written < 0) {
        fprintf(stderr, "%s: error writing metadata\n", meta_path);
        goto cleanup;
    }
    fputs(record, stdout);
    status = EXIT_SUCCESS;

cleanup:
    free(image.pixels);
    free(meta_path);
    return status;
}
