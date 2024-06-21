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
RUN pip install cherrypy ws4py markdown bcrypt mysql-connector-python pywebpush ecdsa numpy scipy

COPY mysql "$APP_PATH/mysql"
RUN bash mysql/install_transient_mysql.sh

COPY . "$APP_PATH/"
RUN find "$APP_PATH/static" \( -name "*.html" -or -name "*.css" -or -name "*.js" \) -exec \
    sed -i -r 's/[\r]+/\n/g;s/[\n]+/\n/g;s/[\t ]+$//g;s/^[\t ]+//g;s/[\t ]{2,}/ /g' {} \;

EXPOSE 8080
CMD bash start.sh
