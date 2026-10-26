from datetime import date, datetime
from typing import Any, Dict, List, Optional
from bioseeder.collectors.base import BaseCollector
from bioseeder.config import get_settings


class ClinicalTrialsCollector(BaseCollector):
    """ClinicalTrials.gov API v2 collector."""

    def __init__(self):
        settings = get_settings()
        super().__init__(base_url=settings.CLINICALTRIALS_BASE_URL)

    async def fetch_studies(
        self,
        sponsor: Optional[str] = None,
        condition: Optional[str] = None,
        term: Optional[str] = None,
        page_size: int = 50,
    ) -> List[Dict[str, Any]]:
        """Fetch studies from ClinicalTrials.gov API v2."""
        params: Dict[str, Any] = {"pageSize": page_size}
        queries = []
        if sponsor:
            queries.append(f"AREA[LeadSponsorName]{sponsor}")
        if condition:
            queries.append(f"AREA[ConditionSearch]{condition}")
        if term:
            queries.append(term)

        if queries:
            params["query.term"] = " AND ".join(queries)

        payload = await self.get("studies", params=params)
        return self.parse_studies(payload)

    def parse_studies(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse raw ClinicalTrials.gov API v2 JSON into normalized dictionaries."""
        studies = payload.get("studies", [])
        results = []

        phase_map = {
            "EARLY_PHASE1": "Early Phase 1",
            "PHASE1": "Phase 1",
            "PHASE2": "Phase 2",
            "PHASE3": "Phase 3",
            "PHASE4": "Phase 4",
            "NA": "N/A",
        }

        status_map = {
            "RECRUITING": "Recruiting",
            "ACTIVE_NOT_RECRUITING": "Active, not recruiting",
            "COMPLETED": "Completed",
            "ENROLLING_BY_INVITATION": "Enrolling by invitation",
            "NOT_YET_RECRUITING": "Not yet recruiting",
            "SUSPENDED": "Suspended",
            "TERMINATED": "Terminated",
            "WITHDRAWN": "Withdrawn",
        }

        for item in studies:
            protocol = item.get("protocolSection", {})
            ident = protocol.get("identificationModule", {})
            status_mod = protocol.get("statusModule", {})
            design = protocol.get("designModule", {})
            desc = protocol.get("descriptionModule", {})
            arms = protocol.get("armsInterventionsModule", {})

            nct_id = ident.get("nctId")
            if not nct_id:
                continue

            title = ident.get("briefTitle", "")
            raw_phases = design.get("phases", [])
            phase = phase_map.get(raw_phases[0], raw_phases[0]) if raw_phases else "N/A"
            if len(raw_phases) > 1:
                phase = "/".join(phase_map.get(p, p) for p in raw_phases)

            raw_status = status_mod.get("overallStatus", "UNKNOWN")
            status = status_map.get(raw_status, raw_status.title())

            # Parse primary completion date
            comp_struct = status_mod.get("primaryCompletionDateStruct", {})
            date_str = comp_struct.get("date")
            parsed_date: Optional[date] = None
            if date_str:
                for fmt in ("%Y-%m-%d", "%Y-%m", "%B %Y", "%B %d, %Y"):
                    try:
                        parsed_date = datetime.strptime(date_str, fmt).date()
                        break
                    except ValueError:
                        continue

            enrollment_info = design.get("enrollmentInfo") or design.get("designInfo", {}).get("enrollmentInfo", {})
            enrollment = enrollment_info.get("count") if isinstance(enrollment_info, dict) else None

            interventions = [
                inv.get("name")
                for inv in arms.get("interventions", [])
                if inv.get("name")
            ]

            results.append({
                "nct_id": nct_id,
                "title": title,
                "phase": phase,
                "status": status,
                "primary_completion_date": parsed_date,
                "study_type": design.get("studyType", "Interventional").title(),
                "enrollment": enrollment,
                "brief_summary": desc.get("briefSummary", ""),
                "interventions": interventions,
                "raw_payload": item,
            })

        return results
