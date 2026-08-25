"""Merge CopyManga cloud subscriptions and reading history into an existing .tachibk backup."""

from __future__ import annotations

import gzip
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from copy2mihon.converter import (
    comic_dict_to_mihon_manga,
    create_chapter_and_history,
    parse_category_names,
    parse_datetime_to_ms,
)
from copy2mihon.models import DEFAULT_COPYMANGA_SOURCE_ID
from copy2mihon.parser import extract_path_word, normalize_path_word, repair_mojibake
from copy2mihon.proto import schema_mihon_pb2
from copy2mihon.proto.serializer import (
    copy_chapter_model_to_pb,
    copy_history_model_to_pb,
    copy_manga_model_to_pb,
    read_tachibk,
)


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
            pw = normalize_path_word(m.url)
            if pw:
                manga_by_path_word[pw] = m

    # 3. Merge bookshelf items
    for item in collected_items:
        pw = extract_path_word(item, fallback=True)

        if pw in manga_by_path_word:
            m = manga_by_path_word[pw]
            if not m.favorite:
                m.favorite = True
                stats["updated_favorites"] += 1
            # Preserve user's existing category assignment for manga already in Mihon
        else:
            new_m = comic_dict_to_mihon_manga(
                item=item,
                source_id=source_id,
                category_ids=target_category_orders,
                is_favorite=True,
            )
            m_pb = backup_pb.backupManga.add()
            copy_manga_model_to_pb(m_pb, new_m)
            manga_by_path_word[pw] = m_pb
            stats["new_manga_added"] += 1

    # 4. Merge reading history
    if browse_history_items:
        for b_item in browse_history_items:
            comic_data = b_item.get("comic", {})
            pw = extract_path_word(b_item, comic_data, fallback=True)

            last_ch_id = b_item.get("last_chapter_id")
            last_ch_name = repair_mojibake(b_item.get("last_chapter_name", ""))
            # Keep 0 for missing timestamps so existing lastRead values are preserved
            read_time_raw = b_item.get("datetime_modifier") or comic_data.get("datetime_updated")
            read_time_ms = parse_datetime_to_ms(read_time_raw) if read_time_raw else 0

            if pw in manga_by_path_word:
                m = manga_by_path_word[pw]
                stats["updated_history"] += 1

                if len(m.chapters) > 0:
                    matched_idx = -1

                    # 1. Exact match by last segment of chapter URL (avoid substring collisions)
                    if last_ch_id:
                        target_id_clean = str(last_ch_id).strip().lower()
                        for idx, ch in enumerate(m.chapters):
                            ch_url_id = ch.url.rstrip("/").rsplit("/", 1)[-1].strip().lower()
                            if ch_url_id == target_id_clean:
                                matched_idx = idx
                                break

                    # 2. Fallback: match by chapter number from repaired name
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
                            fallback_time = read_time_ms or int(time.time() * 1000)
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
                            copy_chapter_model_to_pb(ch_pb, ch_model)
                            hist_pb = m.history.add()
                            copy_history_model_to_pb(hist_pb, hist_model)
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
                    copy_manga_model_to_pb(m_pb, new_m)

                    if ch_model and hist_model:
                        ch_pb = m_pb.chapters.add()
                        copy_chapter_model_to_pb(ch_pb, ch_model)
                        hist_pb = m_pb.history.add()
                        copy_history_model_to_pb(hist_pb, hist_model)

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
