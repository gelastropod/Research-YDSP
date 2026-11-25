#include <errno.h>
#include <stdlib.h>

#include "files.h"
#include "layout_meta.h"

typedef struct {
    uint64_t first, last;
} Range;

typedef enum {
    RANDOM, FLIP, FILL
} Mode;

static int number(const char *s, char **end, uint64_t *result)
{
    if (*s < '0' || *s > '9')
        return 0;
    errno = 0;
    uintmax_t value = strtoumax(s, end, 10);
    if (errno || value > UINT64_MAX)
        return 0;
    *result = (uint64_t)value;
    return 1;
}

static int compare_ranges(const void *a, const void *b)
{
    uint64_t x = ((const Range *)a)->first;
    uint64_t y = ((const Range *)b)->first;
    return (x > y) - (x < y);
}

static int parse_ranges(const char *s, Range *ranges, size_t count)
{
    char *end;
    for (size_t i = 0; i < count; ++i) {
        if (!number(s, &end, &ranges[i].first))
            return 0;
        ranges[i].last = ranges[i].first;
        if (*end == '-' && !number(end + 1, &end, &ranges[i].last))
            return 0;
        if (ranges[i].last < ranges[i].first || *end != (i + 1 < count ? ',' : '\0'))
            return 0;
        s = *end ? end + 1 : end;
    }
    qsort(ranges, count, sizeof *ranges, compare_ranges);
    return 1;
}

static int parse_mode(const char *s, Mode *mode, unsigned char *fill)
{
    if (strcmp(s, "random") == 0) {
        *mode = RANDOM;
    } else if (strcmp(s, "flip") == 0) {
        *mode = FLIP;
    } else if (strcmp(s, "zero") == 0) {
        *mode = FILL;
        *fill = 0;
    } else if (strncmp(s, "fill:", 5) == 0 && strlen(s + 5) == 2 &&
               strspn(s + 5, "0123456789abcdefABCDEF") == 2) {
        *mode = FILL;
        *fill = (unsigned char)strtoul(s + 5, NULL, 16);
    } else {
        return 0;
    }
    return 1;
}

static int copy_data(FILE *in, FILE *out, uint64_t size)
{
    unsigned char buffer[65536];
    while (size) {
        size_t n = size < sizeof buffer ? (size_t)size : sizeof buffer;
        if (fread(buffer, 1, n, in) != n || fwrite(buffer, 1, n, out) != n)
            return 0;
        size -= n;
    }
    return 1;
}

static int modify(FILE *out, FILE *random, Mode mode, unsigned char fill,
                  uint64_t offset, uint64_t length)
{
    unsigned char buffer[65536];
    if (fseeko(out, (off_t)offset, SEEK_SET) != 0)
        return 0;
    if (mode == FILL)
        memset(buffer, fill, sizeof buffer);
    while (length) {
        size_t n = length < sizeof buffer ? (size_t)length : sizeof buffer;
        if (mode == FLIP) {
            if (fread(buffer, 1, n, out) != n ||
                fseeko(out, (off_t)offset, SEEK_SET) != 0)
                return 0;
            for (size_t i = 0; i < n; ++i)
                buffer[i] ^= 0xff;
        } else if (mode == RANDOM && fread(buffer, 1, n, random) != n) {
            return 0;
        }
        if (fwrite(buffer, 1, n, out) != n)
            return 0;
        offset += n;
        length -= n;
        if (mode == FLIP && length && fseeko(out, (off_t)offset, SEEK_SET) != 0)
            return 0;
    }
    return 1;
}

static void usage(const char *program)
{
    fprintf(stderr, "Usage: %s [-b size] [-m random|zero|flip|fill:HH] in.bin out.bin index[,index|a-b...]\n"
                    "       %s [-b size] [-m mode] -M image.bin.meta -p x,y [in.bin out.bin]\n",
            program, program);
}

