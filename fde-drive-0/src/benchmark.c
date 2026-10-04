#define _POSIX_C_SOURCE 200809L

#include "fde.h"

#include <errno.h>
#include <math.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#if defined(__x86_64__) || defined(__i386__)
#include <x86intrin.h>
#define FDE_HAS_TSC 1
#else
#define FDE_HAS_TSC 0
#endif

enum { MAX_TRIALS = 12, TARGET_COUNT = 6 };

typedef struct {
    double mean;
    double median;
    double stdev;
} statistics;

typedef enum {
    BENCH_ECB = 0,
    BENCH_XTS_MANUAL,
    BENCH_XTS_OPENSSL,
    BENCH_CTR_AES,
    BENCH_CTR_BLAKE3,
    BENCH_CBC_AES,
    BENCH_CBC_BLAKE3,
    BENCH_IMPL_COUNT
} bench_impl;

static volatile uint8_t benchmark_sink = 0;

static uint64_t now_ns(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
        return 0;
    }
    return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}

static uint64_t read_tsc(void) {
#if FDE_HAS_TSC
    unsigned int auxiliary;
    _mm_lfence();
    uint64_t value = __rdtscp(&auxiliary);
    _mm_lfence();
    return value;
#else
    return 0;
#endif
}

static int compare_double(const void *left, const void *right) {
    double a = *(const double *)left;
    double b = *(const double *)right;
    return (a > b) - (a < b);
}

static statistics describe(const double *samples, size_t count) {
    statistics result = {0};
    double copy[MAX_TRIALS > 2048 ? MAX_TRIALS : 2048];
    double sum = 0;
    double sumsq = 0;
    if (count == 0 || count > sizeof(copy) / sizeof(copy[0])) {
        return result;
    }
    for (size_t i = 0; i < count; ++i) {
        copy[i] = samples[i];
        sum += samples[i];
        sumsq += samples[i] * samples[i];
    }
    qsort(copy, count, sizeof(copy[0]), compare_double);
    result.mean = sum / (double)count;
    result.median = count % 2 == 0
                        ? (copy[count / 2 - 1] + copy[count / 2]) / 2.0
                        : copy[count / 2];
    if (count > 1) {
        double variance = (sumsq - sum * sum / (double)count) /
                          (double)(count - 1);
        result.stdev = sqrt(variance > 0 ? variance : 0);
    }
    return result;
}

static void fill_data(uint8_t *data, size_t bytes, uint32_t seed) {
    uint32_t value = seed;
    for (size_t i = 0; i < bytes; ++i) {
        value = value * UINT32_C(1664525) + UINT32_C(1013904223);
        data[i] = (uint8_t)(value >> 24);
    }
}

static const char *bench_name(bench_impl implementation) {
    static const char *const names[BENCH_IMPL_COUNT] = {
        "AES-ECB",
        "AES-XTS-manual-sequential",
        "AES-XTS-OpenSSL-full-sector",
        "Ratchet-CTR-AES",
        "Ratchet-CTR-BLAKE3",
        "Ratchet-CBC-AES",
        "Ratchet-CBC-BLAKE3"
    };
    return implementation >= 0 && implementation < BENCH_IMPL_COUNT
               ? names[implementation]
               : "unknown";
}

static fde_scheme implementation_scheme(bench_impl implementation) {
    switch (implementation) {
    case BENCH_ECB:
        return FDE_ECB;
    case BENCH_XTS_MANUAL:
    case BENCH_XTS_OPENSSL:
        return FDE_XTS;
    case BENCH_CTR_AES:
        return FDE_RATCHET_CTR_AES;
    case BENCH_CTR_BLAKE3:
        return FDE_RATCHET_CTR_BLAKE3;
    case BENCH_CBC_AES:
        return FDE_RATCHET_CBC_AES;
    case BENCH_CBC_BLAKE3:
        return FDE_RATCHET_CBC_BLAKE3;
    default:
        return FDE_ECB;
    }
}

