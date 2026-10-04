#define _POSIX_C_SOURCE 200809L
#include "fde.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/fs.h>

#define SECTOR_BYTES 4096
#define SCHEME FDE_RATCHET_CTR_AES
#define BAR_WIDTH 40

int fd;
fde_worker *worker;
uint32_t *indices;
void *plain_buf, *cipher_buf;

void cleanup() {
	free(plain_buf);
	free(cipher_buf);
	free(indices);
	fde_worker_free(worker);
	close(fd);
	exit(1);
}

void print_progress(uint64_t written, uint64_t total) {
	double frac = total ? (double)written / (double)total : 1.0;
	if (frac > 1.0) frac = 1.0;
	int filled = (int)(frac * BAR_WIDTH);

	printf("\r[");
	for (int i = 0; i < BAR_WIDTH; i++)
		putchar(i < filled ? '#' : '.');
	printf("] %6.2f%% (%llu / %llu MB)",
		frac * 100.0,
		(unsigned long long)(written / (1024 * 1024)),
		(unsigned long long)(total / (1024 * 1024)));
	fflush(stdout);
}

int main(int argc, char *argv[]) {
	if (argc < 3) {
		fprintf(stderr,
				"Usage: %s <encrypt/decrypt> <device> [offset_bytes] [count_bytes] [csv_path]\n",
				argv[0]);
		return 1;
	}

	int do_encrypt = strcmp(argv[1], "encrypt") == 0;
	int do_decrypt = strcmp(argv[1], "decrypt") == 0;
	if (!do_encrypt && !do_decrypt) {
		fprintf(stderr, "First argument must be 'encrypt' or 'decrypt'\n");
		return 1;
	}

	const char *device = argv[2];
	off_t offset = (argc > 3) ? (off_t)strtoull(argv[3], NULL, 10) : 0;
	uint64_t requested_count = (argc > 4) ? (off_t)strtoull(argv[4], NULL, 10) : 0;
	

	if (offset % SECTOR_BYTES != 0) {
		fprintf(stderr, "Offset must be a multiple of %d\n", SECTOR_BYTES);
		return 1;
	}

	fd = open(device, O_RDWR);
	if (fd < 0) {
		perror("open");
		return 1;
	}

	uint64_t dev_size = 0;
	if (ioctl(fd, BLKGETSIZE64, &dev_size) < 0) {
		perror("ioctl(BLKGETSIZE64)");
		close(fd);
		return 1;
	}

	if ((uint64_t)offset > dev_size) {
		fprintf(stderr, "Offset (%lld) is beyond device size (%llu)\n",
				(long long)offset, (unsigned long long)dev_size);
		close(fd);
		return 1;
	}

	uint64_t max_remaining = dev_size - (uint64_t)offset;
	uint64_t total_bytes = requested_count ? requested_count : max_remaining;
	if (total_bytes > max_remaining) {
		fprintf(stderr, "Requested count (%llu) exceeds remaining device space (%llu); clamping\n",
				(unsigned long long)total_bytes, (unsigned long long)max_remaining);
		total_bytes = max_remaining;
	}
	if (total_bytes % SECTOR_BYTES != 0) {
		fprintf(stderr, "Bytes to write (%llu) not a multiple of %d; rounding\n",
				(unsigned long long)total_bytes, SECTOR_BYTES);
		total_bytes -= total_bytes % SECTOR_BYTES;
	}

	fde_keys keys;
	fde_default_keys(&keys);
	worker = fde_worker_new(&keys);
	if (worker == NULL) {
		fprintf(stderr, "fde_worker_new failed\n");
		close(fd);
		return 1;
	}

	size_t blocks = SECTOR_BYTES / FDE_BLOCK_BYTES;
	indices = malloc(blocks * sizeof(*indices));
	if (indices == NULL) {
		fde_worker_free(worker);
		close(fd);
		return 1;
	}
	for (size_t j = 0; j < blocks; j++) indices[j] = (uint32_t)j;

	plain_buf = NULL, cipher_buf = NULL;
	if (posix_memalign(&plain_buf, 4096, SECTOR_BYTES) != 0 ||
		posix_memalign(&cipher_buf, 4096, SECTOR_BYTES) != 0) {
		fprintf(stderr, "posix_memalign failed\n");
		cleanup();
	}

	if (lseek(fd, offset, SEEK_SET) < 0) {
		perror("lseek");
		cleanup();
	}

	uint64_t total_sectors = total_bytes / SECTOR_BYTES;
	uint64_t update_interval = total_sectors / 10000;
	if (update_interval == 0) update_interval = 1;

	print_progress(0, total_bytes);

	for (uint64_t s = 0; s < total_sectors; s++) {
		uint64_t sector_number = (uint64_t)offset / SECTOR_BYTES + s;

		if (do_encrypt) {
			if (read(fd, plain_buf, SECTOR_BYTES) != SECTOR_BYTES) {
				perror("read");
				cleanup();
			}
			if (fde_encrypt(worker, SCHEME, plain_buf, indices, sector_number, blocks, cipher_buf, NULL) != 0) {
				fprintf(stderr, "fde_encrypt failed at sector %llu",
						(unsigned long long)sector_number);
				cleanup();
			}
			if (lseek(fd, -(off_t)SECTOR_BYTES, SEEK_CUR) < 0) {
				perror("lseek back");
				cleanup();
			}
			if (write(fd, cipher_buf, SECTOR_BYTES) != SECTOR_BYTES) {
				perror("write");
				cleanup();
			}
		}
		else {
			if (read(fd, cipher_buf, SECTOR_BYTES) != SECTOR_BYTES) {
				perror("read");
				cleanup();
			}
			if (fde_decrypt(worker, SCHEME, cipher_buf, indices, sector_number, blocks, plain_buf, NULL) != 0) {
				fprintf(stderr, "fde_decrypt failed at sector %llu",
						(unsigned long long)sector_number);
				cleanup();
			}
			if (lseek(fd, -(off_t)SECTOR_BYTES, SEEK_CUR) < 0) {
				perror("lseek back");
				cleanup();
			}
			if (write(fd, plain_buf, SECTOR_BYTES) != SECTOR_BYTES) {
				perror("write");
				cleanup();
			}
		}

		if ((s + 1) % update_interval == 0 || s + 1 == total_sectors)
			print_progress((s + 1) * SECTOR_BYTES, total_bytes);
	}
	printf("\n");

	fsync(fd);
	printf("%s complete, %llu sectors (%llu bytes)\n",
		   do_encrypt ? "Encrypt" : "Decrypt",
		   (unsigned long long)total_sectors,
		   (unsigned long long)(total_sectors * SECTOR_BYTES));
	free(plain_buf);
	free(cipher_buf);
	free(indices);
	fde_worker_free(worker);
	close(fd);
	return 0;
}
