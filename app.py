"""
web.py: entry point of the service
"""

from typing import Dict, List

from flask import Flask, Response, request
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pyshacl import validate
from pyshacl.consts import OWL
from rdflib import URIRef
from rdflib.graph import Graph
from rdflib.namespace import DCTERMS
from rdflib.term import Node

from helpers import BESLUIT, EXT, PROV, error, log, result_to_rdflib
from queries import get_agendapunt
from queries import get_filter
from queries import send_mail
from queries import find_related_agendapunten

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

    # Get the filter for the user
    user_filter = get_filter()

    if len(user_filter) == 0: # type: ignore
        error("No user filters found")
        return Response("No user filters found", 200)

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

        if matches(new_agendapunt, user_filter):
            log("Match, notify user")
            notify_user(intermediary, delta, URIRef(agendapunt_url))
        else:
            log("No match, reconstructing old data")
            old_agendapunt = add_partial_delta(intermediary, delta["deletes"])

            if matches(old_agendapunt, user_filter):
                log("Old matched, notify user")
                notify_user(intermediary, delta, URIRef(agendapunt_url))
            else:
                log("No match")

    return Response("OK")

#TODO: move some of these functions to helpers

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

def notify_user(agendapunt: Graph, delta: dict, agendapunt_uri: Node):
    """
    notify_user: Notify the user that a relevant Agendapunt has changed

    :param agendapunt: The current (after the delta) Agendapunt
    :param delta: The change that triggered this notification
    :param agendapunt_uri: The rdflib URI for the current Agendapunt
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
    possible_zittingen = list( # type: ignore
        agendapunt[agendapunt_uri:EXT.zitting:]
    )

    if len(possible_zittingen) == 0:
        zitting = None
    elif len(possible_zittingen) == 1:
        zitting = possible_zittingen[0]
    else:
        error("Agendapunt belongs to multiple zittingen, this is not supported")
        zitting = possible_zittingen[0]

    # Find Notulen
    if zitting is not None:
        possible_notulen = list( # type: ignore
            agendapunt[zitting:BESLUIT.heeftNotulen:]
        )

        if len(possible_notulen) == 0:
            zitting_notulen = None
        elif len(possible_notulen) == 1:
            zitting_notulen = possible_notulen[0]
        else:
            error("Zitting has multiple notulen, this is not supported")
            zitting_notulen = possible_notulen[0]
    else:
        zitting_notulen = None

    # Find Stemming
    possible_stemming = list( # type: ignore
        agendapunt[zitting:EXT.stemming:]
    )

    if len(possible_stemming) == 0:
        stemming = None
    elif len(possible_stemming) == 1:
        stemming = possible_stemming[0]
    else:
        error("Agendapunt has multiple Stemmingen, this is not supported")
        stemming = possible_stemming[0]

    env = Environment(
        loader=FileSystemLoader("/app/templates"),
        autoescape=select_autoescape()
    )

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

    send_mail(html)

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