static int ensure_directory(const char *path) {
    if (mkdir(path, 0775) == 0 || errno == EEXIST) {
        return 0;
    }
    perror(path);
    return -1;
}

static FILE *open_result(const char *directory, const char *filename) {
    char path[1024];
    int length = snprintf(path, sizeof(path), "%s/%s", directory, filename);
    if (length < 0 || (size_t)length >= sizeof(path)) {
        return NULL;
    }
    return fopen(path, "w");
}

static int crypt_sector(fde_worker *worker, bench_impl implementation,
                        int encrypt, const uint8_t *input,
                        const uint32_t *indices, uint64_t sector,
                        size_t sector_bytes, uint8_t *output) {
    size_t blocks = sector_bytes / FDE_BLOCK_BYTES;
    if (implementation == BENCH_XTS_OPENSSL) {
        return encrypt ? fde_xts_openssl_encrypt(worker, input, sector,
                                                 sector_bytes, output)
                       : fde_xts_openssl_decrypt(worker, input, sector,
                                                sector_bytes, output);
    }
    return encrypt ? fde_encrypt(worker, implementation_scheme(implementation),
                                 input, indices, sector, blocks, output, NULL)
                   : fde_decrypt(worker, implementation_scheme(implementation),
                                 input, indices, sector, blocks, output, NULL);
}

static int crypt_volume(fde_worker *worker, bench_impl implementation,
                        int encrypt, const uint8_t *input,
                        const uint32_t *indices, uint64_t first_sector,
                        size_t sector_bytes, size_t volume_bytes,
                        uint8_t *output) {
    size_t sectors = volume_bytes / sector_bytes;
    for (size_t s = 0; s < sectors; ++s) {
        if (crypt_sector(worker, implementation, encrypt,
                         input + s * sector_bytes, indices,
                         first_sector + s, sector_bytes,
                         output + s * sector_bytes) != 0) {
            return -1;
        }
    }
    benchmark_sink ^= output[(sectors * sector_bytes) - 1];
    return 0;
}

