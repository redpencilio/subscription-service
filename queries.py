"""
queries: relevant SPARQL queries for this service
"""

import os
import uuid
from typing import Tuple, Set, Dict

from SPARQLWrapper import JSON, SPARQLWrapper
from rdflib import Graph
from rdflib.term import Node

from helpers import graph_from_results

BASE_URL = os.environ["BASE_URL"]

sparql = SPARQLWrapper(
    endpoint=os.environ.get('MU_SPARQL_ENDPOINT'),
    returnFormat=JSON
)

def read_query(path: str) -> str:
    """
    read_query: Read the query from a given file path.

    :param path: The path of the query file.
    :return: The query as a string.
    """
    with open(path, "r") as query_file:
        return query_file.read()

GET_RELEVANT_CONTENT_QUERY = read_query("/config/get_relevant_content.sparql")
GET_TEMPLATE_SUBJECTS = read_query("/config/get_template_subjects.sparql")
CONSTRUCT_CONTENT_QUERY = read_query("/config/construct_content.sparql")

def get_content(url: str) -> Graph:
    """
    get_content: Get all relevant data for a given URL.

    :param url: The URL to look up.
    :returns: The graph with the relevant data.
    """
    return graph_from_results(query(
        CONSTRUCT_CONTENT_QUERY.replace("CONTENT_URL", url)
    ))

def find_related_content(subject: str) -> Set[str]:
    """
    find_related_content: Find every URL with content related to the given URL.

    :returns: The (potentially empty) set of related content.
    """
    data = query(
        GET_RELEVANT_CONTENT_QUERY.replace("SUBJECT_URL", subject)
    )

    return set(
        binding["content"]["value"]
        for binding in data["results"]["bindings"]
    )

def get_template_subjects(content: Graph, content_url: Node) -> Dict[str, Node]:
    """
    get_template_subjects: Query the content for relevant URLs to pass to the
    template.

    :param content: The content that will be rendered.
    :param content_url: The URL of the content itself.
    :returns: A dict mapping names to their URI for use in the template.
    """
    query_str = GET_TEMPLATE_SUBJECTS.replace("CONTENT_URL", str(content_url))
    bindings = content.query(query_str).bindings

    if len(bindings) == 0:
        return {}
    ret = {}
    for name, url in bindings[0].items():
        ret[str(name)] = url
    return ret


def query(query_str: str, method: str='GET', sudo: bool=False) -> Dict:
    """
    query: Execute the given SPARQL query on the triple store.

    :param query_str: The SPARQL query.
    :param method: The HTTP method to use ('GET' for SELECT/CONSTRUCT/...,
    'POST' for 'INSERT/DELETE/...').
    :param sudo: Whether or not to use the mu-auth-sudo header.
    :returns: The result of the query.
    """
    sparql.setQuery(query_str)
    sparql.method = method
    if sudo:
        sparql.addCustomHttpHeader("mu-auth-sudo", "true")
    return sparql.queryAndConvert() # type: ignore

def escape(string: str) -> str:
    """
    escape: Escape special characters in a string so it can be used as a SPARQL
    object/subject.

    :param string: The string to escape.
    :returns: The escaped string.
    """
    return (
        string.replace("\"", "\\\"")
              .replace("\n", "\\n")
              .replace("\t", "\\t")
    )

def get_user_data() -> Set[Tuple[Graph, str]]:
    """
    get_user_data: Get all the user filters and corresponding email addresses.

    :returns: A set of (filter graph, email address).
    """
    data = query(f"""
        PREFIX ext: <http://mu.semte.ch/vocabularies/ext/>
        PREFIX schema: <http://schema.org/>

        SELECT
          ?email
          ?filter_url
        WHERE {{
          GRAPH <{BASE_URL}/graphs/subscriptions> {{
            ?user_url ext:hasSubscription ?filter_url;
                      schema:email ?email.
          }}
        }}
    """, sudo=True)

    return set(
        (
            get_filter(binding["filter_url"]["value"]),
            binding["email"]["value"]
        )
        for binding in data["results"]["bindings"]
    )

def get_filter(url: str) -> Graph:
    """
    get_filter: Get the shacl filter at the given URL.

    :param url: The URL to look up.
    :returns: The rdflib Graph of the NodeShape.
    """
    return graph_from_results(query(f"""
        PREFIX sh: <http://www.w3.org/ns/shacl#>

        CONSTRUCT  {{
          ?nextNode ?prop ?value.
        }} WHERE {{
          GRAPH <{BASE_URL}/graphs/subscriptions> {{
            BIND(<{url}> as ?nodeShape)
            ?nodeShape a sh:NodeShape.
            ?nodeShape (sh:or|sh:and|sh:not|sh:xone|sh:property|rdf:first|rdf:rest)* ?nextNode.
            ?nextNode ?prop ?value.
          }}
        }}
    """, sudo=True))

def send_mail(mail_html: str, email_address: str):
    """
    send_mail: Queue an email to be sent with the given HTML content to the
    given email address.

    :param mail_html: The HTML data to send.
    :param email_address: The address to send the mail to.
    """
    query(f"""
        PREFIX nmo: <http://www.semanticdesktop.org/ontologies/2007/03/22/nmo#>
        PREFIX nie: <http://www.semanticdesktop.org/ontologies/2007/01/19/nie#>
        PREFIX nfo: <http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#>

        INSERT DATA {{
          GRAPH <{BASE_URL}/graphs/system/email> {{
            <{BASE_URL}/id/emails/{str(uuid.uuid4())}> a nmo:Email;
                nmo:messageFrom "{os.environ["EMAIL_FROM"]}";
                nmo:emailTo "{email_address}";
                nmo:messageSubject "{os.environ["EMAIL_SUBJECT"]}";
                nmo:htmlMessageContent "{escape(mail_html)}";
                nmo:sentDate "";
                nmo:isPartOf <{BASE_URL}/id/mail-folders/2>.
          }}
        }}
    """, 'POST', sudo=True)
