#!/usr/bin/env bash

# --                                               ConsolePi Image Creation Script - Use at own Risk
# --
# --  Author: Pack3tL0ss ~ Wade Wells
# --    !!! USE @ own risk - This is an imaging script as with any imaging script if you select the wrong image... not so good !!!
# --
# --  This is a script I used to expedite testing.  It looks for a raspios-lite image file in whatever directory you run the script from, if it doesn't find one
# --  it downloads the latest image.  It will attempt to determine which drive is the micro-sd card (looks for usb to micro-sd adapter then sd to micro-sd) then flashes
# --  the raspios-lite image to the micro-sd.
# --
# --  This script is an optional tool, provided just because I had it/used it for testing.  It simply automates the burning of the image to the sd-card and provides
# --    a mechanism to pre-configure a number of items and place whatever additional files you might want on the image.
# --
# --  You do get the opportunity to review fdisk -l to ensure it's the correct drive, and you can override the drive the script selects.  Obviously if you
# --  were to select the wrong drive, you would wipe out anything on that drive.  So don't do that.  I did add a validation check which detect if the drive contains
# --  a partition with the boot flag in fdisk
# --
# --  To further expedite testing this script will look for a consolepi-stage subdir and if found it will copy the entire directory and any subdirs to /home/pi/consolepi-stage
# --  This script also searches the script dir (the dir this script is ran from) for the following which are copied to the /home/pi directory on the ConsolePi image if found.
# --    ConsolePi.conf, ConsolePi.ovpn, ovpn_credentials *.dtbo
# --
# --    The install script (not this one this is the image creator) looks for these files in the home dir of whatever user your logged in with and in 'consolepi-stage' subdir.
# --      If found it will pull them in.  If the installer finds ConsolePi.conf it uses those values as the defaults allowing you to bypass the data entry (after confirmation).
# --    The OpenVPN related files are moved (by the installer) to the openvpn/client folder.
# --      The installer only provides example ovpn files as the specifics would be dependent on how your openvpn server is configured
# --
# --  To aid in headless installation this script will enable SSH and can configure a wlan_ssid.  With those options on first boot the raspberry pi will connect to
# --  the SSID, so all you need to do is determine the IP address assigned and initiate an SSH session.
# --    To enable the pre-configuration of an SSID, either configure the parameters below with values appropriate for your system *or* provide a valid wpa_supplicant.conf
# --    file in either the script dir or consolepi-stage subdir.  EAP-TLS can also be pre-configured, just define it in wpa_supplicant.conf and provide the certs
# --    referenced in the wpa_supplicant.conf in the script dir a 'cert' subdir or 'consolepi-stage/cert' subdir.
# --    This script will copy wpa_supplicant.conf and any certs if defined and found to the appropriate dirs so ConsolePi can use those settings on first boot.
# --
# --  The install script (again not this script) also handles a few other files, they just need to be provided in the consolepi-stage subdir
# --    This includes:
# --      - 10-ConsolePi.rules: udev rules file mapping specific serial adapters to specific telnet ports
# --      - ConsolePi_init.sh: Custom post-install script, the installer will run this script at the end of the process, it can be used to automate any additional tweaks
# --          you might want to make.  i.e. copy additional custom scripts you like to have on hand from the consolepi-stage dir to wherever you want them.
# --      - authorized_keys: imported for both pi and root user (for now)
# --      - rpi-poe-overlay.dts: Used to adjust thresholds for when and how fast the fan will kick on (PoE hat). Install script will create the dtbo overlay based on this dts.
# --
# --  Lastly this script also configures one of the consolepi quick commands: 'consolepi-install'. This command
# --  is the same as the single command install command on the github.  btw the 'consolepi-install' command is changed to 'consolepi-upgrade' during the install.
# --
# --  This script should be ran on a Linux system, tested on raspios (a different Raspberry pi), and Linux mint, should work on most Linux distros certailny Debain/Ubuntu based
# --  To use this script enter command:
# --    'curl -JLO https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/ConsolePi_image_creator.sh  && sudo chmod +x ConsolePi_image_creator.sh'
# --  Enter a micro-sd card using a usb to micro-sd card adapter (script only works with usb to micro-sd adapters)
# --  'sudo ./ConsolePi_image_creator.sh' When you are ready to flash the image

# -------------------------------- // CONFIGURATION \\ ---------------------------------
# configuration has moved out of the script itself and into consolepi-image-creator.conf
# alternatively all variables available in consolepi-image-creator.conf can be provided
# via cmd line argumetns in the form --variable=value
# --------------------------------------------------------------------------------------


# Terminal coloring
_norm='\e[0m'
_bold='\e[32;1m' #bold green
_blink='\e[5m'
_red='\e[31m'
_blue='\e[34m'
_lred='\e[91m'
_yellow='\e[33;1m'
_green='\e[32m'
_cyan='\e[96m' # technically light cyan
_excl="${_red}${_blink}"'!!!!'"${_norm}"

