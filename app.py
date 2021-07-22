"""
web.py: entry point of the service
"""

from __future__ import annotations

from flask import Flask
from jinja2 import Environment, select_autoescape, FileSystemLoader

from helpers import query

app = Flask(__name__)

@app.route('/', methods=['GET'])
def schedule() -> str:
    """
    schedule: the main route of the service

    :returns: A response to this request
    """
    data = query("""
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
          ?zittingGeplandeStart
          ?zittingStart
          ?zittingEinde
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
              ?zitting besluit:geplandeStart ?zittingGeplandeStart.
            }
            OPTIONAL {
              ?zitting prov:endedAtTime ?zittingEinde.
              ?zitting prov:startedAtTime ?zittingStart.
            }
            OPTIONAL {
              ?zitting besluit:heeftNotulen ?zittingNotulen.
              ?zittingNotulen owl:sameAs ?zittingNotulenExtern.
            }
          }
          OPTIONAL {
            ?behandeling terms:subject ?agendapunt.
            OPTIONAL {
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
        }
      LIMIT 50
    """)

    env = Environment(
        loader=FileSystemLoader("/app/templates"),
        autoescape=select_autoescape()
    )

    template = env.get_template("mail.html")

    return template.render(
        data=data
    )
