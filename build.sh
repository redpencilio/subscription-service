#!/bin/bash

pylint *.py || exit 1

mypy --install-types --non-interactive
mypy --ignore-missing-imports *.py || exit 1

docker build -t robbe7730/subscription-service . || exit 1

pushd ../app-poc-participatie

docker-compose stop -t 1 subscription
docker-compose up --build -d subscription
docker-compose start subscription

popd
