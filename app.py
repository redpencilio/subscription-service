"""
app.py: entry point of the service
"""

import locale
from typing import Dict

from flask import Flask, Response, request
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pyshacl import validate
from rdflib import URIRef, Graph, DCTERMS, OWL, PROV
from rdflib.term import Node

from helpers import BESLUIT
from helpers import format_date, graph_from_partial_delta, create_modified_graph
from queries import get_content, get_user_data, send_mail, get_template_subjects
from queries import find_related_content

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
        extract_content(delta, subjects, "inserts")
        extract_content(delta, subjects, "deletes")

    # Get the data for every user
    user_data = get_user_data()

    for content_url, delta in subjects.items():
        new_content = get_content(content_url)

        if len(new_content) == 0: # type: ignore
            continue

        # Construct the intermediary
        intermediary = create_modified_graph(
            new_content,
            delta["inserts"],
            False
        )

        # Construct graphs
        unchanged = create_modified_graph(
            intermediary,
            delta["deletes"],
            False
        )
        inserts = graph_from_partial_delta(delta["inserts"])
        deletes = graph_from_partial_delta(delta["deletes"])

        # Construct the previous version
        old_content = create_modified_graph(
            intermediary,
            delta["deletes"],
            True
        )

        # Check if we need to send it to someone
        for user_filter, email in user_data:

            # If the user has no actual filter, skip it
            if len(user_filter) == 0: # type: ignore
                continue

            if (matches(new_content, user_filter) or
                    matches(old_content, user_filter)):
                notify_user(
                    new_content,
                    unchanged,
                    inserts,
                    deletes,
                    URIRef(content_url),
                    email
                )

    return Response("OK")

def extract_content(delta: Dict, subjects: Dict, part: str):
    """
    extract_content: Add all URLs with relevant content and thier relevant delta
    to the subjects dict.

    :param delta: The delta received from delta-notifier.
    :param subjects: The current dict of subjects and their changes.
    :param part: Which part to process ('inserts' or 'deletes').
    """
    for x in delta[part]:
        subject = x["subject"]["value"]

        for related_content in find_related_content(subject):
            if related_content not in subjects:
                subjects[related_content] = {
                    "inserts": [],
                    "deletes": []
                }

            subjects[related_content][part] += [x]

def notify_user(
        content: Graph,
        unchanged: Graph,
        inserts: Graph,
        deletes: Graph,
        content_uri: Node,
        email: str
    ):
    """
    notify_user: Notify the user that a relevant content has changed

    :param content: The current version of the content (after the delta).
    :param unchanged: The graph with the triples that were not affected by the
    delta.
    :param inserts: The graph with the triples that were added by the delta.
    :param deletes: The graph with the triples that were deleted by the delta.
    :param content_uri: The rdflib URI for the current content.
    :param email: The email to which the rendered template needs to be sent.
    """
    subjects = get_template_subjects(content, content_uri)

    # Set up Jinja environment
    env = Environment(
        loader=FileSystemLoader("/config"),
        autoescape=select_autoescape()
    )
    template = env.get_template("template.html")

    # Render the template
    html = template.render(
        # Graphs
        unchanged=unchanged,
        inserts=inserts,
        deletes=deletes,

        # Namespaces
        DCTERMS=DCTERMS,
        OWL=OWL,
        PROV=PROV,
        BESLUIT=BESLUIT,

        # Helper functions
        format_date=format_date,

        # Subjects
        **subjects
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
