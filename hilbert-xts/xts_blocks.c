#include <errno.h>
#include <inttypes.h>
#include <stdlib.h>

#include <openssl/err.h>
#include <openssl/evp.h>

#include "files.h"

typedef struct {
    uint64_t first, last;
} Range;

static int compare_ranges(const void *a, const void *b)
{
    uint64_t first_a = ((const Range *)a)->first;
    uint64_t first_b = ((const Range *)b)->first;
    return (first_a > first_b) - (first_a < first_b);
}

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

static int parse_range(const char *s, Range *range)
{
    char *end;
    if (!number(s, &end, &range->first))
        return 0;
    range->last = range->first;
    if (*end == '-' && !number(end + 1, &end, &range->last))
        return 0;
    return !*end && range->first <= range->last;
}

static int hex_digit(char c)
{
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    if (c >= 'A' && c <= 'F')
        return c - 'A' + 10;
    return -1;
}

static int parse_key(const char *hex, unsigned char key[64])
{
    if (strlen(hex) != 128)
        return 0;
    for (size_t i = 0; i < 64; ++i) {
        int high = hex_digit(hex[2 * i]), low = hex_digit(hex[2 * i + 1]);
        if (high < 0 || low < 0)
            return 0;
        key[i] = (unsigned char)((high << 4) | low);
    }
    return memcmp(key, key + 32, 32) != 0;
}

static int encrypt_sector(EVP_CIPHER_CTX *context, const unsigned char key[64],
                          uint64_t index, const unsigned char *in, int size,
                          unsigned char *out)
{
    unsigned char tweak[16] = {0};
    for (size_t i = 0; i < sizeof index; ++i)
        tweak[i] = (unsigned char)(index >> (8 * i));
    int length, tail;
    return EVP_EncryptInit_ex(context, EVP_aes_256_xts(), NULL, key, tweak) == 1 &&
           EVP_EncryptUpdate(context, out, &length, in, size) == 1 &&
           EVP_EncryptFinal_ex(context, out + length, &tail) == 1 &&
           length + tail == size;
}

int main(int argc, char **argv)
{
    if (argc < 6) {
        fprintf(stderr, "Usage: %s key_hex input.bin output.bin sector_size range...\n", argv[0]);
        return EXIT_FAILURE;
    }
    uint64_t sector_size;
    char *end;
    if (!number(argv[4], &end, &sector_size) || *end ||
        sector_size < 16 || sector_size > (1u << 24) || sector_size % 16) {
        fprintf(stderr, "Sector size must be a multiple of 16 from 16 to 16777216 bytes\n");
        return EXIT_FAILURE;
    }
    if (same_file(argv[2], argv[3])) {
        fprintf(stderr, "Input and output must be different files\n");
        return EXIT_FAILURE;
    }

    int status = EXIT_FAILURE;
    FILE *in = NULL, *out = NULL;
    Range *ranges = NULL;
    EVP_CIPHER_CTX *context = NULL;
    unsigned char *plain = NULL, *cipher = NULL, key[64];
    if (!parse_key(argv[1], key)) {
        fprintf(stderr, "Use 128 hex digits representing two different 256-bit keys\n");
        goto cleanup;
    }
    in = fopen(argv[2], "rb");
    if (!in) {
        perror(argv[2]);
        goto cleanup;
    }
    uint64_t size;
    if (!file_size(in, &size)) {
        fprintf(stderr, "%s: expected a regular file\n", argv[2]);
        goto cleanup;
    }
    uint64_t complete = size / sector_size, remainder = size % sector_size;
    uint64_t encryptable = complete + (remainder >= 16);
    size_t range_count = (size_t)(argc - 5);
    ranges = calloc(range_count, sizeof *ranges);
    plain = malloc((size_t)sector_size);
    cipher = malloc((size_t)sector_size + EVP_MAX_BLOCK_LENGTH);
    context = EVP_CIPHER_CTX_new();
    if (!ranges || !plain || !cipher || !context) {
        fprintf(stderr, "Could not allocate encryption buffers\n");
        goto cleanup;
    }
    for (size_t r = 0; r < range_count; ++r) {
        if (!parse_range(argv[5 + r], &ranges[r]) || ranges[r].last >= encryptable) {
            fprintf(stderr, "Invalid or out-of-bounds sector range: %s\n", argv[5 + r]);
            goto cleanup;
        }
    }
    qsort(ranges, range_count, sizeof *ranges, compare_ranges);
    out = fopen(argv[3], "wb");
    if (!out) {
        perror(argv[3]);
        goto cleanup;
    }

    uint64_t sectors = complete + (remainder != 0);
    size_t next = 0;
    for (uint64_t i = 0; i < sectors; ++i) {
        size_t length = (size_t)(i < complete ? sector_size : remainder);
        if (fread(plain, 1, length, in) != length) {
            fprintf(stderr, "%s: error reading sector %" PRIu64 "\n", argv[2], i);
            goto cleanup;
        }
        while (next < range_count && ranges[next].last < i)
            ++next;
        const unsigned char *data = plain;
        if (next < range_count && ranges[next].first <= i) {
            if (!encrypt_sector(context, key, i, plain, (int)length, cipher)) {
                fprintf(stderr, "XTS encryption failed at sector %" PRIu64 "\n", i);
                ERR_print_errors_fp(stderr);
                goto cleanup;
            }
            data = cipher;
        }
        if (fwrite(data, 1, length, out) != length) {
            fprintf(stderr, "%s: error writing sector %" PRIu64 "\n", argv[3], i);
            goto cleanup;
        }
    }
    status = EXIT_SUCCESS;

cleanup:
    if (out && fclose(out) != 0) {
        perror(argv[3]);
        status = EXIT_FAILURE;
    }
    if (in)
        fclose(in);
    EVP_CIPHER_CTX_free(context);
    OPENSSL_cleanse(key, sizeof key);
    free(cipher);
    free(plain);
    free(ranges);
    return status;
}
