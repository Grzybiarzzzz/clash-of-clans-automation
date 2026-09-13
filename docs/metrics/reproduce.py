"""Reproduce the attack statistics and chart from the accompanying CSVs."""

import argparse
import csv
import json
import math
import statistics as st
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


def load(path):
    with path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    for number, row in enumerate(rows, 1):
        if int(row["attack_number"]) != number:
            raise ValueError(f"{path.name}: attack numbers must be consecutive")
        date.fromisoformat(row["date"])
        row["duration"] = float(row["duration_seconds"])
        if not math.isfinite(row["duration"]) or row["duration"] <= 0:
            raise ValueError(f"{path.name}: invalid duration at attack {number}")
    if [r["date"] for r in rows] != sorted(r["date"] for r in rows):
        raise ValueError(f"{path.name}: dates must be chronological")
    return rows


def timing(rows):
    values = [r["duration"] for r in rows]
    return round(st.mean(values), 4), round(st.median(values), 4)


def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(header)
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Directory for regenerated CSV summaries, JSON, and chart")
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    datasets = {name: load(base / f"{name}.csv")
                for name in ("sbarb_time", "bb_gold_time")}
    s = datasets["sbarb_time"]
    bb = datasets["bb_gold_time"]
    if min(len(s), len(bb)) < 1000:
        raise ValueError("Each dataset needs at least 1,000 attacks")
    first = [r["duration"] for r in s[:1000]]
    last = [r["duration"] for r in s[-1000:]]
    mean_drop = 100 * (1 - st.mean(last) / st.mean(first))
    median_drop = 100 * (1 - st.median(last) / st.median(first))
    known = [r for r in s if r["outcome"]]
    outcomes = Counter(r["outcome"] for r in known)
    report = {
        "attacks": {name: len(rows) for name, rows in datasets.items()},
        "total_attacks": len(s) + len(bb),
        "labelled_sbarb_attacks": len(known),
        "unlabelled_sbarb_attacks": len(s) - len(known),
        "sbarb_outcomes": dict(outcomes),
        "sbarb_target_attainment_percent": 100 * outcomes["Success"] / len(known) if known else None,
        "first_1000_mean_seconds": st.mean(first),
        "last_1000_mean_seconds": st.mean(last),
        "mean_reduction_percent": mean_drop,
        "first_1000_median_seconds": st.median(first),
        "last_1000_median_seconds": st.median(last),
        "median_reduction_percent": median_drop,
        "first_500_mean_seconds": st.mean(r["duration"] for r in s[:500]),
        "last_500_mean_seconds": st.mean(r["duration"] for r in s[-500:]),
        "builder_base_troop_modes": dict(Counter(r["troop_mode"] or "Unrecorded" for r in bb)),
    }
    monthly = []
    for name, rows in datasets.items():
        groups = defaultdict(list)
        for row in rows:
            groups[row["date"][:7]].append(row)
        for month, group in groups.items():
            monthly.append([name, month, len(group), *timing(group)])

    comparison = []
    for window, group in (("First 1,000", bb[:1000]), ("Last 1,000", bb[-1000:])):
        for row in group:
            row["mode"] = row["troop_mode"] or "Unrecorded"
            row["stars"] = int(row["stars"])
        selectors = [("All", "All")]
        selectors += [("All", stars) for stars in sorted({r["stars"] for r in group})]
        selectors += sorted({(r["mode"], r["stars"]) for r in group})
        for mode, stars in selectors:
            selected = [r for r in group if (mode == "All" or r["mode"] == mode)
                        and (stars == "All" or r["stars"] == stars)]
            comparison.append([window, mode, stars, len(selected), *timing(selected)])

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "monthly-summary.csv",
              ["dataset", "month", "attacks", "mean_seconds", "median_seconds"], monthly)
    write_csv(args.output_dir / "builder-base-comparison.csv",
              ["window", "troop_mode", "recorded_stars", "attacks", "mean_seconds", "median_seconds"], comparison)
    (args.output_dir / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    plot(s, first, last, mean_drop, args.output_dir)
    print(json.dumps(report, indent=2))


def plot(s, first, last, mean_drop, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titleweight': 'bold'})
    fig, ax = plt.subplots(figsize=(11, 5.8))
    indices = list(range(500, len(s) + 1, 25))
    if indices[-1] != len(s):
        indices.append(len(s))
    means = [st.mean(r['duration'] for r in s[i-500:i]) for i in indices]
    medians = [st.median(r['duration'] for r in s[i-500:i]) for i in indices]
    ax.plot(indices, means, color='#176b87', lw=2.2, label='Mean of preceding 500 attacks')
    ax.plot(indices, medians, color='#b66a16', lw=1.8, label='Median of preceding 500 attacks')
    ax.set(xlabel='Chronological attack number', ylabel='Logged duration (seconds)',
           ylim=(0, 40), xlim=(0, len(s)))
    ax.grid(axis='y', alpha=.18)
    ax.legend(frameon=False, loc='upper right')
    fig.suptitle(f'SBarb attack duration across {len(s):,} logged attacks',
                 x=.08, ha='left', fontsize=17, fontweight='bold')
    fig.text(.08, .895, f'First 1,000 mean: {st.mean(first):.2f}s  →  Last 1,000: {st.mean(last):.2f}s  |  {mean_drop:.1f}% lower',
             color='#176b87', fontsize=12)
    start, end = (date.fromisoformat(s[i]['date']) for i in (0, -1))
    period = f'{start.day} {start:%b %Y}–{end.day} {end:%b %Y}'
    fig.text(.08, .025, period + ' · All records included; no outlier trimming.\nObserved timing trend across changing configurations, not a controlled benchmark.',
             fontsize=9, color='#555555')
    fig.subplots_adjust(left=.08, right=.98, bottom=.19, top=.82)
    fig.savefig(output / 'sbarb-duration.png', dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
