"""Provider registry."""

from __future__ import annotations

from indiasearchbench.providers.apify import ApifyProvider
from indiasearchbench.providers.base import NormalizedResult, Provider
from indiasearchbench.providers.exa import ExaProvider
from indiasearchbench.providers.searchapi import SearchApiProvider
from indiasearchbench.providers.serpapi import SerpApiProvider
from indiasearchbench.providers.serper import SerperProvider

PROVIDERS: dict[str, type[Provider]] = {
    cls.name: cls
    for cls in (SerpApiProvider, SerperProvider, ExaProvider, ApifyProvider, SearchApiProvider)
}

__all__ = ["PROVIDERS", "NormalizedResult", "Provider"]
