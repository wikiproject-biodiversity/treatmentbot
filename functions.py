import requests
from rdflib import Graph, URIRef
from datetime import datetime
import copy
from wikidataintegrator import wdi_core, wdi_login, wdi_helpers
from bs4 import BeautifulSoup
import traceback
import os
import logging
from pyshex import ShExEvaluator
import config

def ensure_qid(value_or_dict):
    """Ensure the input is a string QID, even if wrapped in a dict with a 'qid' key."""
    return value_or_dict.get("qid") if isinstance(value_or_dict, dict) else value_or_dict

def add_taxon_name(taxon_item, taxon_name, publication_qid):
    existing_taxon_names = [s.getTarget() for s in taxon_item.statements if s.getPropNr() == 'P225']
    if taxon_name not in existing_taxon_names:
        reference = wdi_core.WDItemID(value=publication_qid, prop_nr='P248', is_reference=True)  # Assuming 'P248' is the property for 'stated in'
        statement = wdi_core.WDString(value=taxon_name, prop_nr='P225', references=[reference])
        taxon_item.update(data=[statement])

def update_or_create_taxon(taxon_qid, taxon_name, publication_qid):
    login_instance = setup_wikidata_login()
    taxon_item = wdi_core.WDItemEngine(wd_item_id=taxon_qid) if taxon_qid else wdi_core.WDItemEngine()

    add_taxon_name(taxon_item, taxon_name, publication_qid)

    taxon_item.write(login_instance)

def add_publication(doi, qid):
    config.publication_QIDs[doi] = qid

def get_publication(doi):
    return config.publication_QIDs.get(doi)


def setup_wikidata_login():
    if "WDUSER" in os.environ and "WDPASS" in os.environ:
        WDUSER = os.environ['WDUSER']
        WDPASS = os.environ['WDPASS']
    else:
        raise ValueError("WDUSER and WDPASS must be specified in local.py or as environment variables")
    return wdi_login.WDLogin(WDUSER, WDPASS)

def fetch_treatment_data(url):
    results = requests.get(url).json()
    treatmentURIs = [result["DocUuid"] for result in results["data"]]
    return treatmentURIs

