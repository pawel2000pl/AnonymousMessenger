FROM python:3.11

ARG TRANSIENT_DATABASE="FALSE"

ENV DEBIAN_FRONTEND=noninteractive
ENV APP_PATH="/usr/src/AnonymousMessenger/"
ENV PRODUCTION="TRUE"
ENV PYTHONOPTIMIZE="TRUE"
ENV TRANSIENT_DATABASE="$TRANSIENT_DATABASE"

RUN mkdir -p "$APP_PATH"
WORKDIR "$APP_PATH"

RUN apt update
RUN apt upgrade -y
RUN pip install --upgrade pip
RUN pip install cherrypy ws4py markdown bcrypt mysql-connector-python

COPY mysql "$APP_PATH/mysql"
RUN bash mysql/install_transient_mysql.sh

COPY . "$APP_PATH/"

EXPOSE 8080
CMD bash start.sh