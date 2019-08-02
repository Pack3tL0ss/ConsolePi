#!/usr/bin/env bash

wpa_cli terminate
ip addr flush wlan0
ip link set dev wlan0 down
rm -r /var/run/wpa_supplicant 2>/dev/null
rm -r /tmp/wlan0 2>/dev/null
wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf