import os
import logging
import traceback
import requests
from bs4 import BeautifulSoup
from pyshex import ShExEvaluator
from rdflib import Graph
from wikidataintegrator import wdi_core, wdi_helpers, wdi_login
import functions
import config
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


GH_URL = f'https://api.github.com/repos/{config.OWNER}/{config.REPO}/issues'
DATE = '2025-02'
URL = f"https://tb.plazi.org/GgServer/srsStats/stats?outputFields=doc.uuid+bib.pubDate+bib.year+tax.name+tax.kingdomEpithet+tax.familyEpithet+tax.status&groupingFields=doc.uuid+bib.pubDate+bib.year+tax.name+tax.kingdomEpithet+tax.familyEpithet+tax.status&FP-bib.pubDate=%22{DATE}%25%22&FP-bib.year=2025&FP-tax.status=%22sp.%20nov.%22&format=JSON"
TREATMENT_URI_BASE = "https://git.ld.plazi.org/plazi/treatments-rdf/raw/branch/main/data/"
# TREATMENT_SHAPES = "https://raw.githubusercontent.com/plazi/treatments-rdf/main/shex/treatment.shex"
def main():
    logger.info(GH_URL)
    login = functions.setup_wikidata_login()
    treatmentURIs = functions.fetch_treatment_data(URL)

    print("treatments", len(treatmentURIs))
    #print(treatmentURIs)
    plazi_qid_map = functions.process_treatments(treatmentURIs, login, GH_URL, config.HEADERS, TREATMENT_URI_BASE,  config.TOKEN)
    with open(f"plazi_qid_map_{DATE}.json", "w") as f:
        json.dump(plazi_qid_map, f, indent=2)

if __name__ == "__main__":
    main()
