"""
app.py: entry point of the service
"""

import locale
import os
import base64
import logging
import shutil
from typing import Dict
from pathlib import Path

from flask import Flask, Response, request
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pyshacl import validate
from rdflib import Graph, DCTERMS, OWL, PROV

from helpers import BESLUIT
from helpers import format_date, graph_from_partial_delta, create_modified_graph
from queries import get_content, get_user_data_list, send_mail, get_all_emails
from queries import find_related_content

locale.setlocale(locale.LC_ALL, 'nl_BE.UTF-8')

LOGLEVEL = os.environ.get('LOGLEVEL', 'WARNING').upper()
logging.basicConfig(level=LOGLEVEL)


app = Flask(__name__)

@app.route('/.mu/delta', methods=["POST"])
def delta_notification() -> Response:
    """
    delta_notification: POSTed to by delta-notifier.

    :returns: "OK" when succesful
    """
    logging.info("Received delta notification")

    data = request.json

    if not data:
        logging.info(f"Invalid data {request.data}")
        return Response("Invalid data", 400)

    # Get the inserts and deletes per subject
    subjects: Dict[str, Dict] = {}

    for delta in data:
        extract_content(delta, subjects, "inserts")
        extract_content(delta, subjects, "deletes")
    logging.debug(f"Extracted {len(subjects)} subjects from delta")

    # Get the data off all users
    user_data_list = get_user_data_list()
    logging.debug(f"Found {len(user_data_list)} user entries")

    for content_url, delta in subjects.items():
        post_delta_content = get_content(content_url)


        if len(post_delta_content) == 0: # type: ignore
            logging.debug(f"URI {content_url} has no data.")
            continue

        # Construct the intermediary
        intermediary = create_modified_graph(
            post_delta_content,
            delta["inserts"],
            add=False
        )

        inserts = graph_from_partial_delta(delta["inserts"])
        deletes = graph_from_partial_delta(delta["deletes"])

        # Construct the previous version
        pre_delta_content = create_modified_graph(
            intermediary,
            delta["deletes"],
            add=True
        )

        # Check if we need to send it to someone
        for user_data in user_data_list:
            filter_graph = user_data.filter_graph

            # If the user has no actual filter, skip it
            if len(filter_graph) == 0: # type: ignore
                continue

            if (matches(post_delta_content, filter_graph) or
                    matches(pre_delta_content, filter_graph)):
                logging.info(f"Updating content for {user_data.user_url} for freq {user_data.frequency}.")
                save_graph_to_userfile(
                    user_data.user_url,
                    user_data.frequency,
                    inserts,
                    deletes
                )

    return Response("OK")

def save_graph_to_userfile(
        user_url: str,
        frequency: str,
        inserted: Graph,
        deleted: Graph
    ):
    """
    save_graph_to_userfile: Save a delta to the users' file.

    :param user_url: The URL of the user.
    :param frequency: One of daily/weekly/monthly.
    :param inserted: The graph of inserted triples.
    :param deleted: The graph of deleted triples.
    """
    # TODO: Handle tuples that are inserted again after being deleted
    base = Path(os.environ["USERFILES_DIR"])
    base_user = base / frequency / base64.b64encode(
        user_url.encode("UTF-8")
    ).decode("UTF-8")

    if not base_user.exists():
        base_user.mkdir(parents=True)

    inserted.serialize(destination=base_user / "inserted.ttl")
    deleted.serialize(destination=base_user / "deleted.ttl")


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


@app.route('/notify_users/<string:frequency>', methods=["POST"])
def notify_users(
        frequency: str,
    ) -> Response:
    """
    notify_users: Send the emails about the changed content.

    :param frequency: One of "daily", "weekly" or "monthly".
    :returns: "OK" when succesful
    """
    if frequency not in ["daily", "weekly", "monthly"]:
        return Response(f"Invalid frequency {frequency}", 400)

    emails = get_all_emails()

    path = Path(os.environ['USERFILES_DIR']) / frequency
    path.mkdir(parents=True, exist_ok=True)

    for user_folder_direntry in os.scandir(path):
        if not user_folder_direntry.is_dir():
            continue

        user_folder = Path(user_folder_direntry)

        user_uri = base64.b64decode(user_folder.name).decode("UTF-8")

        inserts_graph = Graph()
        if (user_folder / "inserted.ttl").exists():
            inserts_graph.parse(user_folder / "inserted.ttl")

        deletes_graph = Graph()
        if (user_folder / "deleted.ttl").exists():
            deletes_graph.parse(user_folder / "deleted.ttl")

        relevant_uris = set()

        # TODO: also take objects into account
        for uri in (set(str(uri) for uri in inserts_graph.subjects())
            | set(str(uri) for uri in deletes_graph.subjects())):

            relevant_uris |= find_related_content(uri)

        content_graph = Graph()

        for uri in relevant_uris:
            content_graph += get_content(uri)

        unchanged_graph = content_graph - inserts_graph - deletes_graph

        # Set up Jinja environment
        env = Environment(
            loader=FileSystemLoader("/config"),
            autoescape=select_autoescape()
        )
        template = env.get_template("template.html")

        # Render the template
        html = template.render(
            # Graphs
            unchanged=unchanged_graph,
            inserts=inserts_graph,
            deletes=deletes_graph,

            # Namespaces
            DCTERMS=DCTERMS,
            OWL=OWL,
            PROV=PROV,
            BESLUIT=BESLUIT,

            # Helper functions
            format_date=format_date,
        )

        # Queue for sending
        send_mail(html, emails[user_uri])
        
        # Clean outbox for user
        shutil.rmtree(user_folder_direntry)

    return Response("OK")

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
