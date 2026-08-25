"""Data models for Mihon backup domain entities.

Field aliases follow the camelCase naming used by the Mihon backup schema
(proto/schema_mihon.proto) so that model_dump(by_alias=True) produces
export-ready JSON keys.
"""

from __future__ import annotations

import time
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_COPYMANGA_SOURCE_ID = 6696312508930833206
DEFAULT_COPYMANGA_SOURCE_NAME = "拷贝漫画"


class MihonCategory(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    id: int = 1
    order: int = 0
    flags: int = 0


class MihonSource(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source_id: int = Field(default=DEFAULT_COPYMANGA_SOURCE_ID, alias="sourceId")
    name: str = DEFAULT_COPYMANGA_SOURCE_NAME


class MihonChapter(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    url: str
    name: str
    scanlator: Optional[str] = None
    read: bool = True
    bookmark: bool = False
    last_page_read: int = Field(default=0, alias="lastPageRead")
    date_fetch: int = Field(
        default_factory=lambda: int(time.time() * 1000), alias="dateFetch"
    )
    date_upload: int = Field(
        default_factory=lambda: int(time.time() * 1000), alias="dateUpload"
    )
    chapter_number: float = Field(default=0.0, alias="chapterNumber")
    source_order: int = Field(default=0, alias="sourceOrder")
    last_modified_at: Optional[int] = Field(default=None, alias="lastModifiedAt")
    version: Optional[int] = None
    memo: List[bytes] = Field(default_factory=lambda: [b"{}"])


class MihonHistory(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    url: str
    last_read: int = Field(
        default_factory=lambda: int(time.time() * 1000), alias="lastRead"
    )
    read_duration: int = Field(default=0, alias="readDuration")


class MihonManga(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source: int = DEFAULT_COPYMANGA_SOURCE_ID
    url: str
    title: str
    author: Optional[str] = None
    artist: Optional[str] = None
    description: Optional[str] = None
    genre: List[str] = Field(default_factory=list)
    status: int = 1  # 1 = ONGOING, 2 = COMPLETED
    thumbnail_url: Optional[str] = Field(default=None, alias="thumbnailUrl")
    date_added: int = Field(
        default_factory=lambda: int(time.time() * 1000), alias="dateAdded"
    )
    viewer_flags: int = Field(default=0, alias="viewerFlags")
    chapter_flags: int = Field(default=513, alias="chapterFlags")
    update_strategy: int = Field(default=0, alias="updateStrategy")
    favorite: bool = True
    initialized: bool = True
    version: Optional[int] = None
    categories: List[int] = Field(default_factory=list)
    chapters: List[MihonChapter] = Field(default_factory=list)
    history: List[MihonHistory] = Field(default_factory=list)
    memo: List[bytes] = Field(default_factory=lambda: [b"{}"])


class MihonBackup(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    backup_manga: List[MihonManga] = Field(default_factory=list, alias="backupManga")
    backup_categories: List[MihonCategory] = Field(
        default_factory=list, alias="backupCategories"
    )
    backup_sources: List[MihonSource] = Field(
        default_factory=list, alias="backupSources"
    )
