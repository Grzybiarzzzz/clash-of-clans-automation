"""Replaying saved OCR crops: the accuracy of the digit reader as a number.

The tests at the bottom run over the labelled real crops in ``tests/data/ocr`` (see the
README there). With no crops in the folder they are reported as skipped.
"""

import glob
import json
import os

import cv2
import pytest

from coc_bot.vision import ocr_corpus
from tests import ocr_synth

DARK = ocr_synth.uniform((60, 60, 60))
LABELLED_ROOT = os.path.join(os.path.dirname(__file__), "data", "ocr")


@pytest.mark.parametrize(
    "name, expected",
    [
        ("1731600000000_00012_gold_612004.png", 612004),
        ("1731600000000_00013_dark_elixir_4210.png", 4210),
        ("1731600000000_00014_elixir_0.png", 0),
        ("1731600000000_00015_gold_no_digits.png", ocr_corpus.EMPTY),
        ("1731600000000_00016_dark_elixir_empty.png", ocr_corpus.EMPTY),
        ("1731600000000_00017_gold_bad_grouping.png", None),  # a failure reason is not a label
        ("1731600000000_00018_gold_clipped.png", None),
        ("612004.png", 612004),
    ],
)
def test_the_file_name_of_a_crop_carries_its_label(name, expected):
    assert ocr_corpus.label_from_name(name) == expected


@pytest.fixture
def labelled(tmp_path):
    """A folder of crops: one read correctly, one refused, one empty, one without a label."""
    folder = tmp_path / "attack_screen"
    folder.mkdir()
    cv2.imwrite(str(folder / "a_gold_612004.png"), ocr_synth.compose("attack_screen", 612_004, DARK))
    cv2.imwrite(str(folder / "b_gold_1234567.png"), ocr_synth.compose("attack_screen", 1_234_567, DARK, skip_index=2))
    cv2.imwrite(str(folder / "c_elixir_empty.png"), DARK(52, 240))
    cv2.imwrite(str(folder / "d_gold_unknown_glyph.png"), DARK(52, 240))
    return tmp_path


def test_replay_reads_every_labelled_crop_and_skips_unlabelled_ones(labelled):
    results = ocr_corpus.replay(str(labelled))

    assert [(os.path.basename(r.path), r.context, r.expected, r.value) for r in results] == [
        ("a_gold_612004.png", "attack_screen", 612004, 612004),
        ("b_gold_1234567.png", "attack_screen", 1234567, None),
        ("c_elixir_empty.png", "attack_screen", ocr_corpus.EMPTY, None),
    ]
    assert [r.outcome for r in results] == ["correct", "refused", "correct"]


def test_a_wrong_value_is_told_apart_from_a_refusal(labelled):
    os.rename(labelled / "attack_screen" / "a_gold_612004.png", labelled / "attack_screen" / "a_gold_812004.png")

    outcomes = {os.path.basename(r.path): r.outcome for r in ocr_corpus.replay(str(labelled))}

    assert outcomes["a_gold_812004.png"] == "wrong"  # the dangerous kind: a number the bot would act on
    assert outcomes["b_gold_1234567.png"] == "refused"  # the safe kind: the bot knows it does not know


def test_the_summary_counts_outcomes_per_screen(labelled):
    summary = ocr_corpus.summarize(ocr_corpus.replay(str(labelled)))

    assert summary == {"attack_screen": {"crops": 3, "correct": 2, "refused": 1, "wrong": 0, "legacy_correct": 2}}


def test_the_recorded_index_gives_failure_rates_without_any_labelling(tmp_path):
    rows = [
        {"context": "attack_screen", "value": 500000, "reason": "ok", "legacy": 500000},
        {"context": "attack_screen", "value": 612004, "reason": "ok", "legacy": 61204},
        {"context": "attack_screen", "value": None, "reason": "bad_grouping", "legacy": 1234},
        {"context": "loot_screen", "value": None, "reason": "no_digits", "legacy": None},
    ]
    with open(tmp_path / "index.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(row) + "\n" for row in rows)

    assert ocr_corpus.summarize_index(str(tmp_path)) == {
        "attack_screen": {"saved": 3, "read": 2, "empty": 0, "failed": {"bad_grouping": 1}, "legacy_disagrees": 1},
        "loot_screen": {"saved": 1, "read": 0, "empty": 1, "failed": {}, "legacy_disagrees": 0},
    }


# --- real crops ------------------------------------------------------------------------------

REAL_CROPS = sorted(
    path
    for path in glob.glob(os.path.join(LABELLED_ROOT, "*", "*.png"))
    if ocr_corpus.label_from_name(path) is not None
)


@pytest.mark.parametrize("path", REAL_CROPS, ids=[os.path.relpath(p, LABELLED_ROOT) for p in REAL_CROPS])
def test_a_labelled_real_crop_is_read_as_labelled(path):
    result = ocr_corpus.replay_crop(path)

    assert result.outcome == "correct", f"expected {result.expected}, read {result.value} ({result.reason})"
