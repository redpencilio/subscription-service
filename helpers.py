"""
helpers: Module containing helper functions
"""

from datetime import datetime
from typing import Dict
from typing import List

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, Namespace, OWL, PROV, SH
from rdflib.term import Node

BESLUIT = Namespace("http://data.vlaanderen.be/ns/besluit#")
EXT = Namespace("http://mu.semte.ch/vocabularies/ext/")

def format_date(string: str, include_time: bool=False) -> str:
    """
    format_date: Format a date string to a presentable format.

    :param string: The date in string format.
    :param include_time: Whether or not the time should be included.
    :returns: The date in a presentable format or the string itself if it is not
    in ISO format.
    """
    try:
        date = datetime.fromisoformat(string.strip())
    except ValueError:
        return string

    if include_time:
        return date.strftime("%A %d %B %Y %H:%M")
    return date.strftime("%A %d %B %Y")

def result_to_rdflib(result: Dict) -> Node:
    """
    result_to_rdflib: Turn one value from a SPARQL result into a rdflib Node.

    :param result: The value to convert.
    :returns: The rdflib Node.
    :raises Exception: When the type is unknown.
    """
    if result["type"] == "literal":
        return Literal(result["value"])
    if result["type"] == "uri":
        return URIRef(result["value"])
    raise Exception(f"Invalid type {result['type']}")

def graph_from_results(sparql_results: dict) -> Graph:
    """
    graph_from_results: Create an rdflib Graph from a SPARQL result.

    :param sparql_results: The SPARQL result.
    :returns: The constructed graph.
    """
    g = Graph()

    # Add the triples
    for binding in sparql_results["results"]["bindings"]:
        g.add((
            result_to_rdflib(binding["s"]),
            result_to_rdflib(binding["p"]),
            result_to_rdflib(binding["o"])
        ))

    # Add some namespaces
    g.bind('owl',     OWL)
    g.bind('besluit', BESLUIT)
    g.bind('ext',     EXT)
    g.bind('prov',    PROV)
    g.bind('terms',   DCTERMS)
    g.bind('sh',      SH)

    return g

def create_modified_graph(
        graph: Graph,
        change: List[Dict],
        add: bool
    ) -> Graph:
    """
    create_subgraph: Create a copy of the graph with the given change part of
    the delta removed or added.

    :param graph: The graph to copy and modify.
    :param change: The set of triples to add or remove.
    :param add: True if the change should be added, False if it should be
    removed.
    :returns: The new graph.
    """
    ret = copy_graph(graph)
    for insert in change:
        triple = (
            result_to_rdflib(insert["subject"]),
            result_to_rdflib(insert["predicate"]),
            result_to_rdflib(insert["object"])
        )
        if add:
            ret.add(triple)
        else:
            ret.remove(triple)
    return ret

def copy_graph(g: Graph) -> Graph:
    """
    copy_graph: Utility function to copy a graph.

    :param g: The graph to copy.
    :returns: A copy of the graph with the same triples and namespace bindings.
    """
    ret = Graph()

    for (s, p, o) in g:
        ret.add((s, p, o))

    for (name, url) in g.namespaces():
        ret.bind(name, url)

    return ret

def graph_from_partial_delta(changes: List[Dict]) -> Graph:
    """
    graph_from_partial_delta: Given the inserts or deletes of a delta, construct
    the rdflib Graph with those triples.

    :returns: The graph with the same triples as the partial delta.
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

def escape_sparql_string(string: str) -> str:
    """
    escape_sparql_string: Escape special characters in a string.

    :param string: The string to escape.
    :returns: The escaped string.
    """
    return (
        string.replace("\\", "\\\\")
              .replace("'", "\\'")
              .replace('"', '\\"')
              .replace("\n", "\\n")
              .replace("\t", "\\t")
    )
