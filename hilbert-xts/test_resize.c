#include <stdlib.h>

#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_RESIZE_IMPLEMENTATION
#include "stb_image_resize2.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

int main(int argc, char **argv)
{
    if (argc != 5)
        return 1;
    int width, height;
    unsigned char *pixels = stbi_load(argv[1], &width, &height, NULL, 4);
    if (!pixels)
        return 1;
    int w = atoi(argv[3]), h = atoi(argv[4]);
    unsigned char *out = stbir_resize_uint8_srgb(pixels, width, height, 0, NULL,
                                             w, h, 0, STBIR_RGBA);
    int ok = out && stbi_write_png(argv[2], w, h, 4, out, 0);
    free(out);
    stbi_image_free(pixels);
    return !ok;
}
