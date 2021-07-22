"""
helpers: Helpers module, based on
https://github.com/MikiDi/mu-python-template/blob/development/helpers.py
"""

import logging
import os
import sys
import uuid

from SPARQLWrapper import JSON, SPARQLWrapper
from flask import Response, jsonify


log_levels = {'DEBUG': logging.DEBUG,
              'INFO': logging.INFO,
              'WARNING': logging.WARNING,
              'ERROR': logging.ERROR,
              'CRITICAL': logging.CRITICAL}
log_dir = '/logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
thelogger = logging.getLogger('')
thelogger.setLevel(
    log_levels.get(os.environ.get('LOG_LEVEL', 'INFO').upper(), logging.INFO)
)
fileHandler = logging.FileHandler("{0}/{1}.log".format(log_dir, 'logs'))
thelogger.addHandler(fileHandler)
consoleHandler = logging.StreamHandler(stream=sys.stdout)
thelogger.addHandler(consoleHandler)

def log(msg, *args, **kwargs):
    """write a log message to the log file. Logs are written to the `/logs`
     directory in the docker container."""
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

sparqlQuery = SPARQLWrapper(
    os.environ.get('MU_SPARQL_ENDPOINT'),
    returnFormat=JSON
)
sparqlUpdate = SPARQLWrapper(
    os.environ.get('MU_SPARQL_UPDATEPOINT'),
    returnFormat=JSON
)
sparqlUpdate.method = 'POST'

def query(the_query):
    """
    Execute the given SPARQL query (select/ask/construct) on the triple store
    """
    log("execute query: \n" + the_query)
    sparqlQuery.setQuery(the_query)
    return sparqlQuery.query().convert()


def update(the_query):
    """
    Execute the given update SPARQL query on the triple store, if the given
    query is no update query, nothing happens.
    """
    sparqlUpdate.setQuery(the_query)
    if sparqlUpdate.isSparqlUpdateRequest():
        sparqlUpdate.query()
