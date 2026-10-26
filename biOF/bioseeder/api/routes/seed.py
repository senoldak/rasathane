from datetime import date, timedelta
from typing import Optional
import asyncio
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from bioseeder.config import get_settings
from bioseeder.database import get_db
from bioseeder.models import Company, DrugCandidate, ClinicalTrial, CatalystEvent, BioAlphaScore
from bioseeder.engine.bio_alpha import calculate_bio_alpha
from bioseeder.collectors.market_data import MarketDataCollector

router = APIRouter()


@router.post("/seed")
async def seed_database(
    db: AsyncSession = Depends(get_db),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Seed the database with institutional biotech companies, drug pipelines, and catalysts."""
    settings = get_settings()
    # Authorization guard: Require DEBUG mode or valid ADMIN_API_KEY
    if not settings.DEBUG:
        if not settings.ADMIN_API_KEY or x_admin_key != settings.ADMIN_API_KEY:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Database seeding is restricted. Provide valid X-Admin-Key or enable DEBUG mode.",
            )

    # Clean existing data
    await db.execute(delete(BioAlphaScore))
    await db.execute(delete(CatalystEvent))
    await db.execute(delete(ClinicalTrial))
    await db.execute(delete(DrugCandidate))
    await db.execute(delete(Company))
    await db.commit()

    today = date.today()

    # Broad curated institutional universe (25+ Equities)
    seed_companies = [
        # 1. VERTEX PHARMACEUTICALS (Mega/Large Cap - Pain / CF / Cell Therapy)
        {
            "ticker": "VRTX",
            "name": "Vertex Pharmaceuticals",
            "exchange": "NASDAQ",
            "market_cap": 118500.0,
            "enterprise_value": 108000.0,
            "cash_and_equivalents": 10500.0,
            "quarterly_burn_rate": 650.0,
            "cash_runway_months": 48.5,
            "float_shares": 256.0,
            "short_interest_pct": 1.8,
            "drugs": [
                {
                    "code_name": "VX-548",
                    "generic_name": "Suzetrigine",
                    "brand_name": "Journavo",
                    "indication": "Moderate-to-Severe Acute Pain",
                    "therapeutic_area": "Neurology / Pain",
                    "target_tam": 5500.0,
                    "highest_phase": "NDA/BLA",
                    "mechanism_of_action": "Selective NaV1.8 voltage-gated sodium channel inhibitor",
                    "trials": [
                        {
                            "nct_id": "NCT04208555",
                            "title": "Phase 3 Study of VX-548 Following Abdominoplasty",
                            "phase": "Phase 3",
                            "status": "Completed",
                            "primary_completion_date": today - timedelta(days=120),
                            "enrollment": 1118,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "PDUFA",
                            "target_date": today + timedelta(days=22),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "FDA PDUFA target action date for NDA review of Suzetrigine under Priority Review.",
                            "designations": ["Priority Review", "Breakthrough Therapy"],
                        }
                    ],
                },
                {
                    "code_name": "VX-880",
                    "generic_name": "Stem cell-derived islet cells",
                    "indication": "Type 1 Diabetes with Severe Hypoglycemia",
                    "therapeutic_area": "Endocrinology / Cell Therapy",
                    "target_tam": 8000.0,
                    "highest_phase": "Phase 1/2",
                    "mechanism_of_action": "Allogeneic stem cell-derived islet cells",
                    "trials": [
                        {
                            "nct_id": "NCT04786262",
                            "title": "Safety and Efficacy of VX-880 in Type 1 Diabetes",
                            "phase": "Phase 1/2",
                            "status": "Active, not recruiting",
                            "primary_completion_date": today + timedelta(days=180),
                            "enrollment": 17,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 2 Readout",
                            "target_date": today + timedelta(days=75),
                            "date_precision": "MONTH",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Full Cohort C data readout on endogenous insulin secretion and HbA1c normalization.",
                            "designations": ["Fast Track", "Orphan Drug"],
                        }
                    ],
                },
            ],
        },

        # 2. REGENERON PHARMACEUTICALS (Large Cap - Oncology & Immunology)
        {
            "ticker": "REGN",
            "name": "Regeneron Pharmaceuticals",
            "exchange": "NASDAQ",
            "market_cap": 112000.0,
            "enterprise_value": 104000.0,
            "cash_and_equivalents": 16500.0,
            "quarterly_burn_rate": 800.0,
            "cash_runway_months": 61.8,
            "float_shares": 108.0,
            "short_interest_pct": 2.1,
            "drugs": [
                {
                    "code_name": "REGN5458",
                    "generic_name": "Linvoseltamab",
                    "brand_name": "",
                    "indication": "Relapsed/Refractory Multiple Myeloma",
                    "therapeutic_area": "Oncology",
                    "target_tam": 6000.0,
                    "highest_phase": "NDA/BLA",
                    "mechanism_of_action": "Bispecific BCMA x CD3 T-cell engager antibody",
                    "trials": [
                        {
                            "nct_id": "NCT03761108",
                            "title": "Study of BCMAxCD3 Bispecific Antibody REGN5458 in Multiple Myeloma (LINKER-MM1)",
                            "phase": "Phase 2",
                            "status": "Active, not recruiting",
                            "primary_completion_date": today - timedelta(days=40),
                            "enrollment": 282,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "PDUFA",
                            "target_date": today + timedelta(days=18),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "FDA PDUFA target decision date on BLA submission for Linvoseltamab in R/R Multiple Myeloma.",
                            "designations": ["Priority Review", "Fast Track"],
                        }
                    ],
                }
            ],
        },

        # 3. GILEAD SCIENCES (Mega Cap - Virology & Oncology)
        {
            "ticker": "GILD",
            "name": "Gilead Sciences",
            "exchange": "NASDAQ",
            "market_cap": 98000.0,
            "enterprise_value": 115000.0,
            "cash_and_equivalents": 8400.0,
            "quarterly_burn_rate": 500.0,
            "cash_runway_months": 50.4,
            "float_shares": 1240.0,
            "short_interest_pct": 1.9,
            "drugs": [
                {
                    "code_name": "GS-6207",
                    "generic_name": "Lenacapavir",
                    "brand_name": "Sunlenca",
                    "indication": "HIV-1 Pre-Exposure Prophylaxis (PrEP)",
                    "therapeutic_area": "Infectious Disease / Virology",
                    "target_tam": 7500.0,
                    "highest_phase": "Phase 3",
                    "mechanism_of_action": "Long-acting capsid inhibitor administered twice-yearly subcutaneous",
                    "trials": [
                        {
                            "nct_id": "NCT04994509",
                            "title": "Study to Assess the Efficacy of Lenacapavir for PrEP (PURPOSE 2)",
                            "phase": "Phase 3",
                            "status": "Completed",
                            "primary_completion_date": today - timedelta(days=20),
                            "enrollment": 3200,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 3 Readout",
                            "target_date": today + timedelta(days=28),
                            "date_precision": "MONTH",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Full efficacy and zero-infection cohort data presentation at IDWeek / medical plenary session.",
                            "designations": ["Breakthrough Therapy"],
                        }
                    ],
                }
            ],
        },

        # 4. BIOGEN (Large Cap - Neurology & Neurodegenerative)
        {
            "ticker": "BIIB",
            "name": "Biogen",
            "exchange": "NASDAQ",
            "market_cap": 28500.0,
            "enterprise_value": 31000.0,
            "cash_and_equivalents": 2100.0,
            "quarterly_burn_rate": 220.0,
            "cash_runway_months": 28.6,
            "float_shares": 145.0,
            "short_interest_pct": 3.4,
            "drugs": [
                {
                    "code_name": "BIIB080",
                    "generic_name": "Tau antisense oligonucleotide",
                    "brand_name": "",
                    "indication": "Early Alzheimer's Disease",
                    "therapeutic_area": "Neurology / Alzheimer's",
                    "target_tam": 14000.0,
                    "highest_phase": "Phase 2",
                    "mechanism_of_action": "Intrathecal antisense oligonucleotide targeting MAPT to lower tau mRNA",
                    "trials": [
                        {
                            "nct_id": "NCT05399888",
                            "title": "Phase 2 Study to Evaluate BIIB080 in Mild Cognitive Impairment or Mild Dementia (CELIA)",
                            "phase": "Phase 2",
                            "status": "Recruiting",
                            "primary_completion_date": today + timedelta(days=160),
                            "enrollment": 730,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 2 Readout",
                            "target_date": today + timedelta(days=64),
                            "date_precision": "MONTH",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Interim biomarker readout evaluating CSF total-tau and phosphorylated-tau reduction in CELIA.",
                            "designations": ["Fast Track"],
                        }
                    ],
                }
            ],
        },

        # 5. MODERNA (Large Cap - mRNA Oncology & Vaccines)
        {
            "ticker": "MRNA",
            "name": "Moderna",
            "exchange": "NASDAQ",
            "market_cap": 23000.0,
            "enterprise_value": 16500.0,
            "cash_and_equivalents": 8500.0,
            "quarterly_burn_rate": 780.0,
            "cash_runway_months": 32.7,
            "float_shares": 340.0,
            "short_interest_pct": 11.2,
            "drugs": [
                {
                    "code_name": "mRNA-4157",
                    "generic_name": "Intusertagene autoleucel",
                    "brand_name": "",
                    "indication": "Adjuvant High-Risk Melanoma & NSCLC",
                    "therapeutic_area": "Oncology / Cancer Vaccines",
                    "target_tam": 9000.0,
                    "highest_phase": "Phase 3",
                    "mechanism_of_action": "Individualized neoantigen mRNA vaccine in combination with Keytruda",
                    "trials": [
                        {
                            "nct_id": "NCT05933577",
                            "title": "Phase 3 Trial of Individualized Neoantigen Therapy Plus Pembrolizumab in Melanoma (INTerpath-001)",
                            "phase": "Phase 3",
                            "status": "Recruiting",
                            "primary_completion_date": today + timedelta(days=240),
                            "enrollment": 1089,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 3 Readout",
                            "target_date": today + timedelta(days=82),
                            "date_precision": "MONTH",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Overall recurrence-free survival (RFS) landmark 3-year follow up and NSCLC cohort initiation.",
                            "designations": ["Breakthrough Therapy", "Prime"],
                        }
                    ],
                }
            ],
        },

        # 6. BIONTECH (Large Cap - mRNA & Bispecific Oncology)
        {
            "ticker": "BNTX",
            "name": "BioNTech",
            "exchange": "NASDAQ",
            "market_cap": 26000.0,
            "enterprise_value": 10500.0,
            "cash_and_equivalents": 18200.0,
            "quarterly_burn_rate": 350.0,
            "cash_runway_months": 156.0,
            "float_shares": 235.0,
            "short_interest_pct": 3.8,
            "drugs": [
                {
                    "code_name": "BNT327",
                    "generic_name": "PM8002 (PD-L1 x VEGF-A)",
                    "brand_name": "",
                    "indication": "Triple-Negative Breast Cancer (TNBC) & SCLC",
                    "therapeutic_area": "Oncology",
                    "target_tam": 11000.0,
                    "highest_phase": "Phase 2/3",
                    "mechanism_of_action": "Bispecific antibody blocking PD-L1 and neutralizing VEGF-A",
                    "trials": [
                        {
                            "nct_id": "NCT06385483",
                            "title": "Phase 2/3 Study of BNT327 in Advanced Triple-Negative Breast Cancer",
                            "phase": "Phase 2/3",
                            "status": "Recruiting",
                            "primary_completion_date": today + timedelta(days=190),
                            "enrollment": 450,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 2 Readout",
                            "target_date": today + timedelta(days=48),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "ESMO presentation of confirmed objective response rate (ORR) and progression-free survival (PFS).",
                            "designations": ["Breakthrough Therapy"],
                        }
                    ],
                }
            ],
        },

        # 7. ALNYLAM PHARMACEUTICALS (Large Cap - RNAi Therapeutics)
        {
            "ticker": "ALNY",
            "name": "Alnylam Pharmaceuticals",
            "exchange": "NASDAQ",
            "market_cap": 34500.0,
            "enterprise_value": 33200.0,
            "cash_and_equivalents": 2400.0,
            "quarterly_burn_rate": 160.0,
            "cash_runway_months": 45.0,
            "float_shares": 128.0,
            "short_interest_pct": 5.2,
            "drugs": [
                {
                    "code_name": "ALN-TTRsc04",
                    "generic_name": "Vutrisiran",
                    "brand_name": "Amvuttra",
                    "indication": "ATTR Amyloidosis with Cardiomyopathy (ATTR-CM)",
                    "therapeutic_area": "Rare Disease / Cardiology",
                    "target_tam": 8500.0,
                    "highest_phase": "NDA/BLA",
                    "mechanism_of_action": "Subcutaneously administered transthyretin-directed RNAi therapeutic",
                    "trials": [
                        {
                            "nct_id": "NCT04153149",
                            "title": "Study of Vutrisiran in Patients With Transthyretin Amyloidosis With Cardiomyopathy (HELIOS-B)",
                            "phase": "Phase 3",
                            "status": "Completed",
                            "primary_completion_date": today - timedelta(days=90),
                            "enrollment": 655,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "PDUFA",
                            "target_date": today + timedelta(days=26),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "FDA PDUFA decision on sNDA filing for Vutrisiran in ATTR cardiomyopathy following HELIOS-B success.",
                            "designations": ["Priority Review", "Fast Track", "Orphan Drug"],
                        }
                    ],
                }
            ],
        },

        # 8. ARGENX SE (Large/Mid Cap - Immunology & FcRn)
        {
            "ticker": "ARGX",
            "name": "Argenx SE",
            "exchange": "NASDAQ",
            "market_cap": 31000.0,
            "enterprise_value": 28000.0,
            "cash_and_equivalents": 3200.0,
            "quarterly_burn_rate": 180.0,
            "cash_runway_months": 53.3,
            "float_shares": 60.0,
            "short_interest_pct": 2.8,
            "drugs": [
                {
                    "code_name": "ARGX-113",
                    "generic_name": "Efgartigimod alfa",
                    "brand_name": "Vyvgart Hytrulo",
                    "indication": "Thyroid Eye Disease (TED) & Sjogren's",
                    "therapeutic_area": "Immunology / Rare Disease",
                    "target_tam": 4500.0,
                    "highest_phase": "Phase 3",
                    "mechanism_of_action": "Antibody fragment binding neonatal Fc receptor (FcRn) to clear pathogenic IgG",
                    "trials": [
                        {
                            "nct_id": "NCT05456711",
                            "title": "A Study to Evaluate Efficacy and Safety of Efgartigimod in Adults With Thyroid Eye Disease",
                            "phase": "Phase 3",
                            "status": "Active, not recruiting",
                            "primary_completion_date": today + timedelta(days=55),
                            "enrollment": 210,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 3 Readout",
                            "target_date": today + timedelta(days=40),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Topline primary endpoint readout: proptosis responder rate at week 24 in TED registrational cohort.",
                            "designations": ["Orphan Drug", "Fast Track"],
                        }
                    ],
                }
            ],
        },

        # 9. SAREPTA THERAPEUTICS (Large/Mid Cap - Gene Therapy & DMD)
        {
            "ticker": "SRPT",
            "name": "Sarepta Therapeutics",
            "exchange": "NASDAQ",
            "market_cap": 11200.0,
            "enterprise_value": 11600.0,
            "cash_and_equivalents": 850.0,
            "quarterly_burn_rate": 190.0,
            "cash_runway_months": 13.4,
            "float_shares": 96.0,
            "short_interest_pct": 9.2,
            "drugs": [
                {
                    "code_name": "SRP-9001",
                    "generic_name": "Delandistrogene moxeparvovec",
                    "brand_name": "Elevidys",
                    "indication": "Duchenne Muscular Dystrophy (Non-Ambulatory)",
                    "therapeutic_area": "Rare Disease / Neurology",
                    "target_tam": 4000.0,
                    "highest_phase": "Approved",
                    "mechanism_of_action": "AAVrh74 micro-dystrophin gene therapy",
                    "trials": [
                        {
                            "nct_id": "NCT05096221",
                            "title": "A Study of Delandistrogene Moxeparvovec in Subjects With DMD (EMBARK)",
                            "phase": "Phase 3",
                            "status": "Completed",
                            "primary_completion_date": today - timedelta(days=60),
                            "enrollment": 125,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "AdCom Meeting",
                            "target_date": today + timedelta(days=8),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "FDA Advisory Committee meeting to review efficacy data for label expansion into non-ambulatory DMD patients.",
                            "designations": ["Breakthrough Therapy", "Orphan Drug", "Priority Review"],
                        }
                    ],
                }
            ],
        },

        # 10. VIKING THERAPEUTICS (Mid Cap - Obesity / GLP-1)
        {
            "ticker": "VKTX",
            "name": "Viking Therapeutics",
            "exchange": "NASDAQ",
            "market_cap": 6200.0,
            "enterprise_value": 5300.0,
            "cash_and_equivalents": 930.0,
            "quarterly_burn_rate": 45.0,
            "cash_runway_months": 62.0,
            "float_shares": 105.0,
            "short_interest_pct": 16.8,
            "drugs": [
                {
                    "code_name": "VK2735",
                    "generic_name": "Dual GLP-1/GIP receptor agonist",
                    "brand_name": "",
                    "indication": "Obesity & Metabolic Disorders",
                    "therapeutic_area": "Metabolic / Obesity",
                    "target_tam": 25000.0,
                    "highest_phase": "Phase 3",
                    "mechanism_of_action": "Dual agonist of GLP-1 and GIP receptors (oral and subcutaneous)",
                    "trials": [
                        {
                            "nct_id": "NCT06512345",
                            "title": "Phase 3 Trial of Subcutaneous VK2735 in Adults with Obesity",
                            "phase": "Phase 3",
                            "status": "Recruiting",
                            "primary_completion_date": today + timedelta(days=210),
                            "enrollment": 2500,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 3 Readout",
                            "target_date": today + timedelta(days=14),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Oral tablet Phase 2 extension data and Phase 3 trial initiation milestone update.",
                            "designations": ["Fast Track"],
                        }
                    ],
                }
            ],
        },

        # 11. CRISPR THERAPEUTICS (Mid Cap - Gene Editing & Cell Therapy)
        {
            "ticker": "CRSP",
            "name": "CRISPR Therapeutics",
            "exchange": "NASDAQ",
            "market_cap": 4600.0,
            "enterprise_value": 3100.0,
            "cash_and_equivalents": 1900.0,
            "quarterly_burn_rate": 180.0,
            "cash_runway_months": 31.6,
            "float_shares": 82.0,
            "short_interest_pct": 12.4,
            "drugs": [
                {
                    "code_name": "CTX112",
                    "generic_name": "Allogeneic CD19 CAR-T",
                    "brand_name": "",
                    "indication": "B-cell Malignancies & Lupus Nephritis",
                    "therapeutic_area": "Oncology / Autoimmune",
                    "target_tam": 4200.0,
                    "highest_phase": "Phase 1/2",
                    "mechanism_of_action": "CRISPR-Cas9 gene-edited allogeneic CAR-T",
                    "trials": [
                        {
                            "nct_id": "NCT05643742",
                            "title": "A Study Evaluating CTX112 in Relapsed/Refractory B-Cell Malignancies",
                            "phase": "Phase 1/2",
                            "status": "Recruiting",
                            "primary_completion_date": today + timedelta(days=90),
                            "enrollment": 120,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 1/2 Readout",
                            "target_date": today + timedelta(days=35),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Clinical readout for CTX112 in Systemic Lupus Erythematosus (SLE) at upcoming medical congress.",
                            "designations": ["Fast Track"],
                        }
                    ],
                }
            ],
        },

        # 12. MADRIGAL PHARMACEUTICALS (Mid Cap - MASH / NASH)
        {
            "ticker": "MDGL",
            "name": "Madrigal Pharmaceuticals",
            "exchange": "NASDAQ",
            "market_cap": 6800.0,
            "enterprise_value": 6000.0,
            "cash_and_equivalents": 1100.0,
            "quarterly_burn_rate": 95.0,
            "cash_runway_months": 34.7,
            "float_shares": 19.5,
            "short_interest_pct": 14.5,
            "drugs": [
                {
                    "code_name": "MGL-3196",
                    "generic_name": "Resmetirom",
                    "brand_name": "Rezdiffra",
                    "indication": "Compensated MASH Cirrhosis",
                    "therapeutic_area": "Hepatology / Metabolic",
                    "target_tam": 12000.0,
                    "highest_phase": "Phase 3",
                    "mechanism_of_action": "Oral, liver-directed, selective thyroid hormone receptor-beta agonist",
                    "trials": [
                        {
                            "nct_id": "NCT04197310",
                            "title": "Phase 3 Study of Resmetirom in Patients With Non-Alcoholic Steatohepatitis (MAESTRO-NASH)",
                            "phase": "Phase 3",
                            "status": "Active, not recruiting",
                            "primary_completion_date": today + timedelta(days=95),
                            "enrollment": 1750,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 3 Readout",
                            "target_date": today + timedelta(days=58),
                            "date_precision": "MONTH",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "MAESTRO-NASH Outcomes 54-month cirrhosis prevention and hepatic decompensation hazard ratio readout.",
                            "designations": ["Breakthrough Therapy", "Fast Track"],
                        }
                    ],
                }
            ],
        },

        # 13. CYTOKINETICS (Mid Cap - Cardiovascular)
        {
            "ticker": "CYTK",
            "name": "Cytokinetics",
            "exchange": "NASDAQ",
            "market_cap": 5800.0,
            "enterprise_value": 5500.0,
            "cash_and_equivalents": 620.0,
            "quarterly_burn_rate": 88.0,
            "cash_runway_months": 21.1,
            "float_shares": 112.0,
            "short_interest_pct": 15.3,
            "drugs": [
                {
                    "code_name": "CK-274",
                    "generic_name": "Aficamten",
                    "brand_name": "",
                    "indication": "Obstructive Hypertrophic Cardiomyopathy (oHCM)",
                    "therapeutic_area": "Cardiovascular",
                    "target_tam": 3800.0,
                    "highest_phase": "NDA/BLA",
                    "mechanism_of_action": "Small molecule cardiac myosin inhibitor",
                    "trials": [
                        {
                            "nct_id": "NCT05186818",
                            "title": "A Phase 3 Trial of Aficamten in Patients With Symptomatic oHCM (SEQUOIA-HCM)",
                            "phase": "Phase 3",
                            "status": "Completed",
                            "primary_completion_date": today - timedelta(days=150),
                            "enrollment": 282,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "PDUFA",
                            "target_date": today + timedelta(days=38),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "FDA PDUFA target action date for Aficamten NDA review in obstructive hypertrophic cardiomyopathy.",
                            "designations": ["Breakthrough Therapy"],
                        }
                    ],
                }
            ],
        },

        # 14. INSMED (Mid Cap - Pulmonary & Rare Diseases)
        {
            "ticker": "INSM",
            "name": "Insmed",
            "exchange": "NASDAQ",
            "market_cap": 12500.0,
            "enterprise_value": 11800.0,
            "cash_and_equivalents": 1300.0,
            "quarterly_burn_rate": 140.0,
            "cash_runway_months": 27.8,
            "float_shares": 160.0,
            "short_interest_pct": 8.7,
            "drugs": [
                {
                    "code_name": "INS1007",
                    "generic_name": "Brensocatib",
                    "brand_name": "",
                    "indication": "Non-Cystic Fibrosis Bronchiectasis (NCFBE)",
                    "therapeutic_area": "Pulmonary / Rare Disease",
                    "target_tam": 4800.0,
                    "highest_phase": "NDA/BLA",
                    "mechanism_of_action": "Oral dipeptidyl peptidase 1 (DPP1) inhibitor",
                    "trials": [
                        {
                            "nct_id": "NCT04594369",
                            "title": "Efficacy and Safety of Brensocatib in Patients With Bronchiectasis (ASPEN)",
                            "phase": "Phase 3",
                            "status": "Completed",
                            "primary_completion_date": today - timedelta(days=80),
                            "enrollment": 1700,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "PDUFA",
                            "target_date": today + timedelta(days=52),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "NDA submission and priority review acceptance for Brensocatib in bronchiectasis.",
                            "designations": ["Breakthrough Therapy", "Fast Track", "Orphan Drug"],
                        }
                    ],
                }
            ],
        },

        # 15. BRIDGEBIO PHARMA (Mid Cap - Rare Genetic Diseases)
        {
            "ticker": "BBIO",
            "name": "BridgeBio Pharma",
            "exchange": "NASDAQ",
            "market_cap": 5400.0,
            "enterprise_value": 6200.0,
            "cash_and_equivalents": 480.0,
            "quarterly_burn_rate": 125.0,
            "cash_runway_months": 11.5,
            "float_shares": 170.0,
            "short_interest_pct": 14.8,
            "drugs": [
                {
                    "code_name": "BBP-831",
                    "generic_name": "Infigratinib",
                    "brand_name": "",
                    "indication": "Achondroplasia (Children)",
                    "therapeutic_area": "Rare Genetic Diseases / Skeletal",
                    "target_tam": 3200.0,
                    "highest_phase": "Phase 3",
                    "mechanism_of_action": "Oral FGFR1-3 selective tyrosine kinase inhibitor",
                    "trials": [
                        {
                            "nct_id": "NCT06164951",
                            "title": "Phase 3 Study of Infigratinib in Children With Achondroplasia (PROPEL 3)",
                            "phase": "Phase 3",
                            "status": "Recruiting",
                            "primary_completion_date": today + timedelta(days=220),
                            "enrollment": 110,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 3 Readout",
                            "target_date": today + timedelta(days=68),
                            "date_precision": "MONTH",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Interim annualized growth velocity (AGV) cohort update and safety profile in pediatric achondroplasia.",
                            "designations": ["Fast Track", "Orphan Drug"],
                        }
                    ],
                }
            ],
        },

        # 16. ARROWHEAD PHARMACEUTICALS (Mid Cap - RNAi / Cardiometabolic)
        {
            "ticker": "ARWR",
            "name": "Arrowhead Pharmaceuticals",
            "exchange": "NASDAQ",
            "market_cap": 2900.0,
            "enterprise_value": 3100.0,
            "cash_and_equivalents": 540.0,
            "quarterly_burn_rate": 75.0,
            "cash_runway_months": 21.6,
            "float_shares": 118.0,
            "short_interest_pct": 13.9,
            "drugs": [
                {
                    "code_name": "ARO-APOC3",
                    "generic_name": "Plozasiran",
                    "brand_name": "",
                    "indication": "Severe Hypertriglyceridemia (SHTG) & FCS",
                    "therapeutic_area": "Cardiometabolic",
                    "target_tam": 4000.0,
                    "highest_phase": "NDA/BLA",
                    "mechanism_of_action": "Targeted RNAi silencing apolipoprotein C-III mRNA in hepatocytes",
                    "trials": [
                        {
                            "nct_id": "NCT05081219",
                            "title": "Phase 3 Study of Plozasiran in Familial Chylomicronemia Syndrome (PALISADE)",
                            "phase": "Phase 3",
                            "status": "Completed",
                            "primary_completion_date": today - timedelta(days=45),
                            "enrollment": 75,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "PDUFA",
                            "target_date": today + timedelta(days=45),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "FDA PDUFA action date on NDA for Plozasiran in Familial Chylomicronemia Syndrome (FCS).",
                            "designations": ["Breakthrough Therapy", "Orphan Drug", "Fast Track"],
                        }
                    ],
                }
            ],
        },

        # 17. IOVANCE BIOTHERAPEUTICS (Mid/Small Cap - TIL Cell Therapy)
        {
            "ticker": "IOVA",
            "name": "Iovance Biotherapeutics",
            "exchange": "NASDAQ",
            "market_cap": 2800.0,
            "enterprise_value": 2400.0,
            "cash_and_equivalents": 420.0,
            "quarterly_burn_rate": 115.0,
            "cash_runway_months": 10.9,
            "float_shares": 270.0,
            "short_interest_pct": 19.5,
            "drugs": [
                {
                    "code_name": "LN-145",
                    "generic_name": "Lifileucel",
                    "brand_name": "Amtagvi",
                    "indication": "Metastatic Non-Small Cell Lung Cancer",
                    "therapeutic_area": "Oncology",
                    "target_tam": 6500.0,
                    "highest_phase": "Phase 2",
                    "mechanism_of_action": "Autologous Tumor-Infiltrating Lymphocyte (TIL) cell therapy",
                    "trials": [
                        {
                            "nct_id": "NCT04614103",
                            "title": "A Study of Lifileucel (LN-145) in Combination With Pembrolizumab in NSCLC",
                            "phase": "Phase 2",
                            "status": "Active, not recruiting",
                            "primary_completion_date": today + timedelta(days=45),
                            "enrollment": 180,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 2 Readout",
                            "target_date": today + timedelta(days=42),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Preliminary overall response rate (ORR) and duration of response (DOR) in frontline NSCLC combo cohort.",
                            "designations": ["Fast Track", "Orphan Drug"],
                        }
                    ],
                }
            ],
        },

        # 18. INTELLIA THERAPEUTICS (Small/Mid Cap - In Vivo CRISPR)
        {
            "ticker": "NTLA",
            "name": "Intellia Therapeutics",
            "exchange": "NASDAQ",
            "market_cap": 1650.0,
            "enterprise_value": 850.0,
            "cash_and_equivalents": 920.0,
            "quarterly_burn_rate": 105.0,
            "cash_runway_months": 26.3,
            "float_shares": 98.0,
            "short_interest_pct": 18.1,
            "drugs": [
                {
                    "code_name": "NTLA-2002",
                    "generic_name": "In vivo CRISPR KLKB1 knockout",
                    "brand_name": "",
                    "indication": "Hereditary Angioedema (HAE)",
                    "therapeutic_area": "Rare Genetic Diseases / Immunology",
                    "target_tam": 3000.0,
                    "highest_phase": "Phase 3",
                    "mechanism_of_action": "Lipid nanoparticle delivery of Cas9 mRNA and sgRNA to inactivate KLKB1 gene in hepatocytes",
                    "trials": [
                        {
                            "nct_id": "NCT06638515",
                            "title": "Pivotal Phase 3 Trial of In Vivo CRISPR Therapy NTLA-2002 in Patients With HAE (HAELO)",
                            "phase": "Phase 3",
                            "status": "Recruiting",
                            "primary_completion_date": today + timedelta(days=260),
                            "enrollment": 60,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 2 Readout",
                            "target_date": today + timedelta(days=32),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Phase 2 attack-rate reduction data presentation at ACAAI annual medical congress.",
                            "designations": ["Breakthrough Therapy", "Orphan Drug", "Prime"],
                        }
                    ],
                }
            ],
        },

        # 19. BEAM THERAPEUTICS (Small/Mid Cap - Base Editing)
        {
            "ticker": "BEAM",
            "name": "Beam Therapeutics",
            "exchange": "NASDAQ",
            "market_cap": 1950.0,
            "enterprise_value": 1100.0,
            "cash_and_equivalents": 1050.0,
            "quarterly_burn_rate": 90.0,
            "cash_runway_months": 35.0,
            "float_shares": 85.0,
            "short_interest_pct": 17.6,
            "drugs": [
                {
                    "code_name": "BEAM-302",
                    "generic_name": "In vivo base editor for AATD",
                    "brand_name": "",
                    "indication": "Alpha-1 Antitrypsin Deficiency (AATD)",
                    "therapeutic_area": "Rare Genetic Diseases / Pulmonary",
                    "target_tam": 3500.0,
                    "highest_phase": "Phase 1/2",
                    "mechanism_of_action": "Adenine base editor (ABE) formulated in LNP to correct PiZ mutation in SERPINA1 gene",
                    "trials": [
                        {
                            "nct_id": "NCT06310226",
                            "title": "Phase 1/2 Clinical Trial of BEAM-302 in Patients With Severe AATD",
                            "phase": "Phase 1/2",
                            "status": "Recruiting",
                            "primary_completion_date": today + timedelta(days=150),
                            "enrollment": 36,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 1/2 Readout",
                            "target_date": today + timedelta(days=55),
                            "date_precision": "MONTH",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Initial single ascending dose (SAD) biomarker data showing circulating normal M-AAT protein recovery.",
                            "designations": ["Orphan Drug", "Fast Track"],
                        }
                    ],
                }
            ],
        },

        # 20. AXSOME THERAPEUTICS (Mid Cap - CNS / Psychiatry)
        {
            "ticker": "AXSM",
            "name": "Axsome Therapeutics",
            "exchange": "NASDAQ",
            "market_cap": 4800.0,
            "enterprise_value": 4600.0,
            "cash_and_equivalents": 310.0,
            "quarterly_burn_rate": 60.0,
            "cash_runway_months": 15.5,
            "float_shares": 48.0,
            "short_interest_pct": 16.2,
            "drugs": [
                {
                    "code_name": "AXS-05",
                    "generic_name": "Dextromethorphan-bupropion",
                    "brand_name": "Auvelity",
                    "indication": "Alzheimer's Disease Agitation",
                    "therapeutic_area": "Neurology / Psychiatry",
                    "target_tam": 5000.0,
                    "highest_phase": "Phase 3",
                    "mechanism_of_action": "NMDA receptor antagonist with sigma-1 agonism and monoamine reuptake inhibition",
                    "trials": [
                        {
                            "nct_id": "NCT04797715",
                            "title": "A Phase 3 Study of AXS-05 in Alzheimer's Disease Agitation (ACCORD-2)",
                            "phase": "Phase 3",
                            "status": "Completed",
                            "primary_completion_date": today - timedelta(days=70),
                            "enrollment": 260,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "PDUFA",
                            "target_date": today + timedelta(days=19),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "FDA PDUFA target decision date on sNDA filing for Auvelity in Alzheimer's Disease Agitation.",
                            "designations": ["Breakthrough Therapy"],
                        }
                    ],
                }
            ],
        },

        # 21. DENALI THERAPEUTICS (Small/Mid Cap - BBB Transport & Neuro)
        {
            "ticker": "DNLI",
            "name": "Denali Therapeutics",
            "exchange": "NASDAQ",
            "market_cap": 2900.0,
            "enterprise_value": 2100.0,
            "cash_and_equivalents": 980.0,
            "quarterly_burn_rate": 95.0,
            "cash_runway_months": 30.9,
            "float_shares": 140.0,
            "short_interest_pct": 11.5,
            "drugs": [
                {
                    "code_name": "DNL310",
                    "generic_name": "Iduronate-2-sulfatase enzyme transport vehicle (ETV:IDS)",
                    "brand_name": "",
                    "indication": "Hunter Syndrome (MPS II)",
                    "therapeutic_area": "Rare Disease / Neurology",
                    "target_tam": 1800.0,
                    "highest_phase": "Phase 2/3",
                    "mechanism_of_action": "Engineered enzyme transport vehicle engineered to cross the blood-brain barrier via transferrin receptor",
                    "trials": [
                        {
                            "nct_id": "NCT05371613",
                            "title": "Phase 2/3 Study of DNL310 in Children With MPS II (COMPASS)",
                            "phase": "Phase 2/3",
                            "status": "Recruiting",
                            "primary_completion_date": today + timedelta(days=180),
                            "enrollment": 54,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 3 Readout",
                            "target_date": today + timedelta(days=49),
                            "date_precision": "MONTH",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "CSF glycosaminoglycan (GAG) normalization data and cognitive developmental score analysis.",
                            "designations": ["Fast Track", "Orphan Drug"],
                        }
                    ],
                }
            ],
        },

        # 22. RECURSION PHARMACEUTICALS (Small/Mid Cap - AI Drug Discovery)
        {
            "ticker": "RXRX",
            "name": "Recursion Pharmaceuticals",
            "exchange": "NASDAQ",
            "market_cap": 1800.0,
            "enterprise_value": 1400.0,
            "cash_and_equivalents": 440.0,
            "quarterly_burn_rate": 85.0,
            "cash_runway_months": 15.5,
            "float_shares": 245.0,
            "short_interest_pct": 21.4,
            "drugs": [
                {
                    "code_name": "REC-994",
                    "generic_name": "Superoxide scavenger",
                    "brand_name": "",
                    "indication": "Cerebral Cavernous Malformation (CCM)",
                    "therapeutic_area": "Neurology / Rare Disease",
                    "target_tam": 1500.0,
                    "highest_phase": "Phase 2",
                    "mechanism_of_action": "Small molecule attenuating ROS-mediated brain vascular lesions",
                    "trials": [
                        {
                            "nct_id": "NCT05085561",
                            "title": "Phase 2 Clinical Study of REC-994 in Patients With Symptomatic CCM (SYCAMORE)",
                            "phase": "Phase 2",
                            "status": "Completed",
                            "primary_completion_date": today - timedelta(days=30),
                            "enrollment": 73,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 2 Readout",
                            "target_date": today + timedelta(days=11),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Pivotal MRI brain lesion hemosiderin volume analysis and safety readout from SYCAMORE.",
                            "designations": ["Orphan Drug", "Fast Track"],
                        }
                    ],
                }
            ],
        },

        # 23. KYMERA THERAPEUTICS (Small Cap - Targeted Protein Degradation)
        {
            "ticker": "KYMR",
            "name": "Kymera Therapeutics",
            "exchange": "NASDAQ",
            "market_cap": 2400.0,
            "enterprise_value": 1750.0,
            "cash_and_equivalents": 710.0,
            "quarterly_burn_rate": 55.0,
            "cash_runway_months": 38.7,
            "float_shares": 68.0,
            "short_interest_pct": 10.1,
            "drugs": [
                {
                    "code_name": "KT-474",
                    "generic_name": "IRAK4 Degrader",
                    "brand_name": "",
                    "indication": "Atopic Dermatitis & Hidradenitis Suppurativa",
                    "therapeutic_area": "Immunology / Dermatology",
                    "target_tam": 5200.0,
                    "highest_phase": "Phase 2",
                    "mechanism_of_action": "Heterobifunctional PROTAC targeted degrader of IRAK4",
                    "trials": [
                        {
                            "nct_id": "NCT06085859",
                            "title": "Phase 2 Study of IRAK4 Degrader KT-474 in Adults With Hidradenitis Suppurativa",
                            "phase": "Phase 2",
                            "status": "Recruiting",
                            "primary_completion_date": today + timedelta(days=140),
                            "enrollment": 140,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 2 Readout",
                            "target_date": today + timedelta(days=30),
                            "date_precision": "MONTH",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Sanofi partnered Phase 2 clinical efficacy (HiSCR50 response) in moderate-to-severe HS.",
                            "designations": ["Fast Track"],
                        }
                    ],
                }
            ],
        },

        # 24. BIOCRYST PHARMACEUTICALS (Small Cap - Rare Disease / Dilution Risk Setup)
        {
            "ticker": "BCRX",
            "name": "BioCryst Pharmaceuticals",
            "exchange": "NASDAQ",
            "market_cap": 1450.0,
            "enterprise_value": 1900.0,
            "cash_and_equivalents": 310.0,
            "quarterly_burn_rate": 42.0,
            "cash_runway_months": 22.1,
            "float_shares": 195.0,
            "short_interest_pct": 15.9,
            "drugs": [
                {
                    "code_name": "BCX10013",
                    "generic_name": "Oral factor D inhibitor",
                    "brand_name": "",
                    "indication": "Paroxysmal Nocturnal Hemoglobinuria (PNH)",
                    "therapeutic_area": "Hematology / Rare Disease",
                    "target_tam": 2200.0,
                    "highest_phase": "Phase 1/2",
                    "mechanism_of_action": "Once-daily oral alternative pathway complement factor D inhibitor",
                    "trials": [
                        {
                            "nct_id": "NCT05711719",
                            "title": "Phase 1/2 Clinical Study of BCX10013 in Healthy Adults and Patients With PNH",
                            "phase": "Phase 1/2",
                            "status": "Active, not recruiting",
                            "primary_completion_date": today + timedelta(days=35),
                            "enrollment": 48,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 1/2 Readout",
                            "target_date": today + timedelta(days=16),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Topline alternative pathway complement inhibition pharmacodynamics and LDH reduction data.",
                            "designations": ["Orphan Drug"],
                        }
                    ],
                }
            ],
        },

        # 25. SELLAS LIFE SCIENCES (Micro Cap - DILUTION HAZARD ALERT: Runway < 6 Months)
        {
            "ticker": "SLS",
            "name": "SELLAS Life Sciences Group",
            "exchange": "NASDAQ",
            "market_cap": 92.0,
            "enterprise_value": 98.0,
            "cash_and_equivalents": 9.5,
            "quarterly_burn_rate": 6.8,
            "cash_runway_months": 4.2,  # DILUTION HAZARD (< 6 months)
            "float_shares": 52.0,
            "short_interest_pct": 22.3,
            "drugs": [
                {
                    "code_name": "GPS",
                    "generic_name": "Galinpepimut-S",
                    "brand_name": "",
                    "indication": "Acute Myeloid Leukemia (AML) in Second Complete Remission",
                    "therapeutic_area": "Oncology / Hematology",
                    "target_tam": 1100.0,
                    "highest_phase": "Phase 3",
                    "mechanism_of_action": "WT1-targeting peptide cancer immunotherapeutic vaccine",
                    "trials": [
                        {
                            "nct_id": "NCT04229979",
                            "title": "Phase 3 Study of Galinpepimut-S Maintenance in Patients With AML in CR2 (REGAL)",
                            "phase": "Phase 3",
                            "status": "Active, not recruiting",
                            "primary_completion_date": today + timedelta(days=25),
                            "enrollment": 126,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 3 Readout",
                            "target_date": today + timedelta(days=9),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "REGAL Phase 3 pivotal overall survival interim analysis (event-driven threshold reached). Extreme dilution hazard flagged.",
                            "designations": ["Fast Track", "Orphan Drug"],
                        }
                    ],
                }
            ],
        },

        # 26. APTOSE BIOSCIENCES (Micro Cap - DILUTION HAZARD ALERT: Runway < 6 Months)
        {
            "ticker": "APTO",
            "name": "Aptose Biosciences",
            "exchange": "NASDAQ",
            "market_cap": 38.0,
            "enterprise_value": 42.0,
            "cash_and_equivalents": 4.8,
            "quarterly_burn_rate": 3.9,
            "cash_runway_months": 3.7,  # DILUTION HAZARD (< 6 months)
            "float_shares": 14.0,
            "short_interest_pct": 18.7,
            "drugs": [
                {
                    "code_name": "HM43239",
                    "generic_name": "Tuspetinib",
                    "brand_name": "",
                    "indication": "Relapsed/Refractory Acute Myeloid Leukemia",
                    "therapeutic_area": "Oncology / Hematology",
                    "target_tam": 950.0,
                    "highest_phase": "Phase 1/2",
                    "mechanism_of_action": "Oral dual kinase inhibitor targeting SYK and FLT3",
                    "trials": [
                        {
                            "nct_id": "NCT03850522",
                            "title": "Phase 1/2 Study of Tuspetinib (HM43239) in Patients With Relapsed or Refractory AML",
                            "phase": "Phase 1/2",
                            "status": "Recruiting",
                            "primary_completion_date": today + timedelta(days=40),
                            "enrollment": 110,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 1/2 Readout",
                            "target_date": today + timedelta(days=15),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Triplet combination clinical response data with Venetoclax and Azacitidine. High secondary offering risk.",
                            "designations": ["Fast Track", "Orphan Drug"],
                        }
                    ],
                }
            ],
        },

        # 27. NANOVEST THERAPEUTICS (Benchmark Micro Cap Dilution Control)
        {
            "ticker": "NANO",
            "name": "Nanovest Therapeutics",
            "exchange": "NASDAQ",
            "market_cap": 85.0,
            "enterprise_value": 90.0,
            "cash_and_equivalents": 12.0,
            "quarterly_burn_rate": 8.0,
            "cash_runway_months": 4.5,  # DILUTION HAZARD (< 6 months)
            "float_shares": 18.0,
            "short_interest_pct": 24.1,
            "drugs": [
                {
                    "code_name": "NV-101",
                    "generic_name": "Nanoparticle Paclitaxel Conjugate",
                    "brand_name": "",
                    "indication": "Refractory Glioblastoma",
                    "therapeutic_area": "Oncology / CNS",
                    "target_tam": 1200.0,
                    "highest_phase": "Phase 2",
                    "mechanism_of_action": "Blood-brain barrier permeable nanoparticle taxane",
                    "trials": [
                        {
                            "nct_id": "NCT05988112",
                            "title": "Phase 2 Study of NV-101 in Recurrent Glioblastoma Multiforme",
                            "phase": "Phase 2",
                            "status": "Active, not recruiting",
                            "primary_completion_date": today + timedelta(days=15),
                            "enrollment": 45,
                        }
                    ],
                    "catalysts": [
                        {
                            "catalyst_type": "Phase 2 Readout",
                            "target_date": today + timedelta(days=12),
                            "date_precision": "EXACT",
                            "status": "UPCOMING",
                            "outcome": "PENDING",
                            "details": "Topline overall survival readout in recurrent GBM. High dilution risk flagged due to 4.5 months cash runway.",
                            "designations": ["Orphan Drug"],
                        }
                    ],
                }
            ],
        },
    ]

    companies_count = 0
    catalysts_count = 0

    # Initialize market collector to fetch real-time metrics where available
    market_col = MarketDataCollector()

    # Pre-fetch live market metrics in parallel with timeout to keep seed instantaneous
    async def fetch_live_mkt(ticker_sym: str):
        try:
            return await asyncio.wait_for(
                market_col.fetch_ticker_overview_async(ticker_sym),
                timeout=3.0,
            )
        except Exception:
            return {}

    live_results = await asyncio.gather(*(fetch_live_mkt(c["ticker"]) for c in seed_companies))
    live_map = {res.get("ticker"): res for res in live_results if res and "ticker" in res}

    for c_data in seed_companies:
        drugs_data = c_data.pop("drugs")
        ticker = c_data.get("ticker")

        # Apply live metrics if fetched successfully
        live_mkt = live_map.get(ticker, {})
        if live_mkt.get("market_cap"):
            c_data["market_cap"] = live_mkt["market_cap"]
        if live_mkt.get("enterprise_value"):
            c_data["enterprise_value"] = live_mkt["enterprise_value"]
        if live_mkt.get("cash_and_equivalents"):
            c_data["cash_and_equivalents"] = live_mkt["cash_and_equivalents"]
        if live_mkt.get("quarterly_burn_rate") is not None:
            c_data["quarterly_burn_rate"] = live_mkt["quarterly_burn_rate"]
        if live_mkt.get("cash_runway_months"):
            c_data["cash_runway_months"] = live_mkt["cash_runway_months"]

        company = Company(**c_data)
        db.add(company)
        await db.flush()
        companies_count += 1

        for d_data in drugs_data:
            trials_data = d_data.pop("trials", [])
            catalysts_data = d_data.pop("catalysts", [])

            drug = DrugCandidate(company_id=company.id, **d_data)
            db.add(drug)
            await db.flush()

            trial_id = None
            for t_data in trials_data:
                trial = ClinicalTrial(drug_id=drug.id, **t_data)
                db.add(trial)
                await db.flush()
                trial_id = trial.id

            for cat_data in catalysts_data:
                designations = cat_data.pop("designations", [])
                catalyst = CatalystEvent(
                    company_id=company.id,
                    drug_id=drug.id,
                    trial_id=trial_id,
                    **cat_data,
                )
                db.add(catalyst)
                await db.flush()
                catalysts_count += 1

                # Calculate quantitative Bio-Alpha score
                days_to_event = (catalyst.target_date - today).days
                breakdown = calculate_bio_alpha(
                    days_to_event=days_to_event,
                    therapeutic_area=drug.therapeutic_area,
                    phase=drug.highest_phase,
                    target_tam=drug.target_tam or 1000.0,
                    market_cap=company.market_cap or 500.0,
                    cash_runway_months=company.cash_runway_months or 12.0,
                    designations=designations,
                    insider_score=65.0,
                )

                score = BioAlphaScore(
                    catalyst_id=catalyst.id,
                    composite_score=breakdown.composite_score,
                    proximity_score=breakdown.proximity_score,
                    pos_score=breakdown.pos_score,
                    asymmetry_score=breakdown.asymmetry_score,
                    dilution_hazard_score=breakdown.dilution_hazard_score,
                    smart_money_score=breakdown.smart_money_score,
                    dilution_flag=breakdown.dilution_flag,
                )
                db.add(score)

    await db.commit()
    return {
        "status": "success",
        "message": f"Database seeded with {companies_count} institutional biopharma equities and {catalysts_count} catalysts.",
        "companies_seeded": companies_count,
        "catalysts_seeded": catalysts_count,
    }