int main(int argc, char **argv)
{
    uint64_t block_size = 16;
    Mode mode = RANDOM;
    unsigned char fill = 0;
    const char *point = NULL, *meta = NULL;
    int option;
    while ((option = getopt(argc, argv, "b:m:p:M:")) != -1) {
        char *end;
        switch (option) {
        case 'b':
            if (!number(optarg, &end, &block_size) || *end || !block_size) {
                fprintf(stderr, "Block size must be a positive byte count\n");
                return EXIT_FAILURE;
            }
            break;
        case 'm':
            if (!parse_mode(optarg, &mode, &fill)) {
                fprintf(stderr, "Mode must be random, zero, flip, or fill:HH (two hex digits)\n");
                return EXIT_FAILURE;
            }
            break;
        case 'p': point = optarg; break;
        case 'M': meta = optarg; break;
        default:
            usage(argv[0]);
            return EXIT_FAILURE;
        }
    }

    int paths = argc - optind;
    if ((point && (!meta || (paths != 0 && paths != 2))) ||
        (!point && (meta || paths != 3))) {
        usage(argv[0]);
        return EXIT_FAILURE;
    }

    Range pixel_range;
    uint64_t expected_size = 0;
    if (point) {
        Grid grid;
        PixelFormat format;
        uint64_t x, y;
        char *end;
        if (!read_metadata(meta, &grid, &format))
            return EXIT_FAILURE;
        uint32_t edge = record_edge(format);
        uint32_t width = grid.width * edge, height = grid.height * edge;
        if (!number(point, &end, &x) || *end != ',' ||
            !number(end + 1, &end, &y) || *end ||
            x >= width || y >= height) {
            fprintf(stderr, "Pixel must be inside the %" PRIu32 "x%" PRIu32 " canvas (zero-based x,y)\n",
                    width, height);
            return EXIT_FAILURE;
        }
        size_t bytes = record_bytes(format);
        expected_size = bytes * record_count(&grid);
        uint64_t index = bytes * grid_index(&grid, (uint32_t)x / edge, (uint32_t)y / edge) / block_size;
        pixel_range = (Range){index, index};
        if (!paths)
            return printf("%" PRIu64 "\n", index) < 0 ? EXIT_FAILURE : EXIT_SUCCESS;
    }

    const char *input = argv[optind], *output = argv[optind + 1];
    if (meta && same_file(meta, output)) {
        fprintf(stderr, "Output must not overwrite the metadata file\n");
        return EXIT_FAILURE;
    }
    Range *ranges = &pixel_range;
    size_t count = 1;
    if (!point) {
        const char *indices = argv[optind + 2];
        for (const char *p = indices; *p; ++p)
            count += (*p == ',');
        ranges = calloc(count, sizeof *ranges);
        if (!ranges) {
            perror("calloc");
            return EXIT_FAILURE;
        }
        if (!parse_ranges(indices, ranges, count)) {
            fprintf(stderr, "Expected comma-separated block indices or inclusive ranges\n");
            free(ranges);
            return EXIT_FAILURE;
        }
    }

    int status = EXIT_FAILURE;
    int in_place = same_file(input, output);
    FILE *in = fopen(input, in_place ? "r+b" : "rb");
    FILE *out = NULL, *random = NULL;
    if (!in) {
        perror(input);
        goto cleanup;
    }
    uint64_t size;
    if (!file_size(in, &size) || (point && size != expected_size)) {
        fprintf(stderr, "%s: expected a regular file%s\n", input,
                point ? " matching the metadata canvas size" : "");
        goto cleanup;
    }
    for (size_t i = 0; i < count; ++i) {
        if (ranges[i].last >= size / block_size) {
            fprintf(stderr, "Block %" PRIu64 " extends past end of file\n", ranges[i].last);
            goto cleanup;
        }
    }
    if (mode == RANDOM && !(random = fopen("/dev/urandom", "rb"))) {
        perror("/dev/urandom");
        goto cleanup;
    }

    out = in_place ? in : fopen(output, "w+b");
    if (!out) {
        perror(output);
        goto cleanup;
    }
    if (!in_place && !copy_data(in, out, size)) {
        fprintf(stderr, "Could not copy %s to %s\n", input, output);
        goto cleanup;
    }
    for (size_t i = 0; i < count;) {
        uint64_t first = ranges[i].first, stop = ranges[i].last + 1;
        for (++i; i < count && ranges[i].first <= stop; ++i) {
            if (ranges[i].last >= stop)
                stop = ranges[i].last + 1;
        }
        if (!modify(out, random, mode, fill, first * block_size, (stop - first) * block_size)) {
            fprintf(stderr, "%s: error modifying blocks %" PRIu64 "-%" PRIu64 "\n",
                    output, first, stop - 1);
            goto cleanup;
        }
    }
    status = EXIT_SUCCESS;

cleanup:
    if (in && in != out)
        fclose(in);
    if (out && fclose(out) != 0) {
        perror(output);
        status = EXIT_FAILURE;
    }
    if (random)
        fclose(random);
    if (!point)
        free(ranges);
    if (point && status == EXIT_SUCCESS && printf("%" PRIu64 "\n", pixel_range.first) < 0)
        status = EXIT_FAILURE;
    return status;
}
