"""
queries: relevant SPARQL queries for this service
"""

import os
import uuid
from typing import Set, Dict
from dataclasses import dataclass

from SPARQLWrapper import JSON, SPARQLWrapper
from rdflib import Graph

from helpers import graph_from_results
from helpers import escape_sparql_string

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
CONSTRUCT_CONTENT_QUERY = read_query("/config/construct_content.sparql")

def get_content(url: str) -> Graph:
    """
    get_content: Get all relevant data for a given URL.

    :param url: The URL to look up.
    :returns: The graph with the relevant data.
    """
    return graph_from_results(query(
        CONSTRUCT_CONTENT_QUERY.replace(
            "CONTENT_URL",
            escape_sparql_string(url)
        )
    ))

def find_related_content(subject: str) -> Set[str]:
    """
    find_related_content: Find every URL with content related to the given URL.

    :returns: The (potentially empty) set of related content.
    """
    data = query(
        GET_RELEVANT_CONTENT_QUERY.replace(
            "SUBJECT_URL",
            escape_sparql_string(subject)
        )
    )

    return set(
        binding["content"]["value"]
        for binding in data["results"]["bindings"]
    )

def get_all_emails() -> Dict[str, str]:
    """
    get_all_emails: Get the user ids and their email adresses.

    :returns: A dict with user URIs as keys and email adresses as value.
    """
    data = query(f"""
        PREFIX ext: <http://mu.semte.ch/vocabularies/ext/>
        PREFIX schema: <http://schema.org/>

        SELECT ?user_url ?email
        WHERE {{
          GRAPH <{BASE_URL}/graphs/subscriptions> {{
            ?user_url schema:email ?email .
          }}
        }}
    """, sudo=True)
    return { binding["user_url"]["value"]: binding["email"]["value"]
                for binding in data["results"]["bindings"] }

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

@dataclass
class UserData:
    """
    UserData: A DataClass used in get_user_data_list.
    """
    filter_graph: Graph
    user_url: str
    frequency: str

def get_user_data_list() -> list[UserData]:
    """
    get_user_data_list: Get all the user filters along with the id of the user
    and the frequency.

    :returns: A set of UserDatas.
    """
    data = query(f"""
        PREFIX ext: <http://mu.semte.ch/vocabularies/ext/>
        PREFIX schema: <http://schema.org/>

        SELECT
          ?filter_url
          ?user_url
          ?frequency
        WHERE {{
          GRAPH <{BASE_URL}/graphs/subscriptions> {{
            ?user_url ext:hasSubscription ?filter_url .
            ?filter_url ext:subscriptionFrequency ?frequency.
          }}
        }}
    """, sudo=True)

    return [
        UserData(
            filter_graph = get_filter(binding["filter_url"]["value"]),
            user_url = binding["user_url"]["value"],
            frequency = binding["frequency"]["value"]
        )
        for binding in data["results"]["bindings"]
    ]

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
            BIND(<{escape_sparql_string(url)}> as ?nodeShape)
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
                nmo:emailTo "{escape_sparql_string(email_address)}";
                nmo:messageSubject "{os.environ["EMAIL_SUBJECT"]}";
                nmo:htmlMessageContent "{escape_sparql_string(mail_html)}";
                nmo:sentDate "";
                nmo:isPartOf <{BASE_URL}/id/mail-folders/2>.
          }}
        }}
    """, 'POST', sudo=True)
