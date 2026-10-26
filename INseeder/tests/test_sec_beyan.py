import os

from inseeder.collectors.sec_edgar import (
    extract_form4_xml,
    parse_form4_beyan,
    parse_form4_xml,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name: str) -> str:
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as f:
        return f.read()


def test_extract_form4_xml_from_submission():
    xml = extract_form4_xml(_read("submission_sample.txt"))
    assert xml is not None
    assert "<ownershipDocument" in xml
    assert "<XML>" not in xml
    assert xml.startswith("<?xml")


def test_extract_form4_xml_missing_returns_none():
    assert extract_form4_xml("no xml here") is None


def test_extract_form4_xml_skips_non_ownership_blocks():
    text = "<XML>\n<other/>\n</XML>\n" + _read("submission_sample.txt")
    xml = extract_form4_xml(text)
    assert xml is not None and "<ownershipDocument" in xml


def test_parse_beyan_multiple_owners_and_aggregation():
    b = parse_form4_beyan(_read("form4_coklu_sahip.xml"))
    assert b is not None
    assert b["ticker"] == "KRNT"
    assert b["company_name"] == "KORNET HOLDINGS INC"
    assert len(b["owners"]) == 2
    assert {o["cik"] for o in b["owners"]} == {"0000000001", "0000000002"}
    cfo = [o for o in b["owners"] if o["cik"] == "0000000001"][0]
    assert cfo["title"] == "Chief Financial Officer"
    assert cfo["is_officer"] is True
    p = b["by_code"]["P"]
    assert p["shares"] == 4000
    assert p["value"] == 46000
    assert p["avg_price"] == 11.5
    assert p["owned_after"] == 9000
    assert b["plan_10b5_1"] is False
    assert b["skipped_rows"] == 0


def test_parse_beyan_aff10b5one_and_zero_price():
    b = parse_form4_beyan(_read("form4_aff10b5.xml"))
    assert b is not None
    assert b["plan_10b5_1"] is True
    assert "P" not in b["by_code"]
    assert b["skipped_rows"] == 1
    assert b["by_code"]["S"]["value"] == 10_000_000


def test_parse_beyan_aff10b5one_zero_overrides_footnote():
    xml = _read("form4_aff10b5.xml").replace(
        "<aff10b5One>1</aff10b5One>", "<aff10b5One>0</aff10b5One>"
    ).replace("Weighted average price.", "Sold pursuant to a Rule 10b5-1 plan.")
    assert parse_form4_beyan(xml)["plan_10b5_1"] is False


def test_parse_beyan_footnote_positive_plan():
    xml = _read("form4_coklu_sahip.xml").replace(
        "The reporting person did not trade pursuant to a Rule 10b5-1 plan.",
        "The transactions were effected pursuant to a Rule 10b5-1 trading plan adopted on May 1, 2026.",
    )
    assert parse_form4_beyan(xml)["plan_10b5_1"] is True


def test_parse_beyan_invalid_xml_returns_none():
    assert parse_form4_beyan("<ownershipDocument><broken") is None


def test_existing_parser_unchanged():
    trades = parse_form4_xml(_read("sample_form4.xml"), "0001234567-26-000001", "https://www.sec.gov/x")
    assert len(trades) == 1
