#!/usr/bin/env bash

# Dynamic Console Menu
# Creates menu items only for USB to serial adapters that are plugged in
## this_usb=$( this=$(ls -l /sys/bus/usb-serial/devices | tail -n +2 ) && echo ${this##*/} )
tty_list=(/sys/bus/usb-serial/devices/*)
[[ ${tty_list[0]} == '/sys/bus/usb-serial/devices/*' ]] && tty_list=
baud=9600
flow="n"
parity="n"
dbits=8

do_get_tty_name() {
        tty_name=$(ls -l /dev |grep lrwx.*${this_tty##*/}.* |cut -d: -f2|awk '{print $2}')
        [[ -z tty_name ]] && tty_name=${this_tty##*/}
}

do_flow_pretty() {
        case $flow in
            "x")
             flow_pretty="Xon/Xoff"
             ;;
             "h")
             flow_pretty="RTS/CTS"
             ;;
             "n")
             flow_pretty="None"
             ;;
             *)
             flow_pretty="Undefined"
             ;;
         esac
}


flow_menu() {
    do_flow_pretty
	valid_selection=false
        while ! $valid_selection; do
	valid_selection=true        
        echo '###################################'
        echo '##  Select desired flow control  ##'
        echo '###################################'
        echo ''
        echo '1. Xon/Xoff (software)'
        echo '2. RTS/CTS (hardware)'
        echo '3. No Flow Control (default)'
        echo "x. exit - flow will remain: ${flow_pretty}"
        echo ''
        read -p "Select menu item: " selection
        case $selection in
            "1")
             flow="x"
             ;;
             "2")
             flow="h"
             ;;
             "3")
             flow="n"
             ;;
             "x")
             ;;
             *)
             valid_selection=false
             ;;
        esac
    done
}

do_parity_pretty() {
        case $parity in
            "o")
             parity_pretty="odd"
             parity_up="O"
             ;;
             "e")
             parity_pretty="even"
             parity_up="E"
             ;;
             "n")
             parity_pretty="none"
             parity_up="N"
             ;;
             *)
             parity_pretty="Undefined"
             parity_up="ERR"
             ;;
         esac
}

parity_menu() {
	do_parity_pretty
        valid_input=false
        while ! $valid_input; do
        valid_input=true
        echo '##############################'
        echo '##  Select desired parity   ##'
        echo '##############################'
        echo ''
        echo '1. odd'
        echo '2. even'
        echo '3. No Parity (default)'
        echo "x. exit - parity will remain: ${parity_pretty}"
        echo ''
        read -p "Select menu item: " selection
        case $selection in
            "1")
             parity="o"
             ;;
             "2")
             parity="e"
             ;;
             "3")
             parity="n"
             ;;
             "x")
             ;;
             *)
             valid_input=false
         esac
    done
}

databits_menu() {
        echo '#################################'
        echo '##  Select desired data bits   ##'
        echo '#################################'
        echo ''
        echo 'Enter the number of data bits'
        echo 'Default 8, Valid range 5-8'
        echo ''
        echo "x. exit - data bits will remain: ${dbits}"
        echo ''
	valid_input=false
	while ! $valid_input; do
            read -p "Enter number of data bits: " selection
            if [[ $selection > 4 ]] && [[ $selection < 9 ]]; then
                dbits=$selection
                valid_input=true
            elif [[ ${selection,,} == "x" ]]; then
                valid_input=true                
            else
                echo -e  '\n!!Invalid Selection!!\n'
            fi
        done
}
    
baud_menu() {
        echo '#################################'
        echo '##  Select desired baud rate.  ##'
        echo '#################################'
        echo ''
        echo '1. 300'
        echo '2. 1200'
        echo '3. 9600 (default)'
        echo '4. 19200'
        echo '5. 57600'            
        echo '6. 115200'
        echo '7. custom'
        echo "x. exit - baud will remain ${baud}"
        echo ''
        read -p "Select menu item: " selection
}

