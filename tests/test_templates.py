"""Reference images are read from disk once and then served from memory."""

import cv2
import numpy as np
import pytest

from coc_bot.vision import templates


@pytest.fixture(autouse=True)
def empty_cache():
    templates.clear_cache()
    yield
    templates.clear_cache()


@pytest.fixture
def disk_reads(monkeypatch):
    reads = []
    real_imread = cv2.imread

    def counting_imread(path, *args):
        reads.append(path)
        return real_imread(path, *args)

    monkeypatch.setattr(templates.cv2, "imread", counting_imread)
    return reads


def test_a_template_is_read_from_disk_only_once(tmp_path, disk_reads):
    path = str(tmp_path / "button.png")
    cv2.imwrite(path, np.full((4, 6, 3), 200, np.uint8))

    first = templates.load_template(path)
    second = templates.load_template(path)

    assert first.shape == (4, 6, 3)
    assert second is first
    assert disk_reads == [path]


def test_a_missing_template_is_none_and_is_looked_up_again_later(tmp_path, disk_reads):
    path = str(tmp_path / "added_later.png")
    assert templates.load_template(path) is None

    cv2.imwrite(path, np.zeros((3, 3, 3), np.uint8))

    assert templates.load_template(path) is not None
    assert disk_reads == [path, path]
