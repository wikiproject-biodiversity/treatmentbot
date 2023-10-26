import os
import logging
import traceback
import requests
from bs4 import BeautifulSoup
from pyshex import ShExEvaluator
from rdflib import Graph
from wikidataintegrator import wdi_core, wdi_helpers, wdi_login
import functions

# Constants
OWNER = 'plazi'
REPO = 'treatments-rdf'
TOKEN = os.environ['ghtoken']
HEADERS = {
    'Authorization': f'token {TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}
GH_URL = f'https://api.github.com/repos/{OWNER}/{REPO}/issues'
DATE = '2023-10-18'
URL = f"https://tb.plazi.org/GgServer/srsStats/stats?outputFields=doc.uuid+bib.pubDate+bib.year+tax.name+tax.kingdomEpithet+tax.familyEpithet+tax.status&groupingFields=doc.uuid+bib.pubDate+bib.year+tax.name+tax.kingdomEpithet+tax.familyEpithet+tax.status&FP-bib.pubDate=%22{DATE}%25%22&FP-bib.year=2023&FP-tax.status=%22sp.%20nov.%22&format=JSON"
TREATMENT_URI_BASE = "https://raw.githubusercontent.com/plazi/treatments-rdf/main/data/"
# TREATMENT_SHAPES = "https://raw.githubusercontent.com/plazi/treatments-rdf/main/shex/treatment.shex"
def main():
    print(GH_URL)
    login = functions.setup_wikidata_login()
    # treatmentURIs = functions.fetch_treatment_data(URL)
    treatmentURIs = ['03A41F259217632FFBEEFA44FE4BE8EB',
 '03A41F25921B633BFEA6FBA2FE43EC17',
 '03A41F25921F6335FE8FFCE2FDCAE8EB',
 '03A41F2592216304FEB4FC62FB0CE8EC',
 '03A41F2592236302FEA5F967FE0BE8EB',
 '03A41F25922B630AFC3BFBE2FB47E9CA',
 '03A41F25922B630FFEC6FE20FC7CEB08',
 '03A41F2592326313FC17FB05FC3FE96B',
 '03A41F259236630FFEDCFD63FE0FEE56',
 'BB7C373A27715C9B9521023C0449D77C',
 'CB5F87A3FFF1F039FF2EFF54FC13EA52',
 'CB5F87A3FFFBF037FF2EFD00FEEFEB47',
 'CB5F87A3FFFDF03FFF2EFAF4FABAEC96',
 'CB5F87A3FFFEF033FF2EFA27FA3BE92A']
    print("treatments", len(treatmentURIs))
    print(treatmentURIs)
    functions.process_treatments(treatmentURIs,login, GH_URL, HEADERS, TREATMENT_URI_BASE, TOKEN)


if __name__ == "__main__":
    main()
