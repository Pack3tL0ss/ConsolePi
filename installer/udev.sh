#!/usr/bin/env bash

udev_init(){
    error_file="/var/log/ConsolePi/consolepi-addudev.error"
    shopt -s nocasematch
    input="go"
    rules_file='/etc/udev/rules.d/10-ConsolePi.rules'
    ser2net_conf='/etc/ser2net.conf'
    process="Predictable Console Ports"
    [[ ! -f "/tmp/consolepi_install.log" ]] && touch /tmp/consolepi_install.log
    auto_name=false
}

header() {
	clear
	echo -e "--------------------------------------------- \033[1;32mPredictable Console ports$*\033[m -------------------------------------------------"
	echo "* This script will automatically create udev rules and assign aliases for each USB to serial device (or pig-tail).      *"
	echo "* You should label the adapters.                                                                                        *"
	echo "*                                                                                                                       *"
	echo "* I've Found that some serial adapters in combination with some otg USB hubs may cause the Pi zero w to reboot when     *"
	echo "* plugged in.  If this occurs just run consolepi-addconsole after the reboot completes starting with the adapter that   *"
	echo "* caused the reboot.  The config should retain any previously configured adapters and pick-up at the next available     *"
	echo "* port.  This is the last step in the installation script so there is no need to re-run the installer.                  *"
	echo "-------------------------------------------------------------------------------------------------------------------------"
	echo
	echo "** Insert single port adapters 1 at a time"
	echo "** If you have a multi-port (pig-tail) adapter you can use this script to assign those ports, but you'll have to connect"
	echo "** to the ports after setup to determine which pigtail is assigned to each port - then label the pig-tails." 
}

getdev() {
for sysdevpath in $(find /sys/bus/usb/devices/usb*/ -name dev|grep ttyUSB); do
    syspath="${sysdevpath%/dev}"
    devname="$(udevadm info -q name -p $syspath)"
    # Debug Line # udevadm info -q property --export -p $syspath
    eval "$(udevadm info -q property --export -p $syspath)"

    ( [ -z "$ID_VENDOR_ID" ] || [ -z "$ID_MODEL_ID" ] || [ -z "$ID_SERIAL_SHORT" ] ) && error=true || error=false
    if $error; then
        echo "This adapter does not have all of the attributes defined that are used to uniquely identify it and can not be added by this script."
        echo "The adapter contains the following values. The Blank Value is missing preventing the script from adding this adapter:"
        echo 
        echo "idVendor: ${ID_VENDOR_ID}"
        echo "idProduct: ${ID_MODEL_ID}"
        echo "serial: ${ID_SERIAL_SHORT}"
        echo "$(udevadm info --attribute-walk --name /dev/${syspath##*/})" >> /var/log/ConsolePi/consolepi-addudev.error
        echo 
        echo "It may be possible to add this adapter manually if nothing else you can tie the udev rule to the specific USB port."
        echo "This would require that it's always plugged into the same port."
        echo
        echo "The adapter will also work using the non-predictable ports starting at 8001."
        echo
        echo "To aid in the manual process a full attribute-walk has been dumped to ${error_file}"
    else
        echo "${ID_MODEL_FROM_DATABASE} Found, idVendor: ${ID_VENDOR_ID} idProduct: ${ID_MODEL_ID} Serial: ${ID_SERIAL_SHORT} It Will be assigned to telnet port ${port}"

        if ! $auto_name; then
            echo 
            echo "Let's assign alias names for the adapters.  This is mainly useful for the menu display in consolepi-menu."
            echo "Enter \"auto\" to let the script automatically assign names (you won't see this prompt again for this session)"
            read -p 'What alias (descriptive name) do you want to use for this adapter?: ' alias
        fi
        [[ "${alias}" == "auto" ]] && auto_name=true && alias="ConsolePi"

        this_dev="SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"${ID_VENDOR_ID}\", ATTRS{idProduct}==\"${ID_MODEL_ID}\", ATTRS{serial}==\"${ID_SERIAL_SHORT}\", SYMLINK+=\"${alias}_${port}\""
        if [ -f $rules_file ]; then
            echo $this_dev >> $rules_file
        else
            echo $this_dev > $rules_file
        fi
        [ -f $ser2net_conf ] && echo "${port}:telnet:0:/dev/${alias}_${port}:9600 8DATABITS NONE 1STOPBIT banner" >> $ser2net_conf
        echo "${process}" "${ID_MODEL_FROM_DATABASE} idVendor: ${ID_VENDOR_ID} idProduct: ${ID_MODEL_ID} Serial: ${ID_SERIAL_SHORT} Assigned to telnet port ${port} alias: ${alias}_${port}" \
            >> /tmp/consolepi_install.log
        ((port++))
    fi
done
}

udev_main() {
    udev_init
    header
	
    # -- if rules file already exist grab the port assigned to the last entry and start with the next port --
    if [ -f $rules_file ]; then
        # port=`tail -1 $rules_file |grep SYMLINK |cut -d+ -f2|cut -d\" -f2 |cut -d_ -f2`
        port=$(tail -1 $rules_file | awk '{ print $5 }') && port=${port: -5:4}
        ((port++))
		echo -e '\n\n'
        echo "->> Existing rules file found with the following rules, adding ports will append to these rules starting at port $port <<-"
        cat $rules_file
        echo "-------------------------------------------------------------------------------------------------------------------------"
    else
        port=7001
    fi

    while [[ $input != "end" ]] ; do
        [[ $port -eq 7001 ]] && word="first" || word="next"
        echo
        echo "Insert the ${word} serial adapter - then press enter"
        echo "Type \"end\" when complete"
        read input
        [[ $input != "end" ]] && getdev 
    done

	# -- Show the resulting rules when complete --
    echo "------------------------------------------>> The Following Rules are Active <<-------------------------------------------"
    cat $rules_file 2>/dev/null || echo " No Rules Created."
    echo "-------------------------------------------------------------------------------------------------------------------------"
    sudo udevadm control --reload-rules && udevadm trigger
    
}

# __main__
if [[ ! $0 == *"ConsolePi" ]] && [[ $0 == *"installer/udev.sh"* ]] ; then
    iam=`whoami`
    if [ "${iam}" = "root" ]; then
        echo "...script ran from CLI..."
        [[ -f /tmp/consolepi_install.log ]] && sudo mv /tmp/consolepi_install.log /etc/ConsolePi/installer/install.log
        udev_main
    else
        echo 'Script should be ran as root. exiting.'
    fi
fi
