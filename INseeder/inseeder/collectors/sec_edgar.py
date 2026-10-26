import re
import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger("inseeder.collectors.sec_edgar")

SEC_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&count=100&output=atom"
DEFAULT_USER_AGENT = "INseeder Research admin@inseeder.local"

def _clean_tag(tag: str) -> str:
    """Strip XML namespace prefix if present."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag

def _get_text(elem: Optional[ET.Element], path: str, default: str = "", ns: Optional[dict] = None) -> str:
    """Helper to safely find child and get text."""
    if elem is None:
        return default
    child = elem.find(path, ns) if ns else elem.find(path)
    if child is not None and child.text:
        return child.text.strip()
    return default

def _get_nested_value(elem: Optional[ET.Element], path: str, default: str = "") -> str:
    """Helper for SEC Form 4 elements that wrap values in <value>...</value>."""
    if elem is None:
        return default
    target = elem.find(path)
    if target is None:
        return default
    val_elem = target.find("value")
    if val_elem is not None and val_elem.text:
        return val_elem.text.strip()
    if target.text:
        return target.text.strip()
    return default

def _to_bool(val: str) -> bool:
    return val in ("1", "true", "True", "Y", "yes")

def parse_atom_feed(atom_content: str) -> List[Dict[str, Any]]:
    """Parse SEC EDGAR Atom feed to extract recent Form 4 filings."""
    entries = []
    try:
        root = ET.fromstring(atom_content)
    except ET.ParseError as e:
        logger.error(f"Failed to parse Atom feed XML: {e}")
        return entries

    ns = {}
    if root.tag.startswith("{"):
        ns_uri = root.tag.split("}")[0].strip("{")
        ns = {"atom": ns_uri}

    entry_nodes = root.findall("atom:entry", ns) if ns else root.findall("entry")

    for entry in entry_nodes:
        if ns:
            title = _get_text(entry, "atom:title", ns=ns)
            updated = _get_text(entry, "atom:updated", ns=ns)
            link_node = entry.find("atom:link", ns)
            id_text = _get_text(entry, "atom:id", ns=ns)
            summary_text = _get_text(entry, "atom:summary", ns=ns)
        else:
            title = _get_text(entry, "title")
            updated = _get_text(entry, "updated")
            link_node = entry.find("link")
            id_text = _get_text(entry, "id")
            summary_text = _get_text(entry, "summary")

        index_url = link_node.attrib.get("href", "") if link_node is not None else ""

        # Extract accession number from id or summary or index_url
        accession_no = ""
        acc_match = re.search(r"accession-number=([0-9\-]+)", id_text)
        if not acc_match:
            acc_match = re.search(r"AccNo:\s*</b>\s*([0-9\-]+)", summary_text)
        if not acc_match and index_url:
            acc_match = re.search(r"/([0-9]{10}\-[0-9]{2}\-[0-9]{6})", index_url)
        
        if acc_match:
            accession_no = acc_match.group(1)

        if accession_no and index_url:
            entries.append({
                "accession_no": accession_no,
                "index_url": index_url,
                "title": title,
                "updated": updated
            })

    return entries

def parse_form4_xml(xml_content: str, accession_no: str, sec_url: str) -> List[Dict[str, Any]]:
    """
    Parse SEC Form 4 XML and extract non-derivative transaction records.
    Returns a list of trade dictionaries ready for database insertion.
    """
    trades = []
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        logger.error(f"Error parsing Form 4 XML for {accession_no}: {e}")
        return trades

    # 1. Issuer details
    issuer = root.find("issuer")
    ticker = _get_text(issuer, "issuerTradingSymbol").upper()
    company_name = _get_text(issuer, "issuerName")

    # 2. Reporting Owner details
    rpt_owner = root.find("reportingOwner")
    insider_name = ""
    is_director = False
    is_officer = False
    is_ten_percent = False
    officer_title = ""

    if rpt_owner is not None:
        owner_id = rpt_owner.find("reportingOwnerId")
        insider_name = _get_text(owner_id, "rptOwnerName")

        rel = rpt_owner.find("reportingOwnerRelationship")
        if rel is not None:
            is_director = _to_bool(_get_text(rel, "isDirector", "0"))
            is_officer = _to_bool(_get_text(rel, "isOfficer", "0"))
            is_ten_percent = _to_bool(_get_text(rel, "isTenPercentOwner", "0"))
            officer_title = _get_text(rel, "officerTitle", "")

    # 3. Check for 10b5-1 indicators in footnotes or root
    is_10b5_1 = False
    footnotes_elem = root.find("footnotes")
    if footnotes_elem is not None:
        for fn in footnotes_elem.findall("footnote"):
            if fn.text and ("10b5-1" in fn.text.lower() or "10b5" in fn.text.lower()):
                is_10b5_1 = True
                break

    filing_period = _get_text(root, "periodOfReport")

    # 4. Non-derivative Transactions
    non_deriv = root.find("nonDerivativeTable")
    if non_deriv is not None:
        for trans in non_deriv.findall("nonDerivativeTransaction"):
            # Date
            trans_date = _get_nested_value(trans, "transactionDate", filing_period)

            # Code
            coding = trans.find("transactionCoding")
            trans_code = _get_text(coding, "transactionCode", "")
            if not trans_code:
                # Fallback to direct child
                trans_code = _get_nested_value(trans, "transactionCode", "P")

            # Check 10b5-1 flag if present (SEC rule10b5One flag)
            rule_10b5_flag = _get_text(coding, "rule10b5One", "") or _get_text(trans, "rule10b5One", "") or _get_text(root, "rule10b5One", "")
            if _to_bool(rule_10b5_flag):
                is_10b5_1 = True

            # Amounts
            amounts = trans.find("transactionAmounts")
            shares_str = _get_nested_value(amounts, "transactionShares", "0")
            price_str = _get_nested_value(amounts, "transactionPricePerShare", "0")
            
            try:
                shares = float(shares_str.replace(",", ""))
            except ValueError:
                shares = 0.0

            try:
                price = float(price_str.replace(",", "").replace("$", ""))
            except ValueError:
                price = 0.0

            value = shares * price

            # Post transaction amounts
            post_amounts = trans.find("postTransactionAmounts")
            owned_after_str = _get_nested_value(post_amounts, "sharesOwnedFollowingTransaction", "0")
            try:
                shares_owned_after = float(owned_after_str.replace(",", ""))
            except ValueError:
                shares_owned_after = 0.0

            trade_record = {
                "accession_no": f"{accession_no}_{len(trades)+1}" if len(trades) > 0 else accession_no,
                "filing_date": filing_period or trans_date,
                "trade_date": trans_date,
                "ticker": ticker,
                "company_name": company_name,
                "insider_name": insider_name,
                "insider_title": officer_title,
                "is_director": is_director,
                "is_officer": is_officer,
                "is_ten_percent": is_ten_percent,
                "transaction_code": trans_code,
                "shares": shares,
                "price": price,
                "value": value,
                "shares_owned_after": shares_owned_after,
                "is_10b5_1": is_10b5_1,
                "sec_url": sec_url
            }
            trades.append(trade_record)

    return trades

_XML_BLOCK_RE = re.compile(r"<XML>\s*(.*?)\s*</XML>", re.DOTALL | re.IGNORECASE)
_NEGATION_RE = re.compile(r"\b(not|no)\b", re.IGNORECASE)


def extract_form4_xml(submission_text: str) -> Optional[str]:
    """Return the first ownershipDocument XML block from a full EDGAR submission (.txt)."""
    for match in _XML_BLOCK_RE.finditer(submission_text):
        block = match.group(1).strip()
        if "<ownershipDocument" in block:
            return block
    return None


def _footnotes_mention_plan(root: ET.Element) -> bool:
    """True if a footnote says trades were made under a 10b5-1 plan (negated mentions ignored)."""
    footnotes_elem = root.find("footnotes")
    if footnotes_elem is None:
        return False
    for fn in footnotes_elem.findall("footnote"):
        text = " ".join(fn.itertext())
        for m in re.finditer(r"10b5-1", text, re.IGNORECASE):
            if not _NEGATION_RE.search(text[max(0, m.start() - 60):m.start()]):
                return True
    return False


def _to_float(raw: str) -> float:
    try:
        return float(raw.replace(",", "").replace("$", ""))
    except ValueError:
        return 0.0


def parse_form4_beyan(xml_content: str) -> Optional[Dict[str, Any]]:
    """
    Parse a Form 4 into one filing-level record for the Rasathane channel:
    all reporting owners, 10b5-1 status, and non-derivative rows aggregated per
    transaction code. Returns None if the XML cannot be parsed.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        logger.warning(f"Error parsing Form 4 XML: {e}")
        return None

    issuer = root.find("issuer")
    owners = []
    for rpt_owner in root.findall("reportingOwner"):
        owner_id = rpt_owner.find("reportingOwnerId")
        rel = rpt_owner.find("reportingOwnerRelationship")
        owners.append({
            "cik": _get_text(owner_id, "rptOwnerCik"),
            "name": _get_text(owner_id, "rptOwnerName"),
            "title": _get_text(rel, "officerTitle"),
            "is_director": _to_bool(_get_text(rel, "isDirector", "0")),
            "is_officer": _to_bool(_get_text(rel, "isOfficer", "0")),
            "is_ten_percent": _to_bool(_get_text(rel, "isTenPercentOwner", "0")),
        })

    aff = root.find("aff10b5One")
    if aff is not None and aff.text and aff.text.strip():
        plan_10b5_1 = _to_bool(aff.text.strip())
    else:
        plan_10b5_1 = _footnotes_mention_plan(root)

    by_code: Dict[str, Dict[str, Any]] = {}
    skipped_rows = 0
    non_deriv = root.find("nonDerivativeTable")
    rows = non_deriv.findall("nonDerivativeTransaction") if non_deriv is not None else []
    for trans in rows:
        code = _get_text(trans.find("transactionCoding"), "transactionCode")
        if code not in ("P", "S"):
            continue
        amounts = trans.find("transactionAmounts")
        shares = _to_float(_get_nested_value(amounts, "transactionShares", "0"))
        price = _to_float(_get_nested_value(amounts, "transactionPricePerShare", "0"))
        if shares <= 0 or price <= 0:
            skipped_rows += 1
            continue
        owned_raw = _get_nested_value(trans.find("postTransactionAmounts"), "sharesOwnedFollowingTransaction", "")
        agg = by_code.setdefault(code, {"shares": 0.0, "value": 0.0, "avg_price": 0.0, "owned_after": None})
        agg["shares"] += shares
        agg["value"] += shares * price
        agg["avg_price"] = agg["value"] / agg["shares"]
        agg["owned_after"] = _to_float(owned_raw) if owned_raw else None

    return {
        "ticker": _get_text(issuer, "issuerTradingSymbol").upper(),
        "company_name": _get_text(issuer, "issuerName"),
        "owners": owners,
        "plan_10b5_1": plan_10b5_1,
        "by_code": by_code,
        "skipped_rows": skipped_rows,
    }


