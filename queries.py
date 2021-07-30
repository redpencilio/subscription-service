"""
queries: relevant SPARQL queries for this service
"""

import os
import uuid
from typing import Tuple, Set, Dict

from SPARQLWrapper import JSON, SPARQLWrapper
from rdflib.graph import Graph

from helpers import graph_from_results

MAIL_URL_BASE = "lokaalbeslist.be"

sparql = SPARQLWrapper(
    endpoint=os.environ.get('MU_SPARQL_ENDPOINT'),
    updateEndpoint=os.environ.get('MU_SPARQL_UPDATEPOINT'),
    returnFormat=JSON
)

def query(query_str: str, method: str='GET', sudo: bool=False) -> Dict:
    """
    query: Execute the given SPARQL query on the triple store.

    :param query_str: The SPARQL query.
    :param method: The HTTP method to use ('GET' for SELECT/CONSTRUCT/...,
    'POST' for 'INSERT/DELETE/...').
    :param sudo: Whether or not to use the mu-auth-sudo header.
    :returns: The result of the query.
    """
    sparql.setQuery(query_str)
    sparql.method = method
    sparql.addCustomHttpHeader("mu-auth-sudo", str(sudo).lower())
    return sparql.queryAndConvert() # type: ignore

def escape(string: str) -> str:
    """
    escape: Escape special characters in a string so it can be used as a SPARQL
    object/subject.

    :param string: The string to escape.
    :returns: The escaped string.
    """
    return (
        string.replace("\"", "\\\"")
              .replace("\n", "\\n")
              .replace("\t", "\\t")
    )

def get_user_data() -> Set[Tuple[Graph, str]]:
    """
    get_user_data: Get all the user filters and corresponding email addresses.

    :returns: A set of (filter graph, email address).
    """
    data = query("""
        PREFIX ext: <http://mu.semte.ch/vocabularies/ext/>
        PREFIX schema: <http://schema.org/>

        SELECT
          ?email
          ?filter_url
        WHERE {
          GRAPH <http://lokaalbeslist.be/graphs/subscriptions> {
            ?user_url ext:hasSubscription ?filter_url;
                      schema:email ?email.
          }
        }
    """)

    return set(
        (
            get_filter(binding["filter_url"]["value"]),
            binding["email"]["value"]
        )
        for binding in data["results"]["bindings"]
    )

def find_related_agendapunten(subject: str) -> Set[str]:
    """
    find_related_agendapunten: Find every Agendapunt URI related to the given
    URI.

    :returns: The (potentially empty) set of related Agendapunten.
    """
    data = query(f"""
        PREFIX besluit: <http://data.vlaanderen.be/ns/besluit#>
        PREFIX terms: <http://purl.org/dc/terms/>

        SELECT DISTINCT
            ?agendapunt
        WHERE {{
            BIND(<{subject}> as ?firstNode)
            ?agendapunt a besluit:Agendapunt.
            {{
                ?firstNode a besluit:Agendapunt.
                BIND(?firstNode as ?agendapunt)
            }} UNION {{
                ?firstNode besluit:behandelt ?agendapunt.
            }} UNION {{
                ?firstNode terms:subject ?agendapunt.
            }} UNION {{
                ?behandeling terms:subject ?agendapunt.
                ?behandeling besluit:heeftStemming ?firstNode.
            }}
        }}
    """)

    return set(
        binding["agendapunt"]["value"]
        for binding in data["results"]["bindings"]
    )

def get_filter(url: str) -> Graph:
    """
    get_filter: Get the shacl filter at the given URL.

    :param url: The URL to look up.
    :returns: The rdflib Graph of the NodeShape.
    """
    return graph_from_results(query(f"""
        PREFIX ext: <http://mu.semte.ch/vocabularies/ext/>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX besluit: <http://data.vlaanderen.be/ns/besluit#>
        PREFIX terms: <http://purl.org/dc/terms/>
        PREFIX sh: <http://www.w3.org/ns/shacl#>

        CONSTRUCT  {{
          ?nextNode ?prop ?value.
        }} WHERE {{
          BIND(<{url}> as ?nodeShape)
          ?nodeShape a sh:NodeShape.
          ?nodeShape (sh:or|sh:and|sh:not|sh:xone|sh:property|rdf:first|rdf:rest)* ?nextNode.
          ?nextNode ?prop ?value.
        }}
    """))

