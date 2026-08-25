"""Tests for parser module."""

from copy2mihon.parser import (
    clean_path,
    extract_path_word,
    extract_token,
    normalize_path_word,
    repair_mojibake,
    stable_fallback_key,
)


def test_extract_token():
    assert extract_token("Token abc123xyz") == "abc123xyz"
    assert extract_token("bearer token_val") == "token_val"
    assert extract_token('"my_token"') == "my_token"
    assert extract_token("'my_token'") == "my_token"
    assert extract_token("raw_token") == "raw_token"


def test_clean_path():
    assert clean_path('"D:/test/path.txt"') == "D:/test/path.txt"
    assert clean_path("  'C:/path'  ") == "C:/path"
    assert clean_path("normal_path") == "normal_path"


def test_normalize_path_word():
    assert normalize_path_word("onepiece") == "onepiece"
    assert normalize_path_word("/comic/onepiece/") == "onepiece"
    assert normalize_path_word("https://www.mangacopy.com/comic/naruto") == "naruto"
    assert normalize_path_word("BLEACH/") == "bleach"
    assert normalize_path_word("") == ""
    assert normalize_path_word(None) == ""


def test_extract_path_word():
    item1 = {"comic": {"path_word": "naruto"}}
    assert extract_path_word(item1) == "naruto"

    item2 = {"comic": {"uuid": "comic-uuid-123"}}
    assert extract_path_word(item2) == "comic-uuid-123"

    item3 = {"comic": {"id": 555}}
    assert extract_path_word(item3) == "id_555"

    item4 = {"comic": {"name": "Only Name Comic"}}
    assert extract_path_word(item4) == "name_only name comic"

    item5 = {"other_field": "val"}
    pw5 = extract_path_word(item5, fallback=True)
    assert pw5.startswith("nopathword_")

    pw5_no_fallback = extract_path_word(item5, fallback=False)
    assert pw5_no_fallback == ""


def test_stable_fallback_key_determinism():
    """Verify that stable_fallback_key produces identical, deterministic output across calls and between bookshelf and history formats."""
    bookshelf_item = {
        "comic": {
            "name": "海贼王特别篇",
            "id": 999,
        }
    }
    history_item = {
        "comic": {
            "name": "海贼王特别篇",
            "id": 999,
        },
        "last_chapter_id": "ch1",
    }

    key1 = stable_fallback_key(bookshelf_item)
    key2 = stable_fallback_key(history_item)

    assert key1.startswith("nopathword_")
    assert key1 == key2  # Same title/id MUST map to identical fallback key


def test_repair_mojibake():
    assert repair_mojibake("ç¬¬01å·»") == "第01巻"
    assert repair_mojibake("33è¯\x9då…¬å‘Š") == "33话公告"
    assert repair_mojibake("ç¬¬04è©±å‰\x8dç¯‡") == "第04話前篇"
    assert repair_mojibake("第01话") == "第01话"
