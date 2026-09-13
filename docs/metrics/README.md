# Attack data and reproducible statistics

These are the complete attack records behind the [performance report](../performance.md): **12,093 SBarb attacks** and **3,981 Builder Base Gold attacks**. I recorded them while developing and running the bot.

- [SBarb records](sbarb_time.csv)
- [Builder Base Gold records](bb_gold_time.csv)

I standardized the evolving CSV schemas, sorted records by their original timestamps, and replaced timestamps with calendar dates. `attack_number` preserves that chronological order, including within each day. All other recorded values are retained, including failures and slow attacks. Empty cells represent missing or originally blank values; they are not zeroes or inferred results. Time of day is omitted for privacy.

## Fields

| Field | Meaning |
|---|---|
| `attack_number` | Consecutive chronological index within this dataset, starting at 1. |
| `date` | Recorded calendar date (`YYYY-MM-DD`); no timezone conversion. |
| `loop_number` | Original loop counter, which can reset between runs. |
| `duration_seconds` | Duration recorded by the bot, in seconds. For SBarb, this covers the attack routine and excludes base search. |
| `spell_target` | SBarb target description recorded when the code marks spell completion; not verified building destruction. |
| `outcome` | SBarb's recorded `Success`, `Failed (timeout)`, or `Failed (early end)`. Earlier records lack this field. `Success` means the bot detected the configured destruction target. |
| `stars` | Recorded Builder Base star count; not the intended target. |
| `troop_mode` | Recorded Builder Base strategy; absent in the earliest records. |

The logs come from the bot itself. They do not independently validate its detections, and they do not record opponent strength, settings, or code revisions. See the [measurement definitions and limitations](../performance.md#what-the-logs-measure).

## Reproduce the results

Only Python and Matplotlib are needed; the bot and its Windows dependencies are not required. From the repository root:

```sh
python -m pip install matplotlib
python docs/metrics/reproduce.py --output-dir /path/to/results
```

Choose a writable output directory. The script reads the two CSVs alongside it and writes `summary.json`, `monthly-summary.csv`, `builder-base-comparison.csv`, and `sbarb-duration.png` to that directory. It also prints the summary.

The script uses all records, compares the first and last 1,000 SBarb attacks, and plots rolling windows of 500 attacks every 25 records plus the final record. It calculates target attainment only among records with an outcome. No outlier trimming or missing-outcome imputation is applied. Plot rendering may differ slightly between Matplotlib versions.
