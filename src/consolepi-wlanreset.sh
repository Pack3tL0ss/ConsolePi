#!/usr/bin/env bash

# -- ConsolePi script to reset wlan --
#  This is useful anytime you want to reset the wlan state so you can run/test consolepi-autohotspot
#  Primarily used for testing.  If you just want to search for defined networks you can just run consolepi-autohotspot
#
# - Kills hotspot if running
# - flushes wlan interface (bounce it and flush ips)
# - remove iptables rules added during hotspot launch
# - disable ip forwarding
# - shutdown dhcp for hotspot interface (unless using older dnsmasq system service and override exists)
# - Launches wpa_supplicant to scan and connect (if found) to configured SSIDs

wifidev=wlan0
ethdev=eth0
override_dir="/etc/ConsolePi/overrides"

start_stop_dnsmasq() {
    # if all files are in place to use new separate instance for hotspot dhcp do so otherwise assume using dnsmasq default instance
    if [ -f $ahs_dhcp_config ] && [ -f /etc/dnsmasq.d/01-consolepi ] &&
       ( [ -L /etc/systemd/system/consolepi-autohotspot-dhcp.service ] || [ -f /etc/systemd/system/consolepi-autohotspot-dhcp.service ] ); then
        systemctl $1 consolepi-autohotspot-dhcp.service
    else
        if [ ! -f ${override_dir}/dnsmasq.service ]; then
            systemctl $1 dnsmasq.service
        else
            echo Skipping dnsmasq $1 as dnsmasq.service has override
        fi
    fi
}

wpa_cli terminate >/dev/null 2>&1
ip addr flush $wifidev 2>/dev/null
ip link set dev $wifidev down
systemctl stop hostapd >/dev/null 2>&1
start_stop_dnsmasq stop

# [ -f /var/run/wpa_supplicant/$wifidev ] && rm /var/run/wpa_supplicant/$wifidev
_ctrl_if=$(grep "^ctrl_interface" /etc/wpa_supplicant/wpa_supplicant.conf)
_ctrl_if=$(echo ${x// GROUP*/} | rev | cut -d= -f 1 | rev)
[ -f "$_ctrl_if/$wifidev" ] && rm "$_ctrl_if/$wifidev" >/dev/null 2>&1
rmdir /var/run/wpa_supplicant 2>/dev/null
rm -r /tmp/$wifidev 2>/dev/null

iptables -D FORWARD -i "$ethdev" -o "$wifidev" -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null
iptables -D FORWARD -i "$wifidev" -o "$ethdev" -j ACCEPT 2>/dev/null
echo 0 > /proc/sys/net/ipv4/ip_forward

ip link set dev $wifidev up 2>&1

# wait for interface to come up
idx=0; while ip link show dev $wifidev >/dev/null | grep -q "state DOWN"; do
    [[ $idx == 0 ]] && printf "\nWaiting for $wifidev to come back up..."
    sleep 3 ; printf "..."
    ((idx+=1)); printf $idx
    if [[ $idx > 5 ]]; then
        break
    fi
done
echo

dhcpcd  -n "$wifidev" >/dev/null 2>&1

if [[ $1 =~ debug ]]; then
    echo -e "\nStarting wpa_supplicant in forground with debug"
    echo 'wpa_supplicant -dd -i "$wifidev" -c /etc/wpa_supplicant/wpa_supplicant.conf'
    echo
    wpa_supplicant -dd -i "$wifidev" -c /etc/wpa_supplicant/wpa_supplicant.conf
elif [ -z "$1" ]; then
    wpa_res=$(wpa_supplicant -B -i "$wifidev" -c /etc/wpa_supplicant/wpa_supplicant.conf 2>&1) &&
        echo -e "${wpa_res}"| head -1 || echo -e "${wpa_res[@]}"
else  # Any arg will prevent wpa_from starting
    echo -e "\nwpa_supplicant not started based on "$1" arg"
    echo "  -debug   Starts wpa_supplicant in terminal w/ debug"
    echo -e "  Any Other Arg kills hotspot but does not restart wpa_supplicant\n"
fi
