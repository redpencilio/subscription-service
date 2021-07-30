"""
app.py: entry point of the service
"""

import locale
from typing import Dict

from flask import Flask, Response, request
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pyshacl import validate
from rdflib import URIRef
from rdflib.graph import Graph
from rdflib.namespace import DCTERMS, OWL, PROV
from rdflib.term import Node

from helpers import BESLUIT, EXT
from helpers import format_date, graph_from_partial_delta, create_modified_graph
from queries import get_agendapunt, get_user_data, send_mail
from queries import find_related_agendapunten

locale.setlocale(locale.LC_ALL, 'nl_BE.UTF-8')

app = Flask(__name__)

@app.route('/.mu/delta', methods=["POST"])
def delta_notification() -> Response:
    """
    delta_notification: POSTed to by delta-notifier.

    :returns: "OK" when succesful
    """

    data = request.json

    if not data:
        return Response("Invalid data", 400)

    # Get the inserts and deletes per subject
    subjects: Dict[str, Dict] = {}

    for delta in data:
        extract_subjects(delta, subjects, "inserts")
        extract_subjects(delta, subjects, "deletes")

    # Get the data for every user
    user_data = get_user_data()

    for agendapunt_url, delta in subjects.items():
        new_agendapunt = get_agendapunt(agendapunt_url)

        if len(new_agendapunt) == 0: # type: ignore
            continue

        # Construct the intermediary
        intermediary = create_modified_graph(
            new_agendapunt,
            delta["inserts"],
            False
        )

        # Construct graphs
        unchanged = create_modified_graph(
            create_modified_graph(
                new_agendapunt,
                delta["inserts"],
                False
            ),
            delta["deletes"],
            False
        )
        inserts = graph_from_partial_delta(delta["inserts"])
        deletes = graph_from_partial_delta(delta["deletes"])

        # Construct the previous version
        old_agendapunt = create_modified_graph(
            intermediary,
            delta["deletes"],
            True
        )

        # Check if we need to send it to someone
        for user_filter, email in user_data:

            # If the user has no actual filter, skip it
            if len(user_filter) == 0: # type: ignore
                continue

            # Check if the current version matches
            if matches(new_agendapunt, user_filter):
                notify_user(
                    new_agendapunt,
                    unchanged,
                    inserts,
                    deletes,
                    URIRef(agendapunt_url),
                    email
                )
            else:
                # Check if the previous version matches
                if matches(old_agendapunt, user_filter):
                    notify_user(
                        new_agendapunt,
                        unchanged,
                        inserts,
                        deletes,
                        URIRef(agendapunt_url),
                        email
                    )

    return Response("OK")

def extract_subjects(delta: Dict, subjects: Dict, part: str):
    """
    extract_subjects: Add all subjects and thier relevant delta to the subjects
    dict.

    :param delta: The delta received from delta-notifier.
    :param subjects: The current dict of subjects and their changes.
    :param part: Which part to process ('inserts' or 'deletes').
    """
    for x in delta[part]:
        subject = x["subject"]["value"]

        related_agendapunten = find_related_agendapunten(subject)

        for related_agendapunt in related_agendapunten:
            if related_agendapunt not in subjects:
                subjects[related_agendapunt] = {
                    "inserts": [],
                    "deletes": []
                }

            subjects[related_agendapunt][part] += [x]

def notify_user(
        agendapunt: Graph,
        unchanged: Graph,
        inserts: Graph,
        deletes: Graph,
        agendapunt_uri: Node,
        email: str
    ):
    """
    notify_user: Notify the user that a relevant Agendapunt has changed

    :param agendapunt: The current Agendapunt (after the delta).
    :param unchanged: The graph with the triples that were not affected by the
    delta.
    :param inserts: The graph with the triples that were added by the delta.
    :param deletes: The graph with the triples that were deleted by the delta.
    :param agendapunt_uri: The rdflib URI for the current Agendapunt.
    :param email: The email to which the rendered template needs to be sent.
    """
    # Find Zitting
    zitting = next( # type: ignore
        agendapunt[agendapunt_uri:EXT.zitting:], None
    )

    # Find Notulen
    zitting_notulen = next( # type: ignore
        agendapunt[zitting:BESLUIT.heeftNotulen:], None
    )

    # Find Stemming
    stemming = next( # type: ignore
        agendapunt[agendapunt_uri:EXT.stemming:], None
    )

    # Set up Jinja environment
    env = Environment(
        loader=FileSystemLoader("/app/templates"),
        autoescape=select_autoescape()
    )
    template = env.get_template("mail-delta.html")

    # Add the format_date filter
    env.filters["format_date"] = format_date

    # Render the template
    html = template.render(
        # Graphs
        unchanged=unchanged,
        inserts=inserts,
        deletes=deletes,

        # Subjects
        agendapunt=agendapunt_uri,
        zitting=zitting,
        zitting_notulen=zitting_notulen,
        stemming=stemming,

        # Namespaces
        DCTERMS=DCTERMS,
        OWL=OWL,
        PROV=PROV,
        BESLUIT=BESLUIT,
    )

    # Queue for sending
    send_mail(html, email)

def matches(data: Graph, user_filter: Graph) -> bool:
    """
    matches: Check if the data matches a user's (shacl) filter.

    :param data: The data to check.
    :param user_filter: The filter to check against.
    :returns: True if it matches, false otherwise.
    """
    ret, _, _ = validate(
        data_graph=data,
        shacl_graph=user_filter
    )
    return ret
