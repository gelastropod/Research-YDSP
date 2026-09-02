#!/usr/bin/env sh
set -eu

output_dir="${1:-results}"
mkdir -p "$output_dir"
output_file="$output_dir/environment.txt"

{
    printf 'captured_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'uname=%s\n' "$(uname -a)"
    printf 'logical_cpus=%s\n' "$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf unknown)"
    printf 'compiler=%s\n' "$(cc --version 2>/dev/null | sed -n '1p')"
    printf 'openssl=%s\n' "$(openssl version 2>/dev/null || printf unknown)"
    if [ -r /proc/cpuinfo ]; then
        grep -m1 '^flags' /proc/cpuinfo | grep -qw aes &&
            printf 'cpu_aes_instruction_flag=present\n' ||
            printf 'cpu_aes_instruction_flag=absent_or_hidden\n'
        grep -m1 '^flags' /proc/cpuinfo | grep -qw sha_ni &&
            printf 'cpu_sha_instruction_flag=present\n' ||
            printf 'cpu_sha_instruction_flag=absent_or_hidden\n'
    elif command -v sysctl >/dev/null 2>&1; then
        features=$(sysctl -n machdep.cpu.features 2>/dev/null || printf unknown)
        printf 'cpu_features=%s\n' "$features"
    fi
    if command -v lscpu >/dev/null 2>&1; then
        lscpu | sed -n \
            -e 's/^Model name:[[:space:]]*/cpu_model=/p' \
            -e 's/^Architecture:[[:space:]]*/architecture=/p' \
            -e 's/^CPU(s):[[:space:]]*/reported_cpus=/p' \
            -e 's/^L1d cache:[[:space:]]*/l1d_cache=/p' \
            -e 's/^L2 cache:[[:space:]]*/l2_cache=/p' \
            -e 's/^L3 cache:[[:space:]]*/l3_cache=/p'
    fi
} > "$output_file"

printf 'Wrote %s\n' "$output_file"
