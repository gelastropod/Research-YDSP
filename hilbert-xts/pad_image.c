#include <stdio.h>
#include <stdlib.h>

#include "files.h"
#include "image_prep.h"

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

static void write_png_data(void *out, void *data, int size)
{
    fwrite(data, 1, (size_t)size, out);
}

int main(int argc, char **argv)
{
    uint32_t target;
    Fit fit;
    const char *input, *output;
    if (!image_arguments(argc, argv, "output.png", &target, &fit, NULL, &input, &output))
        return EXIT_FAILURE;
    if (same_file(input, output)) {
        fprintf(stderr, "Input and output must be different files\n");
        return EXIT_FAILURE;
    }

    PreparedImage image;
    if (!prepare_image(input, target, fit, &image))
        return EXIT_FAILURE;
    uint32_t width = image.layout.canvas_width, height = image.layout.canvas_height;
    int status = EXIT_FAILURE;
    unsigned char *canvas = NULL;
    if (width != image.layout.width || height != image.layout.height) {
        canvas = malloc(4 * (size_t)width * height);
        if (!canvas) {
            perror("malloc");
            goto cleanup;
        }
        for (uint32_t y = 0; y < height; ++y) {
            for (uint32_t x = 0; x < width; ++x)
                memcpy(canvas + 4 * ((size_t)y * width + x), prepared_pixel(&image, x, y), 4);
        }
    }
    FILE *out = fopen(output, "wb");
    if (!out) {
        perror(output);
        goto cleanup;
    }
    int written = stbi_write_png_to_func(write_png_data, out, (int)width, (int)height, 4,
                                         canvas ? canvas : image.pixels, (int)(4 * width));
    int write_error = ferror(out);
    if (fclose(out) != 0 || !written || write_error) {
        fprintf(stderr, "%s: error writing PNG\n", output);
        goto cleanup;
    }
    status = EXIT_SUCCESS;

cleanup:
    free(canvas);
    free(image.pixels);
    return status;
}
