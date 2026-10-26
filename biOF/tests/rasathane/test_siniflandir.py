import pytest

from bioseeder.rasathane.olay import OlayTuru
from bioseeder.rasathane.siniflandir import siniflandir

GOVDE = " Lorem ipsum dolor sit amet. " * 40


@pytest.mark.parametrize("metin,beklenen", [
    ("XYZ Announces Positive Topline Results from Phase 3 ACME Trial in Obesity", (OlayTuru.FAZ3_SONUC, True)),
    ("XYZ Reports Phase 3 Trial Did Not Meet Primary Endpoint", (OlayTuru.FAZ3_SONUC, True)),
    ("XYZ Announces Topline Data from Phase 2b Study of ABC-1", (OlayTuru.FAZ2_SONUC, False)),
    ("XYZ Phase 2/3 Trial Met Its Primary Endpoint", (OlayTuru.FAZ3_SONUC, True)),
    ("U.S. FDA Approves XYZ's ACME for Adults with Severe Asthma", (OlayTuru.FDA_ONAY, False)),
    ("XYZ Receives Complete Response Letter from FDA for ACME", (OlayTuru.FDA_RET, False)),
    ("FDA Accepts New Drug Application for ACME; PDUFA Target Action Date Set", None),
    ("XYZ Anticipates FDA Approval Decision in Q1", None),
    ("XYZ Announces $50 Million Registered Direct Offering", None),
    ("XYZ to Present Phase 3 Design at Medical Conference", None),
    ("XYZ Provides Corporate Update." + GOVDE + " Phase 3 results were reported last year.", None),
    ("", None),
    ("FDA Approves XYZ's ACME for Asthma. The approval follows the resubmission addressing the Complete Response "
     "Letter issued in 2025.", (OlayTuru.FDA_ONAY, False)),
    ("XYZ Announces Resubmission of NDA Following Complete Response Letter", None),
    ("XYZ Reports Third Quarter 2026 Financial Results and Business Update. Enrollment in the Phase 3 ACME trial "
     "is on track.", None),
    ("FDA Advisory Committee Votes in Favor of Approval of XYZ's ACME", None),
    ("XYZ Receives FDA Approval to Initiate Phase 1 Trial of ABC-2", None),
    ("XYZ Receives IND Clearance from FDA", None),
])
def test_siniflandir(metin, beklenen):
    assert siniflandir(metin + GOVDE) == beklenen
