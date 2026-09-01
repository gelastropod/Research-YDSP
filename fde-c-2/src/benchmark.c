#include "benchmark.h"

int benchmark_rng_init(benchmark_rng *rng) {
	if (rng->initialised) return ERR_BENCHMARK_RNG_ALREADY_INIT;

	int ret;
	mbedtls_entropy_init(&rng->entropy);
	mbedtls_ctr_drbg_init(&rng->drbg);

	const unsigned char personalisation[] = "fde-benchmark-test";

	ret = mbedtls_ctr_drbg_seed(&rng->drbg, mbedtls_entropy_function, &rng->entropy,
						  personalisation, sizeof(personalisation) - 1);

	if (ret != 0) ret = ERR_BENCHMARK_RNG_SEED;
	else rng->initialised = 1;

	return ret;
}

int benchmark_rng_fill(const benchmark_rng *rng, size_t length, unsigned char *data) {
	if (!rng->initialised) return ERR_BENCHMARK_RNG_NOT_INIT;

	int ret;
	ret = mbedtls_ctr_drbg_random(&rng->drbg, data, length);

	if (ret != 0) ret = ERR_BENCHMARK_RNG_RANDOM;

	return ret;
}

int benchmark_rng_free(benchmark_rng *rng) {
	if (!rng->initialised) return ERR_BENCHMARK_RNG_NOT_INIT;
	mbedtls_ctr_drbg_free(&rng->drbg);
	mbedtls_entropy_free(&rng->entropy);

	rng->initialised = 0;

	return 0;
}

int benchmark(const benchmark_parameters *parameters, benchmark_result *result) {
	
}
