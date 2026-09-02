#!/usr/bin/env python3
"""Generate publication-ready PNG figures from the benchmark CSV files."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


LABELS = {
    "AES-ECB": "ECB",
    "AES-XTS-manual": "XTS manual",
    "AES-XTS-manual-sequential": "XTS manual",
    "AES-XTS-OpenSSL-full-sector": "XTS OpenSSL",
    "Ratchet-CTR-AES": "CTR AES",
    "Ratchet-CTR-BLAKE3": "CTR BLAKE3",
    "Ratchet-CTR-BLAKE2s-256": "CTR BLAKE2s",
    "Ratchet-CTR-SHA3-256": "CTR SHA3",
    "Ratchet-CTR-SHA-256": "CTR SHA-256",
    "Ratchet-CBC-AES": "CBC AES",
    "Ratchet-CBC-BLAKE3": "CBC BLAKE3",
    "Ratchet-CBC-BLAKE2s-256": "CBC BLAKE2s",
    "Ratchet-CBC-SHA3-256": "CBC SHA3",
    "Ratchet-CBC-SHA-256": "CBC SHA-256",
}

TRANSITIONS = ["AES", "BLAKE3", "BLAKE2s-256", "SHA3-256", "SHA-256"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def finish(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def label(name: str) -> str:
    return LABELS.get(name, name)


def plot_rq1(results: Path, figures: Path) -> None:
    rows = [
        row
        for row in read_csv(results / "component_breakdown.csv")
        if row["operation"] == "encrypt"
        and row["implementation"] != "AES-XTS-literal-indexed"
    ]
    names = [label(row["implementation"]) for row in rows]
    seed = np.array([float(row["seed_percent"]) for row in rows])
    data = np.array([float(row["data_percent"]) for row in rows])
    evolution = np.array([float(row["evolution_percent"]) for row in rows])
    y = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(10, 7.5))
    ax.barh(y, seed, label="Sector seed")
    ax.barh(y, data, left=seed, label="AES data path")
    ax.barh(y, evolution, left=seed + data, label="Tweak or ratchet update")
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of instrumented time (%)")
    ax.set_title("RQ1: encryption-time distribution for 4096-byte sectors")
    ax.legend(loc="lower right")
    ax.grid(axis="x", alpha=0.25)
    finish(fig, figures / "rq1_cost_breakdown.png")


def maximum_volume_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for sector in sorted({int(row["sector_bytes"]) for row in rows}):
        sector_rows = [row for row in rows if int(row["sector_bytes"]) == sector]
        maximum = max(int(row["volume_bytes"]) for row in sector_rows)
        selected.extend(
            row for row in sector_rows if int(row["volume_bytes"]) == maximum
        )
    return selected


def plot_rq2(results: Path, figures: Path) -> None:
    rows = maximum_volume_rows(
        [
            row
            for row in read_csv(results / "throughput.csv")
            if row["operation"] == "encrypt"
            and row["implementation"] != "AES-XTS-OpenSSL-full-sector"
        ]
    )
    for metric, axis_label, filename in [
        ("mean_mib_s", "Mean throughput (MiB/s)", "rq2_throughput.png"),
        ("mean_ns_per_byte", "Mean time (ns/byte)", "rq2_ns_per_byte.png"),
    ]:
        fig, axes = plt.subplots(1, 2, figsize=(15, 7), sharey=True)
        for ax, sector in zip(axes, [512, 4096]):
            subset = [row for row in rows if int(row["sector_bytes"]) == sector]
            names = [label(row["implementation"]) for row in subset]
            values = [float(row[metric]) for row in subset]
            y = np.arange(len(subset))
            ax.barh(y, values)
            ax.set_yticks(y, names)
            ax.invert_yaxis()
            ax.set_xlabel(axis_label)
            ax.set_title(f"{sector}-byte sectors")
            ax.grid(axis="x", alpha=0.25)
        fig.suptitle("RQ2: full-volume encryption performance", fontsize=14)
        finish(fig, figures / filename)


def transition_from_primitive(name: str) -> str:
    if name.startswith("AES-256"):
        return "AES"
    return name.split("(", 1)[0].replace("AES-256", "AES")


def plot_rq3(results: Path, figures: Path) -> None:
    primitive_rows = read_csv(results / "ratchet_primitives.csv")
    names = [transition_from_primitive(row["primitive"]) for row in primitive_rows]
    values = [float(row["ns_per_update"]) for row in primitive_rows]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    bars = ax.bar(names, values)
    ax.bar_label(bars, fmt="%.1f")
    ax.set_ylabel("Nanoseconds per state update")
    ax.set_title("RQ3: cost of one sequential ratchet transition")
    ax.grid(axis="y", alpha=0.25)
    finish(fig, figures / "rq3_update_cost.png")

    throughput = maximum_volume_rows(
        [
            row
            for row in read_csv(results / "throughput.csv")
            if row["operation"] == "encrypt" and row["sector_bytes"] == "4096"
        ]
    )
    lookup = {row["implementation"]: float(row["mean_mib_s"]) for row in throughput}
    ctr = [lookup[f"Ratchet-CTR-{name}"] for name in TRANSITIONS]
    cbc = [lookup[f"Ratchet-CBC-{name}"] for name in TRANSITIONS]
    x = np.arange(len(TRANSITIONS))
    width = 0.38
    fig, ax = plt.subplots(figsize=(10, 5.8))
    ax.bar(x - width / 2, ctr, width, label="CTR ratchet")
    ax.bar(x + width / 2, cbc, width, label="CBC ratchet")
    ax.set_xticks(x, [name.replace("-256", "") for name in TRANSITIONS])
    ax.set_ylabel("Mean encryption throughput (MiB/s)")
    ax.set_title("RQ3: end-to-end throughput by state transition")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    finish(fig, figures / "rq3_end_to_end.png")


def plot_random_panel(ax: plt.Axes, rows: list[dict[str, str]], family: str) -> None:
    baselines = {"AES-ECB", "AES-XTS-manual"}
    schemes = sorted(
        {row["scheme"] for row in rows if family in row["scheme"]} | baselines
    )
    for scheme in schemes:
        subset = sorted(
            (row for row in rows if row["scheme"] == scheme),
            key=lambda row: int(row["target_block"]),
        )
        if not subset:
            continue
        ax.plot(
            [int(row["target_block"]) for row in subset],
            [float(row["median_ns"]) for row in subset],
            marker="o",
            linewidth=1.8,
            label=label(scheme),
        )
    ax.set_xlabel("Target intra-sector block")
    ax.set_ylabel("Median recovery latency (ns)")
    ax.set_yscale("log")
    ax.set_title(f"{family} ratchets")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)


def plot_rq4(results: Path, figures: Path) -> None:
    random_rows = [
        row
        for row in read_csv(results / "random_access.csv")
        if row["cache_state"] == "warm"
    ]
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    plot_random_panel(axes[0], random_rows, "CTR")
    plot_random_panel(axes[1], random_rows, "CBC")
    fig.suptitle("RQ4: target-block recovery within a 4096-byte sector", fontsize=14)
    finish(fig, figures / "rq4_random_access.png")

    parallel_rows = read_csv(results / "parallel_scaling.csv")
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), sharex="col")
    for column, family in enumerate(["CTR", "CBC"]):
        baselines = {
            "AES-ECB",
            "AES-XTS-manual-sequential",
            "AES-XTS-OpenSSL-full-sector",
        }
        implementations = sorted(
            {
                row["implementation"]
                for row in parallel_rows
                if family in row["implementation"]
            }
            | baselines
        )
        max_thread = max(int(row["threads"]) for row in parallel_rows)
        axes[0, column].plot(
            range(1, max_thread + 1),
            range(1, max_thread + 1),
            linestyle="--",
            color="black",
            label="Ideal",
        )
        axes[1, column].axhline(1.0, linestyle="--", color="black", label="Ideal")
        for implementation in implementations:
            subset = sorted(
                (
                    row
                    for row in parallel_rows
                    if row["implementation"] == implementation
                ),
                key=lambda row: int(row["threads"]),
            )
            if not subset:
                continue
            threads = [int(row["threads"]) for row in subset]
            axes[0, column].plot(
                threads,
                [float(row["speedup"]) for row in subset],
                marker="o",
                label=label(implementation),
            )
            axes[1, column].plot(
                threads,
                [float(row["efficiency"]) for row in subset],
                marker="o",
                label=label(implementation),
            )
        axes[0, column].set_title(f"{family} family speedup")
        axes[0, column].set_ylabel("Speedup S(t)")
        axes[1, column].set_title(f"{family} family efficiency")
        axes[1, column].set_xlabel("Worker threads")
        axes[1, column].set_ylabel("Efficiency E(t)")
        for row in axes[:, column]:
            row.grid(alpha=0.25)
            row.legend(fontsize=7, ncol=2)
            row.set_xticks(range(1, max_thread + 1))
    fig.suptitle("RQ4: inter-sector parallel scaling", fontsize=15)
    finish(fig, figures / "rq4_parallel_scaling.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", nargs="?", default="results")
    parser.add_argument("figures", nargs="?", default="figures")
    args = parser.parse_args()
    results = Path(args.results)
    figures = Path(args.figures)
    figures.mkdir(parents=True, exist_ok=True)
    plot_rq1(results, figures)
    plot_rq2(results, figures)
    plot_rq3(results, figures)
    plot_rq4(results, figures)
    print(f"Generated figures in {figures}")


if __name__ == "__main__":
    main()
