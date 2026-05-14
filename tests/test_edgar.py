import json

import httpx

from src.tools import edgar
from src.tools.edgar import EdgarClient, normalize_cik


def test_normalize_cik_zero_pads_digits() -> None:
    assert normalize_cik("320193") == "0000320193"
    assert normalize_cik("CIK 320193") == "0000320193"


def test_company_submissions_are_cached(tmp_path, monkeypatch) -> None:
    calls: list[tuple[str, dict[str, str]]] = []
    payload = {"filings": {"recent": {"form": []}}}

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> httpx.Response:
        calls.append((url, headers))
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(edgar.httpx, "get", fake_get)

    client = EdgarClient(
        user_agent="TestAgent/1.0",
        cache_dir=tmp_path,
        min_request_interval_seconds=0,
    )

    first = client.get_company_submissions("320193")
    second = client.get_company_submissions("320193")

    assert first == payload
    assert second == payload
    assert len(calls) == 1
    assert calls[0][0] == "https://data.sec.gov/submissions/CIK0000320193.json"
    assert calls[0][1]["User-Agent"] == "TestAgent/1.0"
    assert json.loads((tmp_path / "submissions" / "CIK0000320193.json").read_text()) == payload


def test_latest_filing_metadata_uses_recent_matching_form(tmp_path) -> None:
    submissions = {
        "filings": {
            "recent": {
                "form": ["8-K", "10-K"],
                "accessionNumber": ["0000320193-24-000001", "0000320193-23-000106"],
                "filingDate": ["2024-01-01", "2023-11-03"],
                "primaryDocument": ["aapl-8k.htm", "aapl-20230930.htm"],
            }
        }
    }
    cache_path = tmp_path / "submissions" / "CIK0000320193.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(json.dumps(submissions), encoding="utf-8")

    client = EdgarClient(cache_dir=tmp_path)

    metadata = client.get_latest_filing_metadata("320193", "10-K")

    assert metadata == {
        "cik": "0000320193",
        "accession_number": "0000320193-23-000106",
        "filing_type": "10-K",
        "filing_date": "2023-11-03",
        "primary_document": "aapl-20230930.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm",
    }


def test_filing_text_is_cached(tmp_path, monkeypatch) -> None:
    calls: list[str] = []

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> httpx.Response:
        calls.append(url)
        return httpx.Response(200, text="<html>filing</html>", request=httpx.Request("GET", url))

    monkeypatch.setattr(edgar.httpx, "get", fake_get)
    client = EdgarClient(cache_dir=tmp_path, min_request_interval_seconds=0)
    metadata: edgar.FilingMetadata = {
        "cik": "0000320193",
        "accession_number": "0000320193-23-000106",
        "filing_type": "10-K",
        "filing_date": "2023-11-03",
        "primary_document": "aapl-20230930.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm",
    }

    first = client.get_filing_text(metadata)
    second = client.get_filing_text(metadata)

    assert first == "<html>filing</html>"
    assert second == "<html>filing</html>"
    assert calls == [metadata["filing_url"]]
