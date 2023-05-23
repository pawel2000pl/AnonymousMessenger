FROM python:3.11

ENV DEBIAN_FRONTEND=noninteractive
ENV APP_PATH="/usr/scr/AnonymousMessenger/"
ENV PRODUCTION="TRUE"
ENV PYTHONOPTIMIZE="TRUE"

RUN apt update
RUN apt install -y sqlite3
RUN pip install cherrypy ws4py markdown bcrypt


RUN mkdir -p "$APP_PATH"
COPY . "$APP_PATH/"

WORKDIR "$APP_PATH"

EXPOSE 8080
CMD python main.py