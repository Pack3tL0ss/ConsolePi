#!/usr/bin/env bash

# Dynamic Console Menu
# Creates menu items only for USB to serial adapters that are plugged in

# -- Defaults --
baud=9600
flow="n"
parity="n"
dbits=8

cloud_file="/etc/ConsolePi/cloud.json"
resize_bin="/etc/ConsolePi/src/consolepi-commands/resize"
WORD="default"
# . /etc/ConsolePi/ConsolePi.conf
# This menu is now only used for bluetooth connections and limited only to local connections
# it can also be launched as an alternative to the normal menu with `consolepi-menu sh` (just pass the parameter 'sh' to the consolepi-menu command)

# if connecting to ConsolePis using Clustering it's expected there would be a network to connect to
cloud=false

# -- Get List of all ttyUSB_ devices currently connected --
get_tty_devices() {
    tty_list=($(ls -lhF /dev/serial/by-id/ 2>/dev/null| grep ^l | cut -d'>' -f2|awk -F'/' '{print $3}'))
    tty_list=($(ls -lhF /dev/serial/by-id/ 2>/dev/null| grep ^l | cut -d'>' -f2))
}

# -- If ttyUSB device has defined alias, Display the alias in menu --
get_tty_name() {
    tty_name=$(ls -l /dev |grep ^lrwx.*${this_tty##*/}$ |cut -d: -f2|awk '{print $2}')
    [[ -z $tty_name ]] && tty_name=${this_tty##*/} ||
        tty_name="${tty_name} (${this_tty##*/})"

}

# Depricated. Remote Device and power support available via consolepi-menu command
get_remote_devices() {
    if [[ -f $cloud_file ]]; then
        unset rem_cmd_list
        prev_host="init"
        while IFS=, read rem_host rem_ip rem_user rem_dev rem_port
        do
            if [ ! $rem_host == '' ]; then
                [[ ! $prev_host == $rem_host ]] && echo " -- REMOTE CONNECTIONS (${rem_host}) --"
                echo "${item}. Connect to ${rem_dev##*/} on ${rem_host} Using $WORD settings"
                rem_cmd_list+=("ssh -t ${rem_user}@${rem_ip} picocom '${rem_dev}'")
                prev_host=$rem_host
                ((item++))
            fi
        done <"$cloud_file"
        echo " -- "
    fi
}

# -- Pretty Display text for flow control selection --
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

# -- Flow Control Selection Menu --
flow_menu() {
    do_flow_pretty
    valid_selection=false
    while ! $valid_selection; do
        valid_selection=true
        echo ' ======================================================='
        echo '  -----------  Select Desired Flow Control  ----------- '
        echo ' ======================================================='
        echo
        echo ' 1. Xon/Xoff (software)'
        echo ' 2. RTS/CTS (hardware)'
        echo ' 3. No Flow Control (default)'
        echo
        echo " b. Back - flow will remain: ${flow_pretty}"
        echo
        echo ' ======================================================='
        read -ep " Flow >> " selection
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
             "b")
             ;;
             *)
             valid_selection=false
             ;;
        esac
    done
}

# -- Pretty Display text for Parity selection --
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

# -- Parity selection menu --
parity_menu() {
    do_parity_pretty
    valid_input=false
    while ! $valid_input; do
        valid_input=true
        echo ' ======================================================='
        echo '  --------------  Select Desired Parity  -------------- '
        echo ' ======================================================='
        echo
        echo ' 1. odd'
        echo ' 2. even'
        echo ' 3. No Parity (default)'
        echo " b. Back - parity will remain: ${parity_pretty}"
        echo
        echo ' ======================================================='
        read -ep " Parity >> " selection
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
             "b")
             ;;
             *)
             valid_input=false
         esac
    done
}

