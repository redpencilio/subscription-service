"""
queries: relevant SPARQL queries for this service
"""

import typing
import uuid

from rdflib.graph import Graph

from helpers import graph_from_results, query, update

MAIL_URL_BASE = "lokaalbeslist.be"

def escape(string: str) -> str:
    """
    escape: escape special characters in a string so it can be used as a SPARQL
    object/subject.

    :returns: the escaped string
    """
    return (
        string.replace("\"", "\\\"")
              .replace("\n", "\\n")
              .replace("\t", "\\t")
    )

def find_related_agendapunten(subject: str) -> typing.Set[str]:
    """
    find_related_agendapunten: Find every Agendapunt URI related to the given
    URI.

    :returns: The (potentially empty) set of related Agendapunten
    """
    data = query(f"""
        PREFIX besluit: <http://data.vlaanderen.be/ns/besluit#>
        PREFIX terms: <http://purl.org/dc/terms/>

        SELECT
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

    print(data)

    return set(
        binding["agendapunt"]["value"]
        for binding in data["results"]["bindings"]
    )

def get_filter() -> Graph:
    """
    get_filter: get the shacl filters for the user

    :returns: the graph for use in validate
    """
    FILTER = "ext:filter1"
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
          BIND({FILTER} as ?nodeShape)
          ?nodeShape a sh:NodeShape.
          ?nodeShape (sh:or|sh:and|sh:not|sh:xone|sh:property|rdf:first|rdf:rest)* ?nextNode.
          ?nextNode ?prop ?value.
        }}
    """))

def get_agendapunt(url: str) -> Graph:
    """
    get_agendapunt: get all relevant data for a given URL. The URL can be a
    besluit:Agendapunt, but can also be something else.

    :returns: the graph with the relevant data
    """
    # TODO: the modifications shouldn't be needed anymore
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

def send_mail(mail_html: str) -> typing.Any:
    """
    send_mail: send an email with the given html

    :returns: the result
    """

    return update(f"""
        PREFIX nmo: <http://www.semanticdesktop.org/ontologies/2007/03/22/nmo#>
        PREFIX nie: <http://www.semanticdesktop.org/ontologies/2007/01/19/nie#>
        PREFIX nfo: <http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#>

        INSERT DATA {{
          GRAPH <http://mu.semte.ch/graphs/system/email> {{
            <http://{MAIL_URL_BASE}/id/emails/{str(uuid.uuid4())}> a nmo:Email;
                nmo:messageFrom "noreply@{MAIL_URL_BASE}";
                nmo:emailTo "robbe@robbevanherck.be";
                nmo:messageSubject "Nieuwe agendapunten beschikbaar";
                nmo:htmlMessageContent "{escape(mail_html)}";
                nmo:sentDate "";
                nmo:isPartOf <http://{MAIL_URL_BASE}/id/mail-folders/2>.
          }}
        }}
    """)

def get_agendapunten_data() -> typing.Any:
    """
    get_agendapunten_data: get the data relevant for all `besluit:Agendapunt`

    :returns: the relevant data
    """
    return query("""
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX besluit: <http://data.vlaanderen.be/ns/besluit#>
        PREFIX purl: <http://www.purl.org/>
        PREFIX terms: <http://purl.org/dc/terms/>

        SELECT DISTINCT
          ?agendapuntTitel
          ?agendapuntExtern
          ?zittingExtern
          ?zittingStart
          ?zittingGeplandeStart
          ?zittingNotulenExtern
          ?stemmingGevolg
          ?stemmingAantalVoorstanders
          ?stemmingAantalTegenstanders
          ?stemmingAantalOnthouders
        WHERE {
          ?agendapunt a besluit:Agendapunt.
          OPTIONAL {
              ?agendapunt terms:title ?agendapuntTitel.
          }
          OPTIONAL {
            ?agendapunt owl:sameAs ?agendapuntExtern.
          }
          OPTIONAL {
            ?zitting besluit:behandelt ?agendapunt.
            OPTIONAL {
              ?zitting owl:sameAs ?zittingExtern. 
            }
            OPTIONAL {
                ?zitting prov:startedAtTime ?zittingStart.
            }
            OPTIONAL {
                ?zitting besluit:geplandeStart ?zittingStartGeplandeStart.
            }
            OPTIONAL {
              ?zitting besluit:heeftNotulen ?zittingNotulen.
              ?zittingNotulen owl:sameAs ?zittingNotulenExtern.
            }
          }
          OPTIONAL {
            ?behandeling terms:subject ?agendapunt.
            ?behandeling besluit:heeftStemming ?stemming.
            OPTIONAL {
              ?stemming besluit:gevolg ?stemmingGevolg.
            }
            OPTIONAL {
              ?stemming besluit:aantalVoorstanders ?stemmingAantalVoorstanders.
              ?stemming besluit:aantalTegenstanders ?stemmingAantalTegenstanders.
              ?stemming besluit:aantalOnthouders ?stemmingAantalOnthouders.
            }
          }
        }
      LIMIT 50
    """)
