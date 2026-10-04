#define _GNU_SOURCE 200809L
#include "fde.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/fs.h>
#include <time.h>

#define SECTOR_BYTES 4096
#define BATCH_BYTES (1024 * 1024)
#define SCHEME FDE_RATCHET_CTR_AES
#define BAR_WIDTH 40

double now_seconds() {
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

int fd;
fde_worker *worker;
uint32_t *indices;
void *in_buf, *out_buf;
FILE *csv_file = NULL;

void cleanup() {
	free(in_buf);
	free(out_buf);
	free(indices);
	fde_worker_free(worker);
	close(fd);
	if (csv_file != NULL) fclose(csv_file);
	exit(1);
}

void print_progress(uint64_t written, uint64_t total, double cumulative_mbps) {
	double frac = total ? (double)written / (double)total : 1.0;
	if (frac > 1.0) frac = 1.0;
	int filled = (int)(frac * BAR_WIDTH);

	printf("\r[");
	for (int i = 0; i < BAR_WIDTH; i++)
		putchar(i < filled ? '#' : '.');
	printf("] %6.1f%% (%llu / %llu MB), %.2f MB/s",
		frac * 100.0,
		(unsigned long long)(written / (1024 * 1024)),
		(unsigned long long)(total / (1024 * 1024)),
		cumulative_mbps);
	fflush(stdout);
}

int main(int argc, char *argv[]) {
	if (argc < 3) {
		fprintf(stderr,
				"Usage: %s <encrypt/decrypt> <device> [offset_bytes] [count_bytes] [csv_path] [direct]\n",
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
	const char *csv_path = (argc > 5) ? argv[5] : NULL;
	int use_direct = (argc > 6) && (strcmp(argv[6], "direct") == 0);

	if (offset % SECTOR_BYTES != 0) {
		fprintf(stderr, "Offset must be a multiple of %d\n", SECTOR_BYTES);
		return 1;
	}

	fd = open(device, O_RDWR | (use_direct ? O_DIRECT : 0));
	if (fd < 0) {
		perror(use_direct ? "open (with O_DIRECT)" : "open");
		return 1;
	}

	size_t io_bytes = use_direct ? BATCH_BYTES : SECTOR_BYTES;
	uint64_t io_sectors = io_bytes / SECTOR_BYTES;
	if (use_direct) {
		printf("Using O_DIRECT with batch size of %zu KB\n", io_bytes / 1024);
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

	in_buf = NULL, out_buf = NULL;
	if (posix_memalign(&in_buf, 4096, io_bytes) != 0 ||
		posix_memalign(&out_buf, 4096, io_bytes) != 0) {
		fprintf(stderr, "posix_memalign failed\n");
		cleanup();
	}

	if (lseek(fd, offset, SEEK_SET) < 0) {
		perror("lseek");
		cleanup();
	}

	uint64_t total_sectors = total_bytes / SECTOR_BYTES;
	uint64_t update_interval = total_sectors / 1000;
	if (update_interval == 0) update_interval = 1;

	if (csv_path != NULL) {
		csv_file = fopen(csv_path, "w");
		if (csv_file == NULL) {
			perror("fopen (csv_path)");
			cleanup();
		}
		fprintf(csv_file, "elapsed_s,sector,bytes_done,instant_MBps,cumulative_MBps,"
						  "seed_ns,data_n,sevolution_ns,io_ns\n");
	}

	double start_time = now_seconds();
	double last_sample_time = start_time;
	uint64_t last_sample_bytes = 0;
	uint64_t last_update_sector = 0;

	fde_profile sector_profile;
	uint64_t total_seed_ns = 0, total_data_ns = 0, total_evolution_ns = 0, total_io_ns = 0;

	print_progress(0, total_bytes, 0.0);

	uint64_t first_sector = (uint64_t)offset / SECTOR_BYTES;

	for (uint64_t s = 0; s < total_sectors; ) {
		uint64_t batch_sectors = total_sectors - s;
		if (batch_sectors > io_sectors) batch_sectors = io_sectors;
		size_t batch_bytes = (size_t)(batch_sectors * SECTOR_BYTES);
		off_t batch_offset = offset + (off_t)(s * SECTOR_BYTES);

		double io_start = now_seconds();
		if (pread(fd, in_buf, batch_bytes, batch_offset) != (ssize_t)batch_bytes) {
			perror("pread");
			cleanup();
		}
		total_io_ns += (uint64_t)((now_seconds() - io_start) * 1e9);

		for (uint64_t i = 0; i < batch_sectors; i++) {
			uint64_t sector_number = (uint64_t)offset / SECTOR_BYTES + s;
			const void *src = (const char*)in_buf + i * SECTOR_BYTES;
			void *dst = (char*)out_buf + i * SECTOR_BYTES;
			int rc;

			if (do_encrypt)
				rc = fde_encrypt(worker, SCHEME, src, indices, sector_number, blocks, dst, &sector_profile);
			else
				rc = fde_decrypt(worker, SCHEME, src, indices, sector_number, blocks, dst, &sector_profile);

			if (rc != 0) {
				fprintf(stderr, "%s failed at sector %llu",
						do_encrypt ? "fde_encrypt" : "fde_decrypt",
						(unsigned long long)sector_number);
				cleanup();
			}
			total_seed_ns += sector_profile.seed_ns;
			total_data_ns += sector_profile.data_ns;
			total_evolution_ns += sector_profile.evolution_ns;
		}

		io_start = now_seconds();
		if (pwrite(fd, out_buf, batch_bytes, batch_offset) != (ssize_t)batch_bytes) {
			perror("pwrite");
			cleanup();
		}
		total_io_ns += (uint64_t)((now_seconds() - io_start) * 1e9);

		s += batch_sectors;

		if (s - last_update_sector >= update_interval || s == total_sectors) {
			uint64_t bytes_done = (s + 1) * SECTOR_BYTES;

			double now = now_seconds();
			double total_elapsed = now - start_time;
			double elapsed = now - last_sample_time;
			uint64_t bytes_since_last = bytes_done - last_sample_bytes;

			double instant_mbps = (elapsed > 0.0) ? ((double)bytes_since_last / elapsed) / 1e6 : 0.0;
			double cumulative_mbps = (total_elapsed > 0.0) ? ((double)bytes_done / total_elapsed) / 1e6 : 0.0;

			print_progress(bytes_done, total_bytes, cumulative_mbps);

			if (csv_file != NULL)
				fprintf(csv_file, "%.6f,%llu,%llu,%.3f,%.3f,%llu,%llu,%llu,%llu\n",
						total_elapsed, (unsigned long long)(first_sector + s), (unsigned long long)bytes_done,
						instant_mbps, cumulative_mbps,
						(unsigned long long)total_seed_ns, (unsigned long long)total_data_ns, (unsigned long long)total_evolution_ns, (unsigned long long)total_io_ns);

			last_sample_time = now;
			last_sample_bytes = bytes_done;
			last_update_sector = s;
		}
	}
	printf("\n");

	fsync(fd);
	printf("%s complete, %llu sectors (%llu bytes)\n",
		   do_encrypt ? "Encrypt" : "Decrypt",
		   (unsigned long long)total_sectors,
		   (unsigned long long)(total_sectors * SECTOR_BYTES));

	double total_crypto_ns = (double)(total_seed_ns + total_data_ns + total_evolution_ns);
	if (total_crypto_ns > 0) {
		printf("Crypto time breakdown: seed %.1f%%, data %.1f%%, evolution %.1f%% "
			   "(%.3fs total crypto time)\n",
			   100.0 * (double)total_seed_ns / total_crypto_ns,
			   100.0 * (double)total_data_ns / total_crypto_ns,
			   100.0 * (double)total_evolution_ns / total_crypto_ns,
			   total_crypto_ns / 1e9);
	}

	double total_elapsed = now_seconds() - start_time;
	double crypto_s = total_crypto_ns / 1e9;
	double io_s = (double)total_io_ns / 1e9;
	double overhead_s = total_elapsed - crypto_s - io_s;
	if (overhead_s < 0.0) overhead_s = 0.0;

	if (total_elapsed > 0.0) {
		printf("Time breakdown: crypto %.1f%% (%.3fs), disk I/O %.1f%% (%.3fs), other overhead %.1f%% (%.3fs) -- %.3fs total\n",
			   100.0 * crypto_s / total_elapsed, crypto_s, 100.0 * io_s / total_elapsed, io_s,
			   100.0 * overhead_s / total_elapsed, overhead_s, total_elapsed);
	}
	if (csv_file != NULL) {
		fclose(csv_file);
		printf("Throughput data written to %s\n", csv_path);
	}

	free(in_buf);
	free(out_buf);
	free(indices);
	fde_worker_free(worker);
	close(fd);
	return 0;
}