# -- data-bits selection menu --
databits_menu() {
    echo ' ======================================================='
    echo '  -------------  Enter Desired Data Bits  ------------- '
    echo ' ======================================================='
    echo
    echo ' Enter the number of data bits'
    echo ' Default 8, Valid range 5-8'
    echo
    echo " b. Back - data bits will remain: ${dbits}"
    echo
    echo ' ======================================================='
    valid_input=false
    while ! $valid_input; do
        read -ep " Data Bits >> " selection
        if [[ $selection > 4 ]] && [[ $selection < 9 ]]; then
            dbits=$selection
            valid_input=true
        elif [[ ${selection,,} == "b" ]]; then
            valid_input=true
        else
            echo -e  "Invalid Selection '$selection' please try again."
        fi
    done
}

# -- baud rate selection menu --
baud_menu() {
    baud_valid=false
    baud_list=(300 1200 9600 19200 57600 115200 0)
    while ! $baud_valid; do
        echo ' ======================================================='
        echo '  ------------  Select Desired Baud Rate  ------------- '
        echo ' ======================================================='
		echo
		echo ' 1. 300'
		echo ' 2. 1200'
		echo ' 3. 9600 (default)'
		echo ' 4. 19200'
		echo ' 5. 57600'
		echo ' 6. 115200'
		echo ' 7. custom'
        echo
		echo " b. Back - baud will remain ${baud}"
		echo
        echo '======================================================='
		read -ep " Select Desired Baud Rate >>" selection

        if (( ! $selection == "b" )) && (( $selection > 0 )) && (( $selection < 7 )); then
            baud=${baud_list[ (($selection-1)) ]}
            baud_valid=true
        elif (( $selection == 7 )); then
            read -ep "Input baud rate" baud
            baud_valid=true
        elif (( $selection == "b" )); then
            baud_valid=true
        else
            echo -e  "Invalid Selection '$selection' please try again."
        fi

    done
}

# -- main port configuration menu --
port_config_menu() {
    valid_input_pcm=false
    while ! $valid_input_pcm; do
        do_parity_pretty
        do_flow_pretty
        echo ' ======================================================='
        echo '  ------------  Connection Settings Menu  ------------- '
        echo ' ======================================================='
        echo
        echo " 1. Change baud [${baud}]"
        echo " 2. Change Data Bits [${dbits}]"
        echo " 3. Change Parity [${parity_pretty}]"
        echo " 4. Change Flow Control [${flow_pretty}]"
        [[ $parity == "n" ]] && parity_txt="N" || parity_txt="-${parity_pretty}-"
        echo
        echo " b. Back [${baud} ${dbits}${parity_txt}1 flow: ${flow_pretty}]"
        echo
        echo ' ======================================================='
        read -ep " >> " selection

        # Re-Print menu until exit
        case $selection in
            "1")
             baud_menu
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
             "b")
             valid_input_pcm=true
             ;;
             *)
              echo -e  "Invalid Selection '$selection' please try again."
             ;;
        esac
    done
}

# -- Extract remote variables from line --
get_rem_vars() {
    rem_host=`echo $this_rem_tty | awk -F' ' '{print $1}'`
    rem_ip=`echo $this_rem_tty | awk -F' ' '{print $2}'`
    rem_user=`echo $this_rem_tty | awk -F' ' '{print $3}'`
    rem_alias=`echo $this_rem_tty | awk -F' ' '{print $4}'`
    # rem_port=`echo $this_rem_tty | awk -F' ' '{print $5}'`
}

