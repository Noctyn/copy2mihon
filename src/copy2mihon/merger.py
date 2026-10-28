"""Merge CopyManga cloud subscriptions and reading history into an existing .tachibk backup."""

from __future__ import annotations

import gzip
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

from copy2mihon.converter import (
    comic_dict_to_mihon_manga,
    create_chapter_and_history,
    parse_category_names,
    parse_chapter_number,
    parse_datetime_to_ms,
)
from copy2mihon.models import (
    DEFAULT_COPYMANGA_SOURCE_ID,
    DEFAULT_COPYMANGA_SOURCE_NAME,
    MihonManga,
)
from copy2mihon.parser import (
    extract_chapter_ref,
    extract_path_word,
    extract_read_time,
    normalize_path_word,
    repair_mojibake,
)
from copy2mihon.proto import schema_mihon_pb2
from copy2mihon.proto.serializer import (
    copy_chapter_model_to_pb,
    copy_history_model_to_pb,
    copy_manga_model_to_pb,
    read_tachibk,
)


def _is_canonical_chapter_url(url: str) -> bool:
    """Prefer /comic/... rows over malformed legacy URLs missing the prefix."""
    return (url or "").startswith("/comic/")


def _chapter_url_key(url: str) -> str:
    clean = (url or "").rstrip("/")
    if "/chapter/" not in clean.lower():
        return ""
    return clean.rsplit("/", 1)[-1].lower()


def _same_chapter_url(a: str, b: str) -> bool:
    if a == b:
        return True
    key = _chapter_url_key(a)
    return bool(key) and key == _chapter_url_key(b)


def _copy_manga_with_children(
    m_pb: schema_mihon_pb2.BackupManga,
    model: MihonManga,
) -> None:
    """Copy a manga model including its chapters and history into a BackupManga message."""
    copy_manga_model_to_pb(m_pb, model)
    for ch in model.chapters:
        copy_chapter_model_to_pb(m_pb.chapters.add(), ch)
    for hist in model.history:
        copy_history_model_to_pb(m_pb.history.add(), hist)


def _append_chapter_and_history(
    m_pb: schema_mihon_pb2.BackupManga,
    path_word: str,
    chapter_id: str,
    chapter_name: str,
    read_time_ms: int,
    stats: Dict[str, int],
) -> None:
    """Append a missing chapter (marked read) plus its history entry."""
    ch_model, hist_model = create_chapter_and_history(
        path_word=path_word,
        chapter_id=chapter_id,
        chapter_name=chapter_name,
        read_time_ms=read_time_ms,
    )
    if not ch_model or not hist_model:
        return
    if any(_same_chapter_url(ch.url, ch_model.url) for ch in m_pb.chapters):
        return

    copy_chapter_model_to_pb(m_pb.chapters.add(), ch_model)
    copy_history_model_to_pb(m_pb.history.add(), hist_model)
    stats["chapters_marked_read"] += 1
    stats["updated_history"] += 1


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
            _copy_manga_with_children(m_pb, new_m)
            manga_by_path_word[pw] = m_pb
            stats["new_manga_added"] += 1

    # 4. Merge reading history
    if browse_history_items:
        for b_item in browse_history_items:
            comic_data = b_item.get("comic", {})
            pw = extract_path_word(b_item, comic_data, fallback=True)

            last_ch_id, last_ch_name = extract_chapter_ref(b_item, comic_data)
            # Keep 0 for missing timestamps so existing lastRead values are preserved
            read_time_raw = extract_read_time(b_item, comic_data)
            read_time_ms = parse_datetime_to_ms(read_time_raw) if read_time_raw else 0

            if pw in manga_by_path_word:
                m = manga_by_path_word[pw]

                if len(m.chapters) > 0:
                    matched_indices: List[int] = []

                    # 1. Exact match by last segment of chapter URL (avoid substring collisions)
                    if last_ch_id:
                        target_id_clean = last_ch_id.strip().lower()
                        for idx, ch in enumerate(m.chapters):
                            ch_url_id = ch.url.rstrip("/").rsplit("/", 1)[-1].strip().lower()
                            if ch_url_id == target_id_clean:
                                matched_indices.append(idx)

                    # 2. Fallback: match by chapter number from repaired name
                    if not matched_indices and last_ch_name:
                        target_val = parse_chapter_number(last_ch_name)
                        if target_val > 0:
                            for idx, ch in enumerate(m.chapters):
                                if abs(ch.chapterNumber - target_val) < 0.01:
                                    matched_indices.append(idx)

                    # Duplicate rows are the same chapter; prefer a canonical URL
                    # so the history entry is not rewritten to a malformed one.
                    if matched_indices:
                        matched_indices.sort(
                            key=lambda idx: 0 if _is_canonical_chapter_url(m.chapters[idx].url) else 1
                        )

                    if matched_indices:
                        target_url = m.chapters[matched_indices[0]].url
                        changed = False
                        any_unread = False

                        for idx in matched_indices:
                            target_ch = m.chapters[idx]
                            if not target_ch.read:
                                target_ch.read = True
                                if target_ch.lastPageRead == 0:
                                    target_ch.lastPageRead = 1
                                any_unread = True
                                changed = True

                        if any_unread:
                            stats["chapters_marked_read"] += 1

                        existing_hist = next(
                            (h for h in m.history if _same_chapter_url(h.url, target_url)),
                            None,
                        )
                        if existing_hist:
                            if read_time_ms > 0 and read_time_ms > existing_hist.lastRead:
                                existing_hist.lastRead = read_time_ms
                                changed = True
                        else:
                            hist_pb = m.history.add()
                            hist_pb.url = target_url
                            hist_pb.lastRead = read_time_ms or int(time.time() * 1000)
                            hist_pb.readDuration = 0
                            changed = True

                        if changed:
                            stats["updated_history"] += 1
                    elif last_ch_id:
                        # Chapter missing from Mihon's list (e.g. not refreshed yet):
                        # keep the progress instead of dropping it silently.
                        _append_chapter_and_history(
                            m, pw, last_ch_id, last_ch_name, read_time_ms, stats
                        )
                elif last_ch_id:
                    _append_chapter_and_history(
                        m, pw, last_ch_id, last_ch_name, read_time_ms, stats
                    )
            else:
                if last_ch_id:
                    new_m = comic_dict_to_mihon_manga(
                        item=b_item,
                        source_id=source_id,
                        category_ids=[],
                        is_favorite=False,
                    )
                    m_pb = backup_pb.backupManga.add()
                    _copy_manga_with_children(m_pb, new_m)
                    manga_by_path_word[pw] = m_pb
                    stats["new_manga_added"] += 1
                    if new_m.chapters:
                        stats["chapters_marked_read"] += 1
                    stats["updated_history"] += 1

    # 5. Ensure the CopyManga source entry exists so Mihon can resolve its name
    if not any(src.sourceId == source_id for src in backup_pb.backupSources):
        src = backup_pb.backupSources.add()
        src.name = DEFAULT_COPYMANGA_SOURCE_NAME
        src.sourceId = source_id

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

    output_path = Path(output_backup_path)
    if not output_path.suffix:
        output_path = output_path.with_suffix(".tachibk")

    serialized_bytes = modified_pb.SerializeToString()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output_path, "wb") as f:
        f.write(serialized_bytes)

    return output_path, stats
