#!/bin/bash

if [ "$TRANSIENT_DATABASE" == "TRUE" ];
then
    cd /tmp
    apt update
    apt install -y mariadb-server

    echo "" >> "/etc/mysql/mariadb.cnf"
    echo "[mariadb]" >> "/etc/mysql/mariadb.cnf"
    echo "innodb_flush_log_at_trx_commit=0" >> "/etc/mysql/mariadb.cnf"

    cd "$APP_PATH"
    
    service mariadb start
    cat mysql/init.sql | mysql &> /tmp/logs.txt
    cat /tmp/logs.txt
    service mariadb stop
fi
