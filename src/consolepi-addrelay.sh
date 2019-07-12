#!/usr/bin/env bash

__init__(){
    shopt -s nocasematch
    input="go"
    relay_file='/etc/ConsolePi/relay.json'
    process="Power Relays"
    valid_gpio=[4, 17, 27, 22, 5, 6, 13, 19, 26, 18, 23, 24, 25, 12, 16, 20, 21]
    auto_name=false
    # if [ -z $CFG_FILE_VERSION ]; then
        [ -f '/etc/ConsolePi/installer/common.sh' ] && 
            . /etc/ConsolePi/installer/common.sh ||
            echo "Fatal error - Failed to import common functions"
    # fi
} 

do_header() {
	# clear
	echo -e "----------------------------------------------------- \033[1;32mPower Relays$*\033[m ------------------------------------------------------"
	echo "* This script will prompt you for details on connected hardware relays.                                                 *"
	echo "*                                                                                                                       *"
	echo "* it's purpose in life is to create a properly formatted data file \"relay.json\" which is used to provide power control  *"
	echo "* options in the menu.                                                                                                  *"
	echo "*                                                                                                                       *"
	echo "* It is acceptable to create the file manually, just be sure you follow desired schema.                                 *"
	echo "-------------------------------------------------------------------------------------------------------------------------"
}




not_used() {
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
            echo "  idVendor: ${ID_VENDOR_ID} idProduct: ${ID_MODEL_ID} Serial: ${ID_SERIAL_SHORT} It Will be assigned to telnet port ${port}"

            if ! $auto_name; then
                echo 
                echo "Let's assign alias names for the adapters.  This is mainly useful for the menu display in consolepi-menu."
                echo "Enter \"auto\" to let the script automatically assign names (you won't see this prompt again for this session)"
                read -e -p 'What alias (descriptive name) do you want to use for this adapter?: ' alias
                echo -e '\n'
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
                >> /var/log/ConsolePi/install.log
            ((port++))
        else
            echo -e " ---!! \033[1;32mDEVICE ALREADY EXISTS$*\033[m !!---"
            echo "${ID_MODEL_FROM_DATABASE} Found, idVendor: ${ID_VENDOR_ID} idProduct: ${ID_MODEL_ID} Serial: ${ID_SERIAL_SHORT}"
            echo -e "This device already exists in ${rules_file}.  Ignoring\n"
        fi
    fi
# done
}

udev_main() {
    __init__
    do_header
	
    # -- if rules file already exist grab the port assigned to the last entry and start with the next port --
        # -- if rules file already exist grab the port assigned to the last entry and start with the next port --
    [ -f '/etc/ser2net.conf' ] && get_ser2net
    if [ -f $relay_file ]; then
        echo -e "------------------------------------------>> The Following Relays are Defined <<-------------------------------------------\n"
        cat $relay_file
        echo -e "\n---------------------------------------------------------------------------------------------------------------------------"
    fi



    _relay_name=()
    _relay_gpio=()
    _relay_linked=()
    _relay_noff=()
    _relay_linked_devs=()
    while [[ $result != "end" ]] ; do
        [[ -z $word ]] && word="first" || word="next"
        echo -e "\nAdding Power Relays."
        echo "Type \"end\" when complete"
        user_input NUL "Provide friendly name for relay"
        _relay_name+=$result
        echo 'GPIO pins use the GPIO # not the pin #'
        echo -e 'i.e. GPIO 4 = pin 7 on the board... you would enter 4\n'
        user_input NUL "What GPIO pin will control the relay"
        _relay_gpio+=$result
        user_input true "Is this outlet Normally Off"
        _relay_noff+=$result
        echo -e "\nThe Power relay function supports linking serial adapters with power relays"
        echo -e "If a power outlet is linked with devices, when you connect to those devices via consolepi-menu"
        echo -e "ConsolePi will make sure the device is powered on, if it's not it will power it up."
        echo -e "  ~Note:  This function will not auto power off the device upon disconnect.\n"
        user_input false "Link this port to a particular serial adapter"
        _relay_linked+=$result
        exit 0
    done

	# -- Show the resulting rules when complete --
    echo "------------------------------------------>> The Following Rules are Active <<-------------------------------------------"
    cat $rules_file 2>/dev/null || echo " No Rules Created."
    echo "-------------------------------------------------------------------------------------------------------------------------"
    sudo udevadm control --reload-rules && udevadm trigger
    
}

# __main__
if [[ ! $0 == *"ConsolePi" ]] && [[ $0 == *"src/consolepi-addrelay.sh"* ]] ; then
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
