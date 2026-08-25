"""Tests for parser module."""

from copy2mihon.parser import clean_path, extract_token, repair_mojibake


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


def test_repair_mojibake():
    assert repair_mojibake("ç¬¬01å·»") == "第01巻"
    assert repair_mojibake("33è¯\x9då…¬å‘Š") == "33话公告"
    assert repair_mojibake("ç¬¬04è©±å‰\x8dç¯‡") == "第04話前篇"
    assert repair_mojibake("第01话") == "第01话"
