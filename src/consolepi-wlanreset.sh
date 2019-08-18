#!/usr/bin/env bash
wifidev=wlan0
ethdev=eth0

wpa_cli terminate
ip addr flush wlan0
ip link set dev wlan0 down
rm -r /var/run/wpa_supplicant 2>/dev/null
rm -r /tmp/wlan0 2>/dev/null
ip link set dev wlan0 up
wpa_supplicant -B -i "$wifidev" -c /etc/wpa_supplicant/wpa_supplicant.conf