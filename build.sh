#!/bin/bash

python -m mypy --install-types --non-interactive
python -m mypy --ignore-missing-imports *.py || exit 1

docker build -t redpencil/subscription . || exit 1
