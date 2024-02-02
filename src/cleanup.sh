#!/usr/bin/env bash

consolepi_tmp_files=($(ls /sys/class/net | grep -v lo))
consolepi_tmp_files+=(consolepi-push-delay.lock)
consolepi_tmp_files+=($( ls -1 /tmp | grep "^tun" ))
for i in "${consolepi_tmp_files[@]}"; do
    if [ -e "/tmp/$i" ]; then
        rm "/tmp/$i"
    fi
done