static int benchmark_throughput(const char *directory, const fde_keys *keys,
                                int quick) {
    const size_t sector_sizes[] = {512, 4096};
    const size_t volumes_full[] = {1u << 20, 32u << 20};
    const size_t volumes_quick[] = {1u << 20, 8u << 20};
    const size_t *volumes = quick ? volumes_quick : volumes_full;
    const size_t volume_count = 2;
    int trials = quick ? 3 : 5;
    FILE *file = open_result(directory, "throughput.csv");
    if (file == NULL) {
        return -1;
    }
    fprintf(file,
            "implementation,operation,sector_bytes,volume_bytes,trials,"
            "mean_ns,median_ns,stdev_ns,mean_mib_s,median_mib_s,"
            "mean_ns_per_sector,mean_tsc_cycles_per_byte\n");

    for (size_t z = 0; z < sizeof(sector_sizes) / sizeof(sector_sizes[0]); ++z) {
        size_t sector_bytes = sector_sizes[z];
        size_t blocks = sector_bytes / FDE_BLOCK_BYTES;
        uint32_t *indices = malloc(blocks * sizeof(*indices));
        if (indices == NULL) {
            fclose(file);
            return -1;
        }
        for (size_t j = 0; j < blocks; ++j) {
            indices[j] = (uint32_t)j;
        }
        for (size_t v = 0; v < volume_count; ++v) {
            size_t volume_bytes = volumes[v] - volumes[v] % sector_bytes;
            uint8_t *plain = malloc(volume_bytes);
            uint8_t *cipher = malloc(volume_bytes);
            uint8_t *output = malloc(volume_bytes);
            if (plain == NULL || cipher == NULL || output == NULL) {
                free(plain);
                free(cipher);
                free(output);
                free(indices);
                fclose(file);
                return -1;
            }
            fill_data(plain, volume_bytes, (uint32_t)(sector_bytes + volume_bytes));
            for (int implementation = 0; implementation < BENCH_IMPL_COUNT;
                 ++implementation) {
                fde_worker *worker = fde_worker_new(keys);
                if (worker == NULL ||
                    crypt_volume(worker, (bench_impl)implementation, 1, plain,
                                 indices, 1000, sector_bytes, volume_bytes,
                                 cipher) != 0) {
                    fde_worker_free(worker);
                    free(plain);
                    free(cipher);
                    free(output);
                    free(indices);
                    fclose(file);
                    return -1;
                }
                for (int operation = 0; operation < 2; ++operation) {
                    double elapsed[MAX_TRIALS] = {0};
                    double cycles[MAX_TRIALS] = {0};
                    const uint8_t *source = operation == 0 ? plain : cipher;
                    for (int trial = 0; trial < trials; ++trial) {
                        uint64_t cycle_start = read_tsc();
                        uint64_t start = now_ns();
                        int ok = crypt_volume(worker, (bench_impl)implementation,
                                              operation == 0, source, indices,
                                              1000, sector_bytes, volume_bytes,
                                              output);
                        uint64_t end = now_ns();
                        uint64_t cycle_end = read_tsc();
                        if (ok != 0) {
                            fde_worker_free(worker);
                            free(plain);
                            free(cipher);
                            free(output);
                            free(indices);
                            fclose(file);
                            return -1;
                        }
                        elapsed[trial] = (double)(end - start);
                        cycles[trial] = FDE_HAS_TSC
                                            ? (double)(cycle_end - cycle_start)
                                            : 0;
                    }
                    statistics ns = describe(elapsed, (size_t)trials);
                    statistics tsc = describe(cycles, (size_t)trials);
                    double mib = (double)volume_bytes / (1024.0 * 1024.0);
                    double mean_rate = mib / (ns.mean * 1e-9);
                    double median_rate = mib / (ns.median * 1e-9);
                    double sectors = (double)volume_bytes / (double)sector_bytes;
                    fprintf(file,
                            "%s,%s,%zu,%zu,%d,%.3f,%.3f,%.3f,%.6f,%.6f,"
                            "%.3f,%.6f\n",
                            bench_name((bench_impl)implementation),
                            operation == 0 ? "encrypt" : "decrypt",
                            sector_bytes, volume_bytes, trials, ns.mean,
                            ns.median, ns.stdev, mean_rate, median_rate,
                            ns.mean / sectors,
                            FDE_HAS_TSC ? tsc.mean / (double)volume_bytes : 0);
                }
                fde_worker_free(worker);
            }
            free(plain);
            free(cipher);
            free(output);
        }
        free(indices);
    }
    fclose(file);
    return 0;
}

