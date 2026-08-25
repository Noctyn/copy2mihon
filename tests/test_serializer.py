"""Tests for serializer module."""

import json
from copy2mihon.models import (
    MihonBackup,
    MihonCategory,
    MihonChapter,
    MihonHistory,
    MihonManga,
    MihonSource,
)
from copy2mihon.proto.serializer import (
    build_protobuf_backup,
    export_to_json,
    export_to_tachibk,
    read_tachibk,
)


def test_build_protobuf_and_serialize(tmp_path):
    backup = MihonBackup(
        backup_sources=[MihonSource(source_id=12345, name="Test Source")],
        backup_categories=[MihonCategory(name="Test Category", id=1, order=0)],
        backup_manga=[
            MihonManga(
                source=12345,
                url="/comic/test",
                title="Test Manga",
                categories=[0],
                chapters=[
                    MihonChapter(
                        url="/comic/test/chapter/ch1",
                        name="Ch 1",
                        read=True,
                        chapter_number=1.0,
                    )
                ],
                history=[
                    MihonHistory(
                        url="/comic/test/chapter/ch1",
                        last_read=1700000000000,
                    )
                ],
            )
        ],
    )

    pb = build_protobuf_backup(backup)
    assert len(pb.backupManga) == 1
    assert pb.backupManga[0].title == "Test Manga"
    assert pb.backupManga[0].chapters[0].name == "Ch 1"

    tachibk_path = tmp_path / "test.tachibk"
    export_to_tachibk(backup, tachibk_path)
    assert tachibk_path.exists()

    loaded_pb = read_tachibk(tachibk_path)
    assert len(loaded_pb.backupManga) == 1
    assert loaded_pb.backupManga[0].title == "Test Manga"


def test_export_to_json(tmp_path):
    backup = MihonBackup(
        backup_sources=[MihonSource(source_id=12345, name="Test Source")],
        backup_categories=[MihonCategory(name="Test Category", id=1, order=0)],
        backup_manga=[
            MihonManga(
                source=12345,
                url="/comic/test",
                title="Test Manga",
                thumbnail_url="https://example.com/cover.jpg",
                categories=[0],
                chapters=[
                    MihonChapter(
                        url="/comic/test/chapter/ch1",
                        name="Ch 1",
                        last_page_read=1,
                    )
                ],
                history=[
                    MihonHistory(
                        url="/comic/test/chapter/ch1",
                        last_read=1700000000000,
                    )
                ],
            )
        ],
    )

    json_path = tmp_path / "test.json"
    export_to_json(backup, json_path)
    assert json_path.exists()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "backupManga" in data
    assert len(data["backupManga"]) == 1
    manga = data["backupManga"][0]
    assert manga["title"] == "Test Manga"
    # Nested fields must use camelCase keys matching the Mihon backup schema
    assert "thumbnailUrl" in manga
    assert "thumbnail_url" not in manga
    assert "dateAdded" in manga
    assert "date_added" not in manga
    assert "chapterFlags" in manga
    assert manga["chapters"][0]["lastPageRead"] == 1
    assert "last_page_read" not in manga["chapters"][0]
    assert "dateFetch" in manga["chapters"][0]
    assert manga["history"][0]["lastRead"] == 1700000000000
    assert "readDuration" in manga["history"][0]
    assert data["backupSources"][0]["sourceId"] == 12345
    assert "source_id" not in data["backupSources"][0]
