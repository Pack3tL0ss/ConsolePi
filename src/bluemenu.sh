#!/usr/bin/env bash

## this_usb=$( this=$(ls -l /sys/bus/usb-serial/devices | tail -n +2 ) && echo ${this##*/} )
tty_list=(/sys/bus/usb-serial/devices/*)
baud=9600

menu() {
		echo ' This program uses screen be sure you know the'
		echo ' command sequences.  The most common are:'
		echo ' alt+c (release) d Enter -> detach but leave session alive'
		echo ' alt+c (release) k Enter -> kill'
		echo " use command 'screen -r' to reattach to a previously detached screen"
		echo ''
        echo -e '\n\n--ConsolePi Bluetooth Connections--'
        echo '#################################'
        echo '##  ConsolePi Connection MENU  ##'
        echo '#################################'
        echo ''
		item=1
		for this_tty in ${tty_list[@]}; do 
        echo "${item} Connect to ${this_tty##*/} Using default settings"
		((item++))
		done

        echo "c. Change Default baud rate [${baud} 8N1]"
        echo 'x. exit'
        echo ''
        read -p "Select menu item: " selection
}

baud_menu() {
        echo -e '\n\n--WadeLab Linux Mounting Script--'
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
	

do_verify_selection(){
valid_selection=false
while ! $valid_selection; do
    valid_selection=true
    if (( $selection > 0 )) && (( $selection < 20 )); then
		selected_dev="${tty_list[$((selection - 1))]##*/}"
		screen "/dev/${tty_list[$((selection - 1))]##*/}" $baud

    elif [[ ${selection,,} == "c" ]]; then
        valid_selection=false # force re-print of menu
		do_change_baud
		menu
		
    elif [[ ${selection,,} == "x" ]]; then
        exit 0
		
    else
        valid_selection=false
        echo -e "\nInvalid Selection Try Again\n\n"
        menu
    fi
done
}

main() {
		[[ -z $(screen -v) ]] && echo "this program requires screen, install screen 'sudo apt-get install screen' ... exiting" && exit 1
		clear
        menu
        do_verify_selection
}

main