static int benchmark_breakdown(const char *directory, const fde_keys *keys,
                               int quick) {
    const size_t sector_bytes = 4096;
    const size_t blocks = sector_bytes / FDE_BLOCK_BYTES;
    int iterations = quick ? 100 : 500;
    uint8_t *plain = malloc(sector_bytes);
    uint8_t *cipher = malloc(sector_bytes);
    uint8_t *output = malloc(sector_bytes);
    uint32_t *indices = malloc(blocks * sizeof(*indices));
    FILE *file = open_result(directory, "component_breakdown.csv");
    if (plain == NULL || cipher == NULL || output == NULL || indices == NULL ||
        file == NULL) {
        free(plain);
        free(cipher);
        free(output);
        free(indices);
        if (file != NULL) {
            fclose(file);
        }
        return -1;
    }
    fill_data(plain, sector_bytes, 451);
    for (size_t j = 0; j < blocks; ++j) {
        indices[j] = (uint32_t)j;
    }
    fprintf(file,
            "implementation,operation,sector_bytes,iterations,outer_total_ns,"
            "measured_seed_ns,measured_data_ns,measured_evolution_ns,"
            "seed_percent,data_percent,evolution_percent\n");

    for (int scheme = 0; scheme < FDE_SCHEME_COUNT; ++scheme) {
        fde_worker *worker = fde_worker_new(keys);
        if (worker == NULL ||
            fde_encrypt(worker, (fde_scheme)scheme, plain, indices, 321, blocks,
                        cipher, NULL) != 0) {
            fde_worker_free(worker);
            fclose(file);
            free(plain);
            free(cipher);
            free(output);
            free(indices);
            return -1;
        }
        for (int operation = 0; operation < 2; ++operation) {
            fde_profile total = {0};
            uint64_t outer_start = now_ns();
            for (int iteration = 0; iteration < iterations; ++iteration) {
                fde_profile one;
                int ok = operation == 0
                             ? fde_encrypt(worker, (fde_scheme)scheme, plain,
                                           indices, 321, blocks, output, &one)
                             : fde_decrypt(worker, (fde_scheme)scheme, cipher,
                                           indices, 321, blocks, output, &one);
                if (ok != 0) {
                    fde_worker_free(worker);
                    fclose(file);
                    free(plain);
                    free(cipher);
                    free(output);
                    free(indices);
                    return -1;
                }
                total.seed_ns += one.seed_ns;
                total.data_ns += one.data_ns;
                total.evolution_ns += one.evolution_ns;
            }
            uint64_t outer_total = now_ns() - outer_start;
            double measured = (double)(total.seed_ns + total.data_ns +
                                       total.evolution_ns);
            fprintf(file,
                    "%s,%s,%zu,%d,%llu,%llu,%llu,%llu,%.6f,%.6f,%.6f\n",
                    fde_scheme_name((fde_scheme)scheme),
                    operation == 0 ? "encrypt" : "decrypt", sector_bytes,
                    iterations, (unsigned long long)outer_total,
                    (unsigned long long)total.seed_ns,
                    (unsigned long long)total.data_ns,
                    (unsigned long long)total.evolution_ns,
                    measured > 0 ? 100.0 * (double)total.seed_ns / measured : 0,
                    measured > 0 ? 100.0 * (double)total.data_ns / measured : 0,
                    measured > 0
                        ? 100.0 * (double)total.evolution_ns / measured
                        : 0);
        }
        fde_worker_free(worker);
    }

    /* Expose the literal indexed XTS cost without using it as the fair baseline. */
    {
        fde_worker *worker = fde_worker_new(keys);
        fde_profile total = {0};
        uint64_t outer_start = now_ns();
        for (int iteration = 0; iteration < iterations; ++iteration) {
            fde_profile one;
            if (fde_xts_encrypt_indexed(worker, plain, indices, 321, blocks,
                                        output, &one) != 0) {
                fde_worker_free(worker);
                fclose(file);
                free(plain);
                free(cipher);
                free(output);
                free(indices);
                return -1;
            }
            total.seed_ns += one.seed_ns;
            total.data_ns += one.data_ns;
            total.evolution_ns += one.evolution_ns;
        }
        uint64_t outer_total = now_ns() - outer_start;
        double measured = (double)(total.seed_ns + total.data_ns +
                                   total.evolution_ns);
        fprintf(file,
                "AES-XTS-literal-indexed,encrypt,%zu,%d,%llu,%llu,%llu,%llu,"
                "%.6f,%.6f,%.6f\n",
                sector_bytes, iterations, (unsigned long long)outer_total,
                (unsigned long long)total.seed_ns,
                (unsigned long long)total.data_ns,
                (unsigned long long)total.evolution_ns,
                100.0 * (double)total.seed_ns / measured,
                100.0 * (double)total.data_ns / measured,
                100.0 * (double)total.evolution_ns / measured);
        fde_worker_free(worker);
    }
    fclose(file);
    free(plain);
    free(cipher);
    free(output);
    free(indices);
    return 0;
}

