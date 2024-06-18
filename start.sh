#!/bin/bash

if [ -e "$APP_PATH/.env" ];
then
    TEMP_ENV="/dev/shm/.am-env-tmp"
    sed -E 's/^(.+)/export \1/g' "$APP_PATH/.env" > "$TEMP_ENV"
    source "$TEMP_ENV"
    rm -f "$TEMP_ENV"
fi

if [ "$TRANSIENT_DATABASE" == "TRUE" ];
then
    # echo "Starting mysql"
    # /usr/bin/mysqld_safe --user=mysql --log-bin-trust-function-creators &
    # while [ `(echo "SELECT 'Hello there';" | mysql &> /dev/null) && echo 1 || echo 0` == 0 ]; do echo "Waiting..."; sleep 1s; done;
    service mariadb start

    export DATABASE_HOST="localhost"
    export DATABASE_NAME="anonymous_messenger_db"
    export DATABASE_USER="anonymous_messenger"
    export DATABASE_PASS="anonymous_messenger_pass"
fi

echo "Starting python3"
cd "$APP_PATH"
python3 server/main.py

echo "Exiting"

if [ "$TRANSIENT_DATABASE" == "TRUE" ];
then
    service mariadb stop
fi
