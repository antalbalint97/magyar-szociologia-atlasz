"""Source registry: config/sources.yaml is the only place source URLs live."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models.enums import InstitutionType

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = REPO_ROOT / "config" / "sources.yaml"


class CrawlPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    respect_robots: bool = True
    min_delay_seconds: float = 3.0
    max_pages_per_run: int = 400
    timeout_seconds: float = 30.0
    max_age_days: int = 30  # reuse a raw snapshot younger than this instead of refetching
    user_agent: str = (
        "MagyarSzociologiaAtlasz/0.1 (academic research; "
        "+https://github.com/antalbalint97/magyar-szociologia-atlasz)"
    )


class InstitutionSeed(BaseModel):
    """A curated institution record. Facts here are MANUAL claims and need a verify_url."""

    model_config = ConfigDict(extra="forbid")
    key: str
    canonical_name: str
    english_name: str | None = None
    alternate_names: list[str] = Field(default_factory=list)
    institution_type: InstitutionType
    city: str | None = None
    website: str | None = None
    parent: str | None = None  # key of parent institution
    verify_url: str | None = None
    notes: str | None = None


class SourceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    institution: str  # InstitutionSeed.key
    unit_name: str | None = None  # the organisational unit this site represents
    unit_english_name: str | None = None
    unit_type: str | None = None
    base_url: str | None = None
    host_aliases: list[str] = Field(default_factory=list)
    source_type: str = "institutional_website"
    adapter: str | None = None
    adapter_config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = False
    scope: str = "core"  # core | adjacent (e.g. law institute: socio-legal overlap only)
    crawl_policy: CrawlPolicy | None = None
    verified: bool = False  # True once a person has confirmed the URLs exist
    last_successful_run: str | None = None  # informational; runs are logged in data/raw
    notes: str | None = None


class Registry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str
    crawl_defaults: CrawlPolicy = Field(default_factory=CrawlPolicy)
    institutions: list[InstitutionSeed]
    sources: list[SourceEntry]

    @model_validator(mode="after")
    def _refs(self) -> Registry:
        keys = {i.key for i in self.institutions}
        if len(keys) != len(self.institutions):
            raise ValueError("duplicate institution keys")
        for i in self.institutions:
            if i.parent and i.parent not in keys:
                raise ValueError(f"{i.key}: unknown parent {i.parent}")
        ids = [s.source_id for s in self.sources]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate source_id")
        for s in self.sources:
            if s.institution not in keys:
                raise ValueError(f"{s.source_id}: unknown institution {s.institution}")
            if s.enabled and not s.adapter:
                raise ValueError(f"{s.source_id}: enabled source needs an adapter")
        return self

    def source(self, source_id: str) -> SourceEntry:
        for s in self.sources:
            if s.source_id == source_id:
                return s
        raise KeyError(source_id)

    def institution(self, key: str) -> InstitutionSeed:
        for i in self.institutions:
            if i.key == key:
                return i
        raise KeyError(key)

    def policy(self, entry: SourceEntry) -> CrawlPolicy:
        if entry.crawl_policy is None:
            return self.crawl_defaults
        merged = self.crawl_defaults.model_dump() | entry.crawl_policy.model_dump(
            exclude_unset=True
        )
        return CrawlPolicy(**merged)

    def host_aliases(self) -> dict[str, str]:
        """alias host -> canonical host, across every source."""
        from urllib.parse import urlsplit

        out: dict[str, str] = {}
        for s in self.sources:
            if not s.base_url:
                continue
            canonical = (urlsplit(s.base_url).hostname or "").lower()
            for a in s.host_aliases:
                out[a.lower()] = canonical
        return out


def load_registry(path: Path | str = DEFAULT_REGISTRY) -> Registry:
    with open(path, encoding="utf-8") as fh:
        return Registry.model_validate(yaml.safe_load(fh))