static int benchmark_ratchet_primitives(const char *directory,
                                        const fde_keys *keys, int quick) {
    size_t iterations = quick ? 100000 : 1000000;
    uint8_t ciphertext[16];
    uint8_t aes_state[16];
    uint8_t blake_state[32];
    FILE *file = open_result(directory, "ratchet_primitives.csv");
    fde_worker *worker = fde_worker_new(keys);
    if (file == NULL || worker == NULL) {
        if (file != NULL) {
            fclose(file);
        }
        fde_worker_free(worker);
        return -1;
    }
    fill_data(ciphertext, sizeof(ciphertext), 91);
    fill_data(aes_state, sizeof(aes_state), 92);
    fill_data(blake_state, sizeof(blake_state), 93);
    fprintf(file,
            "primitive,iterations,input_bytes,output_state_bytes,total_ns,"
            "ns_per_update,tsc_cycles_per_update\n");

    uint64_t cycle_start = read_tsc();
    uint64_t start = now_ns();
    for (size_t i = 0; i < iterations; ++i) {
        if (fde_ratchet_aes_update(worker, aes_state, ciphertext) != 0) {
            fclose(file);
            fde_worker_free(worker);
            return -1;
        }
    }
    uint64_t elapsed = now_ns() - start;
    uint64_t cycles = read_tsc() - cycle_start;
    fprintf(file, "AES-256(KG,KxorC),%zu,16,16,%llu,%.6f,%.6f\n",
            iterations, (unsigned long long)elapsed,
            (double)elapsed / (double)iterations,
            FDE_HAS_TSC ? (double)cycles / (double)iterations : 0);

    cycle_start = read_tsc();
    start = now_ns();
    for (size_t i = 0; i < iterations; ++i) {
        fde_ratchet_blake3_update(blake_state, ciphertext);
    }
    elapsed = now_ns() - start;
    cycles = read_tsc() - cycle_start;
    fprintf(file, "BLAKE3(KconcatC),%zu,48,32,%llu,%.6f,%.6f\n",
            iterations, (unsigned long long)elapsed,
            (double)elapsed / (double)iterations,
            FDE_HAS_TSC ? (double)cycles / (double)iterations : 0);
    benchmark_sink ^= aes_state[0] ^ blake_state[0];
    fclose(file);
    fde_worker_free(worker);
    return 0;
}

static void thrash_cache(uint8_t *buffer, size_t bytes) {
    uint8_t accumulator = 0;
    for (size_t i = 0; i < bytes; i += 64) {
        buffer[i] = (uint8_t)(buffer[i] + 1u);
        accumulator ^= buffer[i];
    }
    benchmark_sink ^= accumulator;
}

static void shuffle_targets(size_t order[TARGET_COUNT], uint32_t *state) {
    for (size_t i = 0; i < TARGET_COUNT; ++i) {
        order[i] = i;
    }
    for (size_t i = TARGET_COUNT - 1; i > 0; --i) {
        *state = *state * UINT32_C(1664525) + UINT32_C(1013904223);
        size_t j = (size_t)(*state % (uint32_t)(i + 1));
        size_t temp = order[i];
        order[i] = order[j];
        order[j] = temp;
    }
}

