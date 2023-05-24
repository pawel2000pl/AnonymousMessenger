#!/bin/bash

if [ "$TRANSIENT_DATABASE" == "TRUE" ];
then
    cd /tmp
    apt install -y wget
    wget https://dev.mysql.com/get/mysql-apt-config_0.8.22-1_all.deb
    apt install -y ./mysql-apt-config_0.8.22-1_all.deb
    apt update
    apt install -y mysql-server mysql-common mysql-client

    cd "$APP_PATH"

    echo "" >> "/etc/mysql/mysql.conf.d/mysqld.cnf"
    echo "innodb_flush_log_at_trx_commit=0" >> "/etc/mysql/mysql.conf.d/mysqld.cnf"
    echo "innodb_flush_log_at_timeout=3" >> "/etc/mysql/mysql.conf.d/mysqld.cnf"

    /usr/bin/mysqld_safe --user=mysql &
    sleep 1s
    while [ `(cat mysql/init.sql | mysql &> /tmp/logs.txt) && echo 1 || echo 0` == 0 ]; do echo "Waiting..."; cat /tmp/logs.txt; sleep 1s; done;
    killall mysqld

    rm -f /tmp/mysql-apt-config_0.8.22-1_all.deb
    rm -f /tmp/logs.txt

fi