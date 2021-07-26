"""
queries: relevant SPARQL queries for this service
"""

import typing

from helpers import query

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