do_defaults() {
    # ----------------------------------- // DEFAULTS \\ -----------------------------------
    # applied if no config file is found and value not set via cmd line arg
    SSID=${ssid} # psk ssid not configured if ssid not provided
    PSK=${psk}
    WLAN_COUNTRY=${wlan_country:-"US"}
    PRIORITY=${priority:-0}
    IMG_TYPE=${img_type:-'lite'}
    IMG_ONLY=${img_only:-false}
    AUTO_INSTALL=${auto_install:-true}
    CP_ONLY=${cp_only:-false}
    # -- these skip prompts and perform the actions based on the value provided
    # if not set user is prompted (Default is Not set)
    MASS_IMPORT=${mass_import}
    EDIT=${edit}
    HOTSPOT_HOSTNAME=${hotspot_hostname}
    # ---------------------------------------------------------------------------------------
    nodd=${nodd:-false}  # development option set by -nodd flag
    STAGE_DIR='consolepi-stage'
    IMG_HOME="/mnt/usb2/home/pi"
    IMG_STAGE="$IMG_HOME/$STAGE_DIR"
    LOCAL_DEV=${local_dev:-false} # dev use only
    DEBUG=${debug:-false} # dev use only
    ( [ ! -z "$SSID" ] && [ ! -z "$PSK" ] ) &&
        CONFIGURE_WPA_SUPPLICANT=true ||
        CONFIGURE_WPA_SUPPLICANT=false
    CUR_DIR=$(pwd)
    PI_UGID=  # set in main after mount of root partition
    [ -d $STAGE_DIR ] && STAGE=true || STAGE=false
    [ -d /etc/ConsolePi ] && ISCPI=true || ISCPI=false
    WPA_CONF=$STAGE_DIR/wpa_supplicant.conf
    MY_HOME=$(grep "^${SUDO_USER}:" /etc/passwd | cut -d: -f6)
    STAGE_FILES=(STAGE:/etc/ConsolePi/ConsolePi.yaml
                /etc/wpa_supplicant/wpa_supplicant.conf
                STAGE:/etc/udev/rules.d/10-ConsolePi.rules
                STAGE:/etc/ser2net.conf
                $MY_HOME/.ssh/authorized_keys
                $MY_HOME/.ssh/known_hosts
                STAGE:/etc/ConsolePi/cloud/gdrive/.credentials/credentials.json
                STAGE:/etc/ConsolePi/cloud/gdrive/.credentials/token.pickle
                STAGE:/etc/openvpn/client/ConsolePi.ovpn
                STAGE:/etc/openvpn/client/ovpn_credentials
    )
}

header() {
    [ "$1" == '-c' ] && clear
    echo -e "${_cyan}   ______                       __    ${_lred} ____  _ "
    echo -e "${_cyan}  / ____/___  ____  _________  / /__  ${_lred}/ __ \(_)"
    echo -e "${_cyan} / /   / __ \/ __ \/ ___/ __ \/ / _ \\\\${_lred}/ /_/ / / "
    echo -e "${_cyan}/ /___/ /_/ / / / (__  ) /_/ / /  __${_lred}/ ____/ /  "
    echo -e "${_cyan}\____/\____/_/ /_/____/\____/_/\___${_lred}/_/   /_/   "
    echo -e "${_blue}  https://github.com/Pack3tL0ss/ConsolePi${_norm}"
    echo -e ""
}

dots() {
    local pad=$(printf "%0.1s" "."{1..70})
    printf " ~ %s%*.*s" "$1" 0 $((70-${#1})) "$pad"
    return 0
}

do_error() {
    local status=$1
    if [[ $status != 0 ]]; then
        red 'Failed!!'  # ; echo -e "\n"
        # echo "$2" # optional additional error details
        [ ! -z "$2" ] && echo -e "   --\n   $(red '!!') $2\n   --\n" # optional additional error details
        exit 1
    else
        green "OK"
    fi
}

green() {
    echo -e "${_green}${*}${_norm}"
}

bold() { # bold green
    echo -e "${_bold}${*}${_norm}"
}

cyan() {
    echo -e "${_cyan}${*}${_norm}"
}

red() {
    echo -e "${_lred}${*}${_norm}"
}

# Function to collect user input
get_input() {
    [ ! -z "$1" ] && prompt="$1"
    valid_input=false
    while ! $valid_input; do
        read -ep "${prompt} (y/n|exit): " input
        case ${input,,} in
            'y'|'yes')
            input=true
            valid_input=true
            ;;
            'n'|'no')
            input=false
            valid_input=true
            ;;
            'exit')
            echo 'Exiting Script based on user input'
            exit 1
            ;;
            *)
            valid_input=false
            echo -e '\n\n!!! Invalid Input !!!\n\n'
            ;;
        esac
    done
    unset prompt
    # return input (input is set globally)
}

do_user_dir_import(){
    [[ $1 == root ]] && local user_home=root || local user_home="home/$1"
    # -- Copy Prep pre-staged files if they exist (stage-dir/home/<username>) for newly created user.
    if [[ -d "$STAGE_DIR/$user_home" ]]; then
        dots "Found staged files for $1, cp to ${1}'s home on image"
        res=$(
            chown -R $(grep "^$1:" /mnt/usb2/etc/passwd | cut -d: -f3-4) "$STAGE_DIR/$user_home" 2>&1 &&
            cp -r "$STAGE_DIR/$user_home/." "/mnt/usb2/$user_home/" 2>&1
            ) &&
                ( do_error $? && return 0 ) || ( do_error $? "$res" && return 1 )
    fi
}

show_disk_details() {
    echo -e "------------------------------- // Device Details for $(green "$my_usb") \\\\\ -----------------------------------"
    echo
    fdisk -l | sed -n "/Disk \/dev\/${my_usb}:/,/Disk \/${my_usb}\//p"
    echo
    echo -e "------------------------------------------------------------------------------------------------"
}

do_unzip() {
    if [ -f "$1" ]; then
        dots "Extracting image from $1"
        unzip $1 >/dev/null >/dev/null
        img_file=$(ls -1 "${1%zip}img" 2>/dev/null)
        [ ! -z "$img_file" ] ; do_error $? 'Something went wrong img file not found after unzip... exiting'
    else
        echo Error "$1" 'not found.  Bad File passed to do_unzip? Exiting.'
    fi
}

