"""
web.py: entry point of the service
"""

from __future__ import annotations

import time

from flask import Flask
from jinja2 import Environment, FileSystemLoader, select_autoescape

from queries import get_agendapunten_data, send_mail

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
