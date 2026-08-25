"""Data models for CopyManga API structures and Mihon backup domain entities."""

from __future__ import annotations

import time
from typing import Any, List, Optional
from pydantic import BaseModel, Field


DEFAULT_COPYMANGA_SOURCE_ID = 6696312508930833206
DEFAULT_COPYMANGA_SOURCE_NAME = "拷贝漫画"


class CopyMangaAuthor(BaseModel):
    name: str = ""
    path_word: Optional[str] = None


class CopyMangaTheme(BaseModel):
    name: str = ""
    path_word: Optional[str] = None


class CopyMangaRegion(BaseModel):
    name: Optional[str] = None
    value: Optional[int] = None


class CopyMangaComic(BaseModel):
    path_word: str
    name: str
    author: List[Any] = Field(default_factory=list)
    brief: Optional[str] = ""
    cover: Optional[str] = ""
    status: Optional[int] = 0
    theme: List[Any] = Field(default_factory=list)
    region: Optional[Any] = None
    datetime_updated: Optional[str] = None
    datetime_created: Optional[str] = None
    datetime_modifier: Optional[str] = None


class CopyMangaCollectItem(BaseModel):
    comic: Optional[CopyMangaComic] = None
    datetime_modifier: Optional[str] = None
    datetime_created: Optional[str] = None
    last_browse: Optional[dict[str, Any]] = None


class CopyMangaBrowseItem(BaseModel):
    id: Optional[int] = None
    last_chapter_id: Optional[str] = None
    last_chapter_name: Optional[str] = None
    comic: Optional[CopyMangaComic] = None


class MihonCategory(BaseModel):
    name: str
    id: int = 1
    order: int = 0
    flags: int = 0


class MihonSource(BaseModel):
    source_id: int = DEFAULT_COPYMANGA_SOURCE_ID
    name: str = DEFAULT_COPYMANGA_SOURCE_NAME


class MihonChapter(BaseModel):
    url: str
    name: str
    scanlator: Optional[str] = None
    read: bool = True
    bookmark: bool = False
    last_page_read: int = 0
    date_fetch: int = Field(default_factory=lambda: int(time.time() * 1000))
    date_upload: int = Field(default_factory=lambda: int(time.time() * 1000))
    chapter_number: float = 0.0
    source_order: int = 0
    last_modified_at: Optional[int] = None
    version: Optional[int] = None
    memo: List[bytes] = Field(default_factory=lambda: [b"{}"])


class MihonHistory(BaseModel):
    url: str
    last_read: int = Field(default_factory=lambda: int(time.time() * 1000))
    read_duration: int = 0


class MihonManga(BaseModel):
    source: int = DEFAULT_COPYMANGA_SOURCE_ID
    url: str
    title: str
    author: Optional[str] = None
    artist: Optional[str] = None
    description: Optional[str] = None
    genre: List[str] = Field(default_factory=list)
    status: int = 1  # 1 = ONGOING, 2 = COMPLETED
    thumbnail_url: Optional[str] = None
    date_added: int = Field(default_factory=lambda: int(time.time() * 1000))
    categories: List[int] = Field(default_factory=list)
    favorite: bool = True
    initialized: bool = True
    viewer_flags: int = 0
    chapter_flags: int = 513
    update_strategy: int = 0
    version: Optional[int] = 406
    chapters: List[MihonChapter] = Field(default_factory=list)
    history: List[MihonHistory] = Field(default_factory=list)
    memo: List[bytes] = Field(default_factory=lambda: [b"{}"])


class MihonBackup(BaseModel):
    backup_manga: List[MihonManga] = Field(default_factory=list)
    backup_categories: List[MihonCategory] = Field(default_factory=list)
    backup_sources: List[MihonSource] = Field(default_factory=list)
