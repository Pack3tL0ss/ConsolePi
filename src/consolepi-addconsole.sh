#!/usr/bin/env bash

udev_init(){
    error_file="/var/log/ConsolePi/consolepi-addudev.error"
    shopt -s nocasematch
    input="go"
    rules_file='/etc/udev/rules.d/10-ConsolePi.rules'
    ser2net_conf='/etc/ser2net.conf'
    process="Predictable Console Ports"
    auto_name=false
    # this isn't used yet.  ser2net 4 uses yaml config
    # ser2net_ver=$(which ser2net >/dev/null 2>&1 && ser2net -v | awk '{print $3}' | cut -d. -f1 || echo 0)
    # [ ! $ser2net_ver -eq 4 ] && ser2net_conf='/etc/ser2net.conf' || ser2net_conf='/etc/ser2net/ser2net.yaml'
    # [ -f /etc/ConsolePi/installer/common.sh ] && . /etc/ConsolePi/installer/common.sh ||
    #     echo "ERROR Failed to import common functions"
}

udev_header() {
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
for sysdevpath in $(find /sys/bus/usb/devices/usb*/ -name dev|grep 'ttyUSB\|ttyACM'); do
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
        if [ ! -f $rules_file ] || [ $(grep -c -m 1 $ID_SERIAL_SHORT $rules_file) -eq 0 ]; then
            echo -e "\033[1;32mDevice Found:$*\033[m ${ID_MODEL_FROM_DATABASE} "
            echo "  vendor: ${ID_VENDOR} / ${ID_VENDOR_FROM_DATABASE} model: ${ID_MODEL}"
            echo "  idVendor: ${ID_VENDOR_ID} idProduct: ${ID_MODEL_ID} Serial: ${ID_SERIAL_SHORT} It Will be assigned to telnet port ${port}"

            if ! $auto_name; then
                echo 
                echo "Let's assign alias names for the adapters.  This is mainly useful for the menu display in consolepi-menu."
                echo "Enter \"auto\" to let the script automatically assign names (you won't see this prompt again for this session)"
                read -e -p 'What alias (descriptive name) do you want to use for this adapter?: ' alias
                echo -e '\n'
            fi
            alias=${alias// /_}  # replace any spaces with underscroes as udev doesn't allow spaces in symlinks
            [[ "${alias}" == "auto" ]] && auto_name=true && alias="ConsolePi"
            $auto_name && $alias+="_${port}"

            this_dev="SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"${ID_VENDOR_ID}\", ATTRS{idProduct}==\"${ID_MODEL_ID}\", ATTRS{serial}==\"${ID_SERIAL_SHORT}\", SYMLINK+=\"${alias}\""
            if [ -f $rules_file ]; then
                echo $this_dev >> $rules_file
            else
                echo $this_dev > $rules_file
            fi
            [ -f $ser2net_conf ] && echo "${port}:telnet:0:/dev/${alias}:9600 8DATABITS NONE 1STOPBIT banner" >> $ser2net_conf
            echo "${process}" "${ID_MODEL_FROM_DATABASE} idVendor: ${ID_VENDOR_ID} idProduct: ${ID_MODEL_ID} Serial: ${ID_SERIAL_SHORT} Assigned to telnet port ${port} alias: ${alias}_${port}" \
                >> /var/log/ConsolePi/install.log
            ((port++))
        else
            echo -e " ---!! \033[1;32mDEVICE ALREADY EXISTS$*\033[m !!---"
            echo "${ID_MODEL_FROM_DATABASE} with serial ${ID_SERIAL_SHORT} already has a defined rule:"
            printf '  ' && grep ${ID_SERIAL_SHORT} ${rules_file}
            echo -e "\nThis device already exists in ${rules_file}.  Ignoring\n"
        fi
    fi
done
}

udev_main() {
    udev_init
    udev_header
	# -- strip blank lines from end of rules file and ser2net.conf
    [ -f $ser2net_conf ] && sudo sed -i -e :a -e '/^\n*$/{$d;N;};/\n$/ba' $ser2net_conf
    [ -f $rules_file ] && sudo sed -i -e :a -e '/^\n*$/{$d;N;};/\n$/ba' $rules_file
    # -- if rules file already exist grab the port assigned to the last entry and start with the next port --
    if [ -f $ser2net_conf ]; then
        port=$(grep ^70[0-9][0-9]: /etc/ser2net.conf | tail -1 | cut -d: -f1)
        [ ${#port} -eq 0 ] && port=7000 # result is port = 7001 if no match in ser2net
        ((port++))
        if [ -f $rules_file ]; then
            echo -e '\n\n'
            echo "->> Existing rules file found with the following rules, adding ports will append to these rules starting at port $port <<-"
            cat $rules_file
        fi
        echo "-------------------------------------------------------------------------------------------------------------------------"
    else
        port=7001
    fi

    while [[ $input != "end" ]] ; do
        [[ $port -eq 7001 ]] && word="first" || word="next"
        echo
        echo "Insert the ${word} serial adapter - then press enter"
        echo "Type \"end\" when complete"
        read -en 3 input
        [[ $input != "end" ]] && getdev 
    done

	# -- Show the resulting rules when complete --
    echo "------------------------------------------>> The Following Rules are Active <<-------------------------------------------"
    cat $rules_file 2>/dev/null || echo " No Rules Created."
    echo "-------------------------------------------------------------------------------------------------------------------------"
    sudo udevadm control --reload-rules && udevadm trigger
    
}

# __main__
if [[ ! $0 == *"ConsolePi" ]] && [[ $0 == *"src/consolepi-addconsole.sh"* ]] ; then
    iam=`whoami`
    if [ "${iam}" = "root" ]; then
        echo "...script ran from CLI..."
        udev_main
    else
        echo 'Script should be ran as root. exiting.'
    fi
else
    echo $0
fi
