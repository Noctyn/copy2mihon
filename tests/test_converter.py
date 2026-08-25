"""Tests for converter module."""

import pytest
from copy2mihon.converter import (
    convert_copymanga_all_to_backup,
    comic_dict_to_mihon_manga,
    create_chapter_and_history,
    normalize_manga_url,
    normalize_status,
    parse_category_names,
)
from copy2mihon.models import DEFAULT_COPYMANGA_SOURCE_ID


def test_parse_category_names():
    assert parse_category_names("拷贝漫画") == ["拷贝漫画"]
    assert parse_category_names("分类1, 分类2 , 分类3") == ["分类1", "分类2", "分类3"]
    assert parse_category_names("none") == []
    assert parse_category_names("") == []
    assert parse_category_names(None) == []


def test_normalize_manga_url():
    assert normalize_manga_url("onepiece") == "/comic/onepiece"
    assert normalize_manga_url("/comic/onepiece") == "/comic/onepiece"
    assert normalize_manga_url("https://www.mangacopy.com/comic/onepiece") == "/comic/onepiece"


def test_normalize_status():
    assert normalize_status(0) == 1
    assert normalize_status(1) == 2
    assert normalize_status("连载中") == 1
    assert normalize_status("已完结") == 2


def test_create_chapter_and_history():
    ch, hist = create_chapter_and_history(
        path_word="naruto",
        chapter_id="uuid-ch-1",
        chapter_name="第01话",
        read_time_ms=1700000000000,
    )
    assert ch is not None
    assert ch.url == "/comic/naruto/chapter/uuid-ch-1"
    assert ch.name == "第01话"
    assert ch.chapter_number == 1.0
    assert ch.read is True
    assert hist is not None
    assert hist.url == "/comic/naruto/chapter/uuid-ch-1"
    assert hist.last_read == 1700000000000


def test_comic_dict_to_mihon_manga_raw_comic():
    raw_item = {
        "comic": {
            "name": "海贼王",
            "path_word": "onepiece",
            "author": [{"name": "尾田荣一郎"}],
            "brief": "大海贼时代",
            "cover": "https://example.com/cover.jpg",
            "status": 0,
            "theme": [{"name": "热血"}, {"name": "冒险"}],
        }
    }
    manga = comic_dict_to_mihon_manga(raw_item, category_ids=[0])
    assert manga.title == "海贼王"
    assert manga.url == "/comic/onepiece"
    assert manga.author == "尾田荣一郎"
    assert "热血" in manga.genre
    assert manga.categories == [0]
    assert manga.source == DEFAULT_COPYMANGA_SOURCE_ID


def test_convert_copymanga_all_to_backup_with_custom_multiple_categories():
    collected = [
        {"comic": {"name": "Manga 1", "path_word": "m1"}},
    ]
    backup = convert_copymanga_all_to_backup(
        collected_items=collected,
        browse_history_items=None,
        category_name="分类A, 分类B",
    )
    assert len(backup.backup_categories) == 2
    assert backup.backup_categories[0].name == "分类A"
    assert backup.backup_categories[0].order == 0
    assert backup.backup_categories[1].name == "分类B"
    assert backup.backup_categories[1].order == 1
    assert backup.backup_manga[0].categories == [0, 1]


def test_convert_copymanga_all_to_backup_without_category():
    collected = [
        {"comic": {"name": "Manga 1", "path_word": "m1"}},
    ]
    backup = convert_copymanga_all_to_backup(
        collected_items=collected,
        browse_history_items=None,
        category_name="none",
    )
    assert len(backup.backup_categories) == 0
    assert backup.backup_manga[0].categories == []