def process_treatments(treatmentURIs, login, ghurl, headers, treatmentURIBase, token):
    plazi_qid_map = {}
    with open("treatment.shex", 'r') as schema_file:
        shex_schema = schema_file.read()

    for uuid in treatmentURIs:
        continueNext = False
        treatmentURI = (f"{uuid[0:2]}/{uuid[2:4]}/{uuid[4:6]}/{uuid}.ttl")
        print("Processing treatment:", treatmentURIBase + treatmentURI)
        results = []
        treatment = Graph()
        try:
            treatment.parse(treatmentURIBase + treatmentURI, format="turtle")
            for result in ShExEvaluator(rdf=treatment, schema=shex_schema, start="http://example.org/treatment",
                                        focus="http://treatment.plazi.org/id/" + uuid).evaluate():
                print(result)
                if not result.result:  # if result is false, then there is a constraint violation
                    data = {
                        'title': treatmentURI + ' cannot be added to Wikidata',
                        'body': 'While running the Wikidata bot, a ShEx validation error on ' + treatmentURI + 'occurred.\n\n# Reason' + result.reason + '\n\n # schema \n``` ' + shex_schema + ' ```',
                    }

                    response = requests.post(ghurl, headers=headers, json=data)

                    if response.status_code == 201:
                        print(f"Issue created: {response.json()['html_url']}")
                    else:
                        print(f"Error {response.status_code}: {response.text}")
                    print(result.reason)
                    continueNext = True
            if continueNext:
                continue
        except Exception as e:
            logging.error(f"Error in file: {treatmentURIBase + treatmentURI} - {str(e)}")

        try:
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
            if len(qres) == 0:
                continue
            for row in qres:
                DOI = str(row["publication"]).replace("https://dx.doi.org/", "").replace("http://dx.doi.org/", "").replace(
                    "http://doi.org/", "").replace("https://doi.org/", "").replace("HTTP://DOI.ORG/", "").replace(
                    "HTTP://DX.DOI.ORG/", "")
                plaziuuid = str(row["treatment"]).replace("http://treatment.plazi.org/id/", "")
                plaziuri = str(row["treatment"])
                plazidashuuid = plaziuuid[0:8] + "-" + plaziuuid[8:12] + "-" + plaziuuid[12:16] + "-" + plaziuuid[
                                                                                                        16:20] + "-" + plaziuuid[
                                                                                                                       20:]
                print(DOI)

            if get_publication(DOI):
                publication_qid = get_publication(DOI)
            else:
                qid = wdi_helpers.PublicationHelper(DOI, id_type="doi", source="crossref").get_or_create(login)
                publication_qid = qid[0]
                if publication_qid == None:
                    publication_qid = create_article_item(plazidashuuid, treatment, None, login, ghurl, headers, token)
                if publication_qid == None:
                    ghtitle = treatmentURIBase + treatmentURI + ' cannot be added to Wikidata'
                    ghbody = "The treament: "+treatmentURIBase + treatmentURI + " can currently not be added to Wikidata. Due to an issue ({publication_qid['ghi']}), there is no publication in Wikidata to cite. This would create a wikidata item for a treatment without citations."
                    data = {
                        'title':  ghtitle,
                        'body': ghbody,
                    }
                    response = requests.post(ghurl, headers=headers, json=data)

                    if response.status_code == 201:
                        print(f"Issue created: {response.json()['html_url']}")
                    else:
                        print(f"Error {response.status_code}: {response.text}")
                    continue
                add_publication(DOI, publication_qid)
                print(publication_qid)

            # Treatment Item
            treatmentstatements = []
            treatment_reference = [wdi_core.WDItemID(value="Q54857867", prop_nr="P248", is_reference=True),
                                   wdi_core.WDExternalID(plazidashuuid, prop_nr="P1992", is_reference=True)]

            # find all subjects of any type
            treatmentstatements.append(wdi_core.WDItemID(value="Q32945461", prop_nr="P31",
                                                         references=[copy.deepcopy(treatment_reference)]))  # instance of
            treatmentstatements.append(
                wdi_core.WDUrl(plaziuri, prop_nr="P2888", references=[copy.deepcopy(treatment_reference)]))  # exact_match
            treatmentstatements.append(wdi_core.WDExternalID(plazidashuuid, prop_nr="P1992",
                                                             references=[copy.deepcopy(treatment_reference)]))  # plazi
            # treatmentstatements.append(wdi_core.WDExternalID(DOI, prop_nr="P356", references=[copy.deepcopy(treatment_reference)])) #DOI
            # treatmentstatements.append(wdi_core.WDExternalID(plazidashuuid, prop_nr="P1746", references=[copy.deepcopy(treatment_reference)])) #zoobank act

            wdTreatmentQuery = f"""SELECT * WHERE {{?treatment wdt:P2888 <{plaziuri}>}}"""
            wdTreatment = wdi_core.WDFunctionsEngine.execute_sparql_query(wdTreatmentQuery)
            contents = requests.get(plaziuri)
            print(plaziuri)
            # print(contents.text)
            soup = BeautifulSoup(contents.content)
            title = soup.title
            title = str(title).split(",")[0].replace("<title>", "").replace("&amp;", "&").replace(
                " - Plazi TreatmentBank</title>", "").replace("</title>", "")

            if len(wdTreatment["results"]["bindings"]) == 0:
                treatmentItem = wdi_core.WDItemEngine(new_item=True, data=treatmentstatements)
                treatmentItem.set_label(title, lang="en")
                treatmentItem.set_description("taxonomic treatment", lang="en")
                treatment_qid = treatmentItem.write(login)
                plazi_qid_map[plaziuri] = {"treatment_qid": treatment_qid}
            else:
                treatmentItem = wdi_core.WDItemEngine(
                    wd_item_id=wdTreatment["results"]["bindings"][0]["treatment"]["value"].replace(
                        "http://www.wikidata.org/entity/", ""), data=treatmentstatements, keep_good_ref_statements=True)
                treatment_qid = treatmentItem.wd_item_id
                plazi_qid_map[plaziuri] = {"treatment_qid": treatment_qid}

            publication_qid_val = ensure_qid(publication_qid)
            ## taxon item
            taxonstatements = []
            publication_reference = [wdi_core.WDItemID(publication_qid_val, prop_nr="P248", is_reference=True)]
            taxonstatements.append(
                wdi_core.WDItemID("Q16521", prop_nr="P31", references=[copy.deepcopy(publication_reference)]))
            taxonrankdict = dict()
            query = """SELECT ?taxonrank ?taxonrankLabel WHERE {?taxonrank wdt:P31 wd:Q427626 .
                       SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
                    }"""
            print(query)
            for row in wdi_core.WDFunctionsEngine.execute_sparql_query(query)["results"]["bindings"]:
                taxonrankdict[row["taxonrankLabel"]["value"]] = row["taxonrank"]["value"].replace(
                    "http://www.wikidata.org/entity/", "")

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
                       OPTIONAL {{?taxon dwc:authorityYear ?year .}}
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
                        taxonName = str(row2.parentTaxonName) + " " + str(row2.taxonName)
                    else:
                        taxonName = str(row2.taxonName)
                    parentTaxonName = row2.parentTaxonName
                    parentRank = row.parentRank
                    wdTaxonQuery = f"""SELECT * WHERE {{?taxon wdt:P225 '{taxonName}'}}"""
                    wdParentTaxonQuery = f"""SELECT * WHERE {{?parentTaxon wdt:P225 '{parentTaxonName}'}}"""

            wdi_core.WDFunctionsEngine.execute_sparql_query(query)
            print(taxonName, row2.parentTaxonName)
            taxonQid = wdi_core.WDFunctionsEngine.execute_sparql_query(wdTaxonQuery)["results"]["bindings"]
            print(wdTaxonQuery)
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
                year_qualifier = wdi_core.WDTime(str(row["year"]) + "-01-01T00:00:00Z", prop_nr="P574", is_qualifier=True)
                if str(row["rank"]) == "species":
                    taxonname = row["genus"] + " " + row["species"]
                    parenttaxon = row["genus"]
                else:
                    query2 = f"""
                            PREFIX trt: <http://plazi.org/vocab/treatment#>
                            PREFIX dwc: <http://rs.tdwg.org/dwc/terms/>
                            SELECT * WHERE {{
                                VALUES ?taxonlinkProp {{trt:definesTaxonConcept trt:augmentsTaxonConcept trt:treatsTaxonName}}
                               <{plaziuri}> ?taxonlinkProp ?taxon ."""
                    query2 += "?taxon dwc:" + row["rank"] + " ?taxonname .}"
                    qres2 = treatment.query(query2)
                    for row2 in qres2:
                        taxonname = row2["taxonname"]
                # taxonstatements.append(wdi_core.WDItemID("Q16521", prop_nr="P31", references=[copy.deepcopy(publication_reference)]))
                if "year" not in row:
                    taxonstatements.append(
                        wdi_core.WDString(taxonname, prop_nr="P225", references=[copy.deepcopy(publication_reference)]))
                else:
                    taxonstatements.append(
                        wdi_core.WDString(taxonname, prop_nr="P225", references=[copy.deepcopy(publication_reference)],
                                          qualifiers=[year_qualifier]))
                taxonstatements.append(wdi_core.WDItemID(taxonrankdict[str(row["rank"].lower())], prop_nr="P105",
                                                         references=[copy.deepcopy(treatment_reference)]))
                if len(parentTaxonQid) > 0:
                    taxonstatements.append(wdi_core.WDItemID(
                        parentTaxonQid[0]["parentTaxon"]["value"].replace("http://www.wikidata.org/entity/", ""),
                        prop_nr="P171", references=[copy.deepcopy(treatment_reference)]))
                taxonstatements.append(
                    wdi_core.WDItemID(treatment_qid, prop_nr="P10594", references=[copy.deepcopy(treatment_reference)]))

            if len(taxonQid) > 0:
                taxon_item = wdi_core.WDItemEngine(
                    wd_item_id=taxonQid[0]["taxon"]["value"].replace("http://www.wikidata.org/entity/", ""),
                    data=taxonstatements, keep_good_ref_statements=True)
            else:
                taxon_item = wdi_core.WDItemEngine(new_item=True, data=taxonstatements)
                taxon_item.set_label(taxonname, lang="en")
                print("2.", taxonname)
                taxon_item.set_description("taxon", lang="en")

            taxon_qid = taxon_item.write(login)
            plazi_qid_map[plaziuri]["taxon_qid"] = taxon_qid
            plazi_qid_map[plaziuri]["publication_qid"] = ensure_qid(publication_qid)

            statements = [
                wdi_core.WDItemID(value=taxon_qid, prop_nr="P921", references=[copy.deepcopy(treatment_reference)])]
            item = wdi_core.WDItemEngine(wd_item_id=publication_qid_val, data=statements, keep_good_ref_statements=True)
            print(item.write(login))



        except Exception as e:

            print("An error occurred:", e)

            # Print the traceback
            traceback.print_exc()

            # Optionally, you can store the traceback as a string for later use
            traceback_str = traceback.format_exc()

            continue
    return plazi_qid_map

