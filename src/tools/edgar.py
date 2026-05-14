from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict

import httpx

FilingType = Literal["10-K", "10-Q", "8-K"]

SEC_BASE_URL = "https://data.sec.gov"
SEC_ARCHIVES_BASE_URL = "https://www.sec.gov/Archives/edgar/data"
DEFAULT_CACHE_DIR = Path(".cache") / "filings"
DEFAULT_USER_AGENT = "FerryEroukAIResearch/1.0"
MIN_REQUEST_INTERVAL_SECONDS = 0.11


class FilingMetadata(TypedDict):
    cik: str
    accession_number: str
    filing_type: FilingType
    filing_date: str
    primary_document: str
    filing_url: str


@dataclass
class EdgarClient:
    user_agent: str | None = None
    cache_dir: Path = DEFAULT_CACHE_DIR
    timeout: float = 30.0
    min_request_interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS

    def __post_init__(self) -> None:
        self.user_agent = self.user_agent or os.getenv("USER_AGENT", DEFAULT_USER_AGENT)
        self.cache_dir = Path(self.cache_dir)
        self._last_request_at = 0.0

    def get_company_submissions(self, cik: str) -> dict[str, Any]:
        normalized_cik = normalize_cik(cik)
        cache_path = self.cache_dir / "submissions" / f"CIK{normalized_cik}.json"

        cached = read_json_cache(cache_path)
        if cached is not None:
            return cached

        url = f"{SEC_BASE_URL}/submissions/CIK{normalized_cik}.json"
        response = self._get(url)
        response.raise_for_status()
        payload = response.json()
        write_json_cache(cache_path, payload)
        return payload

    def get_latest_filing_metadata(self, cik: str, filing_type: FilingType) -> FilingMetadata | None:
        submissions = self.get_company_submissions(cik)
        recent = submissions.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])

        for index, form in enumerate(forms):
            if form != filing_type:
                continue

            accession_number = recent["accessionNumber"][index]
            normalized_cik = normalize_cik(cik)
            accession_without_dashes = accession_number.replace("-", "")
            primary_document = recent["primaryDocument"][index]

            return {
                "cik": normalized_cik,
                "accession_number": accession_number,
                "filing_type": filing_type,
                "filing_date": recent["filingDate"][index],
                "primary_document": primary_document,
                "filing_url": (
                    f"{SEC_ARCHIVES_BASE_URL}/{int(normalized_cik)}/{accession_without_dashes}/{primary_document}"
                ),
            }

        return None

    def get_filing_text(self, metadata: FilingMetadata) -> str:
        cache_path = (
            self.cache_dir
            / "documents"
            / metadata["cik"]
            / metadata["accession_number"].replace("-", "")
            / metadata["primary_document"]
        )

        cached = read_text_cache(cache_path)
        if cached is not None:
            return cached

        response = self._get(metadata["filing_url"])
        response.raise_for_status()
        text = response.text
        write_text_cache(cache_path, text)
        return text

    def _get(self, url: str) -> httpx.Response:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_request_interval_seconds:
            time.sleep(self.min_request_interval_seconds - elapsed)

        headers = {
            "User-Agent": self.user_agent or DEFAULT_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
        }
        response = httpx.get(url, headers=headers, timeout=self.timeout)
        self._last_request_at = time.monotonic()
        return response


def normalize_cik(cik: str | int) -> str:
    digits = "".join(character for character in str(cik) if character.isdigit())
    if not digits:
        raise ValueError("CIK must contain at least one digit.")
    return digits.zfill(10)


def read_json_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_text_cache(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def write_text_cache(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
