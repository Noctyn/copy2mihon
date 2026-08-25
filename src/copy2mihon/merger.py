"""Merge CopyManga cloud subscriptions and reading history into an existing .tachibk backup."""

from __future__ import annotations

import gzip
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from copy2mihon.converter import (
    comic_dict_to_mihon_manga,
    create_chapter_and_history,
    normalize_manga_url,
    parse_category_names,
    parse_datetime_to_ms,
)
from copy2mihon.models import (
    DEFAULT_COPYMANGA_SOURCE_ID,
    DEFAULT_COPYMANGA_SOURCE_NAME,
)
from copy2mihon.parser import repair_mojibake
from copy2mihon.proto import schema_mihon_pb2
from copy2mihon.proto.serializer import read_tachibk


def merge_copymanga_into_backup_pb(
    backup_pb: schema_mihon_pb2.Backup,
    collected_items: List[Dict[str, Any]],
    browse_history_items: Optional[List[Dict[str, Any]]] = None,
    source_id: int = DEFAULT_COPYMANGA_SOURCE_ID,
    category_name: Optional[str] = "拷贝漫画",
) -> Tuple[schema_mihon_pb2.Backup, Dict[str, int]]:
    """Merge CopyManga collected comics and browse history into an existing Protobuf Backup message."""
    stats = {
        "updated_favorites": 0,
        "new_manga_added": 0,
        "updated_history": 0,
        "chapters_marked_read": 0,
    }

    # 1. Categories
    category_names = parse_category_names(category_name)
    target_category_orders: List[int] = []

    if category_names:
        existing_cat_by_name = {c.name.strip().lower(): c for c in backup_pb.backupCategories}
        current_max_order = max((c.order for c in backup_pb.backupCategories), default=-1)

        for name in category_names:
            key = name.strip().lower()
            if key in existing_cat_by_name:
                target_category_orders.append(existing_cat_by_name[key].order)
            else:
                current_max_order += 1
                new_cat = backup_pb.backupCategories.add()
                new_cat.name = name.strip()
                new_cat.order = current_max_order
                new_cat.id = len(backup_pb.backupCategories)
                new_cat.flags = 0
                existing_cat_by_name[key] = new_cat
                target_category_orders.append(new_cat.order)

    # 2. Repair text in existing backup and index manga by path_word
    manga_by_path_word: Dict[str, schema_mihon_pb2.BackupManga] = {}
    for m in backup_pb.backupManga:
        if m.title:
            m.title = repair_mojibake(m.title)
        if m.author:
            m.author = repair_mojibake(m.author)
        if m.artist:
            m.artist = repair_mojibake(m.artist)
        if m.description:
            m.description = repair_mojibake(m.description)
        for ch in m.chapters:
            if ch.name:
                ch.name = repair_mojibake(ch.name)

        if m.source == source_id:
            pw = m.url.strip("/").replace("comic/", "")
            manga_by_path_word[pw.lower()] = m

    # 3. Merge bookshelf items
    for item in collected_items:
        comic_data = item.get("comic", item) if isinstance(item, dict) else {}
        pw = (comic_data.get("path_word") or comic_data.get("uuid") or "").strip("/").replace("comic/", "").lower()
        if not pw:
            continue

        if pw in manga_by_path_word:
            m = manga_by_path_word[pw]
            if not m.favorite:
                m.favorite = True
                stats["updated_favorites"] += 1
            if target_category_orders:
                existing_cats = set(m.categories)
                for cat_ord in target_category_orders:
                    if cat_ord not in existing_cats:
                        m.categories.append(cat_ord)
        else:
            new_m = comic_dict_to_mihon_manga(
                item=item,
                source_id=source_id,
                category_ids=target_category_orders,
                is_favorite=True,
            )
            m_pb = backup_pb.backupManga.add()
            m_pb.source = new_m.source
            m_pb.url = new_m.url
            m_pb.title = new_m.title
            m_pb.artist = new_m.artist or ""
            m_pb.author = new_m.author or ""
            m_pb.description = new_m.description or ""
            if new_m.genre:
                m_pb.genre.extend(new_m.genre)
            m_pb.status = new_m.status
            m_pb.thumbnailUrl = new_m.thumbnail_url or ""
            m_pb.dateAdded = new_m.date_added
            m_pb.viewer_flags = new_m.viewer_flags
            m_pb.chapterFlags = new_m.chapter_flags
            m_pb.updateStrategy = new_m.update_strategy
            m_pb.favorite = new_m.favorite
            if new_m.categories:
                m_pb.categories.extend(new_m.categories)

            manga_by_path_word[pw] = m_pb
            stats["new_manga_added"] += 1

    # 4. Merge reading history
    if browse_history_items:
        for b_item in browse_history_items:
            comic_data = b_item.get("comic", {})
            pw = (comic_data.get("path_word") or comic_data.get("uuid") or "").strip("/").replace("comic/", "").lower()
            if not pw:
                continue

            last_ch_id = b_item.get("last_chapter_id")
            last_ch_name = repair_mojibake(b_item.get("last_chapter_name", ""))
            read_time_ms = int(b_item.get("datetime_modifier_ms") or 0)
            if not read_time_ms and b_item.get("datetime_modifier"):
                read_time_ms = parse_datetime_to_ms(b_item.get("datetime_modifier"))

            if pw in manga_by_path_word:
                m = manga_by_path_word[pw]
                stats["updated_history"] += 1

                if len(m.chapters) > 0:
                    matched_idx = -1

                    for idx, ch in enumerate(m.chapters):
                        if last_ch_id and last_ch_id in ch.url:
                            matched_idx = idx
                            break

                    if matched_idx == -1 and last_ch_name:
                        match = re.search(r"(\d+(\.\d+)?)", last_ch_name)
                        if match:
                            target_val = float(match.group(1))
                            for idx, ch in enumerate(m.chapters):
                                if abs(ch.chapterNumber - target_val) < 0.01:
                                    matched_idx = idx
                                    break

                    if matched_idx != -1:
                        target_ch = m.chapters[matched_idx]
                        target_url = target_ch.url

                        if not target_ch.read:
                            target_ch.read = True
                            stats["chapters_marked_read"] += 1
                        target_ch.lastPageRead = 1

                        existing_hist = next((h for h in m.history if h.url == target_url), None)
                        if existing_hist:
                            if read_time_ms > 0 and read_time_ms > existing_hist.lastRead:
                                existing_hist.lastRead = read_time_ms
                        else:
                            fallback_time = read_time_ms
                            if not fallback_time:
                                fallback_time = parse_datetime_to_ms(comic_data.get("datetime_updated"))
                            hist_pb = m.history.add()
                            hist_pb.url = target_url
                            hist_pb.lastRead = fallback_time
                            hist_pb.readDuration = 0
                else:
                    if last_ch_id:
                        ch_model, hist_model = create_chapter_and_history(
                            path_word=pw,
                            chapter_id=last_ch_id,
                            chapter_name=last_ch_name,
                            read_time_ms=read_time_ms,
                        )
                        if ch_model and hist_model:
                            ch_pb = m.chapters.add()
                            ch_pb.url = ch_model.url
                            ch_pb.name = ch_model.name
                            ch_pb.read = True
                            ch_pb.lastPageRead = 1
                            ch_pb.dateFetch = ch_model.date_fetch
                            ch_pb.dateUpload = ch_model.date_upload
                            ch_pb.chapterNumber = ch_model.chapter_number
                            ch_pb.sourceOrder = ch_model.source_order

                            hist_pb = m.history.add()
                            hist_pb.url = hist_model.url
                            hist_pb.lastRead = hist_model.last_read
                            hist_pb.readDuration = hist_model.read_duration
            else:
                if last_ch_id:
                    new_m = comic_dict_to_mihon_manga(
                        item=b_item,
                        source_id=source_id,
                        category_ids=[],
                        is_favorite=False,
                    )
                    ch_model, hist_model = create_chapter_and_history(
                        path_word=pw,
                        chapter_id=last_ch_id,
                        chapter_name=last_ch_name,
                        read_time_ms=read_time_ms,
                    )
                    m_pb = backup_pb.backupManga.add()
                    m_pb.source = new_m.source
                    m_pb.url = new_m.url
                    m_pb.title = new_m.title
                    m_pb.status = new_m.status
                    m_pb.thumbnailUrl = new_m.thumbnail_url or ""
                    m_pb.dateAdded = new_m.date_added
                    m_pb.favorite = False

                    if ch_model and hist_model:
                        ch_pb = m_pb.chapters.add()
                        ch_pb.url = ch_model.url
                        ch_pb.name = ch_model.name
                        ch_pb.read = True
                        ch_pb.lastPageRead = 1
                        ch_pb.dateFetch = ch_model.date_fetch
                        ch_pb.dateUpload = ch_model.date_upload
                        ch_pb.chapterNumber = ch_model.chapter_number
                        ch_pb.sourceOrder = ch_model.source_order

                        hist_pb = m_pb.history.add()
                        hist_pb.url = hist_model.url
                        hist_pb.lastRead = hist_model.last_read
                        hist_pb.readDuration = 0

                    manga_by_path_word[pw] = m_pb
                    stats["new_manga_added"] += 1
                    stats["updated_history"] += 1

    return backup_pb, stats


def merge_and_export_tachibk(
    input_backup_path: Path,
    output_backup_path: Path,
    collected_items: List[Dict[str, Any]],
    browse_history_items: Optional[List[Dict[str, Any]]] = None,
    source_id: int = DEFAULT_COPYMANGA_SOURCE_ID,
    category_name: Optional[str] = "拷贝漫画",
) -> Tuple[Path, Dict[str, int]]:
    """Load an existing .tachibk file, merge cloud data into it, and write the output."""
    backup_pb = read_tachibk(input_backup_path)
    modified_pb, stats = merge_copymanga_into_backup_pb(
        backup_pb=backup_pb,
        collected_items=collected_items,
        browse_history_items=browse_history_items,
        source_id=source_id,
        category_name=category_name,
    )

    serialized_bytes = modified_pb.SerializeToString()
    output_backup_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output_backup_path, "wb") as f:
        f.write(serialized_bytes)

    return output_backup_path, stats
