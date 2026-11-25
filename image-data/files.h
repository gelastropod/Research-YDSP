#ifndef FILES_H
#define FILES_H

#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static inline int same_file(const char *a, const char *b)
{
    struct stat sa, sb;
    return strcmp(a, b) == 0 ||
           (stat(a, &sa) == 0 && stat(b, &sb) == 0 &&
            sa.st_dev == sb.st_dev && sa.st_ino == sb.st_ino);
}

static inline int file_size(FILE *file, uint64_t *size)
{
    struct stat st;
    if (fstat(fileno(file), &st) != 0 || !S_ISREG(st.st_mode) || st.st_size < 0)
        return 0;
    *size = (uint64_t)st.st_size;
    return 1;
}
#endif
