"""Tests for merger module."""

from datetime import datetime, timezone

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
    # Existing manga's category assignment is preserved (not modified)
    assert len(res_m.categories) == 0

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


def test_chapter_number_fallback_ignores_volume_prefix():
    """'第2卷 第10话' must match local chapter 10, not chapter 2."""
    backup_pb = schema_mihon_pb2.Backup()

    m = backup_pb.backupManga.add()
    m.source = DEFAULT_COPYMANGA_SOURCE_ID
    m.url = "/comic/volume_prefix"
    m.title = "Volume Prefix"

    ch = m.chapters.add()
    ch.url = "/comic/volume_prefix/chapter/local-10"
    ch.name = "第10话"
    ch.chapterNumber = 10.0
    ch.read = False

    browse_history = [
        {
            "comic": {"path_word": "volume_prefix"},
            "last_chapter_id": "remote-uuid-different",
            "last_chapter_name": "第2卷 第10话",
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
    assert len(res_m.chapters) == 1
    assert res_m.chapters[0].read is True
    assert res_m.chapters[0].lastPageRead == 1
    assert stats["chapters_marked_read"] == 1


def test_merge_prefers_canonical_url_and_marks_duplicate_rows_read():
    """A dirty backup may hold the same chapter twice, once missing /comic/."""
    backup_pb = schema_mihon_pb2.Backup()

    m = backup_pb.backupManga.add()
    m.source = DEFAULT_COPYMANGA_SOURCE_ID
    m.url = "/comic/dirty_dup"
    m.title = "Dirty Duplicate"

    legacy = m.chapters.add()
    legacy.url = "dirty_dup/chapter/u-1"
    legacy.name = "第1话"
    legacy.chapterNumber = 1.0
    legacy.read = True

    canonical = m.chapters.add()
    canonical.url = "/comic/dirty_dup/chapter/u-1"
    canonical.name = "第1话"
    canonical.chapterNumber = 1.0
    canonical.read = False

    hist = m.history.add()
    hist.url = "/comic/dirty_dup/chapter/u-1"
    hist.lastRead = 1000

    browse_history = [
        {
            "comic": {"path_word": "dirty_dup"},
            "last_chapter_id": "u-1",
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
    assert all(ch.read for ch in res_m.chapters)
    assert len(res_m.history) == 1
    expected = int(datetime(2026, 8, 25, 2, 0, tzinfo=timezone.utc).timestamp() * 1000)
    assert res_m.history[0].lastRead == expected
    assert stats["chapters_marked_read"] == 1


def test_new_shelf_manga_keeps_last_read_chapter():
    """A newly added bookshelf manga must retain the last chapter from the shelf payload."""
    backup_pb = schema_mihon_pb2.Backup()

    collected = [
        {
            "comic": {"path_word": "new_comic", "name": "New Comic"},
            "last_chapter_id": "ch-1",
            "last_chapter_name": "第1话",
            "datetime_modifier": "2026-08-25 10:00:00",
        }
    ]

    modified_pb, stats = merge_copymanga_into_backup_pb(
        backup_pb=backup_pb,
        collected_items=collected,
        browse_history_items=[],
        source_id=DEFAULT_COPYMANGA_SOURCE_ID,
    )

    assert stats["new_manga_added"] == 1
    m = modified_pb.backupManga[0]
    assert m.favorite is True
    assert len(m.chapters) == 1
    assert m.chapters[0].url == "/comic/new_comic/chapter/ch-1"
    assert m.chapters[0].read is True
    assert len(m.history) == 1
    assert m.history[0].url == "/comic/new_comic/chapter/ch-1"


def test_merge_history_alternate_field_names():
    """History payloads using chapter_id/chapter.name/last_read_time must still sync."""
    backup_pb = schema_mihon_pb2.Backup()

    m = backup_pb.backupManga.add()
    m.source = DEFAULT_COPYMANGA_SOURCE_ID
    m.url = "/comic/alt_comic"
    m.title = "Alt Comic"

    ch = m.chapters.add()
    ch.url = "/comic/alt_comic/chapter/u-7"
    ch.name = "第7话"
    ch.read = False

    history = [
        {
            "comic": {"path_word": "alt_comic", "name": "Alt Comic"},
            "chapter_id": "u-7",
            "chapter": {"name": "第7话"},
            "last_read_time": "2026-08-25 10:00:00",
        }
    ]

    modified_pb, stats = merge_copymanga_into_backup_pb(
        backup_pb=backup_pb,
        collected_items=[],
        browse_history_items=history,
        source_id=DEFAULT_COPYMANGA_SOURCE_ID,
    )

    res_m = modified_pb.backupManga[0]
    assert res_m.chapters[0].read is True
    assert len(res_m.history) == 1
    assert res_m.history[0].url == "/comic/alt_comic/chapter/u-7"
    assert res_m.history[0].lastRead == int(
        datetime(2026, 8, 25, 2, 0, tzinfo=timezone.utc).timestamp() * 1000
    )
    assert stats["chapters_marked_read"] == 1
    assert stats["updated_history"] == 1


def test_merge_appends_unknown_chapter_instead_of_dropping_progress():
    """If Mihon has no matching chapter, the read chapter is appended rather than lost."""
    backup_pb = schema_mihon_pb2.Backup()

    m = backup_pb.backupManga.add()
    m.source = DEFAULT_COPYMANGA_SOURCE_ID
    m.url = "/comic/stale_comic"
    m.title = "Stale Comic"
    for i in range(1, 3):
        ch = m.chapters.add()
        ch.url = f"/comic/stale_comic/chapter/old-{i}"
        ch.name = f"第{i}话"
        ch.chapterNumber = float(i)
        ch.read = i == 1

    history = [
        {
            "comic": {"path_word": "stale_comic"},
            "last_chapter_id": "new-9",
            "last_chapter_name": "第9话",
            "datetime_modifier": "2026-08-25 10:00:00",
        }
    ]

    modified_pb, stats = merge_copymanga_into_backup_pb(
        backup_pb=backup_pb,
        collected_items=[],
        browse_history_items=history,
        source_id=DEFAULT_COPYMANGA_SOURCE_ID,
    )

    res_m = modified_pb.backupManga[0]
    assert [c.url for c in res_m.chapters] == [
        "/comic/stale_comic/chapter/old-1",
        "/comic/stale_comic/chapter/old-2",
        "/comic/stale_comic/chapter/new-9",
    ]
    assert res_m.chapters[2].read is True
    assert res_m.chapters[2].chapterNumber == 9.0
    assert len(res_m.history) == 1
    assert res_m.history[0].url == "/comic/stale_comic/chapter/new-9"
    assert stats["chapters_marked_read"] == 1
    assert stats["updated_history"] == 1


def test_merge_does_not_overwrite_existing_last_page_read():
    backup_pb = schema_mihon_pb2.Backup()

    m = backup_pb.backupManga.add()
    m.source = DEFAULT_COPYMANGA_SOURCE_ID
    m.url = "/comic/paged_comic"
    m.title = "Paged Comic"

    ch = m.chapters.add()
    ch.url = "/comic/paged_comic/chapter/u-1"
    ch.name = "第1话"
    ch.read = True
    ch.lastPageRead = 15

    history = [
        {
            "comic": {"path_word": "paged_comic"},
            "last_chapter_id": "u-1",
            "last_chapter_name": "第1话",
            "datetime_modifier": "2026-08-25 10:00:00",
        }
    ]

    modified_pb, _ = merge_copymanga_into_backup_pb(
        backup_pb=backup_pb,
        collected_items=[],
        browse_history_items=history,
        source_id=DEFAULT_COPYMANGA_SOURCE_ID,
    )

    assert modified_pb.backupManga[0].chapters[0].lastPageRead == 15


def test_merge_output_adds_tachibk_suffix(tmp_path):
    from copy2mihon.merger import merge_and_export_tachibk
    from copy2mihon.models import MihonBackup
    from copy2mihon.proto.serializer import export_to_tachibk

    base = export_to_tachibk(MihonBackup(), tmp_path / "base.tachibk")
    output_path, _ = merge_and_export_tachibk(base, tmp_path / "merged", collected_items=[])

    assert output_path == tmp_path / "merged.tachibk"
    assert output_path.exists()


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


def test_merge_registers_copymanga_source_once():
    """A fresh backup must gain the CopyManga source entry exactly once."""
    backup_pb = schema_mihon_pb2.Backup()
    collected = [{"comic": {"path_word": "solo_comic", "name": "Solo"}}]

    merge_copymanga_into_backup_pb(
        backup_pb=backup_pb,
        collected_items=collected,
        source_id=DEFAULT_COPYMANGA_SOURCE_ID,
    )
    merge_copymanga_into_backup_pb(
        backup_pb=backup_pb,
        collected_items=collected,
        source_id=DEFAULT_COPYMANGA_SOURCE_ID,
    )

    assert len(backup_pb.backupSources) == 1
    assert backup_pb.backupSources[0].sourceId == DEFAULT_COPYMANGA_SOURCE_ID
    assert backup_pb.backupSources[0].name == "拷贝漫画"


def test_new_manga_gets_memo_and_mihon_defaults():
    """Generated manga records must match what a real Mihon export writes."""
    backup_pb = schema_mihon_pb2.Backup()

    merge_copymanga_into_backup_pb(
        backup_pb=backup_pb,
        collected_items=[{"comic": {"path_word": "memo_comic", "name": "Memo"}}],
        source_id=DEFAULT_COPYMANGA_SOURCE_ID,
    )

    m = backup_pb.backupManga[0]
    assert bytes(m.memo) == b"{}"
    assert m.initialized is True
    assert m.chapterFlags == 0
    assert m.viewer_flags == 0
    assert list(m.categories) == [0]
