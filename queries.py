"""
queries: relevant SPARQL queries for this service
"""

import typing
import uuid

from helpers import query, update

MAIL_URL_BASE = "xxxparticipatie.redpencil.io"

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
            <http://{MAIL_URL_BASE}/emails/{str(uuid.uuid4())}> a nmo:Email;
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
        PREFIX mandaat: <http://data.vlaanderen.be/ns/mandaat#>
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
          ?agendapunt terms:title ?agendapuntTitel.
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
