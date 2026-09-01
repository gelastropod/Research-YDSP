#ifndef FDE_H
#define FDE_H

struct FDEScheme {
	size_t kl, bl, sl, il;

	int (*keygen)(unsigned char*);
	int (*enc)(const unsigned char*, const unsigned char*, const unsigned char*, const unsigned char*, unsigned char*);
	int (*dec)(const unsigned char*, const unsigned char*, const unsigned char*, const unsigned char*, unsigned char*);
};

typedef struct FDEScheme FDEScheme;

#endif
