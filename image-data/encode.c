#include <stdio.h>
#include <stdlib.h>

#include "files.h"
#include "ycc.h"

#define STB_DXT_IMPLEMENTATION
#include "stb_dxt.h"

static int write_records(FILE *out, const unsigned char *pixels, const Grid *grid, PixelFormat format)
{
    uint32_t edge = record_edge(format);
    size_t stride = 4 * (size_t)grid->width * edge;
    size_t bytes = record_bytes(format);
    for (uint64_t i = 0; i < record_count(grid); ++i) {
        uint32_t x, y;
        grid_xy(grid, i, &x, &y);
        const unsigned char *data = pixels + (size_t)y * edge * stride + (size_t)x * edge * 4;
        unsigned char block[BLOCK_BYTES];
        if (format != FORMAT_RGBA) {
            unsigned char rgba[BLOCK_EDGE * BLOCK_EDGE * 4];
            for (size_t row = 0; row < BLOCK_EDGE; ++row)
                memcpy(rgba + row * 4 * BLOCK_EDGE, data + row * stride, 4 * BLOCK_EDGE);
            if (format == FORMAT_BC3)
                stb_compress_dxt_block(block, rgba, 1, STB_DXT_HIGHQUAL);
            else
                encode_ycc(block, rgba);
            data = block;
        }
        if (fwrite(data, 1, bytes, out) != bytes)
            return 0;
    }
    return 1;
}

int main(int argc, char **argv)
{
    PixelFormat format = FORMAT_YCC;
    int arg = 1;
    if (argc == 5 && strcmp(argv[1], "-q") == 0) {
        if (!parse_format(argv[2], &format)) {
            fprintf(stderr, "-q requires ycc, bc3, or rgba\n");
            return EXIT_FAILURE;
        }
        arg += 2;
    }
    if (argc - arg != 2 || strcmp(argv[arg], "-q") == 0) {
        fprintf(stderr, "Usage: %s [-q ycc|bc3|rgba] padded.png out.bin\n", argv[0]);
        return EXIT_FAILURE;
    }
    const char *input = argv[arg], *output = argv[arg + 1];
    size_t length = strlen(output);
    char *meta_path = malloc(length + sizeof ".meta");
    if (!meta_path) {
        perror("malloc");
        return EXIT_FAILURE;
    }
    memcpy(meta_path, output, length);
    memcpy(meta_path + length, ".meta", sizeof ".meta");

    int status = EXIT_FAILURE;
    unsigned char *pixels = NULL;
    if (same_file(input, output) || same_file(input, meta_path) || same_file(output, meta_path)) {
        fprintf(stderr, "Input, output and metadata must be different files\n");
        goto cleanup;
    }
    int width, height;
    pixels = load_image(input, &width, &height, 1);
    if (!pixels)
        goto cleanup;
    Grid grid;
    if (!make_grid((uint32_t)width, (uint32_t)height, format, &grid)) {
        fprintf(stderr, "%s: invalid padded size; run pad_image first (short side: power of two >= 4; long side: a multiple of it)\n", input);
        goto cleanup;
    }

    FILE *out = fopen(output, "wb");
    if (!out) {
        perror(output);
        goto cleanup;
    }
    int written = write_records(out, pixels, &grid, format);
    if (fclose(out) != 0 || !written) {
        fprintf(stderr, "%s: error writing binary data\n", output);
        goto cleanup;
    }
    FILE *meta = fopen(meta_path, "w");
    if (!meta) {
        perror(meta_path);
        goto cleanup;
    }
    int fields_written = fprintf(meta, "%d %d %s\n", width, height, format_name(format));
    if (fclose(meta) != 0 || fields_written < 0) {
        fprintf(stderr, "%s: error writing metadata\n", meta_path);
        goto cleanup;
    }
    status = EXIT_SUCCESS;

cleanup:
    free(pixels);
    free(meta_path);
    return status;
}