def extract_journal_details(g):
    # Extract the snippet with the desired predicate
    desired_predicate = URIRef("http://purl.org/spar/fabio/JournalArticle")
    subject_of_interest = None

    for subject, predicate, obj in g:
        if obj == desired_predicate:
            subject_of_interest = subject
            break

    # Access specific elements if the desired subject is found
    if subject_of_interest:
        creator_literals = [str(author) for author in
                            g.objects(subject_of_interest, URIRef("http://purl.org/dc/elements/1.1/creator"))]
        creators = []

        for literal in creator_literals:
            # Split on semicolon to separate multiple authors
            split_authors = [a.strip() for a in literal.split(";") if a.strip()]
            creators.extend(split_authors)
        date = str(next(g.objects(subject_of_interest, URIRef("http://purl.org/dc/elements/1.1/date")), None))
        title = str(next(g.objects(subject_of_interest, URIRef("http://purl.org/dc/elements/1.1/title")), None))
        start_page = str(next(g.objects(subject_of_interest, URIRef("http://purl.org/ontology/bibo/startPage")), None))
        end_page = str(next(g.objects(subject_of_interest, URIRef("http://purl.org/ontology/bibo/endPage")), None))
        issue = str(next(g.objects(subject_of_interest, URIRef("http://purl.org/ontology/bibo/issue")), None))
        journal = str(next(g.objects(subject_of_interest, URIRef("http://purl.org/ontology/bibo/journal")), None))
        pub_date = str(next(g.objects(subject_of_interest, URIRef("http://purl.org/ontology/bibo/pubDate")), None))

        result = {
            "Authors": creators,
            "Date": date,
            "Title": title,
            "Start Page": start_page,
            "End Page": end_page,
            "Issue": issue,
            "Journal": journal,
            "Publication Date": pub_date
        }
        return result
    return {}

