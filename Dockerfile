FROM python:3.9
LABEL maintainer="robbe@robbevanherck.be"

EXPOSE 80

RUN apt-get update
RUN apt-get -y install locales

RUN sed -i '/nl_BE.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen
ENV LANG nl_BE.UTF-8
ENV LANGUAGE nl_BE:nl
ENV LC_ALL nl_BE.UTF-8

RUN mkdir -p /app
WORKDIR /app

ADD requirements.txt /app/

RUN cd /app && pip install -r requirements.txt

ADD *.py /app/

CMD FLASK_APP=app python -m flask run --host=0.0.0.0 --port=80