class SecEdgarCollector:
    """Async collector for SEC EDGAR Form 4 filings adhering to SEC Fair Access."""

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, poll_interval_sec: float = 30.0):
        self.user_agent = user_agent
        self.poll_interval_sec = poll_interval_sec
        self.client = httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            timeout=15.0,
            follow_redirects=True
        )

    async def fetch_feed(self) -> List[Dict[str, Any]]:
        """Fetch the current Form 4 Atom feed."""
        try:
            resp = await self.client.get(SEC_FEED_URL)
            if resp.status_code == 200:
                return parse_atom_feed(resp.text)
            elif resp.status_code == 429:
                logger.warning("SEC Rate limit hit (HTTP 429). Backing off.")
            else:
                logger.warning(f"SEC feed returned status {resp.status_code}")
        except Exception as e:
            logger.error(f"Error fetching SEC feed: {e}")
        return []

    async def fetch_form4_xml(self, index_url: str) -> Optional[str]:
        """
        Given a filing index URL, locate the Form 4 XML file and download it.
        Example index: https://www.sec.gov/Archives/edgar/data/1234567/000123456726000001/0001234567-26-000001-index.htm
        XML is typically form4.xml or doc4.xml or {accession}.xml in that folder.
        """
        try:
            # First fetch index page to find the exact .xml link
            resp = await self.client.get(index_url)
            if resp.status_code != 200:
                return None
            
            # Find xml file link in index page, strictly avoiding XSL-rendered HTML pseudo-XML views
            all_xml_matches = re.findall(r'href=["\']([^"\']+\.xml)["\']', resp.text, re.IGNORECASE)
            raw_xml_matches = [m for m in all_xml_matches if "xsl" not in m.lower()]
            
            xml_rel = None
            if raw_xml_matches:
                # Prefer files named form4, doc4, ownership or primary_doc
                priority_matches = [
                    m for m in raw_xml_matches
                    if any(k in m.lower() for k in ("form4", "doc4", "ownership", "primary_doc"))
                ]
                xml_rel = priority_matches[0] if priority_matches else raw_xml_matches[0]

            if xml_rel:
                if xml_rel.startswith("http"):
                    xml_url = xml_rel
                elif xml_rel.startswith("/"):
                    xml_url = f"https://www.sec.gov{xml_rel}"
                else:
                    base_url = index_url.rsplit("/", 1)[0]
                    xml_url = f"{base_url}/{xml_rel}"
                
                # Fetch XML
                await asyncio.sleep(0.1) # Fair access throttling
                xml_resp = await self.client.get(xml_url)
                if xml_resp.status_code == 200:
                    return xml_resp.text
        except Exception as e:
            logger.error(f"Error downloading Form 4 XML from {index_url}: {e}")
        return None

    async def close(self):
        await self.client.aclose()
