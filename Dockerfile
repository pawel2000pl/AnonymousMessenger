FROM python:3.12

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
RUN pip install cherrypy ws4py markdown bcrypt mysql-connector-python pywebpush ecdsa

COPY mysql "$APP_PATH/mysql"
RUN bash mysql/install_transient_mysql.sh

COPY . "$APP_PATH/"
RUN find "$APP_PATH/static" -name "*.html" -exec python3 "$APP_PATH/static_minifier.py" {} \;
RUN find "$APP_PATH/static" -name "*.css" -exec python3 "$APP_PATH/static_minifier.py" {} \;
RUN find "$APP_PATH/static" -name "*.js" -exec python3 "$APP_PATH/static_minifier.py" {} \;

EXPOSE 8080
CMD bash start.sh