port_config_menu() {
valid_input_pcm=false
while ! $valid_input_pcm; do
do_parity_pretty
do_flow_pretty
        echo '#################################'
        echo '##  Serial Port Configuration  ##'
        echo '#################################'
        echo ''
        echo "1. Change baud (${baud})"
        echo "2. Change Data Bits (${dbits})"
        echo "3. Change Parity (${parity_pretty})"
        echo "4. Change Flow Control (${flow_pretty})"
        echo "x. exit [${baud} ${dbits}${parity_up}1 flow: ${flow_pretty}]"
        echo ''
        read -p "Select menu item: " selection

# Re-Print menu until exit
case $selection in
    "1")
     do_change_baud
     ;;
     "2")
     databits_menu
     ;;
     "3")
     parity_menu
     ;;
     "4")
     flow_menu
     ;;
     "x")
     valid_input_pcm=true
     ;;
     *)
      echo -e  '\n!!Invalid Selection!!\n'
     ;;
esac
done
}

do_change_baud() {
	baud_valid=false
	baud_list=(300 1200 9600 19200 57600 115200 0)
	while ! $baud_valid; do
		baud_menu
		if (( ! $selection == "x" )) && (( $selection > 0 )) && (( $selection < 7 )); then
			baud=${baud_list[ (($selection-1)) ]}
			baud_valid=true
		elif (( $selection == 7 )); then
			read -p "Input baud rate" baud
			baud_valid=true
		elif (( $selection == "x" )); then
			baud_valid=true
		else
			echo -e "\nInvalid Selection Try Again\n\n"
		fi
	done
}
	

main_menu() {
    clear
    valid_selection=false
    while ! $valid_selection; do

    do_flow_pretty
    do_parity_pretty
	echo '########################################################################'
	echo '##                    ConsolePi Connection MENU                       ##'
	echo ''
	echo ' This program will launch serial session via picocom'
	echo ' Be Aware of The following command sequences:'
	echo ''
	echo '   ctrl+a followed by ctrl+x Exit session - reset the port'
	echo '   ctrl+a followed by ctrl+q Exit session - without resetting the port'
	echo '   ctrl+a followed by ctrl+u increase baud'
	echo '   ctrl+a followed by ctrl+d decrease baud'
	echo '   ctrl+a followed by ctrl+f cycle through flow control options'
	echo '   ctrl+a followed by ctrl+y cycle through parity options'
	echo '   ctrl+a followed by ctrl+b cycle through data bits'
	echo '   ctrl+a followed by ctrl+v Show configured port options'
	echo '   ctrl+a followed by ctrl+c toggle local echo'
	echo ''
	echo " Use command 'consolepi-menu' to display this menu after exit"
	echo ''
	echo '##                                                                    ##'
        echo '########################################################################'
        echo ''
		item=1
		for this_tty in ${tty_list[@]}; do 
        do_get_tty_name    
        echo "${item}. Connect to ${tty_name} Using default settings"
		((item++))
		done

        echo "c. Change Connection Settings [${baud} ${dbits}${parity_up}1 flow: ${flow_pretty}]"
        echo 'x. exit to shell'
        echo ''
        read -p "Select menu item: " selection

    #if selection not defined or selection is non-printable cntrl char set to zero to fail through without error
    ( [[ -z $selection ]] || [[ $selection =~ [[:cntrl:]] ]] ) && selection=0
    if (( $selection > 0 )) && (( $selection < $((${#tty_list[@]}+1)) )); then
	this_tty="${tty_list[$((selection - 1))]}"
        do_get_tty_name
	# screen "/dev/${tty_list[$((selection - 1))]##*/}" $baud
	picocom "/dev/${tty_name}" -b $baud
    elif [[ ${selection,,} == "c" ]]; then
        valid_selection=false # force re-print of menu
	port_config_menu
    elif [[ ${selection,,} == "x" ]]; then
        valid_selection=true
        exit 0
    else
        valid_selection=false
        echo -e "\nInvalid Selection Try Again\n\n"
    fi
done
}

main() {
	[[ -z $tty_list ]] && echo "No USB to Serial adapters found... exiting" && exit 1
	[[ -z $(picocom --help | head -1) ]] && echo "this program requires picocom, install picocom 'sudo apt-get install picocom' ... exiting" && exit 1
        main_menu
}

main
