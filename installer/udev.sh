#!/usr/bin/env bash

udev_init(){
	shopt -s nocasematch
	input="go"
	rules_file='/etc/udev/rules.d/10-consolePi.rules'
	ser2net_conf='/etc/ser2net.conf'
}

header() {
clear
echo "--------------Predictable Serial Port Devices--------------"
echo "* This script will assign predictable ports to speccific  *"
echo "* Serial Adapters. reccommend labeling the adapters       *"
echo "*                                                         *"
echo "* I've Found that some serial adapters may cause the      *"
echo "* Pi zero w to reboot when plugged in if this occurs just *"
echo "* re run the script after the reboot completes with only  *"
echo "* the remainins adapters.                                 *"
echo "*---------------------------------------------------------*"
echo
echo "**Insert adapters 1 at a time**"
}

getdev() {
for sysdevpath in $(find /sys/bus/usb/devices/usb*/ -name dev|grep ttyUSB); do
    syspath="${sysdevpath%/dev}"
    devname="$(udevadm info -q name -p $syspath)"
    # Debug Line # udevadm info -q property --export -p $syspath
    eval "$(udevadm info -q property --export -p $syspath)"
    [[ -z "ID_MODEL_FROM_DATABASE" ]] && [[ -z "$ID_VENDOR_ID" ]] && [[ -z "$ID_MODEL_ID" ]] && [[ -z "$ID_SERIAL_SHORT" ]] && continue
    this_dev="SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"${ID_VENDOR_ID}\", ATTRS{idProduct}==\"${ID_MODEL_ID}\", ATTRS{serial}==\"${ID_SERIAL_SHORT}\", SYMLINK+=\"ConsolePi${port}\""
    if [ -f $rules_file ]; then
        echo $this_dev >> $rules_file
    else
        echo $this_dev > $rules_file
    fi
	[ -f $ser2net_conf ] && echo "${port}:telnet:0:/dev/ConsolePi${port}:9600 8DATABITS NONE 1STOPBIT banner"
    echo "${ID_MODEL_FROM_DATABASE} Found with idVendor: ${ID_VENDOR_ID} idProduct ID: ${ID_MODEL_ID} and Serial: ${ID_SERIAL_SHORT} Assigned to telnet port ${port}"
    ((port++))
done
}

udev_main() {
	udev_init
    header
    if [ -f $rules_file ]; then
        port=`tail -1 $rules_file |grep SYMLINK |cut -d+ -f2|cut -d\" -f2 |cut -di -f2`
        ((port++))
    else
        port=7001
    fi

    while [[ $input != "end" ]] ; do
        [[ $port -eq 7001 ]] && word="first" || word="next"
        echo "Insert the ${word} serial adapter - then press enter"
        echo "Type \"end\" when complete"
        read input
        [[ $input != "end" ]] && getdev 
    done
    # mv /tmp/10-consolePi.rules /etc/udev/rules.d/10-consolePi.rules 
    cat $rules_file
    # rm -f /tmp/10-consolePi.rules
}

# __main__
# iam=`whoami`
# if [ "${iam}" = "root" ]; then 
  # udev_main
# else
  # echo 'Script should be ran as root. exiting.'
# fi
