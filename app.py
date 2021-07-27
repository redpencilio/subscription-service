"""
web.py: entry point of the service
"""

from __future__ import annotations
import time

from flask import Flask, Response, request
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pyshacl import validate

from helpers import log
from queries import get_agendapunt, get_agendapunten_data, get_filter, send_mail

app = Flask(__name__)

@app.route('/', methods=['GET'])
def root() -> str:
    """
    root: the main route of the service

    :returns: A response to this request
    """
    start_time = time.time_ns()
    data = get_agendapunten_data()

    env = Environment(
        loader=FileSystemLoader("/app/templates"),
        autoescape=select_autoescape()
    )

    template = env.get_template("mail.html")

    html = template.render(
        data=data
    )

    send_mail(html)

    return f"Execution took {(time.time_ns() - start_time) / 1000000000} s"

@app.route('/.mu/delta', methods=["POST"])
def delta_notification() -> Response:
    """
    delta_notification: POSTed to by delta-notifier.

    :returns: "OK" when succesful
    """

    data = request.json

    if not data:
        return Response("Invalid data", 400)

    subjects = set()

    for delta in data:
        subjects |= (
            set(x["subject"]["value"] for x in delta["inserts"]) |
            set(x["subject"]["value"] for x in delta["deletes"])
        )

    user_filter = get_filter()
    user_filter.print()

    for subject in subjects:
        new_punt = get_agendapunt(str(subject))
        if len(new_punt) == 0:  # type: ignore
            log(f"Not an Agendapunt: {subject}")
            continue
        new_punt.print()
        print(validate(
            data_graph=new_punt,
            shacl_graph=user_filter,
            debug=True
        ))

    return Response("OK")