static int benchmark_random_access(const char *directory, const fde_keys *keys,
                                   int quick) {
    const size_t sector_bytes = 4096;
    const size_t blocks = 256;
    const size_t target_blocks[TARGET_COUNT] = {1, 32, 64, 128, 192, 256};
    int warm_samples = quick ? 200 : 1000;
    int cold_samples = quick ? 20 : 80;
    size_t cache_bytes = quick ? (1u << 20) : (8u << 20);
    uint8_t *plain = malloc(sector_bytes);
    uint8_t *cipher = malloc(sector_bytes);
    uint8_t *cache = calloc(cache_bytes, 1);
    uint32_t *indices = malloc(blocks * sizeof(*indices));
    FILE *file = open_result(directory, "random_access.csv");
    if (plain == NULL || cipher == NULL || cache == NULL || indices == NULL ||
        file == NULL) {
        free(plain);
        free(cipher);
        free(cache);
        free(indices);
        if (file != NULL) {
            fclose(file);
        }
        return -1;
    }
    fill_data(plain, sector_bytes, 277);
    for (size_t j = 0; j < blocks; ++j) {
        indices[j] = (uint32_t)j;
    }
    fprintf(file,
            "cache_state,scheme,target_block,samples,mean_ns,median_ns,stdev_ns\n");

    for (int scheme = 0; scheme < FDE_SCHEME_COUNT; ++scheme) {
        fde_worker *worker = fde_worker_new(keys);
        if (worker == NULL ||
            fde_encrypt(worker, (fde_scheme)scheme, plain, indices, 700, blocks,
                        cipher, NULL) != 0) {
            fde_worker_free(worker);
            fclose(file);
            free(plain);
            free(cipher);
            free(cache);
            free(indices);
            return -1;
        }
        for (int cold = 0; cold < 2; ++cold) {
            int samples = cold ? cold_samples : warm_samples;
            double *measurements[TARGET_COUNT];
            for (size_t t = 0; t < TARGET_COUNT; ++t) {
                measurements[t] = calloc((size_t)samples, sizeof(double));
                if (measurements[t] == NULL) {
                    return -1;
                }
            }
            uint32_t rng = (uint32_t)(1000 + scheme * 100 + cold);
            for (int sample = 0; sample < samples; ++sample) {
                size_t order[TARGET_COUNT];
                shuffle_targets(order, &rng);
                for (size_t q = 0; q < TARGET_COUNT; ++q) {
                    size_t t = order[q];
                    uint8_t recovered[16];
                    if (cold) {
                        thrash_cache(cache, cache_bytes);
                    }
                    uint64_t start = now_ns();
                    int ok = fde_decrypt_target(
                        worker, (fde_scheme)scheme, cipher, indices, 700, blocks,
                        target_blocks[t] - 1, recovered);
                    uint64_t end = now_ns();
                    if (ok != 0 ||
                        memcmp(recovered, plain + 16 * (target_blocks[t] - 1),
                               16) != 0) {
                        return -1;
                    }
                    measurements[t][sample] = (double)(end - start);
                }
            }
            for (size_t t = 0; t < TARGET_COUNT; ++t) {
                statistics result = describe(measurements[t], (size_t)samples);
                fprintf(file, "%s,%s,%zu,%d,%.3f,%.3f,%.3f\n",
                        cold ? "cache-thrashed" : "warm",
                        fde_scheme_name((fde_scheme)scheme), target_blocks[t],
                        samples, result.mean, result.median, result.stdev);
                free(measurements[t]);
            }
        }
        fde_worker_free(worker);
    }
    fclose(file);
    free(plain);
    free(cipher);
    free(cache);
    free(indices);
    return 0;
}

typedef struct {
    pthread_mutex_t mutex;
    pthread_cond_t condition;
    int ready;
    int start;
    int expected;
} start_gate;

typedef struct {
    const fde_keys *keys;
    bench_impl implementation;
    const uint8_t *input;
    uint8_t *output;
    const uint32_t *indices;
    size_t sector_bytes;
    size_t first_sector;
    size_t sector_count;
    start_gate *gate;
    int status;
} parallel_job;

static void *parallel_worker(void *opaque) {
    parallel_job *job = opaque;
    fde_worker *worker = fde_worker_new(job->keys);
    pthread_mutex_lock(&job->gate->mutex);
    ++job->gate->ready;
    pthread_cond_broadcast(&job->gate->condition);
    while (!job->gate->start) {
        pthread_cond_wait(&job->gate->condition, &job->gate->mutex);
    }
    pthread_mutex_unlock(&job->gate->mutex);

    job->status = worker == NULL ? -1 : 0;
    for (size_t local = 0; worker != NULL && local < job->sector_count;
         ++local) {
        size_t sector_index = job->first_sector + local;
        if (crypt_sector(worker, job->implementation, 1,
                         job->input + sector_index * job->sector_bytes,
                         job->indices, 9000 + sector_index, job->sector_bytes,
                         job->output + sector_index * job->sector_bytes) != 0) {
            job->status = -1;
            break;
        }
    }
    fde_worker_free(worker);
    return NULL;
}