def create_article_item(plazidashuuid, treatmentGraph, journalQID, login, ghurl, headers, token):
    details = extract_journal_details(treatmentGraph)
    title = details["Title"]
    pub_date = details["Publication Date"]
    issue = details["Issue"]
    start_page = details["Start Page"]
    end_page = details["End Page"]
    creators = details["Authors"]
    journalTitle = details["Journal"]

    articleQID = {"qid": None, "ghi": None}

    plazireference = wdi_core.WDExternalID(plazidashuuid, prop_nr="P1992", is_reference=True)
    plazistatedin = wdi_core.WDItemID("Q54857867", prop_nr="P248", is_reference=True)
    pubref = [plazireference, plazistatedin]
    publicationStatements = []

    # instance of (P31)
    publicationStatements.append(wdi_core.WDItemID("Q732577", prop_nr="P31", references=[copy.deepcopy(pubref)]))

    # Title (P1476)
    publicationStatements.append(wdi_core.WDMonolingualText(title, language="en", prop_nr="P1476", references=[copy.deepcopy(pubref)]))

    # publication date (P577)
    date_obj = datetime.strptime(pub_date, '%Y-%m-%d')
    pub_dateTime = date_obj.strftime('+%Y-%m-%dT%H:%M:%SZ')
    publicationStatements.append(wdi_core.WDTime(pub_dateTime, prop_nr="P577", references=[copy.deepcopy(pubref)]))

    # issue (P433)
    publicationStatements.append(wdi_core.WDString(issue, prop_nr="P433", references=[copy.deepcopy(pubref)]))

    # pages (P304)
    if start_page and end_page:
        page_range = f"{start_page} - {end_page}"
    elif start_page:
        page_range = start_page
    elif end_page:
        page_range = end_page
    else:
        page_range = None
    publicationStatements.append(wdi_core.WDString(page_range, prop_nr="P304", references=[copy.deepcopy(pubref)]))

    # authors (P2093)
    for index, author in enumerate(creators):
        series_ordinal_qualifier = wdi_core.WDString(str(index+1), prop_nr="P1545", is_qualifier=True)
        publicationStatements.append(wdi_core.WDString(author, prop_nr="P2093", references=[copy.deepcopy(pubref)], qualifiers=[series_ordinal_qualifier]))

    # published in (P1433)
    journalQID = get_or_create_journal(journalTitle, token, ghurl, pubref, login)
    if journalQID:
        publicationStatements.append(wdi_core.WDItemID(journalQID, prop_nr="P1433", references=[copy.deepcopy(pubref)]))

    articleQuery = f"SELECT * WHERE {{?article rdfs:label '{title}'@en .}}"
    article_wdqs_results = wdi_core.WDFunctionsEngine.execute_sparql_query(articleQuery, as_dataframe=True)

    if len(article_wdqs_results) == 1:
        articleQID["qid"] = article_wdqs_results.loc[0, 'article'].replace("http://www.wikidata.org/entity/", "")
    elif len(article_wdqs_results) > 1:
        data = {
            'title': title + ' exists more than once on Wikidata',
            'body': title + ' exists more than once on Wikidata. The Wikidata treatment bot cannot distinguish which is the most appropriate Wikidata item. Please curate both articles by possibly merging the following items: ' + ' '.join(article_wdqs_results['article'].tolist()) + '.',
        }
        response = requests.post(ghurl, headers=headers, json=data)

        if response.status_code == 201:
            print(f"Issue created: {response.json()['html_url']}")
            articleQID["ghi"] = response.json()['html_url']
        else:
            print(f"Error {response.status_code}: {response.text}")
    else:
        articleItem = wdi_core.WDItemEngine(data=publicationStatements)
        articleItem.set_label(title, lang="en")
        articleItem.set_description("scientific article")
        articleQID["qid"] = articleItem.write(login)

    return articleQID

