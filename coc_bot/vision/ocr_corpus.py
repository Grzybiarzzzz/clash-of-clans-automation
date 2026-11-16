"""A growing set of real OCR crops with what the bot read from them.

Each saved crop gets a row in ``index.jsonl`` with the reading, its confidence, the
failure reason and the legacy reader's answer. Review the crops, move the ones whose
file name carries the right value into ``tests/data/ocr/<context>/`` (fixing the value
where the bot was wrong), and ``tools/ocr/replay_corpus.py`` plus the replay test measure
accuracy on them with ``replay``.

To keep the folder useful and small, every failed reading and every disagreement with
the legacy reader is saved; agreeing readings and empty regions are only sampled.
"""

import json
import os
import time
from dataclasses import dataclass
from typing import Optional, Union

import cv2

from coc_bot.vision import digits

EMPTY = "empty"  # label of a crop that shows no number


class OcrCorpus:
    def __init__(self, directory, max_files=5000, keep_every=20):
        self.directory = directory
        self.max_files = max_files
        self.keep_every = keep_every
        self._saved = None  # counted on first use
        self._seen = {}  # (context, label) -> number of routine readings so far

    def _count_saved(self):
        count = 0
        for _, _, files in os.walk(self.directory):
            count += sum(1 for name in files if name.endswith(".png"))
        return count

    def record(self, image_bgr, context, label, reading, legacy_value):
        """Save the crop when it is worth keeping. Returns the saved path, or None."""
        routine = reading.reason == "no_digits" or (reading.ok and legacy_value == reading.value)
        if routine:
            seen = self._seen.get((context, label), 0)
            self._seen[(context, label)] = seen + 1
            if seen % self.keep_every:
                return None
        if self._saved is None:
            self._saved = self._count_saved()
        if self._saved >= self.max_files:
            return None

        folder = os.path.join(self.directory, context)
        os.makedirs(folder, exist_ok=True)
        outcome = str(reading.value) if reading.ok else reading.reason
        name = f"{int(time.time() * 1000)}_{self._saved:05d}_{label}_{outcome}.png"
        path = os.path.join(folder, name)
        cv2.imwrite(path, image_bgr)
        row = {
            "file": f"{context}/{name}",
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "context": context,
            "label": label,
            "value": reading.value,
            "reason": reading.reason,
            "confidence": round(reading.confidence, 3),
            "glyphs": [[g.digit, round(g.score, 3), round(g.runner_up, 3)] for g in reading.glyphs],
            "legacy": legacy_value,
        }
        with open(os.path.join(self.directory, "index.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        self._saved += 1
        return path


def label_from_name(path) -> Union[int, str, None]:
    """What a crop should read as, taken from the end of its file name.

    ``..._612004.png`` is 612004; ``..._empty.png`` and ``..._no_digits.png`` are EMPTY.
    Anything else (a crop still named after its failure reason) has no label: None.
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    if stem.endswith(("_empty", "_no_digits")):
        return EMPTY
    last = stem.rsplit("_", 1)[-1]
    return int(last) if last.isdigit() else None


@dataclass(frozen=True)
class ReplayResult:
    path: str
    context: str
    expected: Union[int, str]
    value: Optional[int]
    reason: str
    legacy: Optional[int]

    @property
    def outcome(self) -> str:
        """'correct', 'refused' (no value: the bot knows it failed) or 'wrong' (a value it would act on)."""
        if self.expected == EMPTY:
            if self.value is None:
                return "correct" if self.reason == "no_digits" else "refused"
            return "wrong"
        if self.value is None:
            return "refused"
        return "correct" if self.value == self.expected else "wrong"

    @property
    def legacy_correct(self) -> bool:
        return self.legacy is None if self.expected == EMPTY else self.legacy == self.expected


def replay_crop(path, context=None) -> ReplayResult:
    """Read one labelled crop with both readers. The context defaults to the name of its folder."""
    context = context or os.path.basename(os.path.dirname(path))
    image = cv2.imread(path)
    reading = digits.read_number(image, context)
    try:
        legacy = digits.legacy_read(image, context)
    except Exception:
        legacy = None
    return ReplayResult(path, context, label_from_name(path), reading.value, reading.reason, legacy)


def replay(directory):
    """Read every labelled crop under ``directory/<context>/``; crops without a label are left out."""
    results = []
    for context in sorted(os.listdir(directory)):
        folder = os.path.join(directory, context)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if name.lower().endswith(".png") and label_from_name(path) is not None:
                results.append(replay_crop(path, context))
    return results


def summarize(results):
    """Counts per context: {'crops', 'correct', 'refused', 'wrong', 'legacy_correct'}."""
    summary = {}
    for result in results:
        row = summary.setdefault(
            result.context, {"crops": 0, "correct": 0, "refused": 0, "wrong": 0, "legacy_correct": 0}
        )
        row["crops"] += 1
        row[result.outcome] += 1
        row["legacy_correct"] += result.legacy_correct
    return summary


def summarize_index(directory):
    """Counts per context from the ``index.jsonl`` a bot run recorded; needs no labelling.

    Saved crops are biased towards trouble (every failure is kept, successes are sampled),
    so the numbers show which failures occur, not how often a read fails overall.
    """
    summary = {}
    with open(os.path.join(directory, "index.jsonl"), encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            row = summary.setdefault(
                entry["context"], {"saved": 0, "read": 0, "empty": 0, "failed": {}, "legacy_disagrees": 0}
            )
            row["saved"] += 1
            if entry["value"] is not None:
                row["read"] += 1
                row["legacy_disagrees"] += entry.get("legacy") != entry["value"]
            elif entry["reason"] == "no_digits":
                row["empty"] += 1
            else:
                row["failed"][entry["reason"]] = row["failed"].get(entry["reason"], 0) + 1
    return summary
