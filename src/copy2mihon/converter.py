"""Data transformation logic from CopyManga API payloads to Mihon backup objects."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Union

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
from copy2mihon.parser import normalize_path_word, repair_mojibake, stable_fallback_key

logger = logging.getLogger(__name__)


def parse_datetime_to_ms(dt_val: Any) -> int:
    """Parse various datetime representations into milliseconds timestamp."""
    if not dt_val:
        return int(time.time() * 1000)

    if isinstance(dt_val, (int, float)):
        if dt_val < 100_000_000_000:
            return int(dt_val * 1000)
        return int(dt_val)

    if isinstance(dt_val, str):
        val_str = dt_val.strip()
        if val_str.isdigit():
            num = int(val_str)
            if num < 100_000_000_000:
                return num * 1000
            return num

        for fmt in (
            "%Y-%m-%d %H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(val_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue

    return int(time.time() * 1000)


def extract_authors(author_field: Any) -> str:
    """Extract authors into a comma-separated string."""
    if not author_field:
        return ""
    if isinstance(author_field, str):
        return repair_mojibake(author_field.strip())
    if isinstance(author_field, list):
        names = []
        for item in author_field:
            if isinstance(item, dict):
                n = item.get("name") or item.get("author_name") or ""
                if n:
                    names.append(repair_mojibake(str(n).strip()))
            elif isinstance(item, str) and item.strip():
                names.append(repair_mojibake(item.strip()))
        return ", ".join(names)
    return ""


def extract_genres(comic_data: Dict[str, Any]) -> List[str]:
    """Extract genres and tags from a comic dictionary."""
    genres: List[str] = []

    region = comic_data.get("region")
    if isinstance(region, dict):
        reg_name = region.get("name")
        if reg_name:
            genres.append(repair_mojibake(str(reg_name).strip()))
    elif isinstance(region, str) and region.strip():
        genres.append(repair_mojibake(region.strip()))

    theme = comic_data.get("theme")
    if isinstance(theme, list):
        for t in theme:
            if isinstance(t, dict):
                t_name = t.get("name")
                if t_name:
                    genres.append(repair_mojibake(str(t_name).strip()))
            elif isinstance(t, str) and t.strip():
                genres.append(repair_mojibake(t.strip()))

    for key in ("tags", "genres", "types", "categories"):
        val = comic_data.get(key)
        if isinstance(val, list):
            for v in val:
                if isinstance(v, dict):
                    v_name = v.get("name")
                    if v_name:
                        genres.append(repair_mojibake(str(v_name).strip()))
                elif isinstance(v, str) and v.strip():
                    genres.append(repair_mojibake(v.strip()))

    seen = set()
    deduped = []
    for g in genres:
        if g and g not in seen:
            seen.add(g)
            deduped.append(g)
    return deduped


def normalize_status(status_val: Any) -> int:
    """Map comic status to Mihon status int (1=ONGOING, 2=COMPLETED)."""
    if status_val is None:
        return 1

    if isinstance(status_val, dict):
        status_val = status_val.get("value", status_val.get("name", 1))

    if isinstance(status_val, (int, float)):
        s_int = int(status_val)
        if s_int == 0:
            return 1
        elif s_int in (1, 2):
            return 2
        return 1

    if isinstance(status_val, str):
        s_lower = status_val.lower()
        if "完结" in s_lower or "completed" in s_lower or "end" in s_lower:
            return 2
        if "连载" in s_lower or "ongoing" in s_lower:
            return 1

    return 1


def normalize_manga_url(path_word: str) -> str:
    """Format manga URL as '/comic/{path_word}'."""
    clean = normalize_path_word(path_word)
    if not clean:
        return ""
    return f"/comic/{clean}"


def create_chapter_and_history(
    path_word: str,
    chapter_id: Optional[str],
    chapter_name: Optional[str] = None,
    read_time_ms: Optional[int] = None,
) -> tuple[Optional[MihonChapter], Optional[MihonHistory]]:
    """Construct MihonChapter and MihonHistory objects for a given chapter ID."""
    if not chapter_id:
        return None, None

    clean_path = normalize_path_word(path_word)
    chapter_url = f"/comic/{clean_path}/chapter/{chapter_id}"
    ch_name = repair_mojibake(chapter_name) or "阅读历史"
    time_ms = read_time_ms or int(time.time() * 1000)

    ch_num = 0.0
    num_match = re.search(r"(\d+(\.\d+)?)", ch_name)
    if num_match:
        try:
            ch_num = float(num_match.group(1))
        except Exception:
            ch_num = 0.0

    chapter = MihonChapter(
        url=chapter_url,
        name=ch_name,
        read=True,
        last_page_read=1,
        date_fetch=time_ms,
        date_upload=time_ms,
        chapter_number=ch_num,
        source_order=0,
        memo=[b"{}"],
    )

    history = MihonHistory(
        url=chapter_url,
        last_read=time_ms,
        read_duration=0,
    )

    return chapter, history


def comic_dict_to_mihon_manga(
    item: Dict[str, Any],
    source_id: int = DEFAULT_COPYMANGA_SOURCE_ID,
    category_ids: Optional[List[int]] = None,
    is_favorite: bool = True,
) -> MihonManga:
    """Convert a CopyManga payload dictionary to a MihonManga object."""
    comic_data = item.get("comic", item) if isinstance(item, dict) else {}
    if not isinstance(comic_data, dict):
        comic_data = {}

    raw_pw = (
        comic_data.get("path_word")
        or comic_data.get("uuid")
        or comic_data.get("url")
        or item.get("url")
        or (f"id_{comic_data.get('id')}" if comic_data.get("id") else None)
        or (f"name_{comic_data.get('name')}" if comic_data.get("name") else None)
        or ""
    )
    path_word = normalize_path_word(raw_pw)
    if not path_word:
        path_word = stable_fallback_key(item, comic_data)
        logger.warning(f"Could not find valid path_word for item, using stable fallback key: {path_word}")

    url = normalize_manga_url(path_word)

    title = repair_mojibake(
        comic_data.get("name")
        or comic_data.get("title")
        or item.get("title")
        or "Unknown Comic"
    )

    author = extract_authors(
        comic_data.get("author")
        or comic_data.get("authors")
        or item.get("author")
        or item.get("authors")
    )
    artist = extract_authors(comic_data.get("artist") or item.get("artist")) or author

    description = (
        comic_data.get("brief")
        or comic_data.get("description")
        or comic_data.get("intro")
        or item.get("description")
        or ""
    )
    description = repair_mojibake(description)

    thumbnail_url = (
        comic_data.get("cover")
        or comic_data.get("thumbnail_url")
        or comic_data.get("thumb")
        or item.get("thumbnail_url")
        or ""
    )

    status = normalize_status(
        comic_data.get("status")
        or item.get("status")
    )

    genre = extract_genres(comic_data)

    date_added_raw = (
        item.get("datetime_modifier")
        or item.get("datetime_created")
        or comic_data.get("datetime_updated")
        or comic_data.get("datetime_created")
    )
    date_added = parse_datetime_to_ms(date_added_raw)

    categories = (category_ids or []) if is_favorite else []

    memo = []
    if "datetime_modifier" in item:
        memo.append(b"{}")

    manga = MihonManga(
        source=source_id,
        url=url,
        title=title,
        artist=artist,
        author=author,
        description=description,
        genre=genre,
        status=status,
        thumbnail_url=thumbnail_url,
        date_added=date_added,
        viewer_flags=0,
        chapter_flags=513,
        update_strategy=0,
        favorite=is_favorite,
        initialized=True,
        categories=categories,
        chapters=[],
        history=[],
        memo=memo,
    )

    last_chapter_id = item.get("last_chapter_id")
    last_chapter_name = item.get("last_chapter_name")
    if last_chapter_id:
        ch, hist = create_chapter_and_history(
            path_word=path_word,
            chapter_id=last_chapter_id,
            chapter_name=last_chapter_name,
            read_time_ms=date_added,
        )
        if ch:
            manga.chapters.append(ch)
        if hist:
            manga.history.append(hist)

    return manga


def parse_category_names(category_input: Optional[str]) -> List[str]:
    """Parse comma-separated category string into a list of category names."""
    if not category_input:
        return []
    cleaned = category_input.strip()
    if cleaned.lower() in ("none", "null", "no", "无", "false", "0", ""):
        return []
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    return parts


def convert_copymanga_all_to_backup(
    collected_items: List[Dict[str, Any]],
    browse_history_items: Optional[List[Dict[str, Any]]] = None,
    source_id: int = DEFAULT_COPYMANGA_SOURCE_ID,
    source_name: str = DEFAULT_COPYMANGA_SOURCE_NAME,
    category_name: Optional[str] = "拷贝漫画",
) -> MihonBackup:
    """Combine collected comics and reading history into a MihonBackup structure."""
    category_names = parse_category_names(category_name)
    categories: List[MihonCategory] = []
    category_orders: List[int] = []

    for idx, name in enumerate(category_names):
        cat_order = idx
        cat_id = idx + 1
        category_orders.append(cat_order)
        categories.append(
            MihonCategory(
                name=name,
                id=cat_id,
                order=cat_order,
                flags=0,
            )
        )

    manga_by_url: Dict[str, MihonManga] = {}

    for item in collected_items:
        manga = comic_dict_to_mihon_manga(
            item=item,
            source_id=source_id,
            category_ids=category_orders,
            is_favorite=True,
        )
        if manga.url:
            manga_by_url[manga.url] = manga

    if browse_history_items:
        for b_item in browse_history_items:
            comic_data = b_item.get("comic", {})
            raw_pw = (
                comic_data.get("path_word")
                or comic_data.get("uuid")
                or (f"id_{comic_data.get('id')}" if comic_data.get("id") else None)
                or (f"name_{comic_data.get('name')}" if comic_data.get("name") else None)
                or ""
            )
            path_word = normalize_path_word(raw_pw)
            if not path_word:
                path_word = stable_fallback_key(b_item, comic_data)
                logger.warning(f"Could not find valid path_word for history item, using stable fallback key: {path_word}")

            url = normalize_manga_url(path_word)

            last_ch_id = b_item.get("last_chapter_id")
            last_ch_name = b_item.get("last_chapter_name")
            read_time_ms = int(b_item.get("datetime_modifier_ms") or 0)
            if not read_time_ms and b_item.get("datetime_modifier"):
                read_time_ms = parse_datetime_to_ms(b_item.get("datetime_modifier"))

            if url in manga_by_url:
                existing_manga = manga_by_url[url]
                if last_ch_id:
                    ch, hist = create_chapter_and_history(
                        path_word=path_word,
                        chapter_id=last_ch_id,
                        chapter_name=last_ch_name,
                        read_time_ms=read_time_ms,
                    )
                    if ch:
                        existing_manga.chapters = [ch]
                    if hist:
                        existing_manga.history = [hist]
            else:
                manga = comic_dict_to_mihon_manga(
                    item=b_item,
                    source_id=source_id,
                    category_ids=[],
                    is_favorite=False,
                )
                if manga.url:
                    manga_by_url[manga.url] = manga

    sources = [
        MihonSource(
            source_id=source_id,
            name=source_name,
        )
    ]

    return MihonBackup(
        backup_manga=list(manga_by_url.values()),
        backup_categories=categories,
        backup_sources=sources,
    )


def convert_copymanga_list_to_backup(
    items: List[Dict[str, Any]],
    source_id: int = DEFAULT_COPYMANGA_SOURCE_ID,
    source_name: str = DEFAULT_COPYMANGA_SOURCE_NAME,
    category_name: Optional[str] = "拷贝漫画",
) -> MihonBackup:
    """Convert a raw collected comics list to a MihonBackup structure."""
    return convert_copymanga_all_to_backup(
        collected_items=items,
        browse_history_items=None,
        source_id=source_id,
        source_name=source_name,
        category_name=category_name,
    )


def convert_json_file_to_backup(
    input_path: Union[str, Path],
    source_id: int = DEFAULT_COPYMANGA_SOURCE_ID,
    source_name: str = DEFAULT_COPYMANGA_SOURCE_NAME,
    category_name: Optional[str] = "拷贝漫画",
) -> MihonBackup:
    """Convert an existing JSON file to MihonBackup."""
    path = Path(input_path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        if "results" in data and isinstance(data["results"], dict) and "list" in data["results"]:
            items = data["results"]["list"]
        elif "results" in data and isinstance(data["results"], list):
            items = data["results"]
        elif "list" in data and isinstance(data["list"], list):
            items = data["list"]
        elif "backupManga" in data:
            return convert_copymanga_all_to_backup(
                collected_items=data.get("backupManga", []),
                browse_history_items=None,
                source_id=source_id,
                source_name=source_name,
                category_name=category_name,
            )
        else:
            items = [data]
    else:
        raise ValueError(f"Unsupported JSON structure in {input_path}")

    return convert_copymanga_all_to_backup(
        collected_items=items,
        browse_history_items=None,
        source_id=source_id,
        source_name=source_name,
        category_name=category_name,
    )
