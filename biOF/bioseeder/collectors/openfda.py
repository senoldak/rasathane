from datetime import date, datetime
from typing import Any, Dict, List, Optional
from bioseeder.collectors.base import BaseCollector
from bioseeder.config import get_settings


class OpenFDACollector(BaseCollector):
    """openFDA drug approvals, 510(k), and regulatory feed collector."""

    def __init__(self):
        settings = get_settings()
        super().__init__(base_url=settings.OPENFDA_BASE_URL)
        self.api_key = settings.OPENFDA_API_KEY

    async def fetch_drug_approvals(
        self,
        search_term: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Fetch drug approvals from openFDA Drugs@FDA endpoint."""
        params: Dict[str, Any] = {"limit": limit}
        if self.api_key:
            params["api_key"] = self.api_key

        if search_term:
            params["search"] = search_term

        payload = await self.get("drug/drugsfda.json", params=params)
        return self.parse_approvals(payload)

    def parse_approvals(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse openFDA drug approval results into normalized records."""
        results = payload.get("results", [])
        parsed_records = []

        for item in results:
            app_no = item.get("application_number", "")
            sponsor = item.get("sponsor_name", "")

            products = item.get("products", [])
            brand_name = ""
            active_ingredient = ""
            dosage_form = ""
            if products:
                prod = products[0]
                brand_name = prod.get("brand_name", "")
                dosage_form = prod.get("dosage_form", "")
                active_ing_list = prod.get("active_ingredients", [])
                if active_ing_list:
                    active_ingredient = active_ing_list[0].get("name", "")

            submissions = item.get("submissions", [])
            submission_status = ""
            parsed_date: Optional[date] = None
            submission_type = ""

            if submissions:
                sorted_subs = sorted(
                    submissions,
                    key=lambda s: s.get("submission_status_date") or "",
                    reverse=True,
                )
                sub = sorted_subs[0]
                submission_status = sub.get("submission_status", "")
                submission_type = sub.get("submission_type", "")
                date_str = sub.get("submission_status_date")
                if date_str and len(date_str) == 8:
                    try:
                        parsed_date = datetime.strptime(date_str, "%Y%m%d").date()
                    except ValueError:
                        parsed_date = None

            parsed_records.append({
                "application_number": app_no,
                "sponsor_name": sponsor,
                "brand_name": brand_name,
                "active_ingredient": active_ingredient,
                "dosage_form": dosage_form,
                "submission_type": submission_type,
                "submission_status": submission_status,
                "status": submission_status,
                "approval_date": parsed_date,
                "raw_payload": item,
            })

        return parsed_records
