"""
web.py: entry point of the service
"""

from __future__ import annotations

from flask import Flask

app = Flask(__name__)

@app.route('/', methods=['GET'])
def schedule() -> str:
    """
    schedule: the main route of the service

    :returns: A response to this request
    """
    return "Hello world"
