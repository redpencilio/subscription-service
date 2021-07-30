"""
web.py: entry point of the service
"""

from datetime import datetime
from typing import Dict, List
import locale

from flask import Flask, Response, request
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pyshacl import validate
from pyshacl.consts import OWL
from rdflib import URIRef
from rdflib.graph import Graph
from rdflib.namespace import DCTERMS
from rdflib.term import Node

from helpers import BESLUIT, EXT, PROV, log, result_to_rdflib
from queries import get_agendapunt
from queries import get_user_data
from queries import send_mail
from queries import find_related_agendapunten

locale.setlocale(locale.LC_ALL, 'nl_BE.UTF-8')

app = Flask(__name__)

@app.route('/.mu/delta', methods=["POST"])
def delta_notification() -> Response: # pylint: disable=too-many-branches
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
        for x in delta["inserts"]:
            subject = x["subject"]["value"]
            related_agendapunten = find_related_agendapunten(subject)
            for related_agendapunt in related_agendapunten:
                if related_agendapunt not in subjects:
                    subjects[related_agendapunt] = {
                        "inserts": [],
                        "deletes": []
                    }
                subjects[related_agendapunt]["inserts"] += [x]

        for x in delta["deletes"]:
            subject = x["subject"]["value"]
            related_agendapunten = find_related_agendapunten(subject)
            for related_agendapunt in related_agendapunten:
                if related_agendapunt not in subjects:
                    subjects[related_agendapunt] = {
                        "inserts": [],
                        "deletes": []
                    }
                subjects[related_agendapunt]["deletes"] += [x]

    user_data = get_user_data()

    for agendapunt_url, delta in subjects.items():
        new_agendapunt = get_agendapunt(str(agendapunt_url))

        if len(new_agendapunt) == 0: # type: ignore
            log(f"Not an Agendapunt: {agendapunt_url}")
            continue

        # Construct the intermediary
        intermediary = remove_partial_delta(
            new_agendapunt,
            delta["inserts"]
        )

        old_agendapunt = add_partial_delta(intermediary, delta["deletes"])

        for user_filter, email in user_data:
            if len(user_filter) == 0: # type: ignore
                continue

            if matches(new_agendapunt, user_filter):
                log("Match, notify user")
                notify_user(
                    new_agendapunt,
                    delta,
                    URIRef(agendapunt_url),
                    email
                )
            else:
                log("No match, reconstructing old data")

                if matches(old_agendapunt, user_filter):
                    log("Old matched, notify user")
                    notify_user(
                        new_agendapunt,
                        delta,
                        URIRef(agendapunt_url),
                        email
                    )
                else:
                    log("No match")

    return Response("OK")

#TODO: move some of these functions to helpers

def format_date(string: str, include_time=False) -> str:
    """
    format_date: Format a date string to a presentable format

    :returns: The date in a presentable format
    """
    try:
        date = datetime.fromisoformat(string.strip())
    except ValueError:
        return string

    if include_time:
        return date.strftime("%A %d %B %Y %H:%M")
    return date.strftime("%A %d %B %Y")

def remove_partial_delta(graph: Graph, change: List[dict]) -> Graph:
    """
    remove_partial_delta: Create a copy of the graph with a part of the delta
    removed

    :returns: The new graph
    """
    ret = copy_graph(graph)
    for insert in change:
        triple = (
            result_to_rdflib(insert["subject"]),
            result_to_rdflib(insert["predicate"]),
            result_to_rdflib(insert["object"])
        )
        ret.remove(triple)
    return ret

def add_partial_delta(graph: Graph, change: List[dict]) -> Graph:
    """
    add_partial_delta: Create a copy of the graph with a part of the delta
    added

    :returns: The new graph
    """
    ret = copy_graph(graph)
    for insert in change:
        triple = (
            result_to_rdflib(insert["subject"]),
            result_to_rdflib(insert["predicate"]),
            result_to_rdflib(insert["object"])
        )
        ret.add(triple)
    return ret

def graph_from_partial_delta(changes: List[Dict]) -> Graph:
    """
    graph_from_partial_delta: given the inserts or deletes of a delta, construct
    the rdflib Graph it represents

    :returns: The graph
    """
    ret = Graph()
    for change in changes:
        triple = (
            result_to_rdflib(change["subject"]),
            result_to_rdflib(change["predicate"]),
            result_to_rdflib(change["object"])
        )
        ret.add(triple)
    return ret

def notify_user(
        agendapunt: Graph,
        delta: dict,
        agendapunt_uri: Node,
        email: str
    ):
    """
    notify_user: Notify the user that a relevant Agendapunt has changed

    :param agendapunt: The current (after the delta) Agendapunt
    :param delta: The change that triggered this notification
    :param agendapunt_uri: The rdflib URI for the current Agendapunt
    :param email: The email to which the rendered template needs to be sent
    """
    # Construct graphs
    unchanged = remove_partial_delta(
        remove_partial_delta(
            agendapunt,
            delta["inserts"]
        ),
        delta["deletes"]
    )
    inserts = graph_from_partial_delta(delta["inserts"])
    deletes = graph_from_partial_delta(delta["deletes"])

    # Find Zitting
    zitting = next( # type: ignore
        agendapunt[agendapunt_uri:EXT.zitting:], None
    )

    # Find Notulen
    if zitting is not None:
        zitting_notulen = next( # type: ignore
            agendapunt[zitting:BESLUIT.heeftNotulen:], None
        )
    else:
        zitting_notulen = None

    # Find Stemming
    stemming = next( # type: ignore
        agendapunt[agendapunt_uri:EXT.stemming:], None
    )

    env = Environment(
        loader=FileSystemLoader("/app/templates"),
        autoescape=select_autoescape()
    )

    env.filters["format_date"] = format_date

    template = env.get_template("mail-delta.html")

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

    send_mail(html, email)

def copy_graph(g: Graph) -> Graph:
    """
    copy_graph: utility function to copy a graph

    :returns: the new graph
    """
    ret = Graph()

    for (s, p, o) in g:
        ret.add((s, p, o))

    return ret

def matches(data, user_filter) -> bool:
    """
    matches: check if the data matches a user filter

    :returns: True if it matches, false otherwise
    """
    ret, _, _ = validate(
        data_graph=data,
        shacl_graph=user_filter
    )
    return ret
