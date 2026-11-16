"""Recording OCR crops with their readings, so accuracy can be measured on real captures."""

import json
import os

import cv2
import numpy as np

from coc_bot.vision.digits import DigitReading, Glyph
from coc_bot.vision.ocr_corpus import OcrCorpus

CROP = np.full((20, 60, 3), 90, np.uint8)
OK = DigitReading(1234, "ok", (Glyph(1, 0, 0, 5, 9, 0.97, 0.5),))
FAILED = DigitReading(None, "bad_grouping")


def index_rows(directory):
    with open(os.path.join(directory, "index.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def test_a_failed_reading_is_saved_with_its_reason(tmp_path):
    corpus = OcrCorpus(str(tmp_path))

    path = corpus.record(CROP, "attack_screen", "gold", FAILED, legacy_value=123)

    assert os.path.basename(path).endswith("_gold_bad_grouping.png")
    assert cv2.imread(path).shape == CROP.shape
    (row,) = index_rows(tmp_path)
    assert row["context"] == "attack_screen" and row["label"] == "gold"
    assert row["value"] is None and row["reason"] == "bad_grouping" and row["legacy"] == 123
    assert row["file"] == os.path.relpath(path, tmp_path).replace(os.sep, "/")


def test_agreeing_readings_are_only_sampled(tmp_path):
    corpus = OcrCorpus(str(tmp_path), keep_every=5)

    saved = [corpus.record(CROP, "base_screen", "gold", OK, legacy_value=1234) for _ in range(11)]

    assert [p is not None for p in saved] == [True] + [False] * 4 + [True] + [False] * 4 + [True]
    assert index_rows(tmp_path)[0]["value"] == 1234
    assert index_rows(tmp_path)[0]["confidence"] == 0.97


def test_empty_regions_are_sampled_like_successes(tmp_path):
    corpus = OcrCorpus(str(tmp_path), keep_every=5)
    empty = DigitReading(None, "no_digits")

    saved = [corpus.record(CROP, "attack_screen", "gold", empty, legacy_value=None) for _ in range(5)]

    assert sum(p is not None for p in saved) == 1


def test_a_disagreement_with_the_legacy_reader_is_always_saved(tmp_path):
    corpus = OcrCorpus(str(tmp_path), keep_every=1000)

    corpus.record(CROP, "loot_screen", "elixir", OK, legacy_value=1234)
    path = corpus.record(CROP, "loot_screen", "elixir", OK, legacy_value=123)

    assert path is not None
    assert os.path.basename(path).endswith("_elixir_1234.png")


def test_recording_stops_at_the_file_limit_counting_earlier_runs(tmp_path):
    first_run = OcrCorpus(str(tmp_path), max_files=3)
    for _ in range(2):
        first_run.record(CROP, "attack_screen", "gold", FAILED, legacy_value=None)

    second_run = OcrCorpus(str(tmp_path), max_files=3)
    saved = [second_run.record(CROP, "attack_screen", "gold", FAILED, legacy_value=None) for _ in range(3)]

    assert [p is not None for p in saved] == [True, False, False]
    assert len(index_rows(tmp_path)) == 3
