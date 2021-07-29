"""
helpers: Helpers module, based on
https://github.com/MikiDi/mu-python-template/blob/development/helpers.py
"""

import logging
import os
import sys
from typing import Union
import uuid

from SPARQLWrapper import JSON, SPARQLWrapper
from flask import Response, jsonify
from rdflib import Literal, URIRef, Graph
from rdflib.namespace import Namespace, OWL, DCTERMS, PROV, SH
BESLUIT = Namespace("http://data.vlaanderen.be/ns/besluit#")
EXT = Namespace("http://mu.semte.ch/vocabularies/ext/")

log_levels = {'DEBUG': logging.DEBUG,
              'INFO': logging.INFO,
              'WARNING': logging.WARNING,
              'ERROR': logging.ERROR,
              'CRITICAL': logging.CRITICAL}
LOG_DIR = '/logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
thelogger = logging.getLogger('')
thelogger.setLevel(
    log_levels.get(os.environ.get('LOG_LEVEL', 'INFO').upper(), logging.INFO)
)
fileHandler = logging.FileHandler("{0}/{1}.log".format(LOG_DIR, 'logs'))
thelogger.addHandler(fileHandler)
consoleHandler = logging.StreamHandler(stream=sys.stdout)
thelogger.addHandler(consoleHandler)

def debug(msg, *args, **kwargs):
    """
    debug: write a log message to the log file. Logs are written to the `/logs`
    directory in the docker container.
     """
    thelogger.debug(msg, *args, **kwargs)

def log(msg, *args, **kwargs):
    """
    log: write a log message to the log file. Logs are written to the `/logs`
    directory in the docker container.
    """
    thelogger.info(msg, *args, **kwargs)

def error(msg, status=400) -> Response:
    """
    error: Returns a JSON:API compliant error response with the given status
    code (400 by default).

    :returns: A JSON:API compliant Flask Response
    """
    response = jsonify({'message': msg})
    response.status_code = status
    return response

def generate_uuid() -> uuid.UUID:
    """
    generate_uuid: Generates a UUIDv4

    :returns: A UUID v4
    """
    return uuid.uuid4()

sparql = SPARQLWrapper(
    endpoint=os.environ.get('MU_SPARQL_ENDPOINT'),
    updateEndpoint=os.environ.get('MU_SPARQL_UPDATEPOINT'),
    returnFormat=JSON
)

def query(the_query, method='GET', sudo=False) -> dict:
    """
    query: Execute the given SPARQL query (select/ask/construct) on the triple
    store

    :returns: The result of the query
    """
    log("execute query: \n" + the_query)
    sparql.setQuery(the_query)
    sparql.method = method
    sparql.addCustomHttpHeader("mu-auth-sudo", str(sudo))
    return sparql.queryAndConvert()  # type: ignore


def update(the_query, method='POST', sudo=False) -> dict:
    """
    update: Execute the given update SPARQL query on the triple store, if the
    given query is no update query, nothing happens.

    :returns: The result of the query
    """
    log("execute update: \n" + the_query)
    sparql.setQuery(the_query)
    sparql.method = method
    sparql.addCustomHttpHeader("mu-auth-sudo", str(sudo))
    if sparql.isSparqlUpdateRequest():
        return sparql.queryAndConvert()  # type: ignore
    log("not executing")
    return {}

def result_to_rdflib(result: dict) -> Union[URIRef, Literal]:
    """
    result_to_rdflib: turn one value from a result into a rdflib value

    :raises Exception: when the type is unknown
    :returns: The rdflib value
    """

    if result["type"] == "literal":
        return Literal(result["value"])
    if result["type"] == "uri":
        return URIRef(result["value"])
    raise Exception(f"Invalid type {result['type']}")

def graph_from_results(sparql_results: dict) -> Graph:
    """
    graph_from_results: given the results of a SPARQL query, construct a graph

    :returns: the constructed graph
    """
    g = Graph()
    for binding in sparql_results["results"]["bindings"]:
        g.add((
            result_to_rdflib(binding["s"]),
            result_to_rdflib(binding["p"]),
            result_to_rdflib(binding["o"])
        ))
    g.bind('owl',     OWL)
    g.bind('besluit', BESLUIT)
    g.bind('ext',     EXT)
    g.bind('prov',    PROV)
    g.bind('terms',   DCTERMS)
    g.bind('sh',      SH)
    return g
