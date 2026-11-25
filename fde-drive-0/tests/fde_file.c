/*
 * Encrypt or decrypt a regular file with an fde scheme, treating each
 * 4096-byte chunk as one sector (sector number = chunk index, matching
 * test_drive's numbering) and each 16-byte block inside it as index j.
 *
 * Usage: fde_file [--scheme NAME] encrypt|decrypt IN OUT
 */
#include "fde.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#define SECTOR_BYTES 4096
#define BLOCKS_PER_SECTOR (SECTOR_BYTES / FDE_BLOCK_BYTES)

static const struct {
	const char *alias;
	fde_scheme scheme;
} scheme_aliases[] = {
	{"ecb", FDE_ECB},
	{"xts", FDE_XTS},
	{"ctr-aes", FDE_RATCHET_CTR_AES},
	{"ctr-blake3", FDE_RATCHET_CTR_BLAKE3},
	{"cbc-aes", FDE_RATCHET_CBC_AES},
	{"cbc-blake3", FDE_RATCHET_CBC_BLAKE3},
	{"xex-sha3", FDE_RATCHET_XEX_SHA3},
	{"xex-blake2b", FDE_RATCHET_XEX_BLAKE2B},
	{"xex-blake3", FDE_RATCHET_XEX_BLAKE3},
	{"xex-siphash", FDE_RATCHET_XEX_SIPHASH},
	{"xex-kmac", FDE_RATCHET_XEX_KMAC},
	{"xex-blake2s", FDE_RATCHET_XEX_BLAKE2S},
	{"xex-hmac-sha256", FDE_RATCHET_XEX_HMAC_SHA256},
	{"xex-cmac", FDE_RATCHET_XEX_CMAC},
	{"xex-ghash", FDE_RATCHET_XEX_GHASH}
};

static int parse_scheme(const char *arg, fde_scheme *out) {
	for (size_t i = 0; i < sizeof(scheme_aliases) / sizeof(scheme_aliases[0]); i++) {
		if (strcasecmp(arg, scheme_aliases[i].alias) == 0) {
			*out = scheme_aliases[i].scheme;
			return 0;
		}
	}
	for (int i = 0; i < FDE_SCHEME_COUNT; i++) {
		if (strcasecmp(arg, fde_scheme_name((fde_scheme)i)) == 0) {
			*out = (fde_scheme)i;
			return 0;
		}
	}
	return -1;
}

static void print_usage(const char *prog) {
	fprintf(stderr,
			"Usage: %s [--scheme <name>] <encrypt|decrypt> <in> <out>\n"
			"File is processed in %d-byte sectors; size must be a multiple of %d.\n"
			"Schemes (default xts):\n",
			prog, SECTOR_BYTES, (int)FDE_BLOCK_BYTES);
	for (size_t i = 0; i < sizeof(scheme_aliases) / sizeof(scheme_aliases[0]); i++)
		fprintf(stderr, "  %-11s %s\n", scheme_aliases[i].alias,
				fde_scheme_name(scheme_aliases[i].scheme));
}

int main(int argc, char *argv[]) {
	fde_scheme scheme = FDE_XTS;
	int nargs = 1;
	for (int i = 1; i < argc; i++) {
		if (strcmp(argv[i], "--scheme") == 0 || strcmp(argv[i], "-s") == 0) {
			if (i + 1 >= argc || parse_scheme(argv[i + 1], &scheme) != 0) {
				fprintf(stderr, "Unknown or missing scheme%s%s\n",
						i + 1 < argc ? ": " : "", i + 1 < argc ? argv[i + 1] : "");
				print_usage(argv[0]);
				return 1;
			}
			i++;
		} else {
			argv[nargs++] = argv[i];
		}
	}
	argc = nargs;

	if (argc != 4) {
		print_usage(argv[0]);
		return 1;
	}

	int do_encrypt = strcmp(argv[1], "encrypt") == 0;
	int do_decrypt = strcmp(argv[1], "decrypt") == 0;
	if (!do_encrypt && !do_decrypt) {
		fprintf(stderr, "First argument must be 'encrypt' or 'decrypt'\n");
		return 1;
	}
	if (strcmp(argv[2], argv[3]) == 0) {
		fprintf(stderr, "Input and output must be different files\n");
		return 1;
	}

	FILE *in = fopen(argv[2], "rb");
	if (in == NULL) {
		perror(argv[2]);
		return 1;
	}
	if (fseeko(in, 0, SEEK_END) != 0) {
		perror("fseeko");
		return 1;
	}
	off_t size = ftello(in);
	if (size < 0 || fseeko(in, 0, SEEK_SET) != 0) {
		perror("ftello");
		return 1;
	}
	if (size % FDE_BLOCK_BYTES != 0) {
		fprintf(stderr, "%s: size must be a multiple of %d bytes\n",
				argv[2], (int)FDE_BLOCK_BYTES);
		return 1;
	}
	FILE *out = fopen(argv[3], "wb");
	if (out == NULL) {
		perror(argv[3]);
		return 1;
	}

	fde_keys keys;
	fde_default_keys(&keys);
	fde_worker *worker = fde_worker_new(&keys);
	if (worker == NULL) {
		fprintf(stderr, "fde_worker_new failed\n");
		return 1;
	}

	uint32_t indices[BLOCKS_PER_SECTOR];
	for (size_t j = 0; j < BLOCKS_PER_SECTOR; j++)
		indices[j] = (uint32_t)j;

	uint8_t in_buf[SECTOR_BYTES], out_buf[SECTOR_BYTES];
	uint64_t sector = 0;
	int status = 1;
	for (;;) {
		size_t n = fread(in_buf, 1, SECTOR_BYTES, in);
		if (n == 0)
			break;
		int rc = do_encrypt
			? fde_encrypt(worker, scheme, in_buf, indices, sector,
						  n / FDE_BLOCK_BYTES, out_buf, NULL)
			: fde_decrypt(worker, scheme, in_buf, indices, sector,
						  n / FDE_BLOCK_BYTES, out_buf, NULL);
		if (rc != 0 || fwrite(out_buf, 1, n, out) != n) {
			fprintf(stderr, "%s failed at sector %llu\n",
					do_encrypt ? "fde_encrypt" : "fde_decrypt",
					(unsigned long long)sector);
			goto cleanup;
		}
		sector++;
	}
	if (ferror(in)) {
		perror(argv[2]);
		goto cleanup;
	}
	printf("%s: %s -> %s, %llu sectors (%lld bytes), scheme %s\n",
		   do_encrypt ? "Encrypted" : "Decrypted", argv[2], argv[3],
		   (unsigned long long)sector, (long long)size,
		   fde_scheme_name(scheme));
	status = 0;

cleanup:
	if (status != 0)
		remove(argv[3]);
	fclose(in);
	if (fclose(out) != 0)
		status = 1;
	fde_worker_free(worker);
	return status;
}
