import json
import requests
url = "https://tb.plazi.org/GgServer/srsStats/stats?outputFields=doc.uuid+bib.pubDate+bib.year+tax.name+tax.kingdomEpithet+tax.familyEpithet+tax.status&groupingFields=doc.uuid+bib.pubDate+bib.year+tax.name+tax.kingdomEpithet+tax.familyEpithet+tax.status&FP-bib.pubDate=%222024-04-01%25%22&FP-bib.year=2024&FP-tax.status=%22sp.%20nov.%22&format=JSON"
json_data = requests.get(url).text
data = json.loads(json_data)

# Extract DocUuid values
doc_uuids = [item["DocUuid"] for item in data["data"]]

print(len(doc_uuids))
# Print the extracted DocUuid values
for doc_uuid in doc_uuids:
    print(f"\"{doc_uuid}\",")