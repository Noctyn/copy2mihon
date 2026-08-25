"""Serialization and deserialization between MihonBackup models and .tachibk Protobuf / JSON files."""

from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path
from typing import Any, Dict, Union

from copy2mihon.models import (
    DEFAULT_COPYMANGA_SOURCE_ID,
    DEFAULT_COPYMANGA_SOURCE_NAME,
    MihonBackup,
    MihonCategory,
    MihonChapter,
    MihonHistory,
    MihonManga,
    MihonSource,
)
from copy2mihon.proto import schema_mihon_pb2


def build_protobuf_backup(backup: MihonBackup) -> schema_mihon_pb2.Backup:
    """Convert MihonBackup domain model into schema_mihon_pb2.Backup message."""
    backup_pb = schema_mihon_pb2.Backup()

    # Sources
    sources_to_add = backup.backup_sources
    if not sources_to_add:
        sources_to_add = [
            MihonSource(
                source_id=DEFAULT_COPYMANGA_SOURCE_ID,
                name=DEFAULT_COPYMANGA_SOURCE_NAME,
            )
        ]

    for src in sources_to_add:
        src_pb = backup_pb.backupSources.add()
        src_pb.sourceId = src.source_id
        if src.name:
            src_pb.name = src.name

    # Categories
    for cat in backup.backup_categories:
        cat_pb = backup_pb.backupCategories.add()
        cat_pb.name = cat.name
        cat_pb.id = cat.id
        cat_pb.order = cat.order
        cat_pb.flags = cat.flags

    # Manga entries
    for m in backup.backup_manga:
        m_pb = backup_pb.backupManga.add()
        m_pb.source = m.source
        m_pb.url = m.url
        if m.title:
            m_pb.title = m.title
        if m.author:
            m_pb.author = m.author
        if m.artist:
            m_pb.artist = m.artist
        if m.description:
            m_pb.description = m.description
        if m.genre:
            m_pb.genre.extend(m.genre)
        m_pb.status = m.status
        if m.thumbnail_url:
            m_pb.thumbnailUrl = m.thumbnail_url
        if m.date_added:
            m_pb.dateAdded = m.date_added
        if m.categories:
            m_pb.categories.extend(m.categories)
        m_pb.favorite = m.favorite
        m_pb.initialized = m.initialized
        m_pb.chapterFlags = m.chapter_flags
        m_pb.viewer_flags = m.viewer_flags
        m_pb.updateStrategy = m.update_strategy
        if m.version:
            m_pb.version = m.version
        if m.memo:
            m_pb.memo.extend(m.memo)

        # Chapters
        for ch in m.chapters:
            ch_pb = m_pb.chapters.add()
            ch_pb.url = ch.url
            ch_pb.name = ch.name
            if ch.scanlator:
                ch_pb.scanlator = ch.scanlator
            ch_pb.read = ch.read
            ch_pb.bookmark = ch.bookmark
            ch_pb.lastPageRead = ch.last_page_read
            ch_pb.dateFetch = ch.date_fetch
            ch_pb.dateUpload = ch.date_upload
            ch_pb.chapterNumber = ch.chapter_number
            ch_pb.sourceOrder = ch.source_order
            if ch.last_modified_at:
                ch_pb.lastModifiedAt = ch.last_modified_at
            if ch.version:
                ch_pb.version = ch.version
            if ch.memo:
                ch_pb.memo.extend(ch.memo)

        # History
        for h in m.history:
            h_pb = m_pb.history.add()
            h_pb.url = h.url
            h_pb.lastRead = h.last_read
            h_pb.readDuration = h.read_duration

    return backup_pb


def serialize_to_protobuf_bytes(backup: MihonBackup) -> bytes:
    """Serialize MihonBackup to Protobuf binary bytes."""
    pb_obj = build_protobuf_backup(backup)
    return pb_obj.SerializeToString()


def export_to_tachibk(backup: MihonBackup, output_path: Union[str, Path]) -> Path:
    """Serialize MihonBackup and write as gzip compressed .tachibk file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw_bytes = serialize_to_protobuf_bytes(backup)
    with gzip.open(path, "wb") as f:
        f.write(raw_bytes)
    return path


def read_tachibk(file_path: Union[str, Path]) -> schema_mihon_pb2.Backup:
    """Read a gzip compressed .tachibk file and parse it into a schema_mihon_pb2.Backup message."""
    path = Path(file_path)
    with gzip.open(path, "rb") as f:
        data = f.read()
    backup_pb = schema_mihon_pb2.Backup()
    backup_pb.ParseFromString(data)
    return backup_pb


def export_to_json(backup: MihonBackup, output_path: Union[str, Path]) -> Path:
    """Export MihonBackup as a JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    def _convert_model(obj: Any) -> Any:
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode("ascii")
        if isinstance(obj, list):
            return [_convert_model(i) for i in obj]
        if isinstance(obj, dict):
            return {k: _convert_model(v) for k, v in obj.items()}
        return obj

    data = {
        "backupManga": [
            {
                "source": m.source,
                "url": m.url,
                "title": m.title,
                "artist": m.artist,
                "author": m.author,
                "description": m.description,
                "genre": m.genre,
                "status": m.status,
                "thumbnailUrl": m.thumbnail_url,
                "dateAdded": m.date_added,
                "viewerFlags": m.viewer_flags,
                "chapterFlags": m.chapter_flags,
                "updateStrategy": m.update_strategy,
                "favorite": m.favorite,
                "initialized": m.initialized,
                "categories": m.categories,
                "version": m.version,
                "chapters": [
                    {
                        "url": ch.url,
                        "name": ch.name,
                        "scanlator": ch.scanlator,
                        "read": ch.read,
                        "bookmark": ch.bookmark,
                        "lastPageRead": ch.last_page_read,
                        "dateFetch": ch.date_fetch,
                        "dateUpload": ch.date_upload,
                        "chapterNumber": ch.chapter_number,
                        "sourceOrder": ch.source_order,
                        "memo": [_convert_model(item) for item in ch.memo],
                    }
                    for ch in m.chapters
                ],
                "history": [
                    {
                        "url": h.url,
                        "lastRead": h.last_read,
                        "readDuration": h.read_duration,
                    }
                    for h in m.history
                ],
                "memo": [_convert_model(item) for item in m.memo],
            }
            for m in backup.backup_manga
        ],
        "backupCategories": [
            {
                "name": cat.name,
                "id": cat.id,
                "order": cat.order,
                "flags": cat.flags,
            }
            for cat in backup.backup_categories
        ],
        "backupSources": [
            {
                "sourceId": src.source_id,
                "name": src.name,
            }
            for src in backup.backup_sources
        ],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return path
