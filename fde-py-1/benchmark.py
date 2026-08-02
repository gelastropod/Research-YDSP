"""
Performance analytics for baseline and ciphertext-ratcheted AES-XTS.

Run a quick benchmark:
    python benchmark.py

Customise the workload:
    python benchmark.py --repeats 9 --iterations 200 --sectors 32 \
        --blocks-per-sector 32 --csv results.csv

The script reports mean, median, sample standard deviation, minimum, maximum,
per-call latency, and throughput where a byte count is meaningful. It also times
the isolated F and G ratchet functions and produces a component-level profile of
one ratcheted sector. The output is analytics only and does not assert a security
or performance conclusion.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from ratchet_fde import (
    BLOCK_SIZE,
    BaselineXTSFDE,
    RatchetedXTSFDE,
    RatchetState,
    derive_subkeys,
    encode_lba,
    ratchet_tweak,
    ratchet_xts_key,
    xts_decrypt_data_unit,
    xts_encrypt_data_unit,
)


@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    repeats: int
    bytes_per_call: int
    mean_ns: float
    median_ns: float
    stdev_ns: float
    min_ns: float
    max_ns: float
    throughput_mib_s: Optional[float]


@dataclass
class ComponentProfile:
    xts_core_ns: int = 0
    tweak_update_ns: int = 0
    key_update_ns: int = 0
    blocks: int = 0


def benchmark_callable(
    name: str,
    function: Callable[[], object],
    *,
    iterations: int,
    repeats: int,
    bytes_per_call: int = 0,
    warmup: int = 10,
) -> BenchmarkResult:
    """Measure a zero-argument callable over repeated batches."""
    for _ in range(warmup):
        function()

    per_call_ns: List[float] = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(iterations):
            function()
        elapsed = time.perf_counter_ns() - start
        per_call_ns.append(elapsed / iterations)

    mean_ns = statistics.fmean(per_call_ns)
    throughput = None
    if bytes_per_call > 0 and mean_ns > 0:
        throughput = (bytes_per_call / (1024 * 1024)) / (mean_ns / 1_000_000_000)

    return BenchmarkResult(
        name=name,
        iterations=iterations,
        repeats=repeats,
        bytes_per_call=bytes_per_call,
        mean_ns=mean_ns,
        median_ns=statistics.median(per_call_ns),
        stdev_ns=statistics.stdev(per_call_ns) if len(per_call_ns) > 1 else 0.0,
        min_ns=min(per_call_ns),
        max_ns=max(per_call_ns),
        throughput_mib_s=throughput,
    )


def profile_ratcheted_sector_encrypt(
    model: RatchetedXTSFDE,
    lba: int,
    plaintext_sector: bytes,
    repetitions: int,
) -> ComponentProfile:
    """
    Accumulate internal time spent in XTS, F, and G over full sector encryptions.

    This deliberately times Python call boundaries, so it is an implementation
    profile rather than a primitive-cycle benchmark.
    """
    profile = ComponentProfile()

    for _ in range(repetitions):
        state = model.initial_state(lba)
        for offset in range(0, model.sector_size, BLOCK_SIZE):
            plaintext_block = plaintext_sector[offset:offset + BLOCK_SIZE]

            start = time.perf_counter_ns()
            ciphertext_block = xts_encrypt_data_unit(state.xts_key, state.tweak, plaintext_block)
            profile.xts_core_ns += time.perf_counter_ns() - start

            start = time.perf_counter_ns()
            next_tweak = ratchet_tweak(model.k_f, ciphertext_block)
            profile.tweak_update_ns += time.perf_counter_ns() - start

            start = time.perf_counter_ns()
            next_key = ratchet_xts_key(model.k_g, state.xts_key, ciphertext_block)
            profile.key_update_ns += time.perf_counter_ns() - start

            state = RatchetState(next_key, next_tweak)
            profile.blocks += 1

    return profile


def make_volume(sectors: int, sector_size: int) -> bytes:
    """Generate deterministic benchmark data without timing random generation."""
    seed = bytes(range(256))
    required = sectors * sector_size
    return (seed * ((required // len(seed)) + 1))[:required]


def format_ns(value: float) -> str:
    if value < 1_000:
        return f"{value:.2f} ns"
    if value < 1_000_000:
        return f"{value / 1_000:.2f} us"
    if value < 1_000_000_000:
        return f"{value / 1_000_000:.2f} ms"
    return f"{value / 1_000_000_000:.3f} s"


def print_results(results: Iterable[BenchmarkResult]) -> None:
    print("\nBenchmark summary")
    print("=" * 118)
    header = (
        f"{'operation':38} {'mean':>12} {'median':>12} {'stdev':>12} "
        f"{'min':>12} {'max':>12} {'MiB/s':>10}"
    )
    print(header)
    print("-" * 118)
    for result in results:
        throughput = "-" if result.throughput_mib_s is None else f"{result.throughput_mib_s:.2f}"
        print(
            f"{result.name:38} "
            f"{format_ns(result.mean_ns):>12} "
            f"{format_ns(result.median_ns):>12} "
            f"{format_ns(result.stdev_ns):>12} "
            f"{format_ns(result.min_ns):>12} "
            f"{format_ns(result.max_ns):>12} "
            f"{throughput:>10}"
        )


def print_relative_ratios(results: List[BenchmarkResult]) -> None:
    by_name = {result.name: result for result in results}
    pairs = (
        ("sector encrypt", "baseline sector encrypt", "ratcheted sector encrypt"),
        ("sector decrypt", "baseline sector decrypt", "ratcheted sector decrypt"),
        ("volume encrypt", "baseline volume encrypt", "ratcheted-sector volume encrypt"),
        ("volume decrypt", "baseline volume decrypt", "ratcheted-sector volume decrypt"),
    )
    print("\nRelative elapsed-time ratios")
    print("=" * 72)
    for label, baseline_name, ratcheted_name in pairs:
        baseline = by_name[baseline_name].mean_ns
        ratcheted = by_name[ratcheted_name].mean_ns
        print(f"{label:24} ratcheted / baseline = {ratcheted / baseline:.3f}x")


def print_component_profile(profile: ComponentProfile) -> None:
    total = profile.xts_core_ns + profile.tweak_update_ns + profile.key_update_ns
    print("\nRatcheted-sector component profile")
    print("=" * 72)
    print(f"profiled blocks: {profile.blocks}")
    for name, value in (
        ("AES-XTS block operation", profile.xts_core_ns),
        ("F tweak update", profile.tweak_update_ns),
        ("G XTS-key update", profile.key_update_ns),
    ):
        share = (100 * value / total) if total else 0.0
        per_block = value / profile.blocks if profile.blocks else 0.0
        print(f"{name:28} total={format_ns(value):>12}  per-block={format_ns(per_block):>12}  share={share:6.2f}%")
    print(f"{'measured component total':28} {format_ns(total):>12}")


def write_csv(path: Path, results: List[BenchmarkResult], profile: ComponentProfile) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))

    profile_path = path.with_name(f"{path.stem}_component_profile.csv")
    with profile_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["component", "total_ns", "blocks", "mean_ns_per_block"])
        for name, value in (
            ("xts_core", profile.xts_core_ns),
            ("tweak_update_F", profile.tweak_update_ns),
            ("key_update_G", profile.key_update_ns),
        ):
            writer.writerow([name, value, profile.blocks, value / profile.blocks])

    print(f"\nCSV written to: {path}")
    print(f"Component CSV written to: {profile_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=7, help="number of independent timing batches")
    parser.add_argument("--iterations", type=int, default=100, help="calls per timing batch")
    parser.add_argument("--sectors", type=int, default=16, help="sectors in the volume benchmark")
    parser.add_argument("--blocks-per-sector", type=int, default=32, help="16-byte blocks per sector")
    parser.add_argument("--profile-repetitions", type=int, default=200, help="sector encryptions in component profile")
    parser.add_argument("--csv", type=Path, default=None, help="optional CSV output path")
    args = parser.parse_args()
    for field in ("repeats", "iterations", "sectors", "blocks_per_sector", "profile_repetitions"):
        if getattr(args, field) <= 0:
            parser.error(f"--{field.replace('_', '-')} must be positive")
    return args


def main() -> None:
    args = parse_args()
    master_key = b"benchmark-master-key".ljust(32, b"\x00")

    baseline = BaselineXTSFDE(master_key, args.blocks_per_sector)
    ratcheted_sector = RatchetedXTSFDE(master_key, args.blocks_per_sector, "sector")
    ratcheted_global = RatchetedXTSFDE(master_key, args.blocks_per_sector, "global")

    volume = make_volume(args.sectors, baseline.sector_size)
    sector = volume[:baseline.sector_size]
    block = sector[:BLOCK_SIZE]

    baseline_sector_ciphertext = baseline.encrypt_sector(0, sector)
    ratcheted_sector_ciphertext, _ = ratcheted_sector.encrypt_sector(0, sector)
    baseline_volume_ciphertext = baseline.encrypt_volume(volume)
    ratcheted_sector_volume_ciphertext = ratcheted_sector.encrypt_volume(volume)
    ratcheted_global_volume_ciphertext = ratcheted_global.encrypt_volume(volume)

    k0, k_f, k_g = derive_subkeys(master_key)
    initial_tweak = encode_lba(0)
    one_block_ciphertext = xts_encrypt_data_unit(k0, initial_tweak, block)

    results = [
        benchmark_callable(
            "AES-XTS encrypt 16-byte data unit",
            lambda: xts_encrypt_data_unit(k0, initial_tweak, block),
            iterations=args.iterations,
            repeats=args.repeats,
            bytes_per_call=BLOCK_SIZE,
        ),
        benchmark_callable(
            "F: AES tweak update",
            lambda: ratchet_tweak(k_f, one_block_ciphertext),
            iterations=args.iterations,
            repeats=args.repeats,
        ),
        benchmark_callable(
            "G: 256-bit XTS-key update",
            lambda: ratchet_xts_key(k_g, k0, one_block_ciphertext),
            iterations=args.iterations,
            repeats=args.repeats,
        ),
        benchmark_callable(
            "baseline sector encrypt",
            lambda: baseline.encrypt_sector(0, sector),
            iterations=args.iterations,
            repeats=args.repeats,
            bytes_per_call=len(sector),
        ),
        benchmark_callable(
            "ratcheted sector encrypt",
            lambda: ratcheted_sector.encrypt_sector(0, sector),
            iterations=args.iterations,
            repeats=args.repeats,
            bytes_per_call=len(sector),
        ),
        benchmark_callable(
            "baseline sector decrypt",
            lambda: baseline.decrypt_sector(0, baseline_sector_ciphertext),
            iterations=args.iterations,
            repeats=args.repeats,
            bytes_per_call=len(sector),
        ),
        benchmark_callable(
            "ratcheted sector decrypt",
            lambda: ratcheted_sector.decrypt_sector(0, ratcheted_sector_ciphertext),
            iterations=args.iterations,
            repeats=args.repeats,
            bytes_per_call=len(sector),
        ),
        benchmark_callable(
            "baseline volume encrypt",
            lambda: baseline.encrypt_volume(volume),
            iterations=max(1, args.iterations // 10),
            repeats=args.repeats,
            bytes_per_call=len(volume),
        ),
        benchmark_callable(
            "ratcheted-sector volume encrypt",
            lambda: ratcheted_sector.encrypt_volume(volume),
            iterations=max(1, args.iterations // 10),
            repeats=args.repeats,
            bytes_per_call=len(volume),
        ),
        benchmark_callable(
            "ratcheted-global volume encrypt",
            lambda: ratcheted_global.encrypt_volume(volume),
            iterations=max(1, args.iterations // 10),
            repeats=args.repeats,
            bytes_per_call=len(volume),
        ),
        benchmark_callable(
            "baseline volume decrypt",
            lambda: baseline.decrypt_volume(baseline_volume_ciphertext),
            iterations=max(1, args.iterations // 10),
            repeats=args.repeats,
            bytes_per_call=len(volume),
        ),
        benchmark_callable(
            "ratcheted-sector volume decrypt",
            lambda: ratcheted_sector.decrypt_volume(ratcheted_sector_volume_ciphertext),
            iterations=max(1, args.iterations // 10),
            repeats=args.repeats,
            bytes_per_call=len(volume),
        ),
        benchmark_callable(
            "ratcheted-global volume decrypt",
            lambda: ratcheted_global.decrypt_volume(ratcheted_global_volume_ciphertext),
            iterations=max(1, args.iterations // 10),
            repeats=args.repeats,
            bytes_per_call=len(volume),
        ),
    ]

    profile = profile_ratcheted_sector_encrypt(
        ratcheted_sector,
        lba=0,
        plaintext_sector=sector,
        repetitions=args.profile_repetitions,
    )

    print(f"Configuration: repeats={args.repeats}, iterations={args.iterations}, "
          f"sectors={args.sectors}, blocks/sector={args.blocks_per_sector}, "
          f"sector_size={baseline.sector_size} bytes")
    print_results(results)
    print_relative_ratios(results)
    print_component_profile(profile)

    if args.csv is not None:
        write_csv(args.csv, results, profile)


if __name__ == "__main__":
    main()
