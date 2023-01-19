from rdflib import Graph
from wikidataintegrator import wdi_core, wdi_login, wdi_helpers
import copy
from bs4 import BeautifulSoup
import requests
import os

if "WDUSER" in os.environ and "WDPASS" in os.environ:
    WDUSER = os.environ['WDUSER']
    WDPASS = os.environ['WDPASS']
else:
    raise ValueError("WDUSER and WDPASS must be specified in local.py or as environment variables")

login = wdi_login.WDLogin(WDUSER, WDPASS)

treatmentURIBase = "https://raw.githubusercontent.com/plazi/treatments-rdf/main/data/"
treatmentURIs = [
"03/BD/87/03BD87E0FFB340296E07C329B68B1336.ttl",
"03/BD/87/03BD87E0FFB5402E6D4AC677B42F11D5.ttl",
"03/BD/87/03BD87E0FFB5402F6D4AC221B1E910DD.ttl",
"03/BD/87/03BD87E0FFB5402F6E07C744B185140C.ttl",
"03/BD/87/03BD87E0FFB6402F6D4AC537B47613BB.ttl",
"03/BD/87/03BD87E0FFB7402D6E07C5C0B1BE104E.ttl",
"03/BD/87/03BD87E0FFB940226D4AC7EDB1351112.ttl"
]

