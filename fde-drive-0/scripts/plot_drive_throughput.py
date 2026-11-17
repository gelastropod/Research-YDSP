import argparse
import os
import re

import matplotlib.pyplot as plt
import pandas as pd

"""
Usage:
    python plot_drive_throughput.py [csv_path ...] [output_png] [--window N] [--device-bytes B] [--title T]

Multiple CSVs (e.g. one per scheme from run_drive_schemes.sh) are overlaid:
    python plot_drive_throughput.py results/drive_encrypt_*.csv -o figures/schemes.png
"""

COLUMNS = ["elapsed_s", "sector", "bytes_done", "instant_MBps", "cumulative_MBps",
           "seed_ns", "data_ns", "evolution_ns", "io_ns"]


def load(csv_path):
    df = pd.read_csv(csv_path)
    if len(df.columns) != len(COLUMNS):
        raise ValueError(f"expected {len(COLUMNS)} columns, got {list(df.columns)}")
    df.columns = COLUMNS
    return df


def label_for(csv_path):
    stem = os.path.splitext(os.path.basename(csv_path))[0]
    m = re.fullmatch(r"drive_(encrypt|decrypt)_(.+)", stem)
    if m:
        return f"{m.group(2)} ({m.group(1)})"
    return stem


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv", nargs="+", default=["results/drive_throughput.csv"],
                   help="one or more throughput CSVs (last argument is used as the output "
                        "path if it ends in .png, otherwise use -o)")
    p.add_argument("-o", "--output", default=None)
    p.add_argument("--window", type=int, default=51, help="rolling median window (samples)")
    p.add_argument("--device-bytes", type=float, default=None,
                   help="device size for the progress axis (default: final bytes_done)")
    p.add_argument("--title", default="Ratcheted AES-XTS FDE throughput vs. progress")
    p.add_argument("--dpi", type=int, default=150)
    args = p.parse_args()

    csv_paths = list(args.csv)
    output = args.output
    if output is None:
        if len(csv_paths) > 1 and csv_paths[-1].endswith(".png"):
            output = csv_paths.pop()
        else:
            output = "figures/throughput_plot.png"

    frames = [(path, load(path), label_for(path)) for path in csv_paths]
    multi = len(frames) > 1

    device_bytes = args.device_bytes or max(df["bytes_done"].iloc[-1] for _, df, _ in frames)
    gb_per_pct = device_bytes / 1e9 / 100

    roll = lambda s: s.rolling(args.window, center=True, min_periods=1).median()
    cmap = plt.get_cmap("tab10")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10.4, 7.3), sharex=True,
                                   gridspec_kw={"height_ratios": [2.35, 1]})

    for idx, (path, df, label) in enumerate(frames):
        progress = df["bytes_done"] / device_bytes * 100

        # Per-sample disk I/O share: io_ns and elapsed_s are cumulative, so use deltas.
        d_io = df["io_ns"].diff().fillna(df["io_ns"].iloc[0])
        d_t = df["elapsed_s"].diff().fillna(df["elapsed_s"].iloc[0]) * 1e9
        io_share = (d_io / d_t * 100).clip(0, 100)

        if not multi:
            ax1.plot(progress, df["instant_MBps"], color="#9ecae1", lw=0.7, label="Instantaneous")
            ax1.plot(progress, roll(df["instant_MBps"]), color="#08519c", lw=2,
                     label=f"Rolling median ({args.window} samples)")
            ax1.plot(progress, df["cumulative_MBps"], color="#e6550d", lw=2, ls="--",
                     label="Cumulative average")
            ax2.plot(progress, io_share, color="#a1d99b", lw=0.7)
            ax2.plot(progress, roll(io_share), color="#238b45", lw=2)
        else:
            color = cmap(idx % 10)
            ax1.plot(progress, roll(df["instant_MBps"]), color=color, lw=2, label=label)
            ax1.plot(progress, df["cumulative_MBps"], color=color, lw=1.4, ls="--", alpha=0.7)
            ax2.plot(progress, roll(io_share), color=color, lw=2, label=label)

    ax1.set_ylabel("Throughput (MB/s)")
    ax1.set_ylim(bottom=0)
    ax1.grid(alpha=0.3)
    ax1.legend(loc="lower left")
    ax1.set_title(args.title)
    top = ax1.secondary_xaxis("top", functions=(lambda x: x * gb_per_pct, lambda g: g / gb_per_pct))
    top.set_xlabel("Data processed (GB)")

    ax2.set_ylabel("Disk I/O share\nof wall time (%)")
    ax2.set_ylim(0, 100)
    ax2.set_xlabel("Progress (% of device)")
    ax2.grid(alpha=0.3)
    if multi:
        ax2.legend(loc="lower left", fontsize="small")

    fig.tight_layout()
    fig.savefig(output, dpi=args.dpi)
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
