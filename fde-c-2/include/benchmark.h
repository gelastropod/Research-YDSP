#ifndef BENCHMARK_H
#define BENCHMARK_H

#include "fde.h"

#include "mbedtls/entropy.h"
#include "mbedtls/ctr_drbg.h"

#define ERR_BENCHMARK_RNG_ALREADY_INIT 0x1;
#define ERR_BENCHMARK_RNG_NOT_INIT 0x2;
#define ERR_BENCHMARK_RNG_SEED 0x4;
#define ERR_BENCHMARK_RNG_RANDOM 0x8;

struct benchmark_rng {
	mbedtls_entropy_context entropy;
	mbedtls_ctr_drbg_context drbg;
	int initialised;
};

struct benchmark_parameters {
	FDEScheme *scheme;
	size_t num_blocks_per_sector, num_sectors;
	int rounds;
};

struct benchmark_result {
	int rounds;
	size_t bytes_per_round;
	double total_time, average_time;
};

typedef struct benchmark_rng benchmark_rng;
typedef struct benchmark_parameters benchmark_parameters;
typedef struct benchmark_result benchmark_result;

int benchmark_rng_init(benchmark_rng *rng);
int benchmark_rng_fill(const benchmark_rng *rng, size_t length, unsigned char *data);

int benchmark(const benchmark_parameters *parameters, benchmark_result *result);

#endif
