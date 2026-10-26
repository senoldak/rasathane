import pytest
import os
from inseeder.collectors.sec_edgar import parse_form4_xml, parse_atom_feed

def test_parse_form4_xml():
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_form4.xml")
    with open(fixture_path, "r", encoding="utf-8") as f:
        xml_content = f.read()

    trades = parse_form4_xml(
        xml_content=xml_content,
        accession_no="0001234567-26-000001",
        sec_url="https://www.sec.gov/Archives/edgar/data/sample.xml"
    )

    assert len(trades) == 1
    trade = trades[0]
    assert trade["ticker"] == "XYZ"
    assert trade["company_name"] == "XYZ CORP"
    assert trade["insider_name"] == "DOE JOHN"
    assert trade["insider_title"] == "Chief Executive Officer"
    assert trade["is_officer"] is True
    assert trade["is_director"] is True
    assert trade["is_ten_percent"] is False
    assert trade["transaction_code"] == "P"
    assert trade["shares"] == 10000.0
    assert trade["price"] == 50.0
    assert trade["value"] == 500000.0
    assert trade["shares_owned_after"] == 50000.0
    assert trade["is_10b5_1"] is False

def test_parse_atom_feed():
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_feed.atom")
    with open(fixture_path, "r", encoding="utf-8") as f:
        atom_content = f.read()

    entries = parse_atom_feed(atom_content)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["accession_no"] == "0001234567-26-000001"
    assert "0001234567-26-000001-index.htm" in entry["index_url"]

def test_detect_10b5_1_footnote():
    xml_with_10b5 = """<?xml version="1.0"?>
    <ownershipDocument>
        <issuer><issuerTradingSymbol>ABC</issuerTradingSymbol><issuerName>ABC Inc</issuerName></issuer>
        <reportingOwner>
            <reportingOwnerId><rptOwnerName>Smith</rptOwnerName></reportingOwnerId>
            <reportingOwnerRelationship><isOfficer>1</isOfficer><officerTitle>CFO</officerTitle></reportingOwnerRelationship>
        </reportingOwner>
        <nonDerivativeTable>
            <nonDerivativeTransaction>
                <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
                <transactionAmounts>
                    <transactionShares><value>5000</value></transactionShares>
                    <transactionPricePerShare><value>100.0</value></transactionPricePerShare>
                </transactionAmounts>
                <postTransactionAmounts><sharesOwnedFollowingTransaction><value>20000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
            </nonDerivativeTransaction>
        </nonDerivativeTable>
        <footnotes>
            <footnote id="F1">The sales reported were effected pursuant to a Rule 10b5-1 trading plan.</footnote>
        </footnotes>
    </ownershipDocument>
    """
    trades = parse_form4_xml(xml_with_10b5, "000999-26-000001", "https://sec.gov")
    assert len(trades) == 1
    assert trades[0]["is_10b5_1"] is True

def test_detect_10b5_1_tag_and_equity_swap_distinction():
    # Test 1: XML with <rule10b5One>1</rule10b5One>
    xml_tag = """<?xml version="1.0"?>
    <ownershipDocument>
        <issuer><issuerTradingSymbol>ABC</issuerTradingSymbol><issuerName>ABC Inc</issuerName></issuer>
        <reportingOwner>
            <reportingOwnerId><rptOwnerName>Smith</rptOwnerName></reportingOwnerId>
            <reportingOwnerRelationship><isOfficer>1</isOfficer><officerTitle>CFO</officerTitle></reportingOwnerRelationship>
        </reportingOwner>
        <nonDerivativeTable>
            <nonDerivativeTransaction>
                <transactionCoding>
                    <transactionCode>S</transactionCode>
                    <rule10b5One>1</rule10b5One>
                </transactionCoding>
                <transactionAmounts>
                    <transactionShares><value>1000</value></transactionShares>
                    <transactionPricePerShare><value>50.0</value></transactionPricePerShare>
                </transactionAmounts>
                <postTransactionAmounts><sharesOwnedFollowingTransaction><value>10000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
            </nonDerivativeTransaction>
        </nonDerivativeTable>
    </ownershipDocument>
    """
    trades_tag = parse_form4_xml(xml_tag, "000999-26-000002", "https://sec.gov")
    assert len(trades_tag) == 1
    assert trades_tag[0]["is_10b5_1"] is True

    # Test 2: XML with equitySwapInvolved=1 but NO 10b5-1 tag or footnote
    xml_swap = """<?xml version="1.0"?>
    <ownershipDocument>
        <issuer><issuerTradingSymbol>ABC</issuerTradingSymbol><issuerName>ABC Inc</issuerName></issuer>
        <reportingOwner>
            <reportingOwnerId><rptOwnerName>Smith</rptOwnerName></reportingOwnerId>
            <reportingOwnerRelationship><isOfficer>1</isOfficer><officerTitle>CFO</officerTitle></reportingOwnerRelationship>
        </reportingOwner>
        <nonDerivativeTable>
            <nonDerivativeTransaction>
                <transactionCoding>
                    <transactionCode>P</transactionCode>
                    <equitySwapInvolved>1</equitySwapInvolved>
                </transactionCoding>
                <transactionAmounts>
                    <transactionShares><value>1000</value></transactionShares>
                    <transactionPricePerShare><value>50.0</value></transactionPricePerShare>
                </transactionAmounts>
                <postTransactionAmounts><sharesOwnedFollowingTransaction><value>10000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
            </nonDerivativeTransaction>
        </nonDerivativeTable>
    </ownershipDocument>
    """
    trades_swap = parse_form4_xml(xml_swap, "000999-26-000003", "https://sec.gov")
    assert len(trades_swap) == 1
    assert trades_swap[0]["is_10b5_1"] is False

