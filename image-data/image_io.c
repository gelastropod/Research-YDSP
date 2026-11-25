#include <stdio.h>

#include "image_io.h"

#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_RESIZE_IMPLEMENTATION
#include "stb_image_resize2.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

unsigned char *load_image(const char *path, int *width, int *height, int require_png)
{
    FILE *in = fopen(path, "rb");
    if (!in) {
        perror(path);
        return NULL;
    }
    if (require_png) {
        static const unsigned char signature[] = {137, 80, 78, 71, 13, 10, 26, 10};
        unsigned char header[sizeof signature];
        if (fread(header, 1, sizeof header, in) != sizeof header ||
            memcmp(header, signature, sizeof header) != 0 || fseek(in, 0, SEEK_SET) != 0) {
            fprintf(stderr, "%s: expected a PNG; run pad_image first\n", path);
            fclose(in);
            return NULL;
        }
    }
    unsigned char *pixels = stbi_load_from_file(in, width, height, NULL, 4);
    fclose(in);
    if (!pixels)
        fprintf(stderr, "%s: %s\n", path, stbi_failure_reason());
    return pixels;
}

unsigned char *resize_image(const unsigned char *pixels, int width, int height, int new_width, int new_height)
{
    unsigned char *resized = stbir_resize_uint8_srgb(pixels, width, height, 0, NULL,
                                                     new_width, new_height, 0, STBIR_RGBA);
    if (!resized)
        fprintf(stderr, "Could not resize image\n");
    return resized;
}

static void write_png_data(void *out, void *data, int size)
{
    fwrite(data, 1, (size_t)size, out);
}

int write_png(const char *path, const unsigned char *pixels, int width, int height)
{
    FILE *out = fopen(path, "wb");
    if (!out) {
        perror(path);
        return 0;
    }
    int written = stbi_write_png_to_func(write_png_data, out, width, height, 4, pixels, width * 4);
    int write_error = ferror(out);
    if (fclose(out) != 0 || !written || write_error) {
        fprintf(stderr, "%s: error writing PNG\n", path);
        return 0;
    }
    return 1;
}