# -- picocom help --
picocom_help() {
    echo '----------------------------  Picocom Help  ----------------------------'
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
    echo '------------------------------------------------------------------------'
    echo ''
    read -p "Press enter to Continue "
    clear
}
# -- ConsolePi Main Menu --
main_menu() {
    valid_selection=false
    while ! $valid_selection; do
        clear && [ -f "$resize_bin" ] && $resize_bin >/dev/null
        do_flow_pretty
        do_parity_pretty
        echo ' ===================================================================='
        echo '  --------------------- ConsolePi Serial Menu ----------------------'
        echo ' ===================================================================='
        # Loop through Connected USB-Serial adapters creating menu option for each found
        item=1
        # echo " -- LOCAL CONNECTIONS --"
        echo ''
        for this_tty in ${tty_list[@]}; do
            get_tty_name    # checks for alias created via udev rules and uses alias as a descriptor if exists
            [[ $item -lt 10 ]] && spc="  " || spc=" "
            echo " ${item}.${spc}${tty_name}"
            ((item++))
        done

        # Build Menu items for remote devices updated from GDrive
        # get_remote_devices  # Disabled this is now only used for bluetooth user
        echo
        echo " c. Change Connection Settings [${baud} ${dbits}${parity_txt}1 flow: ${flow_pretty}]"
        echo ' r. refresh - detect connected serial adapters'
        $cloud && echo 'g. refresh - detect connected serial adapters + Update Connections to GDrive enabled ConsolePis'
        echo ' h. Display picocom help'
        echo ' x. exit to shell'
        echo
                echo ' ===================================================================='
        [[ $parity == "n" ]] && parity_txt="N" || parity_txt="-${parity_pretty}-"
        echo "  CURRENT CONNECTION SETTINGS: [${baud} ${dbits}${parity_txt}1 flow: ${flow_pretty}]"
        echo ' ===================================================================='
        read -ep " >> " selection

        #if selection not defined or selection is non-printable cntrl char set to zero to fail through without error
        ( [[ -z $selection ]] || [[ $selection =~ [[:cntrl:]] ]] ) && selection=0
        if (( $selection > 0 )) && (( $selection < $((${#tty_list[@]}+1)) )); then
            this_tty="${tty_list[$((selection - 1))]}"
            get_tty_name
            # depricated screen in favor of picocom
            ## screen "/dev/${tty_list[$((selection - 1))]##*/}" $baud
            # -- Always use native dev (ttyUSB#) --
            picocom "/dev/${tty_list[$((selection - 1))]##*/}" --baud $baud --flow $flow --databits $dbits --parity $parity
        elif (( $selection > 0 )) && (( $selection < $((${#tty_list[@]}+${#rem_cmd_list[@]}+1)) )); then
            exec="${rem_cmd_list[$((selection-${#tty_list[@]}-1))]} -b $baud -f $flow -d $dbits -y $parity"
            $exec
        elif [[ ${selection,,} == "c" ]]; then
            WORD="configured"
            port_config_menu
            valid_selection=false # force re-print of menu
        elif [[ ${selection,,} == "r" ]]; then
            get_tty_devices
        elif $cloud && [[ ${selection,,} == "g" ]]; then
            get_tty_devices
            sudo /etc/ConsolePi/cloud/gdrive/gdrive.py
        elif [[ ${selection,,} == "h" ]]; then
            picocom_help
        elif [[ ${selection,,} == "x" ]]; then
            valid_selection=true
            echo -e "\n*******************************"
            echo ''
            exit_script
        else
            echo -e  "Invalid Selection '$selection' please try again."
        fi
    done
}

exit_script() {
    if [ $(who | tail -1 | awk '{print $1}') = "blue" ]; then
        echo -e "exiting to shell"
        echo ''
        echo -e "The blue user used in this shell"
        echo -e "has limited permissions"
        echo ''
        echo -e "'su consolepi -l' to gain typical"
        echo -e " rights."
        echo ''
        echo -e "*******************************\n"
    else
        echo -e "exiting to shell\n"
        echo -e "*******************************\n"
    fi
    exit 0
}

main() {
    get_tty_devices
    if [[ $tty_list ]]; then # || [ -f $cloud_file ]; # then (disabling cloud local only for blue user)
	    ttyusb_connected=true
	else
	    echo -e "\n*******************************\n"
		echo -e "No USB to Serial adapters found"
		echo -e "No Need to display Console Menu"
		echo -e " 'consolepi-menu' to re-launch "
		# echo -e "*******************************\n"
		ttyusb_connected=false
	fi
    [[ $(picocom --help 2>>/dev/null | head -1) ]] && dep_installed=true ||
	    ( echo "this program requires picocom, install picocom 'sudo apt-get install picocom' ... exiting" && dep_installed=false )
    $ttyusb_connected && $dep_installed && main_menu || exit_script
}

# __main__
# [ $iam ] && echo $iam || echo Undefined
main
