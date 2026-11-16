# Labelled OCR crops

Real crops of resource numbers, used by `tests/test_ocr_replay.py` to measure the digit reader.

Layout: `tests/data/ocr/<context>/<anything>_<value>.png`

- `<context>` is the screen the crop comes from, which selects the digit templates:
  `attack_screen`, `base_screen`, `base_dark_elixir`, `bb_base_screen` or `loot_screen`.
- `<value>` is the number a person reads in the crop, e.g. `..._gold_612004.png`.
  Use `_empty` (or the recorded `_no_digits`) for a region that shows no number.

Where the crops come from: while the bot runs it saves crops to `data/ocr_corpus/<context>/`
with the value it read in the file name (every failed reading, every disagreement with the old
reader, and a sample of the rest). To add test cases:

1. Look through `data/ocr_corpus/<context>/`.
2. Copy interesting crops here, keeping the context folder.
3. Fix the value at the end of the file name where the bot was wrong. Crops that failed are named
   after the failure (`..._bad_grouping.png`); replace that with the real value.

Then run `python tools/ocr/replay_corpus.py` for an accuracy table, or `pytest tests/test_ocr_replay.py`.
