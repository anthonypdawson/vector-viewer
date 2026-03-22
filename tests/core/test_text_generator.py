"""Tests for text_generator.py sample data generation."""

import textwrap

import pytest

from vector_inspector.core.sample_data.text_generator import (
    SampleDataType,
    _generate_json_samples,
    _generate_markdown_samples,
    _generate_text_samples,
    _parse_srt,
    generate_sample_data,
    generate_subtitles_from_file,
)

# ---------------------------------------------------------------------------
# generate_sample_data — basic dispatch
# ---------------------------------------------------------------------------


def test_generate_text_samples_returns_correct_count():
    results = generate_sample_data(5, SampleDataType.TEXT, randomize=False)
    assert len(results) == 5


def test_generate_markdown_samples_returns_correct_count():
    results = generate_sample_data(3, SampleDataType.MARKDOWN, randomize=False)
    assert len(results) == 3


def test_generate_json_samples_returns_correct_count():
    results = generate_sample_data(4, SampleDataType.JSON, randomize=False)
    assert len(results) == 4


def test_generate_sample_data_accepts_string_type():
    """SampleDataType enum value should work."""
    results = generate_sample_data(2, SampleDataType.TEXT, randomize=False)
    assert len(results) == 2


def test_generate_sample_data_subtitles_raises():
    with pytest.raises(ValueError, match="generate_subtitles_from_file"):
        generate_sample_data(1, SampleDataType.SUBTITLES)


def test_generate_sample_data_unknown_type_raises():
    """An invalid string data_type raises ValueError via the SampleDataType enum lookup."""
    with pytest.raises(ValueError):
        generate_sample_data(1, data_type="not_a_valid_type")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TEXT format
# ---------------------------------------------------------------------------


def test_text_sample_structure():
    results = _generate_text_samples(1, randomize=False)
    item = results[0]
    assert "text" in item
    assert "metadata" in item
    assert item["metadata"]["type"] == "text"
    assert item["metadata"]["source"] == "sample"
    assert isinstance(item["metadata"]["index"], int)
    assert isinstance(item["metadata"]["topic"], str)


def test_text_sample_deterministic():
    r1 = _generate_text_samples(3, randomize=False)
    r2 = _generate_text_samples(3, randomize=False)
    assert [i["text"] for i in r1] == [i["text"] for i in r2]


def test_text_sample_randomized_varies():
    """Randomized samples for a large count should have some variety."""
    results = _generate_text_samples(30, randomize=True)
    texts = [r["text"] for r in results]
    assert len(set(texts)) > 1


def test_text_sample_second_sentence_branch_deterministic():
    """Deterministic mode: indices 0-2 (i%10 < 3) get second sentence."""
    results = _generate_text_samples(10, randomize=False)
    # indices 0,1,2 should have two sentences (ends with second "It ...")
    for i in range(3):
        assert " It " in results[i]["text"], f"Expected second sentence in index {i}"
    # index 5 should not
    assert " It " not in results[5]["text"]


# ---------------------------------------------------------------------------
# MARKDOWN format
# ---------------------------------------------------------------------------


def test_markdown_sample_structure():
    results = _generate_markdown_samples(1, randomize=False)
    item = results[0]
    assert item["text"].startswith("##")
    assert item["metadata"]["type"] == "markdown"
    assert "section" in item["metadata"]


def test_markdown_sample_list_branch_deterministic():
    """indices 0,1,2 in deterministic mode get a list appended."""
    results = _generate_markdown_samples(10, randomize=False)
    for i in range(3):
        assert "- Key point one" in results[i]["text"]
    assert "- Key point one" not in results[5]["text"]


# ---------------------------------------------------------------------------
# JSON format
# ---------------------------------------------------------------------------


def test_json_sample_structure():
    results = _generate_json_samples(1, randomize=False)
    item = results[0]
    assert "Title:" in item["text"]
    assert "Description:" in item["text"]
    assert "Topic:" in item["text"]
    assert item["metadata"]["type"] == "json"


def test_json_sample_tags_branch_deterministic():
    """Even indices in deterministic mode get tags."""
    results = _generate_json_samples(4, randomize=False)
    # index 0 (even) should have tags
    assert "Tags:" in results[0]["text"]
    # index 1 (odd) should not
    assert "Tags:" not in results[1]["text"]


# ---------------------------------------------------------------------------
# SUBTITLES — generate_subtitles_from_file
# ---------------------------------------------------------------------------


def _write_srt(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(content))


def test_subtitles_from_valid_srt(tmp_path):
    srt_path = str(tmp_path / "test.srt")
    _write_srt(
        srt_path,
        """\
        1
        00:00:01,000 --> 00:00:02,000
        Hello world

        2
        00:00:03,000 --> 00:00:04,000
        Second line
        """,
    )
    results = generate_subtitles_from_file(srt_path, count=0, randomize=False)
    assert len(results) == 2
    assert results[0]["text"] == "Hello world"
    assert results[1]["text"] == "Second line"
    assert results[0]["metadata"]["type"] == "subtitles"
    assert results[0]["metadata"]["start"] == "00:00:01,000"


def test_subtitles_count_limits_results(tmp_path):
    srt_path = str(tmp_path / "test.srt")
    lines = []
    for i in range(1, 6):
        lines.append(f"{i}\n00:00:0{i},000 --> 00:00:0{i + 1},000\nCue {i}\n")
    _write_srt(srt_path, "\n".join(lines))
    results = generate_subtitles_from_file(srt_path, count=3, randomize=False)
    assert len(results) == 3


def test_subtitles_missing_file_returns_empty():
    results = generate_subtitles_from_file("/does/not/exist.srt", count=5)
    assert results == []


def test_subtitles_randomize_returns_count(tmp_path):
    srt_path = str(tmp_path / "test.srt")
    lines = []
    for i in range(1, 11):
        lines.append(f"{i}\n00:00:0{i},000 --> 00:00:0{i},999\nCue {i}\n")
    _write_srt(srt_path, "\n".join(lines))
    results = generate_subtitles_from_file(srt_path, count=4, randomize=True)
    assert len(results) == 4


# ---------------------------------------------------------------------------
# _parse_srt edge cases
# ---------------------------------------------------------------------------


def test_parse_srt_malformed_block_no_time_line(tmp_path):
    """Block without --> is treated as plain text."""
    srt_path = str(tmp_path / "bad.srt")
    _write_srt(srt_path, "1\nThis line has no timecode\n")
    cues = _parse_srt(srt_path)
    assert len(cues) >= 1
    # text should contain something
    assert cues[0]["text"] != ""


def test_parse_srt_empty_file(tmp_path):
    srt_path = str(tmp_path / "empty.srt")
    _write_srt(srt_path, "")
    cues = _parse_srt(srt_path)
    assert cues == []


def test_parse_srt_windows_line_endings(tmp_path):
    srt_path = str(tmp_path / "win.srt")
    with open(srt_path, "w", encoding="utf-8", newline="") as f:
        f.write("1\r\n00:00:00,000 --> 00:00:01,000\r\nWindows cue\r\n\r\n")
    cues = _parse_srt(srt_path)
    assert any("Windows cue" in c["text"] for c in cues)
