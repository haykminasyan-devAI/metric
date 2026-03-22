"""
Bank Data Scraper  v2
─────────────────────
Scrapes credits, deposits, and branch location data from Armenian bank websites.
Output: one clean .txt file per bank saved to bank_data/

Major improvements over v1:
  - Single Playwright browser session per run (10x faster, more reliable)
  - Main-content targeting — removes sidebar/nav/map noise before extraction
  - Cross-page deduplication — prevents repeated navigation blocks
  - Smarter branch extraction with multiple fallback strategies
  - Cleaned URL lists — no campaigns or duplicate overview pages
"""

import time
import os
import re
import hashlib
from typing import Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.getenv("SCRAPER_OUTPUT_DIR", os.path.join(BASE_DIR, "bank_data"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "hy,en;q=0.9",
}
DELAY_BETWEEN_REQUESTS = 1.0
MAX_SUBLINKS_PER_URL = 30
MAX_FETCH_RETRIES = int(os.getenv("SCRAPER_MAX_RETRIES", "3"))

NOISE_TAGS = ["script", "style", "nav", "footer", "header", "noscript", "iframe", "svg"]

SIDEBAR_SELECTORS = [
    "aside",
    "[role='navigation']",
    "[role='banner']",
    ".sidebar",
    ".side-menu",
    ".nav-menu",
    ".cookie-banner",
    ".popup",
    ".modal",
    ".breadcrumb",
    ".breadcrumbs",
    ".gm-style",
    ".gmnoprint",
    ".social-links",
    ".share-buttons",
]

MAIN_CONTENT_SELECTORS = [
    "main",
    "[role='main']",
    ".main-content",
    ".page-content",
    ".content-wrapper",
    "#main-content",
    "article",
]


# ══════════════════════════════════════════════════════════════════════════════
# BANK CONFIGURATIONS
# ══════════════════════════════════════════════════════════════════════════════

BANK_CONFIGS = [
    {
        "id": "ameriabank",
        "name": "Ameriabank",
        "js_rendered": True,
        "follow_sublinks": True,
        "urls": {
            "credits": [
                "https://ameriabank.am/personal/loans/consumer-loans/consumer-loans",
                "https://ameriabank.am/personal/loans/consumer-loans/overdraft",
                "https://ameriabank.am/personal/loans/consumer-loans/credit-line",
                "https://ameriabank.am/loans/secured-loans/consumer-loan",
                "https://ameriabank.am/loans/secured-loans/overdraft",
                "https://ameriabank.am/loans/secured-loans/credit-line",
                "https://ameriabank.am/personal/loans/other-loans/investment-loan",
                "https://ameriabank.am/personal/loans/mortgage/online",
                "https://ameriabank.am/personal/loans/mortgage/primary-market-loan",
                "https://ameriabank.am/personal/loans/mortgage/secondary-market",
                "https://ameriabank.am/personal/loans/mortgage/commercial-mortgage",
                "https://ameriabank.am/personal/loans/mortgage/renovation-mortgage",
                "https://ameriabank.am/personal/loans/mortgage/construction-mortgage",
                "https://ameriabank.am/personal/loans/car-loan/without-bank-visit",
                "https://ameriabank.am/personal/loans/car-loan/online-secondary-market",
                "https://ameriabank.am/personal/loans/car-loan/primary",
                "https://ameriabank.am/personal/loans/car-loan/secondary-market",
                "https://ameriabank.am/personal/loans/car-loan/secondary-market-unused",
            ],
            "deposits": [
                "https://ameriabank.am/personal/saving/deposits/ameria-deposit",
                "https://ameriabank.am/personal/saving/deposits/kids-deposit",
                "https://ameriabank.am/personal/saving/deposits/cumulative-deposit",
                "https://ameriabank.am/personal/accounts/accounts/saving-account",
            ],
            "branches": [
                "https://ameriabank.am/service-network",
            ],
        },
    },
    {
        "id": "aeb",
        "name": "Armeconombank (AEB)",
        "js_rendered": True,
        "follow_sublinks": True,
        "urls": {
            "credits": [
                "https://www.aeb.am/hy/individual/loans",
                "https://www.aeb.am/hy/individual/loans/armat",
                "https://www.aeb.am/hy/individual/loans/loan-without-a-pledge",
                "https://www.aeb.am/hy/individual/loans/student-loan-from-the-banks-resources",
                "https://www.aeb.am/hy/individual/loans/student-loan-state-program",
                "https://www.aeb.am/hy/individual/loans/online-loan",
                "https://www.aeb.am/hy/individual/loans/guru-guru-travel-credit-line",
                "https://www.aeb.am/hy/individual/loans/agro",
                "https://www.aeb.am/hy/individual/loans/income-ground",
                "https://www.aeb.am/hy/individual/loans/salary-credit-line",
                "https://www.aeb.am/hy/individual/loans/armecs-standard-credit-line",
                "https://www.aeb.am/hy/individual/loans/mastercard-world-qartervov-varkayin-gits",
                "https://www.aeb.am/hy/individual/loans/loans-with-fund-collateration",
                "https://www.aeb.am/hy/individual/loans/fund-collateration",
                "https://www.aeb.am/hy/individual/loans/cash-collateral-aeb-online",
                "https://www.aeb.am/hy/individual/loans/consumer-loan-with-real-estate-collateral",
                "https://www.aeb.am/hy/individual/loans/loan-with-gold-item-collateral",
                "https://www.aeb.am/hy/individual/loans/agricultural-with-gold-collateral",
                "https://www.aeb.am/hy/individual/loans/car-loan-primary-market",
                "https://www.aeb.am/hy/individual/loans/car-loan-secondary-market",
                "https://www.aeb.am/hy/individual/loans/gold-bullions-on-credit",
                "https://www.aeb.am/hy/individual/loans/installment-loan",
                "https://www.aeb.am/hy/individual/loans/installment-loan-subsidized-solar-loan",
                "https://www.aeb.am/hy/individual/loans/housing-for-young-families",
                "https://www.aeb.am/hy/individual/loans/affordable-housing-to-servicemen",
                "https://www.aeb.am/hy/individual/loans/refinanced-mortgage-loan",
                "https://www.aeb.am/hy/individual/loans/mortgage-loan-acquisition",
                "https://www.aeb.am/hy/individual/loans/ea-bnakaranayin-mikrvovarker",
                "https://www.aeb.am/hy/individual/loans/mortgage-loan-renovation-construction",
                "https://www.aeb.am/hy/individual/loans/mortgage-loans-provided-within-the-framework-of-own-resources-of-the-bank",
                "https://www.aeb.am/hy/individual/loans/housing-for-forcibly-displaced-families-from-separate-regions-of-nkh",
                "https://www.aeb.am/hy/individual/loans/arevtrayin-ev-gyuxatntesakan-lizing",
                "https://www.aeb.am/hy/business/loans/instant",
                "https://www.aeb.am/hy/business/loans/easy",
                "https://www.aeb.am/hy/business/loans/ecoeasy",
                "https://www.aeb.am/hy/business/loans/commercial-loan-credit-line-provided-by-account-turnover",
                "https://www.aeb.am/hy/business/loans/commercial-loan-granted-under-fund-collateration",
                "https://www.aeb.am/hy/business/loans/business-loan-with-pledge-of-gold-with-gaf-programs",
                "https://www.aeb.am/hy/business/loans/easy-plus",
                "https://www.aeb.am/hy/business/loans/ecoeasy-plus",
                "https://www.aeb.am/hy/business/loans/ecoloan",
                "https://www.aeb.am/hy/business/loans/commercial-loan",
                "https://www.aeb.am/hy/business/loans/renewable-energy-development",
                "https://www.aeb.am/hy/business/loans/trade-finance-program",
                "https://www.aeb.am/hy/business/loans/loans-granted-for-export-financing",
                "https://www.aeb.am/hy/business/loans/start-up",
                "https://www.aeb.am/hy/business/loans/commercial-car-loan",
                "https://www.aeb.am/hy/business/loans/projects-financed-through-eib-facilities",
                "https://www.aeb.am/hy/business/loans/commercial-credit-line",
                "https://www.aeb.am/hy/business/loans/armat-individual",
                "https://www.aeb.am/hy/business/loans/agricultural-property-pledged-gaf-sme-program-to-business-women",
                "https://www.aeb.am/hy/business/loans/agricultural-with-estate-collateral",
                "https://www.aeb.am/hy/business/loans/support-of-the-agricultural-sector-with-the-gf-program",
                "https://www.aeb.am/hy/business/loans/program-loans-provided-to-the-agricultural-sector-with-partial-or-full-subsidization-of-interest-rates",
                "https://www.aeb.am/hy/business/loans/loans-provided-for-the-agricultural-purposes-with-estate-collateral-under-the-gaf-sme-program",
                "https://www.aeb.am/hy/business/loans/commercial-leasing",
                "https://www.aeb.am/hy/business/loans/aeb-commercial-leasing",
            ],
            "deposits": [
                "https://www.aeb.am/hy/individual/deposits",
                "https://www.aeb.am/hy/individual/deposit/classic-plus",
                "https://www.aeb.am/hy/individual/deposit/simple-deposit",
                "https://www.aeb.am/hy/individual/deposit/classic-deposit",
                "https://www.aeb.am/hy/individual/deposit/beneficial-deposit",
                "https://www.aeb.am/hy/individual/deposit/child-deposit",
                "https://www.aeb.am/hy/business/deposit/classic-plus-business",
                "https://www.aeb.am/hy/business/deposit/classic-deposit-business",

            ],
            "branches": [
                "https://www.aeb.am/hy/branch-service-network",
            ],
        },
    },
    {
        "id": "amio",
        "name": "Amio Bank",
        "js_rendered": True,
        "follow_sublinks": True,
        "urls": {
            "credits": [
                "https://amiobank.am/loans",
                "https://amiobank.am/loans/consumer-loans",
                "https://amiobank.am/loans/mortgage-loans",
                "https://amiobank.am/loans/car-loans",
                "https://amiobank.am/loans/refinancing",
                "https://amiobank.am/business/lending/document?source=c291cmNlPWxlbmRpbmcuYWNjb3JkaW9uLjAuY29udGVudC4wLm5hbWUmdGl0bGU9bGVuZGluZy5hY2NvcmRpb24uMC50aXRsZSZpZD11bmRlZmluZWQ=",
                "https://amiobank.am/business/lending/document?source=c291cmNlPWxlbmRpbmcuYWNjb3JkaW9uLjAuY29udGVudC4xLm5hbWUmdGl0bGU9bGVuZGluZy5hY2NvcmRpb24uMC50aXRsZSZpZD11bmRlZmluZWQ=",
                "https://amiobank.am/business/lending/document?source=c291cmNlPWxlbmRpbmcuYWNjb3JkaW9uLjEuY29udGVudC4wLm5hbWUmdGl0bGU9bGVuZGluZy5hY2NvcmRpb24uMS50aXRsZSZpZD11bmRlZmluZWQ=",
                "https://amiobank.am/business/lending/document?source=c291cmNlPWxlbmRpbmcuYWNjb3JkaW9uLjIuY29udGVudC4wLm5hbWUmdGl0bGU9bGVuZGluZy5hY2NvcmRpb24uMi50aXRsZSZpZD11bmRlZmluZWQ=",
                "https://amiobank.am/business/lending/document?source=c291cmNlPWxlbmRpbmcuYWNjb3JkaW9uLjIuY29udGVudC4wLm5hbWUmdGl0bGU9bGVuZGluZy5hY2NvcmRpb24uMi50aXRsZSZpZD11bmRlZmluZWQ=",
                "https://amiobank.am/business/lending/document?source=c291cmNlPWxlbmRpbmcuYWNjb3JkaW9uLjMuY29udGVudC4wLm5hbWUmdGl0bGU9bGVuZGluZy5hY2NvcmRpb24uMy50aXRsZSZpZD11bmRlZmluZWQ=",
                "https://amiobank.am/business/lending/document?source=c291cmNlPWxlbmRpbmcuYWNjb3JkaW9uLjQuY29udGVudC4wLm5hbWUmdGl0bGU9bGVuZGluZy5hY2NvcmRpb24uNC50aXRsZSZpZD11bmRlZmluZWQ=",
                "https://amiobank.am/business/lending/document?source=c291cmNlPWxlbmRpbmcuYWNjb3JkaW9uLjUuY29udGVudC4wLm5hbWUmdGl0bGU9bGVuZGluZy5hY2NvcmRpb24uNS50aXRsZSZpZD11bmRlZmluZWQ=",
                "https://amiobank.am/business/lending/document?source=c291cmNlPWxlbmRpbmcuYWNjb3JkaW9uLjYuY29udGVudC4wLm5hbWUmdGl0bGU9bGVuZGluZy5hY2NvcmRpb24uNi50aXRsZSZpZD11bmRlZmluZWQ=",
                "https://amiobank.am/business/lending/document?source=c291cmNlPWxlbmRpbmcuYWNjb3JkaW9uLjcuY29udGVudC4wLm5hbWUmdGl0bGU9bGVuZGluZy5hY2NvcmRpb24uNy50aXRsZSZpZD11bmRlZmluZWQ=",
                "https://amiobank.am/business/lending/document?source=c291cmNlPWxlbmRpbmcuYWNjb3JkaW9uLjguY29udGVudC4wLm5hbWUmdGl0bGU9bGVuZGluZy5hY2NvcmRpb24uOC50aXRsZSZpZD11bmRlZmluZWQ=",

            ],
            "deposits": [
                "https://amiobank.am/deposits",
                "https://amiobank.am/deposits/document?source=c291cmNlPWRlcG9zaXRzLmRvY3VtZW50cy5jb250ZW50LjAubmFtZSZ0aXRsZT1kZXBvc2l0cy5kb2N1bWVudHMudGl0bGUmaWQ9dW5kZWZpbmVk",
                "https://amiobank.am/deposits/document?source=c291cmNlPWRlcG9zaXRzLmRvY3VtZW50cy5jb250ZW50LjEubmFtZSZ0aXRsZT1kZXBvc2l0cy5kb2N1bWVudHMudGl0bGUmaWQ9dW5kZWZpbmVk",
                "https://amiobank.am/deposits/document?source=c291cmNlPWRlcG9zaXRzLmRvY3VtZW50cy5jb250ZW50LjIubmFtZSZ0aXRsZT1kZXBvc2l0cy5kb2N1bWVudHMudGl0bGUmaWQ9dW5kZWZpbmVk",
                "https://amiobank.am/deposits/document?source=c291cmNlPWRlcG9zaXRzLmRvY3VtZW50cy5jb250ZW50LjMubmFtZSZ0aXRsZT1kZXBvc2l0cy5kb2N1bWVudHMudGl0bGUmaWQ9dW5kZWZpbmVk",
                "https://amiobank.am/deposits/document?source=c291cmNlPWRlcG9zaXRzLmRvY3VtZW50cy5jb250ZW50LjQubmFtZSZ0aXRsZT1kZXBvc2l0cy5kb2N1bWVudHMudGl0bGUmaWQ9dW5kZWZpbmVk",
                "https://amiobank.am/deposits/document?source=c291cmNlPWRlcG9zaXRzLmRvY3VtZW50cy5jb250ZW50LjUubmFtZSZ0aXRsZT1kZXBvc2l0cy5kb2N1bWVudHMudGl0bGUmaWQ9dW5kZWZpbmVk",
                "https://amiobank.am/deposits/document?source=c291cmNlPWRlcG9zaXRzLmRvY3VtZW50cy5jb250ZW50LjYubmFtZSZ0aXRsZT1kZXBvc2l0cy5kb2N1bWVudHMudGl0bGUmaWQ9dW5kZWZpbmVk",
                "https://amiobank.am/deposits/document?source=c291cmNlPWRlcG9zaXRzLmRvY3VtZW50cy5jb250ZW50LjcubmFtZSZ0aXRsZT1kZXBvc2l0cy5kb2N1bWVudHMudGl0bGUmaWQ9dW5kZWZpbmVk",
                "https://amiobank.am/business/lending",
                "https://amiobank.am/business/deposits-business",

            ],
            "branches": [
                "https://amiobank.am/offices",
            ],
        },
    },
    {
        "id": "fastbank",
        "name": "Fast Bank",
        "js_rendered": True,
        "follow_sublinks": True,
        "urls": {
            "credits": [
                "https://www.fastbank.am/hy/individual/loans/mortgage",
                "https://www.fastbank.am/hy/individual/loans/collateral",
                "https://www.fastbank.am/hy/individual/loans/non-collateral",
                "https://www.fastbank.am/hy/individual/loans/mortgage/national-mordgage-loans-2-2",
                "https://www.fastbank.am/hy/individual/loans/mortgage/loans-for-young-families",
                "https://www.fastbank.am/hy/individual/loans/mortgage/mortgage-loans-2",
                "https://www.fastbank.am/hy/individual/loans/mortgage/mortgage-loans-for-families-displaced-from-artsakh",
                "https://www.fastbank.am/hy/individual/loans/mortgage/mortgage-loan-for-families-forcibly-displaced-from-nagorno-karabakh",
                "https://www.fastbank.am/hy/individual/loans/mortgage/mortgage-loans-for-housing-provision-of-military-servicemen",
                "https://www.fastbank.am/hy/individual/loans/mortgage/commercial-property-mortgage-loans-construction-refinancing",
                "https://www.fastbank.am/hy/individual/loans/mortgage/national-mordgage-loans",
                "https://www.fastbank.am/hy/individual/loans/mortgage/loans-for-young-families",
                "https://www.fastbank.am/hy/individual/loans/mortgage/mortgage-loans-2",
                "https://www.fastbank.am/hy/individual/loans/mortgage/mortgage-loans-for-families-displaced-from-artsakh",
                "https://www.fastbank.am/hy/individual/loans/mortgage/mortgage-loan-for-families-forcibly-displaced-from-nagorno-karabakh",
                "https://www.fastbank.am/hy/individual/loans/mortgage/mortgage-loans-for-housing-provision-of-military-servicemen",
                "https://www.fastbank.am/hy/individual/loans/mortgage/commercial-property-mortgage-loans-construction-refinancing",
                "https://www.fastbank.am/hy/individual/loans/non-collateral/akntart-loans",
                "https://www.fastbank.am/hy/individual/loans/non-collateral/student-loan",
                "https://www.fastbank.am/hy/individual/loans/non-collateral/unsecured-consumer-loan",
                "https://www.fastbank.am/hy/individual/loans/non-collateral/card-credit-line",
                "https://www.fastbank.am/hy/individual/loans/collateral/loan-secured-by-bonds",
                "https://www.fastbank.am/hy/individual/loans/collateral/refinancing-of-loans-secured-by-real-estate",
                "https://www.fastbank.am/hy/individual/loans/collateral/car-loan",
                "https://www.fastbank.am/hy/individual/loans/collateral/loans-secured-by-on-real-estate-assets",
                "https://www.fastbank.am/hy/individual/loans/collateral/gold-loans",
                "https://www.fastbank.am/hy/individual/loans/collateral/loans-secured-by-financial-instruments",


            ],
            "deposits": [
                "https://www.fastbank.am/hy/individual/deposits",
                "https://fcstaticimages.blob.core.windows.net/fbfiles/deposit/1/%D4%B2%D5%A1%D5%B6%D5%AF%D5%A1%D5%B5%D5%AB%D5%B6_%D6%87_%D5%A1%D5%BE%D5%A1%D5%B6%D5%A4%D5%A1%D5%B5%D5%AB%D5%B6_%D5%B0%D5%A1%D5%B7%D5%AB%D5%BE%D5%B6%D5%A5%D6%80%D5%AB_%D5%A2%D5%A1%D6%81%D5%B4%D5%A1%D5%B6_%D6%87_%D5%BE%D5%A1%D6%80%D5%B4%D5%A1%D5%B6_%D5%AF%D5%A1%D5%B6%D5%B8%D5%B6%D5%B6%D5%A5%D6%80.pdf",
                "https://fcstaticimages.blob.core.windows.net/fbfiles/deposit/1/%D5%96%D5%AB%D5%A6_%D5%A1%D5%B6%D5%B1_%D5%A1%D5%BE%D5%A1%D5%B6%D5%A4_%D5%A1%D5%B4%D6%83%D5%B8%D6%83%D5%A1%D5%A3%D5%AB%D6%80_%D5%B8%D6%82%D5%AA%D5%AB_%D5%B4%D5%A5%D5%BB_%D5%A7_27.11.pdf",
                "https://fcstaticimages.blob.core.windows.net/fbfiles/deposit/1/file_e2223ef4-3e63-45b2-a891-7f76ec53f5b8.pdf",
                "https://fcstaticimages.blob.core.windows.net/fbfiles/deposit/1/%D4%B1%D5%BE%D5%A1%D5%B6%D5%A4%D5%A1%D5%BF%D5%B8%D6%82_%D5%B0%D5%A1%D5%B3%D5%A1%D5%AD%D5%B8%D6%80%D5%A4%D5%B6%D5%A5%D6%80%D5%AB%D5%B6_%D5%A1%D5%B6%D5%B0%D5%A1%D5%BF%D5%A1%D5%AF%D5%A1%D5%B6_%D5%BA%D5%A1%D5%B0%D5%A1%D5%BF%D5%B8%D6%82%D6%83_%D5%BF%D6%80%D5%A1%D5%B4%D5%A1%D5%A4%D6%80%D5%A5%D5%AC%D5%B8%D6%82_%D5%B0%D5%A1%D5%BF%D5%B8%D6%82%D5%AF_%D5%A1%D5%BC%D5%A1%D5%BB%D5%A1%D6%80%D5%AF_ENG.pdf",
                "https://fcstaticimages.blob.core.windows.net/fbfiles/deposit/1/%D4%B1%D5%BE%D5%A1%D5%B6%D5%A4%D5%A1%D5%BF%D5%B8%D6%82_%D5%B0%D5%A1%D5%B3%D5%A1%D5%AD%D5%B8%D6%80%D5%A4%D5%B6%D5%A5%D6%80%D5%AB%D5%B6_%D6%84%D5%A1%D6%80%D5%BF%D5%A5%D6%80_%D5%BF%D6%80%D5%A1%D5%B4%D5%A1%D5%A4%D6%80%D5%A5%D5%AC%D5%B8%D6%82_%D5%B0%D5%A1%D5%BF%D5%B8%D6%82%D5%AF_%D5%A1%D5%BC%D5%A1%D5%BB%D5%A1%D6%80%D5%AF_ARM.pdf",
                "https://fcstaticimages.blob.core.windows.net/fbfiles/deposit/1/%D5%96%D5%AB%D5%A6.%20%D5%A1%D5%B6%D5%B1%D5%A1%D5%B6%D6%81%20%D5%AA%D5%A1%D5%B4%D5%AF%D5%A5%D5%BF%D5%A1%D5%B5%D5%AB%D5%B6%20%D5%A1%D5%BE%D5%A1%D5%B6%D5%A4%D5%AB%20%D5%BA%D5%A1%D5%B5%D5%B4%D5%A1%D5%B6%D5%A1%D5%A3%D5%AB%D6%80.pdf",
                "https://fcstaticimages.blob.core.windows.net/fbfiles/deposit/1/%D4%BB%D6%80%D5%A1%D5%BE.%20%D5%A1%D5%B6%D5%B1%D5%A1%D5%B6%D6%81%20%D5%AA%D5%A1%D5%B4%D5%AF%D5%A5%D5%BF%D5%A1%D5%B5%D5%AB%D5%B6%20%D5%A1%D5%BE%D5%A1%D5%B6%D5%A4%D5%AB%20%D5%BA%D5%A1%D5%B5%D5%B4%D5%A1%D5%B6%D5%A1%D5%A3%D5%AB%D6%80.pdf",
                "https://fcstaticimages.blob.core.windows.net/fbfiles/deposit/1/%D5%8A%D5%A1%D5%B5%D5%B4%D5%A1%D5%B6%D5%B6%D5%A5%D6%80%D5%AB_%D5%A1%D6%80%D5%AD%D5%AB%D5%BE_%D6%86%D5%AB%D5%A6_%D5%A1%D5%B6%D5%B1_%D5%A1%D5%BE%D5%A1%D5%B6%D5%A4.pdf",
                

            ],
            "branches": [
                "https://www.fastbank.am/hy/branches",
            ],
        },
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# BROWSER POOL — reuse a single browser for the entire run
# ══════════════════════════════════════════════════════════════════════════════

class BrowserPool:
    """Manage a shared Playwright browser for all scraping."""

    def __init__(self):
        self._pw = None
        self._browser = None

    def start(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(headless=True)
            print("  [BROWSER] Chromium launched")
        except Exception as e:
            print(f"  [BROWSER] Chromium launch failed ({e}); trying system Chrome...")
            self._browser = self._pw.chromium.launch(channel="chrome", headless=True)
            print("  [BROWSER] System Chrome launched")

    def new_page(self):
        page = self._browser.new_page()
        page.set_extra_http_headers({"Accept-Language": "hy,en;q=0.9"})
        return page

    def stop(self):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        print("  [BROWSER] Closed")


# ══════════════════════════════════════════════════════════════════════════════
# TEXT DEDUPLICATOR — prevents repeated blocks across pages
# ══════════════════════════════════════════════════════════════════════════════

class TextDeduplicator:
    """Track seen text paragraphs to remove cross-page duplication."""

    def __init__(self):
        self._seen: set[str] = set()

    def _fingerprint(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def deduplicate(self, text: str) -> str:
        paragraphs = re.split(r"\n{2,}", text)
        unique = []
        for para in paragraphs:
            stripped = para.strip()
            if not stripped or len(stripped) < 30:
                if stripped:
                    unique.append(stripped)
                continue
            fp = self._fingerprint(stripped)
            if fp not in self._seen:
                self._seen.add(fp)
                unique.append(stripped)
        return "\n\n".join(unique)


# ══════════════════════════════════════════════════════════════════════════════
# TEXT EXTRACTION — targets main content, strips sidebar/nav
# ══════════════════════════════════════════════════════════════════════════════

def extract_text(html: str) -> str:
    """
    Extract clean text from HTML:
    1. Remove noise tags (scripts, nav, footer, etc.)
    2. Remove sidebar/map/modal elements
    3. Try to find main content area
    4. Collapse whitespace
    """
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(NOISE_TAGS):
        tag.decompose()

    for selector in SIDEBAR_SELECTORS:
        for el in soup.select(selector):
            el.decompose()

    content_root = None
    for selector in MAIN_CONTENT_SELECTORS:
        candidate = soup.select_one(selector)
        if candidate and len(candidate.get_text(strip=True)) > 200:
            content_root = candidate
            break

    source = content_root if content_root else soup.body if soup.body else soup
    raw_text = source.get_text(separator="\n")
    lines = [line.strip() for line in raw_text.splitlines()]

    cleaned = []
    prev_empty = False
    for line in lines:
        if line == "":
            if not prev_empty:
                cleaned.append("")
            prev_empty = True
        else:
            cleaned.append(line)
            prev_empty = False

    return "\n".join(cleaned).strip()


# ══════════════════════════════════════════════════════════════════════════════
# FETCHING
# ══════════════════════════════════════════════════════════════════════════════

def fetch_page_with_browser(url: str, pool: BrowserPool) -> Optional[str]:
    """Fetch a page using the shared browser pool."""
    try:
        page = pool.new_page()
        page.goto(url, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(1500)
        html = page.content()
        page.close()
        return html
    except Exception as e:
        print(f"    [BROWSER ERROR] {url} → {e}")
        return None


def fetch_page_http(url: str) -> Optional[str]:
    """Fetch page with plain HTTP — fast, no JavaScript."""
    import requests
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text
    except Exception as e:
        print(f"    [HTTP ERROR] {url} → {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# LINK DISCOVERY
# ══════════════════════════════════════════════════════════════════════════════

def discover_sublinks(parent_url: str, html: str) -> list:
    """
    Find child page links from a parent page.
    Pass 1: strict sub-path URLs.
    Pass 2: Armenian trigger phrases in link text.
    """
    parsed_parent = urlparse(parent_url)
    parent_domain = parsed_parent.netloc
    parent_path = parsed_parent.path.rstrip("/")

    soup = BeautifulSoup(html, "lxml")
    seen = set()
    found = []

    def _clean_url(parsed):
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def _is_noise(href):
        if href.startswith("#") or href.startswith("javascript") or href.startswith("mailto"):
            return True
        if any(href.lower().endswith(ext) for ext in [".pdf", ".doc", ".xlsx", ".zip"]):
            return True
        return False

    def _add(url):
        if url not in seen:
            seen.add(url)
            found.append(url)

    for tag in soup.find_all("a", href=True):
        if len(found) >= MAX_SUBLINKS_PER_URL:
            break

        href = tag["href"].strip()
        if _is_noise(href):
            continue

        absolute = urljoin(parent_url, href)
        parsed = urlparse(absolute)

        if parsed.netloc != parent_domain:
            continue

        clean = _clean_url(parsed)
        if clean.rstrip("/") == parent_url.rstrip("/"):
            continue

        child_path = parsed.path.rstrip("/")

        if child_path.startswith(parent_path + "/"):
            _add(clean)
            continue

        link_text = tag.get_text(strip=True).lower()
        arm_triggers = [
            "\u056b\u0574\u0561\u0576\u0561\u056c \u0561\u057e\u0565\u056c\u056b\u0576",
            "\u0561\u057e\u0565\u056c\u056b\u0576",
            "\u057a\u0561\u0575\u0574\u0561\u0576\u0576\u0565\u0580 \u0587 \u057d\u0561\u056f\u0561\u0563\u0576\u0565\u0580",
            "\u057a\u0561\u0575\u0574\u0561\u0576\u0576\u0565\u0580",
            "\u0574\u0561\u0576\u0580\u0561\u0574\u0561\u057d\u0576\u0565\u0580",
            "\u0564\u056b\u057f\u0565\u056c",
            "\u056e\u0561\u0576\u0578\u0569\u0561\u0576\u0561\u056c",
        ]
        if any(trigger in link_text for trigger in arm_triggers):
            _add(clean)

    return found


# ══════════════════════════════════════════════════════════════════════════════
# BRANCH SCRAPING — multi-strategy extraction
# ══════════════════════════════════════════════════════════════════════════════

def scrape_branches_ameriabank(url: str, pool: BrowserPool) -> str:
    """
    Ameriabank service-network page: click through region/city dropdowns
    to extract branch addresses.
    """
    try:
        page = pool.new_page()
        page.goto(url, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(3000)

        branches = []

        branch_items = page.query_selector_all(
            ".branch-item, .location-item, .network-item, "
            "[class*='branch'], [class*='location'], "
            ".list-group-item, .service-point"
        )

        if branch_items:
            print(f"    [BRANCHES] Found {len(branch_items)} branch items")
            for item in branch_items:
                text = item.inner_text().strip()
                if text and len(text) > 10:
                    branches.append(text)
        else:
            print("    [BRANCHES] No branch list found, trying tab clicks...")
            tabs = page.query_selector_all(
                ".tab-item, .region-tab, [data-region], "
                ".dropdown-item, .accordion-item, "
                "button[class*='region'], a[class*='region']"
            )

            if tabs:
                print(f"    [BRANCHES] Found {len(tabs)} region tabs")
                for tab in tabs[:15]:
                    try:
                        tab_text = tab.inner_text().strip()
                        if not tab_text or len(tab_text) < 2:
                            continue
                        tab.click()
                        page.wait_for_timeout(1500)
                        content = page.evaluate("""
                            () => {
                                const items = document.querySelectorAll(
                                    '.branch-detail, .branch-info, .location-detail, ' +
                                    '.service-point-info, [class*="branch-card"], ' +
                                    '.network-point, [class*="location-card"]'
                                );
                                return Array.from(items).map(el => el.innerText.trim()).filter(t => t.length > 10);
                            }
                        """)
                        if content:
                            for item in content:
                                branches.append(item)
                        else:
                            body_text = page.evaluate("""
                                () => {
                                    const main = document.querySelector('main, [role="main"], .main-content, .content');
                                    return main ? main.innerText : document.body.innerText;
                                }
                            """)
                            if body_text:
                                lines = [l.strip() for l in body_text.split('\n') if l.strip()]
                                address_lines = []
                                addr_markers = [
                                    "\u0574/\u0573",
                                    "\u0584.",
                                    "\u0583\u0578\u0572",
                                    "\u0570\u0565\u057c",
                                    "\u0570\u0561\u057d\u0581\u0565",
                                ]
                                for line in lines:
                                    if any(kw in line for kw in addr_markers):
                                        address_lines.append(line)
                                if address_lines:
                                    branches.extend(address_lines)
                    except Exception:
                        pass

        if not branches:
            print("    [BRANCHES] Trying full page text extraction as fallback")
            html = page.content()
            page.close()
            return extract_text(html)

        page.close()
        return "\n\n".join(branches)

    except Exception as e:
        print(f"    [BRANCH ERROR] {url} → {e}")
        return ""


def scrape_branches_fastbank(url: str, pool: BrowserPool) -> str:
    """
    FastBank branches page: branch items are buttons with class Branch_item.
    Clicking opens details in Branch_lines div inside the button.
    """
    try:
        page = pool.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)

        count = page.evaluate("""
            () => document.querySelectorAll('button[class*="Branch_item"]').length
        """)
        print(f"    [BRANCHES] FastBank: found {count} Branch_item buttons")

        branches_text = []
        for i in range(count):
            try:
                result = page.evaluate(f"""
                    () => {{
                        const items = document.querySelectorAll('button[class*="Branch_item"]');
                        const item = items[{i}];
                        if (!item) return null;

                        item.click();
                        return true;
                    }}
                """)
                if not result:
                    continue

                page.wait_for_timeout(1200)

                detail = page.evaluate(f"""
                    () => {{
                        const items = document.querySelectorAll('button[class*="Branch_item"]');
                        const item = items[{i}];
                        if (!item) return null;

                        const name_el = item.querySelector('[class*="Branch_name"]') ||
                                        item.querySelector('span') ||
                                        item;
                        const name = name_el.textContent.trim().split('\\n')[0];

                        const lines_div = item.querySelector('[class*="Branch_lines"]');
                        if (lines_div) {{
                            return {{name: name, detail: lines_div.innerText.trim()}};
                        }}

                        const full = item.innerText.trim();
                        if (full.length > name.length + 10) {{
                            return {{name: name, detail: full}};
                        }}

                        return {{name: name, detail: ''}};
                    }}
                """)

                if detail:
                    if detail['detail']:
                        branches_text.append(f"{detail['name']}\n{detail['detail']}")
                        print(f"      Got: {detail['name']}")
                    else:
                        branches_text.append(detail['name'])
                        print(f"      Name only: {detail['name']}")

            except Exception as ex:
                print(f"      Error on item {i}: {ex}")

        page.close()

        if branches_text:
            return "\n\n".join(branches_text)
        return ""

    except Exception as e:
        print(f"    [BRANCH ERROR] {url} -> {e}")
        return ""


def scrape_branches_generic(url: str, pool: BrowserPool) -> str:
    """
    Generic branch scraper for FastBank and similar sites.
    Tries multiple strategies to extract branch data.
    """
    try:
        page = pool.new_page()
        page.goto(url, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(3000)

        branches_text = []

        BRANCH_LIST_SELECTORS = [
            ".branch-item",
            ".branches-list li",
            ".branch-list-item",
            "[data-branch]",
            ".sidebar-item",
            ".location-item",
            ".fspace-item",
            ".branch-card",
            "[class*='branch'] li",
            "[class*='branches'] > div",
            ".list-group-item",
            ".accordion-item",
            "[class*='office']",
            "[class*='location'] li",
        ]

        branch_elements = []
        for selector in BRANCH_LIST_SELECTORS:
            elements = page.query_selector_all(selector)
            if elements and len(elements) >= 2:
                print(f"    [BRANCHES] Found {len(elements)} items with '{selector}'")
                branch_elements = elements
                break

        if branch_elements:
            DETAIL_SELECTORS = [
                ".branch-detail", ".branch-info", ".location-detail",
                ".branch-popup", ".info-panel", ".selected-branch",
                "[class*='detail']", "[class*='info-panel']",
            ]

            for element in branch_elements:
                try:
                    branch_name = element.inner_text().strip().split("\n")[0]
                    element.click()
                    page.wait_for_timeout(1000)

                    detail_text = ""
                    for sel in DETAIL_SELECTORS:
                        detail = page.query_selector(sel)
                        if detail:
                            text = detail.inner_text().strip()
                            if text and len(text) > len(branch_name):
                                detail_text = text
                                break

                    if detail_text:
                        branches_text.append(f"{branch_name}\n{detail_text}")
                    else:
                        full_text = element.inner_text().strip()
                        if full_text:
                            branches_text.append(full_text)
                except Exception:
                    pass

        if not branches_text:
            print("    [BRANCHES] Interactive scraping failed, extracting all text")
            all_text = page.evaluate("""
                () => {
                    const elements = document.querySelectorAll(
                        '[class*="branch"], [class*="office"], [class*="location"], ' +
                        '[class*="address"], [class*="contact"]'
                    );
                    if (elements.length > 0) {
                        return Array.from(elements).map(el => el.innerText.trim()).filter(t => t.length > 5).join('\\n\\n');
                    }
                    const main = document.querySelector('main, [role="main"], .main-content');
                    return main ? main.innerText : '';
                }
            """)
            if all_text:
                branches_text.append(all_text)
            else:
                html = page.content()
                page.close()
                return extract_text(html)

        page.close()
        return "\n\n".join(branches_text)

    except Exception as e:
        print(f"    [BRANCH ERROR] {url} → {e}")
        return ""


def scrape_branches_aeb(url: str, pool: BrowserPool) -> str:
    """
    AEB branch-service-network page: branches are listed with names,
    addresses, hours, and phone numbers directly on the page.
    """
    try:
        page = pool.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)

        branch_data = page.evaluate("""
            () => {
                const results = [];
                const allText = document.body.innerText;
                const lines = allText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);

                let current_branch = null;
                let current_lines = [];

                for (const line of lines) {
                    // Branch names are typically in ALL CAPS Armenian
                    const isAllCapsArmenian = /^[\u0531-\u0556\u0559\s\\-\\.0-9]+$/.test(line) && line.length > 2 && line.length < 50;
                    const hasAddress = /\u0540\u0540|\u0584\\.|\u0583\u0578\u0572|\u0577\u056b\u0576/i.test(line);
                    const hasPhone = /\+374|510.910|86\s*86/.test(line);
                    const hasHours = /\\d{2}:\\d{2}/.test(line) && (/\u0535\u0580\u056f|\u0548\u0582\u0580|\u0532\u0561\u0581/.test(line));

                    if (isAllCapsArmenian && !hasAddress && !hasPhone) {
                        if (current_branch && current_lines.length > 0) {
                            results.push(current_branch + '\\n' + current_lines.join('\\n'));
                        }
                        current_branch = line;
                        current_lines = [];
                    } else if (current_branch && (hasAddress || hasPhone || hasHours)) {
                        current_lines.push(line);
                    }
                }
                if (current_branch && current_lines.length > 0) {
                    results.push(current_branch + '\\n' + current_lines.join('\\n'));
                }
                return results.join('\\n---\\n');
            }
        """)

        if not branch_data or len(branch_data) < 100:
            print("    [BRANCHES] JS extraction got little data, trying full page text")
            html = page.content()
            page.close()
            return extract_text(html)

        page.close()
        return branch_data

    except Exception as e:
        print(f"    [BRANCH ERROR] {url} -> {e}")
        return ""


def scrape_branches_amio(url: str, pool: BrowserPool) -> str:
    """
    Amio Bank offices page: extract branch list with addresses.
    The page has a list of branches with addresses visible.
    """
    try:
        page = pool.new_page()
        page.goto(url, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(3000)

        branch_data = page.evaluate("""
            () => {
                const results = [];
                const items = document.querySelectorAll(
                    '[class*="branch"], [class*="office"], [class*="location"], ' +
                    '.list-group-item, [class*="card"]'
                );
                for (const item of items) {
                    const text = item.innerText.trim();
                    if (text.length > 15) {
                        results.push(text);
                    }
                }
                if (results.length > 0) return results.join('\\n---\\n');
                const main = document.querySelector('main, [role="main"], .main-content, .content');
                return main ? main.innerText : document.body.innerText;
            }
        """)

        page.close()

        if branch_data:
            return branch_data
        return ""

    except Exception as e:
        print(f"    [BRANCH ERROR] {url} → {e}")
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPING ORCHESTRATION
# ══════════════════════════════════════════════════════════════════════════════

def scrape_topic(urls, pool: BrowserPool, js_rendered=False, follow_sublinks=True):
    """Scrape all URLs for one topic."""
    sections = []
    visited = set()
    dedup = TextDeduplicator()

    def scrape_single(url):
        if url in visited:
            return None
        visited.add(url)

        html = None
        for attempt in range(1, MAX_FETCH_RETRIES + 1):
            print(f"    Fetching ({attempt}/{MAX_FETCH_RETRIES}): {url}")
            if js_rendered:
                html = fetch_page_with_browser(url, pool)
            else:
                html = fetch_page_http(url)
            time.sleep(DELAY_BETWEEN_REQUESTS)
            if html is not None:
                break
        if html is None:
            print(f"    [FAILED] Unreachable after retries: {url}")

        if html is None:
            return None

        text = extract_text(html)
        if len(text) < 80:
            print(f"    [WARNING] Very little text — skipping.")
            return None

        text = dedup.deduplicate(text)
        return (text, html)

    for url in urls:
        result = scrape_single(url)
        if result is None:
            continue

        text, html = result
        sections.append(text)

        if not follow_sublinks:
            continue

        sublinks = discover_sublinks(url, html)
        if sublinks:
            print(f"    [CRAWL] Found {len(sublinks)} sub-links under {url}")

        for sublink in sublinks:
            sub_result = scrape_single(sublink)
            if sub_result is None:
                continue
            sub_text, _ = sub_result
            sections.append(sub_text)

    return "\n\n".join(sections)


def scrape_bank(bank, pool: BrowserPool):
    """Scrape all topics for one bank using shared browser."""
    print(f"\n{'═' * 60}")
    print(f"  Scraping: {bank['name']}")
    print(f"{'═' * 60}")

    js_rendered = bank.get("js_rendered", False)
    follow_sublinks = bank.get("follow_sublinks", True)
    sections = [f"BANK: {bank['name']}"]

    topic_labels = {
        "credits":  "CREDITS & LOANS",
        "deposits": "DEPOSITS & SAVINGS",
        "branches": "BRANCH LOCATIONS",
    }

    for topic_key, topic_label in topic_labels.items():
        urls = bank["urls"].get(topic_key, [])
        if not urls:
            continue
        print(f"\n  Topic: {topic_label}")

        if topic_key == "branches":
            bank_id = bank["id"]
            if bank_id == "ameriabank":
                content = scrape_branches_ameriabank(urls[0], pool)
            elif bank_id == "amio":
                content = scrape_branches_amio(urls[0], pool)
            elif bank_id == "aeb":
                content = scrape_branches_aeb(urls[0], pool)
            elif bank_id == "fastbank":
                content = scrape_branches_fastbank(urls[0], pool)
            else:
                content = scrape_branches_generic(urls[0], pool)
        else:
            content = scrape_topic(
                urls, pool,
                js_rendered=js_rendered,
                follow_sublinks=follow_sublinks,
            )

        sections.append(f"{topic_label}\n{content}")

    return "\n\n".join(sections)


def save_bank_data(bank_id, content):
    """Write scraped bank data to bank_data/<bank_id>.txt"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, f"{bank_id}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    size_kb = len(content.encode("utf-8")) / 1024
    print(f"\n  Saved → {filepath}  ({size_kb:.1f} KB)")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

def run_scraper(banks=BANK_CONFIGS):
    print("\nArmenian Bank Data Scraper  v2")
    print("=" * 60)
    print(f"Banks to scrape: {[b['name'] for b in banks]}")
    print(f"Output directory: {OUTPUT_DIR}\n")

    pool = BrowserPool()
    pool.start()

    try:
        for bank in banks:
            content = scrape_bank(bank, pool)
            save_bank_data(bank["id"], content)
    finally:
        pool.stop()

    print(f"\n{'═' * 60}")
    print("Scraping complete.")
    print(f"Files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        bank_ids = sys.argv[1:]
        selected = [b for b in BANK_CONFIGS if b["id"] in bank_ids]
        if selected:
            run_scraper(selected)
        else:
            print(f"No banks matched IDs: {bank_ids}")
            print(f"Available: {[b['id'] for b in BANK_CONFIGS]}")
    else:
        run_scraper()