def get_agendapunt(url: str) -> Graph:
    """
    get_agendapunt: Get all relevant data for a given URL.

    :param url: The URL to look up.
    :returns: The graph with the relevant data.
    """
    # TODO: turn this into a simple CONSTRUCT WHERE
    return graph_from_results(query(f"""
        PREFIX ext: <http://mu.semte.ch/vocabularies/ext/>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX besluit: <http://data.vlaanderen.be/ns/besluit#>
        PREFIX terms: <http://purl.org/dc/terms/>

        CONSTRUCT {{
            ?agendapunt     a besluit:Agendapunt;
                            terms:title ?agendapuntTitel;
                            owl:sameAs ?agendapuntExtern;
                            ext:zitting ?zitting;
                            ext:stemming ?stemming.

            ?zitting        a besluit:Zitting;
                            owl:sameAs ?zittingExtern;
                            prov:startedAtTime ?zittingStart;
                            besluit:geplandeStart ?zittingStartGeplandeStart;
                            besluit:heeftNotulen ?zittingNotulen.

            ?zittingNotulen a besluit:Notulen;
                            owl:sameAs ?zittingNotulenExtern.
            
            ?stemming       a besluit:Stemming;
                            besluit:gevolg ?stemmingGevolg;
                            besluit:aantalVoorstanders ?stemmingAantalVoorstanders;
                            besluit:aantalTegenstanders ?stemmingAantalTegenstanders;
                            besluit:aantalOnthouders ?stemmingAantalOnthouders.
        }} WHERE {{
            BIND(<{url}> as ?agendapunt)
            ?agendapunt a besluit:Agendapunt.
            ?agendapunt terms:title ?agendapuntTitel.
            OPTIONAL {{
                ?agendapunt owl:sameAs ?agendapuntExtern.
            }}
            OPTIONAL {{
                ?zitting besluit:behandelt ?agendapunt.
                OPTIONAL {{
                    ?zitting owl:sameAs ?zittingExtern. 
                }}
                OPTIONAL {{
                    ?zitting prov:startedAtTime ?zittingStart.
                }}
                OPTIONAL {{
                    ?zitting besluit:geplandeStart ?zittingStartGeplandeStart.
                }}
                OPTIONAL {{
                    ?zitting besluit:heeftNotulen ?zittingNotulen.
                    ?zittingNotulen owl:sameAs ?zittingNotulenExtern.
                }}
            }}
            OPTIONAL {{
                ?behandeling terms:subject ?agendapunt.
                ?behandeling besluit:heeftStemming ?stemming.
                OPTIONAL {{
                    ?stemming besluit:gevolg ?stemmingGevolg.
                }}
                OPTIONAL {{
                    ?stemming besluit:aantalVoorstanders ?stemmingAantalVoorstanders.
                    ?stemming besluit:aantalTegenstanders ?stemmingAantalTegenstanders.
                    ?stemming besluit:aantalOnthouders ?stemmingAantalOnthouders.
                }}
            }}
        }}
        LIMIT 1
    """))

def send_mail(mail_html: str, email_address: str):
    """
    send_mail: Queue an email to be sent with the given HTML content to the
    given email address.

    :param mail_html: The HTML data to send.
    :param email_address: The address to send the mail to.
    """
    query(f"""
        PREFIX nmo: <http://www.semanticdesktop.org/ontologies/2007/03/22/nmo#>
        PREFIX nie: <http://www.semanticdesktop.org/ontologies/2007/01/19/nie#>
        PREFIX nfo: <http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#>

        INSERT DATA {{
          GRAPH <http://mu.semte.ch/graphs/system/email> {{
            <http://{MAIL_URL_BASE}/id/emails/{str(uuid.uuid4())}> a nmo:Email;
                nmo:messageFrom "noreply@{MAIL_URL_BASE}";
                nmo:emailTo "{email_address}";
                nmo:messageSubject "Nieuwe agendapunten beschikbaar";
                nmo:htmlMessageContent "{escape(mail_html)}";
                nmo:sentDate "";
                nmo:isPartOf <http://{MAIL_URL_BASE}/id/mail-folders/2>.
          }}
        }}
    """, 'POST')
