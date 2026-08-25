"""Tests for merger module."""

import pytest
from copy2mihon.merger import merge_copymanga_into_backup_pb
from copy2mihon.proto.serializer import copy_manga_model_to_pb
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


def test_merge_history_only_manga_preserves_full_metadata():
    """Verify that a manga only found in reading history retains all metadata fields."""
    backup_pb = schema_mihon_pb2.Backup()

    browse_history = [
        {
            "comic": {
                "path_word": "history_comic",
                "name": "History Only Comic",
                "author": [{"name": "Author A"}],
                "brief": "A test description",
                "cover": "https://img.example.com/cover.jpg",
                "status": 0,
                "theme": [{"name": "Adventure"}],
            },
            "last_chapter_id": "ch-uuid-99",
            "last_chapter_name": "第99话",
            "datetime_modifier": "2026-08-25 12:00:00",
        }
    ]

    modified_pb, stats = merge_copymanga_into_backup_pb(
        backup_pb=backup_pb,
        collected_items=[],
        browse_history_items=browse_history,
        source_id=DEFAULT_COPYMANGA_SOURCE_ID,
    )

    assert stats["new_manga_added"] == 1
    assert len(modified_pb.backupManga) == 1

    m = modified_pb.backupManga[0]
    assert m.title == "History Only Comic"
    assert m.url == "/comic/history_comic"
    assert m.author == "Author A"
    assert m.artist == "Author A"
    assert m.description == "A test description"
    assert "Adventure" in list(m.genre)
    assert m.thumbnailUrl == "https://img.example.com/cover.jpg"
    assert m.initialized is True
    assert m.favorite is False
    assert m.status == 1
    assert len(m.chapters) == 1
    assert m.chapters[0].url == "/comic/history_comic/chapter/ch-uuid-99"
    assert m.chapters[0].read is True


def test_chapter_exact_id_matching_prevents_substring_collision():
    """Verify that chapter id '1' does not falsely match chapter id '12' or '21'."""
    backup_pb = schema_mihon_pb2.Backup()

    m = backup_pb.backupManga.add()
    m.source = DEFAULT_COPYMANGA_SOURCE_ID
    m.url = "/comic/test_collision"
    m.title = "Test Collision"

    # Chapters: ID "12", ID "21", ID "1"
    ch12 = m.chapters.add()
    ch12.url = "/comic/test_collision/chapter/12"
    ch12.name = "第12话"
    ch12.read = False

    ch21 = m.chapters.add()
    ch21.url = "/comic/test_collision/chapter/21"
    ch21.name = "第21话"
    ch21.read = False

    ch1 = m.chapters.add()
    ch1.url = "/comic/test_collision/chapter/1"
    ch1.name = "第1话"
    ch1.read = False

    browse_history = [
        {
            "comic": {"path_word": "test_collision"},
            "last_chapter_id": "1",
            "last_chapter_name": "第1话",
            "datetime_modifier": "2026-08-25 10:00:00",
        }
    ]

    modified_pb, stats = merge_copymanga_into_backup_pb(
        backup_pb=backup_pb,
        collected_items=[],
        browse_history_items=browse_history,
        source_id=DEFAULT_COPYMANGA_SOURCE_ID,
    )

    res_m = modified_pb.backupManga[0]
    assert res_m.chapters[0].read is False  # ID 12 should NOT match
    assert res_m.chapters[1].read is False  # ID 21 should NOT match
    assert res_m.chapters[2].read is True   # ID 1 should match exactly


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
