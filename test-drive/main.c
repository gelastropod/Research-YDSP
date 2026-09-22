#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <linux/fs.h>
#include <stdint.h>

#define BAR_WIDTH 40

static void print_progress(uint64_t written, uint64_t total) {
    double frac = total ? (double)written / (double)total : 1.0;
    if (frac > 1.0) frac = 1.0;
    int filled = (int)(frac * BAR_WIDTH);

    printf("\r[");
    for (int i = 0; i < BAR_WIDTH; i++)
        putchar(i < filled ? '#' : ' ');
    printf("] %6.2f%%  (%llu / %llu MB)",
           frac * 100.0,
           (unsigned long long)(written / (1024 * 1024)),
           (unsigned long long)(total / (1024 * 1024)));
    fflush(stdout);
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <device> [offset_bytes] [count_bytes]\n", argv[0]);
        return 1;
    }

    const char *device = argv[1];
    off_t offset = (argc > 2) ? (off_t)strtoull(argv[2], NULL, 10) : 0;
    // count_bytes: if given, limits how much to write; otherwise write to end of device
    uint64_t requested_count = (argc > 3) ? strtoull(argv[3], NULL, 10) : 0;

    size_t block_size = 4 * 1024 * 1024; // 4MB per write() call

    int fd = open(device, O_WRONLY);
    if (fd < 0) {
        perror("open");
        return 1;
    }

    // get total device size in bytes
    uint64_t dev_size = 0;
    if (ioctl(fd, BLKGETSIZE64, &dev_size) < 0) {
        perror("ioctl(BLKGETSIZE64)");
        close(fd);
        return 1;
    }

    if ((uint64_t)offset > dev_size) {
        fprintf(stderr, "offset (%lld) is beyond device size (%llu)\n",
                (long long)offset, (unsigned long long)dev_size);
        close(fd);
        return 1;
    }

    uint64_t max_writeable = dev_size - (uint64_t)offset;
    uint64_t total_to_write = requested_count ? requested_count : max_writeable;
    if (total_to_write > max_writeable) {
        fprintf(stderr, "requested count exceeds remaining device space; clamping\n");
        total_to_write = max_writeable;
    }

    void *buf;
    if (posix_memalign(&buf, 4096, block_size) != 0) {
        perror("posix_memalign");
        close(fd);
        return 1;
    }
    memset(buf, 0, block_size);

    if (offset > 0) {
        if (lseek(fd, offset, SEEK_SET) < 0) {
            perror("lseek");
            free(buf);
            close(fd);
            return 1;
        }
    }

    uint64_t total_written = 0;
    print_progress(0, total_to_write);

    while (total_written < total_to_write) {
        size_t chunk = block_size;
        uint64_t remaining = total_to_write - total_written;
        if ((uint64_t)chunk > remaining)
            chunk = (size_t)remaining;

        size_t chunk_written = 0;
        while (chunk_written < chunk) {
            ssize_t n = write(fd, (char *)buf + chunk_written, chunk - chunk_written);
            if (n < 0) {
                if (errno == EINTR) continue;
                printf("\n");
                perror("write");
                free(buf);
                close(fd);
                return 1;
            }
            chunk_written += (size_t)n;
        }

        total_written += chunk_written;
        print_progress(total_written, total_to_write);
    }

    printf("\n");

    if (fsync(fd) < 0) {
        perror("fsync");
        free(buf);
        close(fd);
        return 1;
    }

    free(buf);
    close(fd);
    return 0;
}