import requests
from wikidataintegrator import wdi_core


def get_or_create_journal(journalTitle, token, ghurl, pubref, login):
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    journalQuery = f"""
    SELECT * WHERE {{
        ?journal wdt:P31 wd:Q5633421 ;
                 rdfs:label "{journalTitle}"@en .
    }}
    """
    print(journalQuery)
    journal_wdqs_results = wdi_core.WDFunctionsEngine.execute_sparql_query(journalQuery, as_dataframe=True)

    if len(journal_wdqs_results) == 1:
        return journal_wdqs_results.loc[0, 'journal'].replace("http://www.wikidata.org/entity/", "")
    elif len(journal_wdqs_results) > 1:
        data = {
            'title': journalTitle + ' as a scientific journal exists more than once on Wikidata',
            'body': journalTitle + ' exists more than once on Wikidata. The Wikidata treatment bot cannot distinguish which is the most appropriate Wikidata item. Please curate by possibly merging or curating the following items: ' + ' '.join(
                journal_wdqs_results['journal'].tolist()) + '.',
        }
        response = requests.post(ghurl, headers=headers, json=data)

        if response.status_code == 201:
            print(f"Issue created: {response.json()['html_url']}")
        else:
            print(f"Error {response.status_code}: {response.text}")
        return None
    else:
        journalStatements = [
            wdi_core.WDItemID("Q5633421", prop_nr="P31", references=[copy.deepcopy(pubref)]),
            wdi_core.WDMonolingualText(journalTitle, language="en", prop_nr="P1476", references=[copy.deepcopy(pubref)])
        ]
        journalItem = wdi_core.WDItemEngine(data=journalStatements)
        journalItem.set_label(journalTitle, lang="en")
        journalItem.set_description("scientific journal", lang="en")
        return journalItem.write(login)

# Example Usage:
# journalQID = get_or_create_journal("Zoosystema", your_token, your_ghurl, your_pubref, your_login)
