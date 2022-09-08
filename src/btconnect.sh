#!/usr/bin/env bash

source /etc/ConsolePi/installer/common.sh
device=$1
[ $(echo ${1} | tr -cd : | wc -c) -eq 5 ] && is_mac=true || is_mac=false

if ! $is_mac; then
    device=$(echo devices | sudo bluetoothctl | grep "^Device.*${device}$" | awk '{print $2}')
fi

##echo $device
#echo -e "sdptool add --channel=1 SP\nrfcomm connect /dev/rfcomm0 ${device} 1" > /tmp/consolepi-btclient

if [ ! -z "$device" ]; then
    sudo sdptool add --channel=1 SP
    echo -e ${_cyan}initiating connection...${_norm}
    sudo -b rfcomm connect /dev/rfcomm0 ${device} >/tmp/btclient 2>&1 ;

    printf "waiting for connection" # && sleep 5
    out=$(cat /tmp/btclient)

    i=0;while [ -z "$out" ]; do
        ((i+=1))
        sleep 1
        out=$(cat /tmp/btclient)
        printf '.'
        [ $i -ge 20 ] && echo -e "\ntimeout" && break
    done
    echo

    if [[ ! "$out" =~ "t connect" ]]; then
        su $iam -c "picocom /dev/rfcomm0 -b 115200 2>/dev/null"
    else
        echo $out
    fi

fi

rm -f /tmp/btclient