# -- Check for ConsolePi.yaml collect info if not found --
do_import_configs() {
    # -- pre-stage Staging Dir on image if found --
    if $STAGE; then
        # -- repoint dst staging dir to __consolepi-stage if -cponly in use dev option to prevent
        #    installer import but still have the files pre-loaded on the image.
        if $CP_ONLY; then
            # remove existing dir on img when do repeated testing of this script
            [ -d "$IMG_HOME/__$STAGE_DIR" ] && rm -r "$IMG_HOME/__$STAGE_DIR"
            dots "-cponly flag set using __consolepi-stage as dest on image"
            # res=$(mv $IMG_STAGE $IMG_HOME/__$STAGE_DIR 2>&1) ; do_error $? "$res"
            IMG_STAGE="$IMG_HOME/__$STAGE_DIR" ; do_error $?
        fi
        # DO NOT USE $IMG_HOME/$STAGE_DIR beyond this point, use $IMG_STAGE

        dots "$STAGE_DIR dir found Pre-Staging all files"
        # mkdir -p $IMG_STAGE ; rc=$?
        cp -r $STAGE_DIR/. $IMG_STAGE/ ; ((rc+=$?))
        chown -R $PI_UGID $IMG_STAGE/ ; do_error $((rc+=$?))

        # -- import authorized keys for the pi and root users on image if found --
        if [[ -f $IMG_STAGE/authorized_keys ]]; then
            dots "SSH authorized keys found pre-staging"
            mkdir -p $IMG_HOME/.ssh ; rc=$?
            mkdir -p /mnt/usb2/root/.ssh ; ((rc+=$?))
            cp ${CUR_DIR}/$STAGE_DIR/authorized_keys $IMG_HOME/.ssh/ ; ((rc+=$?))
            cp ${CUR_DIR}/$STAGE_DIR/authorized_keys /mnt/usb2/root/.ssh/ ; do_error $((rc+=$?))
        fi

        # -- import SSH known hosts on image if found --
        if [[ -f $IMG_STAGE/known_hosts ]]; then
            dots "SSH known_hosts found pre-staging"
            mkdir -p $IMG_HOME/.ssh ; rc=$?
            mkdir -p /mnt/usb2/root/.ssh ; ((rc+=$?))
            cp ${CUR_DIR}/$STAGE_DIR/known_hosts $IMG_HOME/.ssh/ ; ((rc+=$?))
            cp ${CUR_DIR}/$STAGE_DIR/known_hosts /mnt/usb2/root/.ssh/ ; do_error $((rc+=$?))
        fi

        do_user_dir_import root
        do_user_dir_import pi

        # -- adjust perms in .ssh directory if created imported --
        if [[ -d $IMG_HOME/.ssh ]]; then
            dots "Set Ownership of $IMG_HOME/.ssh"
            uid_gid=$(grep "^pi:" /mnt/usb2/etc/passwd | cut -d':' -f3-4) ; ((rc+=$?))
            chown -R $uid_gid $IMG_HOME/.ssh ; do_error $((rc+=$?))
        fi
    fi

    # pre-stage wpa_supplicant.conf on image if found in stage dir
    # if EAP-TLS SSID is configured in wpa_supplicant extract EAP-TLS cert details and cp certs (not a loop only good to pre-configure 1)
    #   certs should be in script dir or 'cert' subdir cert_names are extracted from the wpa_supplicant.conf file found in script dir
    # NOTE: Currently the cert parsing will only work if you are using double quotes in wpa_supplicant.conf ~ client_cert="/etc/cert/ConsolePi-dev.pem"
    if [ -f $WPA_CONF ]; then
        dots "wpa_supplicant.conf found pre-staging on image"
        cp $WPA_CONF /mnt/usb2/etc/wpa_supplicant  ; rc=$?
        chown root /mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf ; ((rc+=$?))
        chgrp root /mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf ; ((rc+=$?))
        chmod 644 /mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf ; do_error $((rc+=$?))
        client_cert=$(grep client_cert= $WPA_CONF | cut -d'"' -f2| cut -d'"' -f1)
        # client_cert=$(grep client_cert= $WPA_CONF | cut -d'=' -f2);
        #     client_cert=$(echo ${y//\"/}); client_cert=$(echo ${y//\'/})
        if [[ ! -z $client_cert ]]; then
            dots "staged wpa_supplicant includes EAP-TLS SSID looking for certs"
            cert_path="/mnt/usb2"${client_cert%/*}
            ca_cert=$(grep ca_cert= $WPA_CONF | cut -d'"' -f2| cut -d'"' -f1)
            private_key=$(grep private_key= $WPA_CONF | cut -d'"' -f2| cut -d'"' -f1)
            if [ -d $STAGE_DIR/cert ]; then
                pushd $STAGE_DIR/cert/ >/dev/null
                mkdir -p $cert_path ; rc=$?
                [[ -f ${client_cert##*/} ]] && cp ${client_cert##*/} "${cert_path}/${client_cert##*/}" ; ((rc+=$?))
                [[ -f ${ca_cert##*/} ]] && cp ${ca_cert##*/} "${cert_path}/${ca_cert##*/}" ; ((rc+=$?))
                [[ -f ${private_key##*/} ]] && cp ${private_key##*/} "${cert_path}/${private_key##*/}" ; do_error $((rc+=$?))
                popd >/dev/null
            else
                echo "WARNING"; echo -e "\tEAP-TLS is defined, but no certs found for import"
            fi
        fi
    fi

    # -- If image being created from a ConsolePi offer to import settings --
    if $ISCPI; then
        # header -c
        if [ -z "$MASS_IMPORT" ]; then
            echo -e "\n-----------------------  $(green 'This is a ConsolePi') -----------------------\n"
            echo -e "You can mass import settings from this ConsolePi onto the new image."
            echo -e "The following files will be evaluated:\n"
            for f in "${STAGE_FILES[@]}"; do echo -e "\t${f//STAGE:/}" ; done
            echo -e "\nAny files already staged via $STAGE_DIR will be skipped"
            echo -e "Any files not found on this ConsolePi will by skipped\n"
            echo '--------------------------------------------------------------------'
            get_input "Perform mass import"
            MASS_IMPORT=$input
        fi

        if $MASS_IMPORT; then
            if [[ ! -d $IMG_STAGE ]]; then
                dots "Create stage dir on image"
                mkdir -p $IMG_STAGE ; rc=$?
                chown -R $PI_UGID $IMG_STAGE/ ; do_error $((rc+=$?))
                do_error $rc
            fi

            cyan "\n   -- Performing Imports from This ConsolePi --"
            for f in "${STAGE_FILES[@]}"; do
                if [[ "$f" =~ ^"STAGE:" ]]; then
                    src="$(echo $f| cut -d: -f2)"
                    dst="$IMG_STAGE/$(basename $(echo $f| cut -d: -f2))"

                # -- Accomodate Files imported from users home on a ConsolePi for non pi user --
                elif [[ ! $f =~ "/home/pi" ]] && [[ $f =~ $MY_HOME ]]; then
                    src="$f"
                    # dst is in the stage dir for non pi/root users.  After user creation installer will look for files in the stage dir
                    dst="${IMG_STAGE}${f}"
                else
                    src="$f"
                    dst="/mnt/usb2${f}"
                fi

                dots "$src"
                if [ -f "$src" ] && [ ! -f "$dst" ]; then
                    if res=$(
                        mkdir -p $(dirname "$dst") &&
                        cp "$src" "$dst" 2>&1 &&
                            (
                                if [[ $(stat -c %u "$(dirname $src)") != 0 ]]; then
                                    local this_ugid=$(grep "^$(stat -c %U $(dirname $src)):" /etc/passwd | cut -d: -f3-4) &&
                                    [[ ! -z $this_ugid ]] && chown -R $this_ugid $(dirname $dst)
                                elif [[ $(stat -c %u "$src") != 0 ]]; then
                                    local this_ugid=$(grep "^$(stat -c %U $src):" /etc/passwd | cut -d: -f3-4) &&
                                    [[ ! -z $this_ugid ]] && chown $this_ugid $dst
                                fi
                            )
                        ); then
                        echo "Imported"
                    else
                        echo ERROR
                        echo -e "  --\n  $res\n  --"
                    fi
                else
                    if [ ! -f "$src" ]; then
                        echo "Skipped - File Not Found"
                    elif [ -f "$dst" ]; then
                        echo "Skipped - Already Staged"
                    fi
                fi
            done
            [ -f $IMG_STAGE/credentials.json ] && ( mkdir -p $IMG_STAGE/.credentials >/dev/null ; rc=$? ) || rc=0
            [ -f $IMG_STAGE/credentials.json ] && mv $IMG_STAGE/credentials.json $IMG_STAGE/.credentials ; ((rc+=$?))
            [ -f $IMG_STAGE/token.pickle ] && mv $IMG_STAGE/token.pickle $IMG_STAGE/.credentials ; ((rc+=$?))
            [[ "$rc" > 0 ]] && logit "Error Returned moving cloud creds into $STAGE_DIR/.credentials directory"

        # We still prompt for ConsolePi.yaml even if not doing mass_import
        elif [ ! -f $STAGE_DIR/ConsolePi.yaml ] && [ -f /etc/ConsolePi/ConsolePi.yaml ]; then
            echo
            get_input "Do you want to pre-stage configuration using the config from this ConsolePi (you will be given the chance to edit)"
            if $input; then
                sudo -u $SUDO_USER mkdir -p $IMG_STAGE/
                sudo -u $SUDO_USER cp /etc/ConsolePi/ConsolePi.yaml $IMG_STAGE/
            fi
        fi

    fi



    # prompt to modify staged config
    if [ -f $IMG_STAGE/ConsolePi.yaml ]; then
        if [ -z "$EDIT" ]; then
            echo
            get_input "Do you want to edit the pre-staged ConsolePi.yaml to change details"
            EDIT=$input
        fi
        $EDIT && nano -ET2 $IMG_STAGE/ConsolePi.yaml

        # -- offer to pre-configure hostname based on hotspot SSID in config
        cfg_ssid=$(grep '  wlan_ssid: ' $IMG_STAGE/ConsolePi.yaml | awk '{print $2}')
        if [ -z "$HOTSPOT_HOSTNAME" ]; then
            [[ ! -z $cfg_ssid ]] && prompt="Do you want to pre-stage the hostname as $cfg_ssid" && get_input
            [[ ! -z $cfg_ssid ]] && HOTSPOT_HOSTNAME=$input || HOTSPOT_HOSTNAME=false
        fi
        $HOTSPOT_HOSTNAME && echo $cfg_ssid > /mnt/usb2/etc/hostname
    fi
}

do_select_image() {
    args=("${@}")
    # echo "@ ${@}"
    # echo "args2 ${args[2]}"
    idx=1; for i in "${args[@]}"; do
        echo ${idx}. ${i}
        ((idx+=1))
    done
    echo
    valid_input=false
    while ! $valid_input; do
        read -ep "Select desired image (1-${#args[@]}|exit): " input
        if [[ "${input,,}" == "exit" ]]; then
            echo "Exiting based on user input" && exit 1
        else
            echo "${args[@]}" =~ "${args[((${input}-1))]}"
            if [[ "$input" =~ ^[0-9]+$ ]] && [[ ! -z "${args[((${input}-1))]}" ]]; then
                valid_input=true
            else
                echo -e "\t!! Invalid Input"
            fi
        fi
    done
    if [[ "${args[${input}]}" =~ ".zip" ]]; then
        do_unzip "${args[((${input}-1))]}" # do_unzip sets img_file
    else
        # echo "$input ${args[0]} ${args[1]} ${args[2]} ${args[3]} ${args[${input}]}"
        img_file="${args[((${input}-1))]}"
    fi
}

main() {
    header -c

    # if ! $CONFIGURE_WPA_SUPPLICANT && [[ ! -f "$STAGE_DIR/wpa_supplicant.conf" ]]; then
    #     echo "wlan configuration will not be applied to image, to apply WLAN configuration break out of the script"
    #     echo "and configure via consolepi-stage.conf or import file or command line args"
    # fi

    my_usb=($(ls -l /dev/disk/by-path/*usb* 2>/dev/null |grep -v part | sed 's/.*\(...\)/\1/'))
    # -- Exit now if more than 1 usb storage dev found
    if [[ ${#my_usb[@]} > 1 ]]; then
        echo -e "\nMore than 1 USB Storage Device Found, To use this script Only plug in the device you want to image.\n"
        exit 1
    else
        my_usb=${my_usb[0]}
    fi
    [[ $my_usb ]] && boot_list=($(sudo fdisk -l |grep -o '/dev/sd[a-z][0-9]  \*'| cut -d'/' -f3| awk '{print $1}'))
    [[ $boot_list =~ $my_usb ]] && my_usb=    # if usb device found make sure it's not marked as bootable if so reset my_usb so we can check for sd card adapter
    # basename $(mount | grep 'on / '|awk '{print $1}')
    [[ -z $my_usb ]] && my_usb=$( sudo fdisk -l | grep 'Disk /dev/mmcblk' | awk '{print $2}' | cut -d: -f1 | cut -d'/' -f3)

    ! $LOCAL_DEV && SCRIPT_TITLE=$(green "ConsolePi Image Creator") || SCRIPT_TITLE="${_green}ConsolePi Image Creator${_norm} ${_lred}${_blink}Local DEV${_norm}"
    echo -e "\n\n$SCRIPT_TITLE \n'exit' (which will terminate the script) is valid at all prompts\n"

    [[ $my_usb ]] && echo -e "Script has discovered removable flash device @ $(green "${my_usb}") with the following details\n" ||
        echo -e "Script failed to detect removable flash device, you will need to specify the device"

    show_disk_details ${my_usb}

    # -- check if detected media is mounted to / or /boot and exit if so This is a fail-safe Should not happen --
    if mount | grep "^.* on /\s.*\|^.* on /boot\s.*" | grep -q "/dev/${my_usb}[p]\{0,1\}1\|/dev/${my_usb}[p]\{0,1\}2"; then
        oh_shit=$(mount | grep "^.* on /\s.*\|^.* on /boot\s.*" | grep "/dev/${my_usb}[p]\{0,1\}1\|/dev/${my_usb}[p]\{0,1\}2")
        echo -e "${_excl}\t$(green ${my_usb}) $(red "Appears to be mounted as a critical system directory if this is a script flaw please report it.")\t${_excl}"
        echo -e "\t$(green ${my_usb}) mount: $oh_shit\n\tScript will now exit to prevent borking the running image."
        exit 1
    fi

    # Give user chance to change target drive
    echo -e "\n\nPress enter to accept $(green "${my_usb}") as the destination drive or specify the correct device (i.e. 'sdc' or 'mmcblk0')"

    read -ep "Device to flash with image [$(green "${my_usb}")]: " drive
    [[ ${drive,,} == "exit" ]] && echo "Exit based on user input." && exit 1

    if [[ $drive ]]; then
        if [[ $boot_list =~ $drive ]]; then
            prompt="The selected drive contains a bootable partition, are you sure about this?" && get_input
            ! $input && echo "Exiting based on user input" && exit 1
        fi
        drive_list=( $(sudo fdisk -l | grep 'Disk /dev/' | awk '{print $2}' | cut -d'/' -f3 | cut -d':' -f1) )
        [[ $drive_list =~ $drive ]] && echo "${my_usb} not found on system. Exiting..." && exit 1
        my_usb=$drive
    fi

    [[ -z $my_usb ]] && echo "Something went wrong no destination device selected... exiting" && exit 1

    # umount device if currently mounted
    cur_mounts=($(mount | grep "/dev/${my_usb}p\?[1|2]\s" | awk '{print $3}'))
    for mnt in "${cur_mounts[@]}"; do
        echo "$mnt is mounted un-mounting"
        umount $mnt
    done

    # get raspios-lite image if not in script dir
    echo -e "\nGetting latest raspios image (${IMG_TYPE})"

    # Find out what current raspios release is
    [ ! $IMG_TYPE = 'desktop' ] && img_url="https://downloads.raspberrypi.org/raspios_${IMG_TYPE}_armhf_latest" ||
        img_url="https://downloads.raspberrypi.org/raspios_armhf_latest"

    # remove DH cipher security improvement in curl broke this, need this until raspberrypi.org changes to use a larger key
    cur_rel=$(curl -sIL --ciphers 'DEFAULT:!DH' $img_url | grep location);cur_rel=$(echo ${cur_rel//*\/} | cut -d'.' -f1)
    [[ -z $cur_rel ]]  && red "Script Failed to determine current image... exiting" && exit 1
    cur_rel_date=$(echo $cur_rel | cut -d'-' -f1-3)

    # Check to see if any images exist in script dir already
    found_img_file=$(ls -lc | grep ".*rasp[bian\|ios].*\.img" | awk '{print $9}')
    found_img_zip=$(ls -lc | grep ".*rasp[bian\|ios].*\.zip" | awk '{print $9}')
    readarray -t found_img_files <<<"$found_img_file"
    readarray -t found_img_zips <<<"$found_img_zip"

    # If img or zip raspios-lite image exists in script dir see if it is current
    # if not prompt user to determine if they want to download current
    if [[ $found_img_file ]]; then
        if [[ ! " ${found_img_files[@]} " =~ ${cur_rel_date}.*\.img ]]; then
            echo "the following images were found:"
            idx=1
            for i in ${found_img_files[@]}; do echo ${idx}. ${i} && ((idx+=1));  done
            echo -e "\nbut the current release is $(cyan $cur_rel)"
            prompt="Would you like to download and use the latest release? ($(cyan $cur_rel)):"
            get_input
            $input || do_select_image "${found_img_files[@]}"  # Selecting No currently broken # $img_file set in do_select_image
        else
            _msg="found in $(pwd). It is the current release"
            img_file=${cur_rel}.img
        fi
    elif [[ $found_img_zip ]]; then
        if [[ ! " ${found_img_zips[@]} " =~ ${cur_rel_date}.*\.zip ]]; then
            echo "the following images were found:"
            idx = 1
            for i in ${found_img_zips[@]}; do echo ${idx}. ${i} && ((idx+=1));  done
            echo -e "\nbut the current release is $(cyan $cur_rel)"
            prompt="Would you like to download and use the latest release? ($(cyan ${cur_rel})):"
            get_input
            $input || do_select_image "${$found_img_zips[@]}" # TODO selecting NO broke right now # $img_file set in do_select_image/do_unzip
        else
            # echo "Using $(cyan ${cur_rel}) found in $(pwd).
            _msg="It is the current release"
            do_unzip ${cur_rel}.zip #img_file assigned in do_unzip
        fi
    else
        echo "no image found in $(pwd)"
    fi
    [ ! -z "$img_file" ] && echo "Using $(cyan ${img_file}) $_msg"

    # img_file will only be assigned if an image was found in the script dir
    retry=1
    while [[ -z $img_file ]] ; do
        [[ $retry > 3 ]] && echo "Exceeded retries exiting " && exit 1
        echo "downloading image from raspberrypi.org.  Attempt: ${retry}"
        wget -q --show-progress $img_url -O ${cur_rel}.zip
        do_unzip "${cur_rel}.zip"
        ((retry++))
    done

    # ----------------------------------- // Burn raspios image to device (micro-sd) \\ -----------------------------------
    echo -e "\n\n${_red}${_blink}!!! Last chance to abort !!!${_norm}"
    get_input "About to write image $(cyan ${img_file}) to $(green ${my_usb}), Continue?"
    ! $input && echo 'Exiting Script based on user input' && exit 1
    header -c
    echo -e "\nNow Writing image $(cyan ${img_file}) to $(green ${my_usb}) standby...\n This takes a few minutes\n"

    if ! $nodd; then  # nodd is dev/testing flag to expedite testing of the script (doesn't write image to sd-card)
        dd bs=4M if="${img_file}" of=/dev/${my_usb} conv=fsync status=progress &&
            echo -e "\n\n$(bold Image written to flash - no Errors)\n\n" ||
            ( echo -e "\n\n$(red Error writing image to falsh)\n\n" ; exit 1 )
    fi

    # Create some mount-points if they don't exist already.  Script will remove them if it has to create them, they will remain if they were already there
    [[ ! -d /mnt/usb1 ]] && sudo mkdir /mnt/usb1 && usb1_existed=false || usb1_existed=true
    [[ ! -d /mnt/usb2 ]] && sudo mkdir /mnt/usb2 && usb2_existed=false || usb2_existed=true

    # Mount boot partition
    dots "Mounting boot partition to enable ssh"
    for i in {1..2}; do
        [[ $my_usb =~ "mmcblk" ]] && res=$(sudo mount /dev/${my_usb}p1 /mnt/usb1 2>&1) || res=$(sudo mount /dev/${my_usb}1 /mnt/usb1  2>&1) ; rc=$?
        if [[ $rc == 0 ]]; then
            break
        else
            # mmcblk device would fail on laptop after image creation re-run with -nodd and was fine
            echo "Sleep then Retry"
            sleep 3
            dots "Mounting boot partition to enable ssh"
        fi
    done
    do_error $rc "$res"

    # Create empty file ssh in boot partition
    dots "Enabling ssh on image"
    touch /mnt/usb1/ssh ; do_error $? # && echo -e " + SSH is now enabled" || echo ' - Error enabling SSH... script will continue anyway'

    # Done with boot partition unmount
    dots "unmount boot partition"
    sync && umount /mnt/usb1 ; do_error $?

    # EXIT IF img_only option = true
    $IMG_ONLY && echo -e "\nimage only option configured.  No Pre-Staging will be done. \n$(green 'Consolepi image ready')\n\a" && exit 0

    # echo -e "\nMounting System partition to Configure ConsolePi auto-install and copy over any pre-config files found in script dir"
    dots "Mounting System partition to pre-configure ConsolePi image"
    [[ $my_usb =~ "mmcblk" ]] && res=$(sudo mount /dev/${my_usb}p2 /mnt/usb2 2>&1) || res=$(sudo mount /dev/${my_usb}2 /mnt/usb2 2>&1)
    do_error $? "$res"

    # get pi users uid:gid from /etc/passwd on image file
    PI_UGID=$(grep "^pi:" /mnt/usb2/etc/passwd | cut -d':' -f3-4)
    PI_UGID=${PI_UGID:-'1000:1000'}

    # Configure simple psk SSID based args or config file
    if $CONFIGURE_WPA_SUPPLICANT; then
        dots "Configuring wpa_supplicant.conf | defining ${SSID}"
        sudo echo "country=${WLAN_COUNTRY}" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        sudo echo "network={" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        sudo echo "    ssid=\"${SSID}\"" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        sudo echo "    psk=\"${PSK}\"" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        [[ $PRIORITY > 0 ]] && sudo echo "    priority=${PRIORITY}" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        sudo echo "}" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        [ -f /mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf ] && echo OK ||echo ERROR
    else
        dots "Script Option to pre-config psk ssid"; echo "Skipped - Not Configured"
    fi

    # Configure pi user to auto-launch ConsolePi installer on first-login
    if $AUTO_INSTALL; then
        dots "Configure Auto-Install on first login"
        echo '#!/usr/bin/env bash' > /mnt/usb2/usr/local/bin/consolepi-install

        if $LOCAL_DEV || ( [ ! -z "$1" ] && [[ "$1" =~ "dev" ]] ) ; then
            echo '[ ! -f /home/pi/.ssh/id_rsa.pub ] && ssh-keygen && ssh-copy-id pi@consolepi-dev' >> /mnt/usb2/usr/local/bin/consolepi-install
            echo 'sudo ls /root/.ssh | grep -q id_rsa.pub || ( sudo ssh-keygen && sudo ssh-copy-id pi@consolepi-dev )' >> /mnt/usb2/usr/local/bin/consolepi-install
            echo 'sftp pi@consolepi-dev:/etc/ConsolePi/installer/install.sh /tmp/ConsolePi && sudo bash /tmp/ConsolePi "${@}" && sudo rm -f /tmp/ConsolePi' >> /mnt/usb2/usr/local/bin/consolepi-install
        else
            echo 'wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/install.sh -O /tmp/ConsolePi && sudo bash /tmp/ConsolePi "${@}" && sudo rm -f /tmp/ConsolePi' >> /mnt/usb2/usr/local/bin/consolepi-install
        fi

        $LOCAL_DEV && cmd_line="-dev $cmd_line"
        grep -q "consolepi-install" $IMG_HOME/.profile || echo "consolepi-install ${cmd_line}" >> $IMG_HOME/.profile

        # make install command/script executable
        sudo chmod +x /mnt/usb2/usr/local/bin/consolepi-install &&
            echo OK && echo "     Configured with the following args $(cyan ${cmd_line})" ||
            ( echo "ERROR"; echo -e "\tERROR making consolepi-install command executable" )
    fi

    # -- pre-stage-configs --
    do_import_configs

    # -- warn if no wlan config --
    [ ! -f /mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf ] && echo -e "\nwarning ~ WLAN configuration not provided, WLAN has *not* been pre-configured"

    # -- Custom Post Image Creation Script --
    if [ -f "$STAGE_DIR/consolepi-image-creator-post.sh" ]; then
        echo -e "\nCustom Post image creation script ($STAGE_DIR/consolepi-image-creator-post.sh) found Executing...\n--"
        . $STAGE_DIR/consolepi-image-creator-post.sh && rc=$? ; echo -e "-- return code: $rc\n"
    fi

    # Done prepping system partition un-mount
    sync && umount /mnt/usb2

    # Remove our mount_points if they didn't happen to already exist when the script started
    ! $usb1_existed && rmdir /mnt/usb1
    ! $usb2_existed && rmdir /mnt/usb2

    green "\nConsolepi image ready\n\a"
    ! $AUTO_INSTALL && echo "Boot RaspberryPi with this image use $(cyan 'consolepi-install') to deploy ConsolePi"
}

verify_local_dev() {
    # -- double check dev option if image created using development ConsolePi --
    if $AUTO_INSTALL && ! $LOCAL_DEV && [[ "$HOSTNAME" == "ConsolePi-dev" ]] ; then
        get_input "dev ConsolePi detected run in local dev mode"
        $input && LOCAL_DEV=true
    fi
}

_help() {
    local pad=$(printf "%0.1s" " "{1..40})
    printf " %s%*.*s%s.\n" "$1" 0 $((40-${#1})) "$pad" "$2"
}

show_usage() {
    # -- hidden dev options --
    # -debug: additional logging
    # -dev: dev local mode, configures image to install from dev branch of local repo
    # -nodd: run without actually burning the image (used to re-test on flash that has already been imaged)
    # -cponly: consolepi-stage dir will be cp to image if found but as __consolepi-stage to prevent installer
    #          from importing from the dir during install
    echo -e "\n$(green USAGE:) sudo $(echo $SUDO_COMMAND | cut -d' ' -f1) [OPTIONS]\n"
    echo -e "$(cyan Available Options)"
    _help "--help | -help | help" "Display this help text"
    _help "-C <location of config file>" "Look @ Specified config file loc to get command line values vs. the default consolepi-image-creator.conf (in cwd)"
    _help "--branch=<branch>" "Configure image to install from designated branch (Default: master)"
    _help "--ssid=<ssid>" "Configure SSID on image (configure wpa_supplicant.conf)"
    _help "--psk=<psk>" "pre-shared key for SSID (must be provided if ssid is provided)"
    _help "--wlan_country=<wlan_country>" "wlan regulatory domain (Default: US)"
    _help "--priority=<priority>" "wlan priority (Default 0)"
    _help "--img_type=<lite|desktop|full>" "Type of RaspiOS image to write to media (Default: lite)"
    _help "--img_only=<true|false>" "If set to true no pre-staging will be done other than enabling SSH (Default: false)"
    _help "--auto_install=<true|false>" "If set to false image will not be configured to auto launch the installer on first login (Default true)"
    _help "--cmd_line='<cmd_line arguments>'" "*Use single quotes* cmd line arguments passed on to 'consolepi-install' cmd/script on image"
    _help "--mass_import=<true|false>" "Bypass mass_import prompt presented when the system creating the image is a ConsolePi. Do it or not based on this value <true|false>"
    _help "--edit=<true|false>" "Bypass prompt asking if you want to edit (nano) the imported ConsolePi.yaml. Do it or not based on this value <true|false>"
    _help "--hotspot_hostname=<true|false>" "Bypass prompt asking to pre-configure hostname based on HotSpot SSID in imported ConsolePi.yaml.  Do it or not based on this value <true|false>"
    echo
    echo -e "The consolepi-image-creator will also look for consolepi-image-creator.conf in the current working directory for the above settings"
    echo
    echo -e "$(cyan Examples:)"
    echo "  This example overrides the default RaspiOS image type (lite) in favor of the desktop image and configures a psk SSID (use single quotes if special characters exist)"
    echo -e "\tsudo ./consolepi-image-creator.sh --img_type=desktop --ssid=MySSID --psk='ConsolePi!!!'"
    echo "  This example passes the -C option to the installer (telling it to get some info from the specified config) as well as the silent install option (no prompts)"
    echo -e "\tsudo ./consolepi-image-creator.sh --cmd_line='-C /home/pi/consolepi-stage/installer.conf -silent'"
    echo
}

parse_args() {
    # echo "DEBUG: ${@}"  ## -- DEBUG LINE --
    [[ ! "${@}" =~ "-C" ]] && [ -f consolepi-image-creator.conf ] && . consolepi-image-creator.conf
    while (( "$#" )); do
        # echo -e "DEBUG ~ Currently evaluating: '$1'"
        case "$1" in
            -dev) # used for development/testing
                local_dev=true
                shift
                ;;
            -cponly) # used for development/testing
                cp_only=true
                shift
                ;;
            -debug) # used for development/testing
                debug=true
                shift
                ;;
            -nodd) # used for development/testing
                nodd=true
                shift
                ;;
            -C) # override the default location script looks for config file (consolepi-image-creator.conf)
                [ -f "$2" ] && . "$2" || ( echo -e "Config File $2 not found" && exit 1 )
                shift 2
                ;;
            *help)
                show_usage
                exit 0
                ;;
            --branch=*) # install from a branch other than master
                branch=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --ssid=*) # psk ssid to pre-configure on img
                ssid=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --psk=*) # psk of ssid (both must be specified)
                psk=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --wlan_country=*) # for pre-configured ssid defaults to US
                wlan_country=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --priority=*) # for pre-configured ssid defaults to 0
                priority=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --img_type=*) # Type of raspiOS to write to img, defaults to lite
                img_type=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --img_only=*) # Only deploy img (and enable SSH) no further pre-config beyond that
                img_only=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --auto_install=*) # configure image to launch installer on first login
                auto_install=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --cmd_line=*) # arguments passed on to install script
                cmd_line=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --mass_import=*) # skip mass import prompt that appears if script is ran from a ConsolePi
                mass_import=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --edit=*) # skip do you want to edit prompt that appears if script imports a ConsolePi.yaml
                edit=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --hotspot_hostname=*) # skip do you want to pre-configure hostname as <HotSpot SSID> presented if script imports a ConsolePi.yaml
                hotspot_hostname=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            *) ## -*|--*=) # unsupported flags
                echo "Error: Unsupported flag $1" >&2
                exit 1
                ;;
        esac
    done
}

check_dir(){
    if [[ $(basename $(pwd)) == "consolepi-stage" ]]; then
        get_input "you are in the consolepi-stage directory, Do you want to chg the working directory to $(dirname $(pwd))"
        if $input; then
            cd $(dirname $(pwd)) &&
            echo -e "\nNew Working Directory $CUR_DIR\n"
        else
            echo -e "\n${_lred}Failed to change Working Directory${_norm}"
        fi
        sleep 3
    fi
}

iam=`whoami`
if [ "${iam}" = "root" ]; then
    check_dir
    parse_args "$@"
    do_defaults
    $DEBUG && ( set -o posix ; set ) | grep -v _xspecs | grep -v LS_COLORS  | less +G
    verify_local_dev
    main
else
    printf "\n${_lred}Script should be ran as root"
    [[ "${@,,}" =~ "help" ]] && ( echo ".${_norm}"; show_usage ) || echo -e " exiting.${_norm}\n"
fi