static int parallel_trial(const fde_keys *keys, bench_impl implementation,
                          int threads, const uint8_t *input, uint8_t *output,
                          const uint32_t *indices, size_t sector_bytes,
                          size_t volume_bytes, double *elapsed_ns) {
    size_t sectors = volume_bytes / sector_bytes;
    pthread_t *handles = calloc((size_t)threads, sizeof(*handles));
    parallel_job *jobs = calloc((size_t)threads, sizeof(*jobs));
    start_gate gate;
    if (handles == NULL || jobs == NULL) {
        free(handles);
        free(jobs);
        return -1;
    }
    pthread_mutex_init(&gate.mutex, NULL);
    pthread_cond_init(&gate.condition, NULL);
    gate.ready = 0;
    gate.start = 0;
    gate.expected = threads;

    size_t cursor = 0;
    for (int t = 0; t < threads; ++t) {
        size_t remaining = sectors - cursor;
        size_t workers_left = (size_t)(threads - t);
        size_t count = remaining / workers_left;
        jobs[t] = (parallel_job){keys,
                                 implementation,
                                 input,
                                 output,
                                 indices,
                                 sector_bytes,
                                 cursor,
                                 count,
                                 &gate,
                                 0};
        cursor += count;
        if (pthread_create(&handles[t], NULL, parallel_worker, &jobs[t]) != 0) {
            return -1;
        }
    }

    pthread_mutex_lock(&gate.mutex);
    while (gate.ready < gate.expected) {
        pthread_cond_wait(&gate.condition, &gate.mutex);
    }
    uint64_t start = now_ns();
    gate.start = 1;
    pthread_cond_broadcast(&gate.condition);
    pthread_mutex_unlock(&gate.mutex);

    int status = 0;
    for (int t = 0; t < threads; ++t) {
        pthread_join(handles[t], NULL);
        if (jobs[t].status != 0) {
            status = -1;
        }
    }
    *elapsed_ns = (double)(now_ns() - start);
    benchmark_sink ^= output[volume_bytes - 1];
    pthread_cond_destroy(&gate.condition);
    pthread_mutex_destroy(&gate.mutex);
    free(handles);
    free(jobs);
    return status;
}

static int benchmark_parallel(const char *directory, const fde_keys *keys,
                              int quick) {
    const size_t sector_bytes = 4096;
    const size_t blocks = 256;
    size_t volume_bytes = quick ? (16u << 20) : (64u << 20);
    int trials = quick ? 2 : 3;
    const int candidates[] = {1, 2, 4, 8};
    long online = sysconf(_SC_NPROCESSORS_ONLN);
    uint8_t *input = malloc(volume_bytes);
    uint8_t *output = malloc(volume_bytes);
    uint32_t *indices = malloc(blocks * sizeof(*indices));
    FILE *file = open_result(directory, "parallel_scaling.csv");
    if (input == NULL || output == NULL || indices == NULL || file == NULL) {
        free(input);
        free(output);
        free(indices);
        if (file != NULL) {
            fclose(file);
        }
        return -1;
    }
    fill_data(input, volume_bytes, 662);
    for (size_t j = 0; j < blocks; ++j) {
        indices[j] = (uint32_t)j;
    }
    fprintf(file,
            "implementation,threads,sector_bytes,volume_bytes,trials,mean_ns,"
            "mean_mib_s,speedup,efficiency\n");

    for (int implementation = 0; implementation < BENCH_IMPL_COUNT;
         ++implementation) {
        double baseline = 0;
        for (size_t c = 0; c < sizeof(candidates) / sizeof(candidates[0]); ++c) {
            int threads = candidates[c];
            if (online > 0 && threads > online) {
                continue;
            }
            double samples[MAX_TRIALS] = {0};
            for (int trial = 0; trial < trials; ++trial) {
                if (parallel_trial(keys, (bench_impl)implementation, threads,
                                   input, output, indices, sector_bytes,
                                   volume_bytes, &samples[trial]) != 0) {
                    fclose(file);
                    free(input);
                    free(output);
                    free(indices);
                    return -1;
                }
            }
            statistics result = describe(samples, (size_t)trials);
            if (threads == 1) {
                baseline = result.mean;
            }
            double speedup = baseline / result.mean;
            double mib_s = ((double)volume_bytes / (1024.0 * 1024.0)) /
                           (result.mean * 1e-9);
            fprintf(file, "%s,%d,%zu,%zu,%d,%.3f,%.6f,%.6f,%.6f\n",
                    bench_name((bench_impl)implementation), threads,
                    sector_bytes, volume_bytes, trials, result.mean, mib_s,
                    speedup, speedup / (double)threads);
        }
    }
    fclose(file);
    free(input);
    free(output);
    free(indices);
    return 0;
}

