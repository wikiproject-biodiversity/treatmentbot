import json
import csv
import sys
import os
from datetime import datetime

# Argumentcontrole
if len(sys.argv) < 2:
    print("Gebruik: python generate_sssom_with_metadata.py <input_json>")
    sys.exit(1)

input_json = sys.argv[1]
if not os.path.isfile(input_json):
    print(f"File not found: {input_json}")
    sys.exit(1)

# Genereer output-bestandsnaam met .sssom.tsv extensie
basename = os.path.splitext(os.path.basename(input_json))[0]
output_file = f"{basename}.sssom.tsv"

# Datum van laatste wijziging van het JSON-bestand
timestamp = os.path.getmtime(input_json)
json_modified_date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")

# Metadata instellingen
MAPPING_JUSTIFICATION = "semapv:ManualMappingCuration"
AUTHOR_ID = "orcid:0000-0001-9773-4008"  # ← Vervang met jouw echte ORCID
CONFIDENCE = "0.9"

# YAML-header
yaml_header = f"""\
# SSSOM-METADATA
mapping_set_id: https://github.com/YOUR-GITHUB-USERNAME/YOUR-REPO-NAME
mapping_set_title: Plazi-Wikidata Treatment Mappings
mapping_set_description: >
  Mappings between Plazi treatment URIs and Wikidata QIDs representing treatments, taxa, and publications.
  Includes semantic predicates like skos:exactMatch, cito:isEvidenceFor, and cito:cites.
created_by: {AUTHOR_ID}
curie_map:
  wd: https://www.wikidata.org/entity/
  skos: http://www.w3.org/2004/02/skos/core#
  cito: http://purl.org/spar/cito/
  semapv: http://purl.org/semapv/
  orcid: https://orcid.org/
  dwc: http://rs.tdwg.org/dwc/terms/
  prov: http://www.w3.org/ns/prov#
license: https://creativecommons.org/publicdomain/zero/1.0/
version: 1.0
mapping_provider: Plazi via Wikidata bot
subject_source: https://plazi.org
object_source: https://www.wikidata.org
date: {json_modified_date}
# END SSSOM-METADATA

"""

# SSSOM kolommen
fieldnames = [
    "subject_id", "subject_label", "predicate_id", "object_id", "object_label",
    "mapping_justification", "author_id", "confidence", "comment"
]

# Laad JSON-bestand
with open(input_json, "r", encoding="utf-8") as f:
    treatments = json.load(f)

# Bouw mapping-rijen
rows = []
for treatment_uri, qids in treatments.items():
    treatment_qid = f"wd:{qids['treatment_qid']}"
    taxon_qid = f"wd:{qids['taxon_qid']}"
    publication_qid = f"wd:{qids['publication_qid']}"

    rows.append({
        "subject_id": treatment_uri,
        "subject_label": "treatment",
        "predicate_id": "skos:exactMatch",
        "object_id": treatment_qid,
        "object_label": "treatment_qid",
        "mapping_justification": MAPPING_JUSTIFICATION,
        "author_id": AUTHOR_ID,
        "confidence": CONFIDENCE,
        "comment": ""
    })
    rows.append({
        "subject_id": treatment_uri,
        "subject_label": "treatment",
        "predicate_id": "cito:isEvidenceFor",
        "object_id": taxon_qid,
        "object_label": "taxon_qid",
        "mapping_justification": MAPPING_JUSTIFICATION,
        "author_id": AUTHOR_ID,
        "confidence": CONFIDENCE,
        "comment": ""
    })
    rows.append({
        "subject_id": publication_qid,
        "subject_label": "publication",
        "predicate_id": "cito:cites",
        "object_id": treatment_uri,
        "object_label": "treatment",
        "mapping_justification": MAPPING_JUSTIFICATION,
        "author_id": AUTHOR_ID,
        "confidence": CONFIDENCE,
        "comment": ""
    })

# Schrijf bestand met YAML-header + TSV-data
with open(output_file, "w", encoding="utf-8", newline="") as f:
    f.write(yaml_header)
    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)

print(f"✅ SSSOM-bestand gegenereerd: {output_file} (datum: {json_modified_date})")