for treatmentURI in treatmentURIs:
    print(
        "Processing treatment: " + treatmentURIBase + treatmentURI
    )
    try:
            treatmentURI = treatmentURIBase + treatmentURI
            treatment = Graph()
            treatment.parse(treatmentURI, format="turtle")

            query = """
            PREFIX trt: <http://plazi.org/vocab/treatment#>
            SELECT DISTINCT ?treatment ?taxon ?publication WHERE
            {
                VALUES ?taxonlinkProp {trt:definesTaxonConcept trt:augmentsTaxonConcept trt:treatsTaxonName}
                ?treatment rdf:type trt:Treatment ;
                           ?taxonlinkProp ?taxon ;
                           trt:publishedIn ?publication .
            }
            """
            qres = treatment.query(query)
            if len(qres)==0:
                continue
            for row in qres:
                DOI = str(row["publication"]).replace("https://dx.doi.org/", "").replace("http://dx.doi.org/", "").replace("http://doi.org/", "").replace("https://doi.org/", "").replace("HTTP://DOI.ORG/", "").replace("HTTP://DX.DOI.ORG/", "")
                plaziuuid = str(row["treatment"]).replace("http://treatment.plazi.org/id/", "")
                plaziuri = str(row["treatment"])
                plazidashuuid = plaziuuid[0:8]+"-"+plaziuuid[8:12]+"-"+plaziuuid[12:16]+"-"+plaziuuid[16:20]+"-"+plaziuuid[20:]
                print(DOI)

            qid = wdi_helpers.PublicationHelper(DOI, id_type="doi", source="crossref").get_or_create(login)
            publication_qid = qid[0]
            publication_qid
            print(publication_qid)

            # Treatment Item
            treatmentstatements = []
            treatment_reference = [wdi_core.WDItemID(value="Q54857867", prop_nr="P248", is_reference=True),
                                  wdi_core.WDExternalID(plazidashuuid, prop_nr="P1992", is_reference=True)]

            # find all subjects of any type
            treatmentstatements.append(wdi_core.WDItemID(value="Q32945461", prop_nr="P31", references=[copy.deepcopy(treatment_reference)])) # instance of
            treatmentstatements.append(wdi_core.WDUrl(plaziuri, prop_nr="P2888", references=[copy.deepcopy(treatment_reference)])) # exact_match
            treatmentstatements.append(wdi_core.WDExternalID(plazidashuuid, prop_nr="P1992", references=[copy.deepcopy(treatment_reference)])) #plazi
            # treatmentstatements.append(wdi_core.WDExternalID(DOI, prop_nr="P356", references=[copy.deepcopy(treatment_reference)])) #DOI
            #treatmentstatements.append(wdi_core.WDExternalID(plazidashuuid, prop_nr="P1746", references=[copy.deepcopy(treatment_reference)])) #zoobank act

            wdTreatmentQuery = f"""SELECT * WHERE {{?treatment wdt:P2888 <{plaziuri}>}}"""
            wdTreatment = wdi_core.WDFunctionsEngine.execute_sparql_query(wdTreatmentQuery)
            contents = requests.get(plaziuri)
            soup = BeautifulSoup(contents.content, 'lxml')
            title = soup.title
            title = str(title).split(",")[0].replace("<title>", "").replace("&amp;", "&").replace(" - Plazi TreatmentBank</title>", "").replace("</title>", "")

            if len(wdTreatment["results"]["bindings"]) == 0:
                treatmentItem = wdi_core.WDItemEngine(new_item=True, data=treatmentstatements)
                treatmentItem.set_label(title, lang="en")
                treatmentItem.set_description("taxonomic treatment", lang="en")
            else:
                treatmentItem = wdi_core.WDItemEngine(wd_item_id=wdTreatment["results"]["bindings"][0]["treatment"]["value"].replace("http://www.wikidata.org/entity/",""), data=treatmentstatements, keep_good_ref_statements=True)

            treatment_qid = treatmentItem.write(login)

            ## taxon item
            taxonstatements = []
            publication_reference = [wdi_core.WDItemID(publication_qid, prop_nr="P248", is_reference=True)]
            taxonstatements.append(wdi_core.WDItemID("Q16521", prop_nr="P31", references=[copy.deepcopy(publication_reference)]))
            taxonrankdict = dict()
            query = """SELECT ?taxonrank ?taxonrankLabel WHERE {?taxonrank wdt:P31 wd:Q427626 .
               SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
            }"""
            print(query)
            for row in wdi_core.WDFunctionsEngine.execute_sparql_query(query)["results"]["bindings"]:
                taxonrankdict[row["taxonrankLabel"]["value"]] = row["taxonrank"]["value"].replace("http://www.wikidata.org/entity/", "")

            query = f"""
            PREFIX trt: <http://plazi.org/vocab/treatment#>
            prefix dwc: <http://rs.tdwg.org/dwc/terms/>
            SELECT * WHERE {{
               VALUES ?taxonlinkProp {{trt:definesTaxonConcept trt:augmentsTaxonConcept trt:treatsTaxonName}}
               <{plaziuri}> ?taxonlinkProp ?taxon .
               ?taxon trt:hasTaxonName ?taxonName .
               ?taxonName dwc:rank ?rank ;
                          trt:hasParentName ?parentTaxonname .
               ?parentTaxonname dwc:rank ?parentRank .
               OPTiONAL {{?taxon dwc:authorityYear ?year .}}
            }}
            """
            qres = treatment.query(query)
            for row in qres:
                print(row.taxonName, row.rank, row.parentTaxonname, row.parentRank)
                query2 = f"""
                PREFIX trt: <http://plazi.org/vocab/treatment#>
                prefix dwc: <http://rs.tdwg.org/dwc/terms/>
                SELECT * WHERE {{
                <{row.taxonName}> dwc:{row.rank} ?taxonName .
                <{row.parentTaxonname}> dwc:{row.parentRank} ?parentTaxonName .
                }}
                """

                qres2 = treatment.query(query2)
                for row2 in qres2:
                    if str(row.rank) == "species":
                        taxonName = str(row2.parentTaxonName)+" "+ str(row2.taxonName)
                    else:
                        taxonName = str(row2.taxonName)
                    parentTaxonName = row2.parentTaxonName
                    parentRank = row.parentRank
                    wdTaxonQuery = f"""SELECT * WHERE {{?taxon wdt:P225 '{taxonName}'}}"""
                    wdParentTaxonQuery = f"""SELECT * WHERE {{?parentTaxon wdt:P225 '{parentTaxonName}'}}"""

            wdi_core.WDFunctionsEngine.execute_sparql_query(query)
            print(taxonName, row2.parentTaxonName)
            taxonQid = wdi_core.WDFunctionsEngine.execute_sparql_query(wdTaxonQuery)["results"]["bindings"]
            parentTaxonQid = wdi_core.WDFunctionsEngine.execute_sparql_query(wdParentTaxonQuery)["results"]["bindings"]

            query = f"""
            PREFIX trt: <http://plazi.org/vocab/treatment#>
            prefix dwc: <http://rs.tdwg.org/dwc/terms/>
            SELECT * WHERE {{
               VALUES ?taxonlinkProp {{trt:definesTaxonConcept trt:augmentsTaxonConcept trt:treatsTaxonName}}
               <{plaziuri}> ?taxonlinkProp ?taxon .
               ?taxon dwc:rank ?rank .
               OPTIONAL {{?taxon dwc:genus ?genus }}
               OPTIONAL {{?taxon dwc:species ?species }}
               OPTiONAL {{?taxon dwc:authorityYear ?year .}}
            }}
            """
            qres = treatment.query(query)
            for row in qres:
                year_qualifier = wdi_core.WDTime(str(row["year"])+"-01-01T00:00:00Z", prop_nr="P574", is_qualifier=True)
                if str(row["rank"]) == "species":
                    taxonname = row["genus"]+" "+row["species"]
                    parenttaxon = row["genus"]
                else:
                    query2 = f"""
                    PREFIX trt: <http://plazi.org/vocab/treatment#>
                    PREFIX dwc: <http://rs.tdwg.org/dwc/terms/>
                    SELECT * WHERE {{
                        VALUES ?taxonlinkProp {{trt:definesTaxonConcept trt:augmentsTaxonConcept trt:treatsTaxonName}}
                       <{plaziuri}> ?taxonlinkProp ?taxon ."""
                    query2 += "?taxon dwc:"+row["rank"]+" ?taxonname .}"
                    qres2 = treatment.query(query2)
                    for row2 in qres2:
                        taxonname = row2["taxonname"]
                # taxonstatements.append(wdi_core.WDItemID("Q16521", prop_nr="P31", references=[copy.deepcopy(publication_reference)]))
                if "year" not in row:
                    taxonstatements.append(wdi_core.WDString(taxonname, prop_nr="P225", references=[copy.deepcopy(publication_reference)]))
                else:
                    taxonstatements.append(wdi_core.WDString(taxonname, prop_nr="P225", references=[copy.deepcopy(publication_reference)], qualifiers=[year_qualifier]))
                taxonstatements.append(wdi_core.WDItemID(taxonrankdict[str(row["rank"].lower())], prop_nr="P105", references=[copy.deepcopy(treatment_reference)]))
                if len(parentTaxonQid) > 0:
                    taxonstatements.append(wdi_core.WDItemID(parentTaxonQid[0]["parentTaxon"]["value"].replace("http://www.wikidata.org/entity/",""), prop_nr="P171", references=[copy.deepcopy(treatment_reference)]))
                taxonstatements.append(wdi_core.WDItemID(treatment_qid, prop_nr="P10594", references=[copy.deepcopy(treatment_reference)]))

            if len(taxonQid)>0:
                taxon_item = wdi_core.WDItemEngine(wd_item_id=taxonQid[0]["taxon"]["value"].replace("http://www.wikidata.org/entity/",""), data=taxonstatements, keep_good_ref_statements=True)
            else:
                taxon_item = wdi_core.WDItemEngine(new_item=True, data=taxonstatements)
                taxon_item.set_label(taxonname, lang="en")
                print("2.",taxonname)
                taxon_item.set_description("taxon", lang="en")

            taxon_qid=taxon_item.write(login)

            statements = [wdi_core.WDItemID(value=taxon_qid, prop_nr="P921", references=[copy.deepcopy(treatment_reference)])]
            item = wdi_core.WDItemEngine(wd_item_id=publication_qid, data=statements,keep_good_ref_statements=True)
            item.write(login)

    except:
        print("error", plaziuri)
        continue