static int write_run_metadata(const char *directory, int quick) {
    FILE *file = open_result(directory, "run_metadata.txt");
    if (file == NULL) {
        return -1;
    }
    time_t current = time(NULL);
    fprintf(file, "benchmark_profile=%s\n", quick ? "quick" : "full");
    fprintf(file, "unix_time=%lld\n", (long long)current);
    fprintf(file, "logical_cpus=%ld\n", sysconf(_SC_NPROCESSORS_ONLN));
    fprintf(file, "tsc_available=%d\n", FDE_HAS_TSC);
    fprintf(file, "benchmark_sink=%u\n", (unsigned)benchmark_sink);
    fclose(file);
    return 0;
}

static void usage(const char *program) {
    fprintf(stderr,
            "Usage: %s --all [results-directory]\n"
            "       %s --quick [results-directory]\n"
            "       %s --rq1|--rq2|--rq3|--rq4 [results-directory]\n",
            program, program, program);
}

int main(int argc, char **argv) {
    int quick = 0;
    int run_rq1 = 0;
    int run_rq2 = 0;
    int run_rq3 = 0;
    int run_rq4 = 0;
    const char *directory;
    fde_keys keys;
    if (argc < 2) {
        usage(argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "--all") == 0) {
        run_rq1 = run_rq2 = run_rq3 = run_rq4 = 1;
    } else if (strcmp(argv[1], "--quick") == 0) {
        quick = 1;
        run_rq1 = run_rq2 = run_rq3 = run_rq4 = 1;
    } else if (strcmp(argv[1], "--rq1") == 0) {
        run_rq1 = 1;
    } else if (strcmp(argv[1], "--rq2") == 0) {
        run_rq2 = 1;
    } else if (strcmp(argv[1], "--rq3") == 0) {
        run_rq3 = 1;
    } else if (strcmp(argv[1], "--rq4") == 0) {
        run_rq4 = 1;
    } else {
        usage(argv[0]);
        return 2;
    }
    directory = argc >= 3 ? argv[2] : "results";
    if (ensure_directory(directory) != 0) {
        return 1;
    }
    fde_default_keys(&keys);

    printf("Running %s in-memory benchmark profile.\n",
           quick ? "quick" : "full");
    printf("Writing CSV files to %s.\n", directory);

    if (run_rq2) {
        printf("RQ2: throughput and latency...\n");
        if (benchmark_throughput(directory, &keys, quick) != 0) {
            return 1;
        }
    }
    if (run_rq1) {
        printf("RQ1: component breakdown...\n");
        if (benchmark_breakdown(directory, &keys, quick) != 0) {
            return 1;
        }
    }
    if (run_rq3) {
        printf("RQ3: ratchet primitive controls...\n");
        if (benchmark_ratchet_primitives(directory, &keys, quick) != 0) {
            return 1;
        }
    }
    if (run_rq4) {
        printf("RQ4: random access...\n");
        if (benchmark_random_access(directory, &keys, quick) != 0) {
            return 1;
        }
        printf("RQ4: inter-sector parallel scaling...\n");
        if (benchmark_parallel(directory, &keys, quick) != 0) {
            return 1;
        }
    }
    if (write_run_metadata(directory, quick) != 0) {
        return 1;
    }
    printf("Benchmark complete. Sink=%u\n", (unsigned)benchmark_sink);
    return 0;
}
