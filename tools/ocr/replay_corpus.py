"""Measure the digit reader on saved crops.

    python tools/ocr/replay_corpus.py                      # labelled crops in tests/data/ocr
    python tools/ocr/replay_corpus.py path/to/labelled     # another labelled folder
    python tools/ocr/replay_corpus.py --recorded           # what a bot run recorded in data/ocr_corpus

Labelled crops carry the right value at the end of their file name (see tests/data/ocr/README.md).
For each screen the table shows how many were read correctly, how many the reader refused
(it returned no value) and how many it got wrong, next to the old reader's score.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # digit templates are relative paths

import config  # noqa: E402
from coc_bot.vision import ocr_corpus  # noqa: E402


def show_labelled(directory):
    results = ocr_corpus.replay(directory)
    if not results:
        print(f"No labelled crops under {directory}. See tests/data/ocr/README.md for how to add some.")
        return 0
    print(f"{'screen':<18}{'crops':>7}{'correct':>9}{'refused':>9}{'wrong':>7}{'old reader':>12}")
    for context, row in ocr_corpus.summarize(results).items():
        print(
            f"{context:<18}{row['crops']:>7}{row['correct']:>9}{row['refused']:>9}{row['wrong']:>7}"
            f"{row['legacy_correct']:>12}"
        )
    failures = [r for r in results if r.outcome != "correct"]
    if failures:
        print("\nNot read correctly:")
        for r in failures:
            read = r.value if r.value is not None else f"refused ({r.reason})"
            print(f"  {r.path}: expected {r.expected}, read {read}, old reader {r.legacy}")
    return 1 if any(r.outcome == "wrong" for r in results) else 0


def show_recorded(directory):
    if not os.path.exists(os.path.join(directory, "index.jsonl")):
        print(f"Nothing recorded under {directory} yet. Run the bot with OCR_CORPUS_ENABLED = True.")
        return 0
    print("Saved crops (every failure is kept, successes are only sampled):\n")
    print(f"{'screen':<18}{'saved':>7}{'read':>7}{'empty':>7}{'old reader differs':>20}  failures")
    for context, row in ocr_corpus.summarize_index(directory).items():
        failed = ", ".join(f"{reason}: {count}" for reason, count in sorted(row["failed"].items())) or "-"
        print(
            f"{context:<18}{row['saved']:>7}{row['read']:>7}{row['empty']:>7}{row['legacy_disagrees']:>20}  {failed}"
        )
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory", nargs="?", help="folder of labelled crops (default: tests/data/ocr)")
    parser.add_argument("--recorded", action="store_true", help="summarise the crops a bot run recorded")
    args = parser.parse_args()
    if args.recorded:
        return show_recorded(args.directory or getattr(config, "OCR_CORPUS_DIR", os.path.join("data", "ocr_corpus")))
    return show_labelled(args.directory or os.path.join("tests", "data", "ocr"))


if __name__ == "__main__":
    sys.exit(main())
