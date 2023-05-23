FROM python:3.11

ENV DEBIAN_FRONTEND=noninteractive
ENV APP_PATH="/usr/src/AnonymousMessenger/"
ENV PRODUCTION="TRUE"
ENV PYTHONOPTIMIZE="TRUE"

RUN mkdir -p "$APP_PATH"
WORKDIR "$APP_PATH"

RUN apt update
RUN pip install cherrypy ws4py markdown bcrypt mysql-connector-python

COPY mysql "$APP_PATH/mysql"
RUN bash mysql/install_transient_mysql.sh

COPY . "$APP_PATH/"

EXPOSE 8080
CMD bash start.sh