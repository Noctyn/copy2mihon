"""Tests for merger module."""

import pytest
from copy2mihon.merger import merge_copymanga_into_backup_pb
from copy2mihon.models import DEFAULT_COPYMANGA_SOURCE_ID
from copy2mihon.proto import schema_mihon_pb2


def test_merge_copymanga_into_backup_pb():
    backup_pb = schema_mihon_pb2.Backup()

    cat = backup_pb.backupCategories.add()
    cat.name = "拷贝漫画"
    cat.order = 0
    cat.id = 1

    m = backup_pb.backupManga.add()
    m.source = DEFAULT_COPYMANGA_SOURCE_ID
    m.url = "/comic/test_comic"
    m.title = "Test Comic"
    m.favorite = False

    for i in range(1, 6):
        ch = m.chapters.add()
        ch.url = f"/comic/test_comic/chapter/uuid-{i}"
        ch.name = f"第{i}话"
        ch.chapterNumber = float(i)
        ch.read = False

    collected = [{"comic": {"path_word": "test_comic", "name": "Test Comic"}}]
    browse_history = [
        {
            "comic": {"path_word": "test_comic"},
            "last_chapter_id": "uuid-3",
            "last_chapter_name": "ç¬¬03å·»",
            "datetime_modifier": "2026-08-25 10:00:00",
        }
    ]

    modified_pb, stats = merge_copymanga_into_backup_pb(
        backup_pb=backup_pb,
        collected_items=collected,
        browse_history_items=browse_history,
        source_id=DEFAULT_COPYMANGA_SOURCE_ID,
        category_name="拷贝漫画",
    )

    assert stats["updated_favorites"] == 1
    assert stats["chapters_marked_read"] == 1

    res_m = modified_pb.backupManga[0]
    assert res_m.favorite is True
    assert 0 in res_m.categories

    # Only matched chapter is marked read
    assert res_m.chapters[0].read is False
    assert res_m.chapters[1].read is False
    assert res_m.chapters[2].read is True
    assert res_m.chapters[3].read is False
    assert res_m.chapters[4].read is False

    assert len(res_m.history) == 1
    assert res_m.history[0].url == "/comic/test_comic/chapter/uuid-3"


def test_merge_when_mihon_progress_is_ahead():
    backup_pb = schema_mihon_pb2.Backup()

    m = backup_pb.backupManga.add()
    m.source = DEFAULT_COPYMANGA_SOURCE_ID
    m.url = "/comic/test_comic"
    m.title = "Test Comic"
    m.favorite = True

    for i in range(1, 11):
        ch = m.chapters.add()
        ch.url = f"/comic/test_comic/chapter/uuid-{i}"
        ch.name = f"第{i}话"
        ch.chapterNumber = float(i)
        ch.read = True if i <= 5 else False

    browse_history = [
        {
            "comic": {"path_word": "test_comic"},
            "last_chapter_id": "uuid-3",
            "last_chapter_name": "第3话",
            "datetime_modifier": "2026-08-20 10:00:00",
        }
    ]

    modified_pb, stats = merge_copymanga_into_backup_pb(
        backup_pb=backup_pb,
        collected_items=[],
        browse_history_items=browse_history,
        source_id=DEFAULT_COPYMANGA_SOURCE_ID,
    )

    res_m = modified_pb.backupManga[0]
    for i in range(5):
        assert res_m.chapters[i].read is True
    for i in range(5, 10):
        assert res_m.chapters[i].read is False
