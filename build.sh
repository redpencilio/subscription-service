#!/bin/bash

python -m pylint *.py || exit 1

python -m mypy --install-types --non-interactive
python -m mypy --ignore-missing-imports *.py || exit 1

docker build -t robbe7730/subscription . || exit 1

pushd ../app-lokaalbeslist

docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.override.yml stop -t 1 subscription
docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.override.yml up --build -d subscription
docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.override.yml start subscription

popd
