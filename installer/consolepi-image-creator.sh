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
# --  To further expedite testing this script will look for a consolepi-stage subdir and if found it will copy the entire directory and any subdirs to /home/consolepi/consolepi-stage
# --  This script also searches the script dir (the dir this script is ran from) for the following which are copied to the /home/consolepi directory on the ConsolePi image if found.
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
# --      - consolepi-post.sh: Custom post-install script, the installer will run this script at the end of the process, it can be used to automate any additional tweaks
# --          you might want to make.  i.e. copy additional custom scripts you like to have on hand from the consolepi-stage dir to wherever you want them.
# --      - authorized_keys: imported for both consolepi and root user (for now)
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
# via cmd line argumetns see --help for available flags
# --------------------------------------------------------------------------------------

# TODO check pre-stage hostname did not appear to work on last run

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

# TODO allow as env vars i.e. [ -z "$DEBUG" ] && DEBUG=${debug:-false}
do_defaults() {
    # ----------------------------------- // DEFAULTS \\ -----------------------------------
    # applied if no config file is found and value not set via cmd line arg
    SSID=${ssid} # psk ssid not configured if ssid not provided
    PSK=${psk}
    WLAN_COUNTRY=${wlan_country:-"US"}
    PRIORITY=${priority:-0}
    IMG_TYPE=${img_type:-'lite'}
    IMG_ONLY=${img_only:-false}  # burn image and enable ssh only, nothing else
    AUTO_INSTALL=${auto_install:-true}
    CONSOLEPI_PASS=$consolepi_pass
    [ -z "$CONSOLEPI_PASS" ] && get_pass
    NEW_HOSTNAME=${img_hostname:-'consolepi'}

    # -- these skip prompts and perform the actions based on the value provided
    # if not set user is prompted (Default is Not set)
    MASS_IMPORT=${import}
    EDIT=${edit}

    # -- development flags
    [ -n "$debug" ] && DEBUG=$debug  # allow envvar unless overridden by --debug flag
    [ -z "$DEBUG" ] && DEBUG=false

    CP_ONLY=${cp_only:-false}  # cp consolepi-stage dir as __consolepi-stage (installer won't look there)
    NODD=${nodd:-false}  # skip writing image to scipt (expedite repeat testing)
    LOCAL_DEV=${local_dev:-false} # Configures image to pull installer from local (dev) repo

    # Some static variables
    STAGE_DIR='consolepi-stage'
    [ -d "$STAGE_DIR" ] && STAGE=true || STAGE=false
    IMG_ROOT="/mnt/usb2"
    IMG_HOME="/mnt/usb2/home/consolepi"
    IMG_STAGE="$IMG_HOME/$STAGE_DIR"
    # STAGED_CONFIG=${get_staged_file_path ConsolePi.yaml}
    ( [ -n "$SSID" ] && [ -n "$PSK" ] ) &&
        CONFIGURE_WPA_SUPPLICANT=true ||
        CONFIGURE_WPA_SUPPLICANT=false
    CUR_DIR=$(pwd)
    IMG_UGID='1000:1000'  # the user and group id, As of April 2022 no default user, consolepi user will be 1st user, uid:1000
    [ -d /etc/ConsolePi ] && ISCPI=true || ISCPI=false

    # /etc/wpa_supplicant/wpa_supplicant.conf is added to STAGE_FILES array if pre-bookworm
    # TODO add logic to grab all network profiles off current system for bookworm+
    MY_HOME=$(grep "^${SUDO_USER}:" /etc/passwd | cut -d: -f6)
    STAGE_FILES=(STAGE:/etc/ConsolePi/ConsolePi.yaml
                STAGE:/etc/udev/rules.d/10-ConsolePi.rules
                STAGE:/etc/ser2net.conf
                STAGE:/etc/ser2net.yaml
                $MY_HOME/.ssh/authorized_keys
                $MY_HOME/.ssh/known_hosts
                $MY_HOME/.ssh/id_rsa
                $MY_HOME/.ssh/id_rsa.pub
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
    unset rc  # in case it was made global and not reset elsewhere
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
    # return input in global context
}

# -- Find path for any files pre-staged in consolepi-stage/$NEW_HOSTNAME subdir then consolepi-stage --
# default is to check for file, pass -d as 2nd arg to check for dir
get_staged_file_path() {
    [ -z "$1" ] && echo "FATAL Error get_staged_file_path() passed NUL value" >$(readlink /dev/fd/0) && exit 3
    local flag=${2:-'-f'}
    if [ $flag "$CUR_DIR/$STAGE_DIR/$NEW_HOSTNAME/$1" ]; then
        echo "$CUR_DIR/$STAGE_DIR/$NEW_HOSTNAME/$1"
    elif [ $flag "$CUR_DIR/$STAGE_DIR/$1" ]; then
        echo "$CUR_DIR/$STAGE_DIR/$1"
    fi
}

# -- determine what ConsolePi.yaml that has been pre-staged, applies
get_staged_config(){
    if [ "$NEW_HOSTNAME" != "consolepi" ] && [ -f "$IMG_STAGE/$NEW_HOSTNAME/ConsolePi.yaml" ]; then
        echo "$IMG_STAGE/$NEW_HOSTNAME/ConsolePi.yaml"
    elif [ -f "$IMG_STAGE/ConsolePi.yaml" ]; then
        echo "$IMG_STAGE/ConsolePi.yaml"
    fi
}

# TODO this is only valid for root and consolepi users, so just loop through those users
# -- Copy Prep pre-staged files if they exist (stage-dir/home/<username>) for newly created user.
do_user_dir_import(){
    if [ "$1" = "root" ]; then
        local uid=0
        local user_home=root
    else
        local uid=1000
        local user_home=home/$1
    fi
    local found=$(get_staged_file_path $user_home -d)
    if [ -n "$found" ]; then
        dots "Found staged files for $1, cp to ${1}'s home on image"
        res=$(cp -r $found/. /mnt/usb2/$user_home/ 2>&1); local rc=$?
        if [ "$rc" -eq 0 ]; then
            res+="\n"
            res+=$(chown -R $uid:$uid /mnt/usb2/$user_home 2>&1); ((rc+=$?))
        fi
        do_error $rc $res
    else
        dots "No staged /$user_home files found"; echo "skip"
    fi
}

show_disk_details() {
    [ -z "$1" ] && echo FATAL ERROR No Arg Provided to show_disk_details && exit 1
    echo -e "------------------------------- // Device Details for $(green "$1") \\\\\ -----------------------------------"
    echo
    fdisk -l /dev/$1  # | sed -n "/Disk \/dev\/$1:/,/Disk \/${1}\//p"
    echo
    echo -e "------------------------------------------------------------------------------------------------"
}

do_extract() {
    $DEBUG && echo do_extract sent arg $1
    if [ -f "$1" ]; then
        dots "Extracting image from $1"
        $(which unxz >/dev/null 2>&1) || do_error $? 'unxz utility is required, please install with "apt install xz-utils"'
        if $DEBUG; then
            unxz_res=$(unxz -k $1 2>&1) || do_error $? "$unxz_res"
        else
            unxz_res=$(unxz $1 2>&1) || do_error $? "$unxz_res"
        fi
        img_file=$(ls -1 "${1%'.xz'}" 2>/dev/null)
        [ ! -z "$img_file" ] ; do_error $? "Something went wrong img file (${1%'.xz'}) not found after extracting... exiting"
    else
        echo Error "$1" 'not found.  Bad File passed to do_extract? Exiting.'
    fi
}

get_pass(){
    header -c
    echo -e "\nPlease provide credentials for 'consolepi' user..."
    match=false; while ! $match; do
        read -sep "New password: " _pass && echo "$_pass" | echo  # sed -r 's/./*/g'
        read -sep "Retype new password: " _pass2 && echo "$_pass2" | echo  # sed -r 's/./*/g'
        [[ "${_pass}" == "${_pass2}" ]] && match=true || match=false
        ! $match && echo -e "ERROR: Passwords Do Not Match\n"
    done
    CONSOLEPI_PASS=$_pass
    unset _pass; unset _pass2
}

# -- Check for ConsolePi.yaml collect info if not found --
do_import_configs() {
    # -- pre-stage Staging Dir on image if found --
    if $STAGE; then
        # -- repoint dst staging dir to __consolepi-stage if -cponly in use dev option to prevent
        #    installer import but still have the files pre-loaded on the image.
        if $CP_ONLY; then
            # remove existing dir on img when doing repeated testing of this script
            [ -d "$IMG_HOME/__$STAGE_DIR" ] && rm -r "$IMG_HOME/__$STAGE_DIR"
            dots "--cp-only flag set using __consolepi-stage as dest on image"
            IMG_STAGE="$IMG_HOME/__$STAGE_DIR" ; do_error $?
        fi
        # DO NOT USE $IMG_HOME/$STAGE_DIR beyond this point, use $IMG_STAGE

        dots "$STAGE_DIR dir found Pre-Staging all files"
        # mkdir -p $IMG_STAGE ; rc=$?
        cp -r $STAGE_DIR/. $IMG_STAGE/ ; local rc=$?
        chown -R $IMG_UGID $IMG_STAGE/ ; do_error $((rc+=$?))

        # -- import authorized keys for the consolepi and root users on image if found --
        local found_path=$(get_staged_file_path authorized_keys)
        if [ -n "$found_path" ]; then
            dots "stage ssh authorized_keys found in $(dirname $found_path)"
            mkdir -p $IMG_HOME/.ssh ; rc=$?
            mkdir -p /mnt/usb2/root/.ssh ; ((rc+=$?))
            cp $found_path $IMG_HOME/.ssh/ ; ((rc+=$?))
            cp $found_path /mnt/usb2/root/.ssh/ ; do_error $((rc+=$?))
        fi

        # -- import SSH known hosts on image if found --
        local found_path=$(get_staged_file_path known_hosts)
        if [ -n "$found_path" ]; then
            dots "stage ssh known_hosts found in $(dirname $found_path)"
            mkdir -p $IMG_HOME/.ssh ; rc=$?
            mkdir -p /mnt/usb2/root/.ssh ; ((rc+=$?))
            cp $found_path $IMG_HOME/.ssh/ ; ((rc+=$?))
            cp $found_path /mnt/usb2/root/.ssh/ ; do_error $((rc+=$?))
        fi

        do_user_dir_import consolepi
        do_user_dir_import root

        # -- adjust perms in .ssh directory if created imported --
        if [ -d "$IMG_HOME/.ssh" ]; then
            dots "Set Ownership of $IMG_HOME/.ssh"
            chown -R $IMG_UGID $IMG_HOME/.ssh ; do_error $?
        fi

        # -- verify/adjust perms on private key file if imported --
        for key in "$IMG_HOME/.ssh/id_rsa" "$IMG_ROOT/root/.ssh/id_rsa"; do
            if [ -f "$key" ]; then
                local key_perms="$(stat -c %a "$key")"
                if [ "$key_perms" -ne 600 ]; then
                    dots "correct permissions on "$key" ~ 600"
                    chmod 600 "$key" ; do_error $?
                fi
            fi
        done
    fi

    # pre-stage wpa_supplicant.conf on image if found in stage dir
    # if EAP-TLS SSID is configured in wpa_supplicant extract EAP-TLS cert details and cp certs (not a loop only good to pre-configure 1)
    #   certs should be in script dir or 'cert' subdir cert_names are extracted from the wpa_supplicant.conf file found in script dir
    # NOTE: Currently the cert parsing will only work if you are using double quotes in wpa_supplicant.conf ~ client_cert="/etc/cert/ConsolePi-dev.pem"
    if $PRE_BOOKWORM; then
        WPA_CONF=$(get_staged_file_path wpa_supplicant.conf)
        if [ -n "$WPA_CONF" ]; then
            dots "wpa_supplicant.conf found pre-staging on image"
            cp $WPA_CONF /mnt/usb2/etc/wpa_supplicant  ; rc=$?
            chown root /mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf ; ((rc+=$?))
            chgrp root /mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf ; ((rc+=$?))
            chmod 644 /mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf ; ((rc+=$?))
            do_error $rc

            # -- extract cert paths from wpa_supplicant.conf and move any staged certs to those paths
            # TODO need to have it pull the current certs if $NEW_HOSTNAME == $HOSTNAME and the files extracted paths exist
            client_cert=$(grep client_cert= $WPA_CONF | cut -d= -f2 | tr -d ' "')
            if [ -n "$client_cert" ]; then
                dots "staged wpa_supplicant includes EAP-TLS SSID looking for certs"
                cert_path="/mnt/usb2"${client_cert%/*}
                ca_cert=$(grep ca_cert= $WPA_CONF | cut -d'"' -f2| cut -d'"' -f1)
                private_key=$(grep private_key= $WPA_CONF | cut -d'"' -f2| cut -d'"' -f1)
                cert_stage_dir=$(get_staged_file_path cert -d)
                if [ -n "$cert_stage_dir" ]; then
                    do_error 0
                    dots "client certs found copying"
                    pushd $cert_stage_dir >/dev/null
                    mkdir -p $cert_path ; rc=$?
                    [ "$rc" -eq 0 ] || echo fail mkdir
                    [[ -f ${client_cert##*/} ]] && cp ${client_cert##*/} "${cert_path}/${client_cert##*/}" ; ((rc+=$?))
                    [[ -f ${ca_cert##*/} ]] && cp ${ca_cert##*/} "${cert_path}/${ca_cert##*/}" ; ((rc+=$?))
                    [[ -f ${private_key##*/} ]] && cp ${private_key##*/} "${cert_path}/${private_key##*/}"; ((rc+=$?))
                    popd >/dev/null
                    do_error $rc
                else
                    echo "WARNING"; echo -e "\tEAP-TLS is defined, but no certs found for import"
                fi
            fi
        fi
    else  # Network Manager based system
        nm_stage_dir=$(get_staged_file_path "NetworkManager/system-connections" -d)
        if [ -n "$nm_stage_dir" ]; then
            nm_con_files=($(ls -1 "$nm_stage_dir"))
            if [ "${#nm_con_files[@]}" -gt 0 ]; then
                cert_stage_dir=$(get_staged_file_path cert -d)

                for nm_profile in "${nm_con_files[@]}"; do
                    dots "stage NetworkManager profile ${nm_profile/.*}"
                    cp $nm_stage_dir/$nm_profile $IMG_ROOT/etc/NetworkManager/system-connections ; rc=$?
                    do_error $rc

                    if [ -n "$cert_stage_dir" ]; then
                        img_profile="$IMG_ROOT/etc/NetworkManager/system-connections/$nm_profile"
                        client_cert=$(grep "client-cert=" $img_profile | cut -d= -f2 | tr -d ' "')
                        if [ -n "$client_cert" ]; then
                            dots "${nm_profile/.*} is EAP-TLS SSID looking for certs"
                            ca_cert=$(grep ca-cert= $img_profile | cut -d= -f2 | tr -d ' "')
                            private_key=$(grep private-key= $img_profile | cut -d= -f2 | tr -d ' "')

                            cert_path="/mnt/usb2"${client_cert%/*}
                            mkdir -p $cert_path ; rc=$?
                            [ "$rc" -eq 0 ] || echo fail mkdir
                            pushd $cert_stage_dir >/dev/null
                            [ -n "$ca_cert" ] && [ -f "$ca_cert" ] && [ ! -f "${cert_path}/${ca_cert##*/}" ] && ( cp ${ca_cert##*/} "${cert_path}/${ca_cert##*/}" ; ((rc+=$?)) )
                            [ -n "$client_cert" ] && [ -f "$client_cert" ] && [ ! -f "${cert_path}/${client_cert##*/}" ] && ( cp ${ca_cert##*/} "${cert_path}/${client_cert##*/}" ; ((rc+=$?)) )
                            [ -n "$private_key" ] && [ -f "$private_key" ] && [ ! -f "${cert_path}/${private_key##*/}" ] && ( cp ${ca_cert##*/} "${cert_path}/${private_key##*/}" ; ((rc+=$?)) )
                            do_error $rc

                            # adjust key file permissions
                            if [ -f "${cert_path}/${private_key##*/}" ]; then
                                dots "Set staged private key (${private_key##*/}) permissions (600)"
                                res=$(chmod 600 "${cert_path}/${private_key##*/}" 2>&1) ; do_error $? "$res"
                            fi
                            popd >/dev/null
                        fi
                    fi
                done

                dots "chown/chmod pre-staged profiles"
                chown root:root $IMG_ROOT/etc/NetworkManager/system-connections/* ; rc=$?
                chmod 600 $IMG_ROOT/etc/NetworkManager/system-connections/* ; ((rc+=$?))
                do_error $rc
            fi
        fi
    fi

    # -- If image being created from a ConsolePi offer to import settings --
    if $ISCPI; then

        STAGED_CONFIG=$(get_staged_config)

        if [ -z "$MASS_IMPORT" ]; then
            echo -e "\n-----------------------  $(green 'This is a ConsolePi') -----------------------\n"
            echo -e "You can mass import settings from this ConsolePi onto the new image."
            echo -e "The following files will be evaluated:\n"
            for f in "${STAGE_FILES[@]}"; do echo -e "\t${f//STAGE:/}" ; done
            [ "$HOSTNAME" == "$NEW_HOSTNAME" ] && echo -e "\t/etc/ssh/*"
            echo -e "\nAny files already staged via $STAGE_DIR will be skipped"
            echo -e "Any files not found on this ConsolePi will by skipped\n"
            echo '--------------------------------------------------------------------'
            get_input "Perform mass import"
            MASS_IMPORT=$input
        fi

        if $MASS_IMPORT; then
            if [ ! -d "$IMG_STAGE" ]; then
                dots "create stage dir on image"
                mkdir -p $IMG_STAGE ; rc=$?
                chown -R $IMG_UGID $IMG_STAGE/ ; ((rc+=$?))
                do_error $rc
            fi

            cyan "\n   -- Performing Imports from This ConsolePi --"
            $PRE_BOOKWORM && STAGE_FILES+=("/etc/wpa_supplicant/wpa_supplicant.conf")
            for f in "${STAGE_FILES[@]}"; do
                if [[ "$f" =~ ^"STAGE:" ]]; then
                    src="$(echo $f| cut -d: -f2)"
                    dst="$IMG_STAGE/$(basename $(echo $f| cut -d: -f2))"

                # -- Accomodate Files imported from users home on a ConsolePi for non consolepi user (consolepi user already imported) --
                elif [[ ! $f =~ "/home/consolepi" ]] && [[ $f =~ $MY_HOME ]]; then
                    src="$f"
                    # dst is in consolepi-stage/$NEW_HOSTNAME if there is a host specific subdir in the stage dir otherwise the root of the stage dir
                    [ -d "$IMG_STAGE/$NEW_HOSTNAME" ] && dst="${IMG_STAGE}/$NEW_HOSTNAME${f}" || dst="${IMG_STAGE}${f}"
                else
                    src="$f"
                    dst="${IMG_ROOT}${f}"
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
                        echo -e "${_green}Imported${_norm}"
                        [ "$(basename "$dst" 2>/dev/null)" = "ConsolePi.yaml" ] && STAGED_CONFIG=$dst
                    else
                        echo -e "${_green}Error${_norm}"
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

            # pull ssh keys and config and place on this Pi
            if [ "$HOSTNAME" == "$NEW_HOSTNAME" ]; then
                dots "/etc/ssh/*"
                cp -r /etc/ssh/* $IMG_ROOT/etc/ssh 2>&1 && echo "Imported"
            fi


        # We still prompt for ConsolePi.yaml even if not doing import
        elif [ -z $STAGED_CONFIG ] && [ -f /etc/ConsolePi/ConsolePi.yaml ]; then
            echo
            get_input "Do you want to pre-stage configuration using the config from this ConsolePi (you will be given the chance to edit)"
            if $input; then
                sudo -u $SUDO_USER mkdir -p $IMG_STAGE/
                sudo -u $SUDO_USER cp /etc/ConsolePi/ConsolePi.yaml $IMG_STAGE/
                STAGED_CONFIG="$IMG_STAGE/ConsolePi.yaml"
            fi
        fi
    fi # /if $ISCPI

    # prompt to modify staged config
    if [ -n "$STAGED_CONFIG" ]; then
        if [ -z "$EDIT" ]; then
            echo
            get_input "Do you want to edit the pre-staged ConsolePi.yaml to change details"
            EDIT=$input
        fi
        $EDIT && nano -ET2 $STAGED_CONFIG
        cfg_ssid=$(grep '  wlan_ssid: ' $STAGED_CONFIG | awk '{print $2}')
    fi

    # -- set hostname based on flag or based on pre-staged config if found
    # -- consolepi is the default, if they provided via flag then skip
    if [ "$NEW_HOSTNAME" = consolepi ] || [ "$NEW_HOSTNAME" != "$cfg_ssid" ]; then
        if [ -n "$cfg_ssid" ]; then
            get_input "Do you want to pre-stage the hostname as $cfg_ssid"
            $input && NEW_HOSTNAME=$cfg_ssid
        fi
    fi

    # This actually always true as we default to consolepi if not provided
    if [ -n "$NEW_HOSTNAME" ]; then
        dots "configure hostname $NEW_HOSTNAME on image"
        echo $NEW_HOSTNAME > /mnt/usb2/etc/hostname ; do_error $?
        sed -i "s/127\.0\.1\.1.*raspberrypi/127.0.1.1\t$NEW_HOSTNAME/g" /mnt/usb2/etc/hosts
    fi
}

do_select_image() {
    args=("${@}")
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
    if [[ "${args[${input}]}" =~ ".xz" ]]; then
        do_extract "${args[((${input}-1))]}" # do_extract sets img_file
    else
        img_file="${args[((${input}-1))]}"
    fi
}

# TODO combine with do_select_image just set var with the selection
do_select_device() {
    args=("${@}")
    idx=1; for i in "${args[@]}"; do
        echo ${idx}. ${i/'_'/' '}
        ((idx+=1))
    done
    echo
    valid_input=false
    while ! $valid_input; do
        read -ep "Select item # or 'exit' to abort> " input
        if [[ "${input,,}" == "exit" ]]; then
            echo "Exiting based on user input" && exit 1
        else
            echo "${args[@]}" =~ "${args[((${input}-1))]}"
            if [[ "$input" =~ ^[0-9]+$ ]] && [[ ! -z "${args[((${input}-1))]}" ]]; then
                valid_input=true
                ((input-=1))
            else
                echo -e "\t!! Invalid Input"
            fi
        fi
    done
}

do_detect_download_image() {
    echo -e "\nGetting latest raspios image (${IMG_TYPE})"

    # Find out what current raspios release is
    # https://downloads.raspberrypi.org/raspios_lite_armhf/images/raspios_lite_armhf-2022-09-07/2022-09-06-raspios-bullseye-armhf-lite.img.xz
    [ ! $IMG_TYPE = 'desktop' ] && img_url="https://downloads.raspberrypi.org/raspios_${IMG_TYPE}_armhf_latest" ||
        img_url="https://downloads.raspberrypi.org/raspios_armhf_latest"

    # remove DH cipher security improvement in curl broke this, need this until raspberrypi.org changes to use a larger key
    cur_rel_url=$(curl -sIL --ciphers 'DEFAULT:!DH' $img_url | grep location | cut -d' ' -f2 | strings)
    cur_rel_full=$(echo ${cur_rel_url//*\/})
    cur_rel_img=$(echo $cur_rel_full | cut -d'.' -f1-2)
    cur_rel_base=$(echo $cur_rel_full | cut -d'.' -f1)
    [[ -z $cur_rel_full ]]  && red "Script Failed to determine current image... exiting" && exit 1
    cur_rel_date=$(echo $cur_rel_full | cut -d'-' -f1-3)

    # Check to see if any images exist in script dir already
    found_img_files=($(ls -1 | grep ".*rasp[bian\|ios].*\.img"$))
    found_xz_files=($(ls -1 | grep ".*rasp[bian\|ios].*\.xz"$))

    # If img or xz raspios-lite image exists in script dir see if it is current
    # if not prompt user to determine if they want to download current
    # FIXME if both the img file and xz exist it will try to extract the xz again and crash as the file already exists
    if (( ${#found_img_files[@]} )); then
        if [[ ! " ${found_img_files[@]} " =~ ${cur_rel_date}.*\.img ]]; then
            echo "the following images were found:"
            idx=1
            for i in ${found_img_files[@]}; do echo "${idx}. ${i}" && ((idx+=1));  done
            echo -e "\nbut the current release is $(cyan $cur_rel_base)"
            prompt="Would you like to download and use the latest release? ($(cyan $cur_rel_base)):"
            get_input
            $input || do_select_image "${found_img_files[@]}"  # Selecting No currently broken # $img_file set in do_select_image
        else
            _msg="found in $(pwd). It is the current release"
            img_file=$cur_rel_img
        fi
    fi
    if (( ${#found_xz_files[@]} )); then
        if [[ ! " ${found_xz_files[@]} " =~ ${cur_rel_date}.*\.xz ]]; then
            echo "the following images were found:"
            idx = 1
            for i in ${found_xz_files[@]}; do echo ${idx}. ${i} && ((idx+=1));  done
            echo -e "\nbut the current release is $(cyan $cur_rel_base)"
            prompt="Would you like to download and use the latest release? ($(cyan ${cur_rel_base})):"
            get_input
            $input || do_select_image "${$found_xz_files[@]}" # TODO selecting NO broke right now # $img_file set in do_select_image/do_extract
        else
            # echo "Using $(cyan ${cur_rel_base}) found in $(pwd)."
            _msg="It is the current release"
            do_extract $cur_rel_full #img_file assigned in do_extract
        fi
    else
        echo "no image found in $(pwd)"
    fi

    [ ! -z "$img_file" ] && echo "Using $(cyan ${img_file}) $_msg"

    # img_file will only be assigned if an image was found in the script dir
    retry=1
    while [ -z "$img_file" ] ; do
        [[ $retry > 3 ]] && echo "Exceeded retries exiting " && exit 1
        echo "downloading image from raspberrypi.org.  Attempt: ${retry}"
        wget -q --show-progress $img_url -O $cur_rel_full
        do_extract $cur_rel_full
        ((retry++))
    done
}

main() {
    header -c

    # if ! $CONFIGURE_WPA_SUPPLICANT && [[ ! -f "$STAGE_DIR/wpa_supplicant.conf" ]]; then
    #     echo "wlan configuration will not be applied to image, to apply WLAN configuration break out of the script"
    #     echo "and configure via consolepi-stage.conf or import file or command line args"
    # fi

    ### OLD LOGIC
    # my_usb=($(ls -l /dev/disk/by-path/*usb* 2>/dev/null |grep -v part | sed 's/.*\(...\)/\1/'))
    # # -- Exit now if more than 1 usb storage dev found
    # if [[ ${#my_usb[@]} > 1 ]]; then
    #     echo -e "\nMore than 1 USB Storage Device Found, To use this script Only plug in the device you want to image.\n"
    #     exit 1
    # else
    #     my_usb=${my_usb[0]}
    # fi

    ROOT_PART="$(findmnt / -o source -n)"
    ROOT_DEV="$(lsblk -no pkname "$ROOT_PART")"
    # constructs a list in form sda_(58.2G)
    my_usb=($(lsblk -no name,type,size | grep disk | grep -v ${ROOT_DEV#'/dev/'} | awk '{print $1 "_(" $3 ")"}'))

    SCRIPT_TITLE=$(green "ConsolePi Image Creator")
    $LOCAL_DEV && SCRIPT_TITLE+=" ${_lred}${_blink}Local DEV${_norm}"
    echo -e "\n\n$SCRIPT_TITLE \n'exit' (which will terminate the script) is valid at all prompts\n"

    if [ "${#my_usb[@]}" -gt 1 ]; then
        echo -e "$(red "Multiple") removable flash devices discovered"
        do_select_device ${my_usb[@]}
        out_usb=${my_usb[$input]%_*}
    else
        out_usb=${my_usb[0]%_*}
    fi
    # DEVICE IS out_usb my_usb is the list of discovered devices with _(size) appended

    [ -n "$out_usb" ] && echo -e "Script has discovered removable flash device @ $(green "${out_usb}") with the following details\n" ||
        echo -e "Script failed to detect removable flash device, you will need to specify the device"

    show_disk_details ${out_usb}

    # Give user chance to change target drive
    echo -e "\n\nPress enter to accept $(green "${out_usb}") as the destination drive or specify the correct device (i.e. 'sdc' or 'mmcblk0')"

    read -ep "Device to flash with image [$(green "${out_usb}")]: " drive
    [[ ${drive,,} == "exit" ]] && echo "Exit based on user input." && exit 1

    if [[ $drive ]]; then  ## They made a change
        if [[ ! ${my_usb[@]} =~ $drive ]]; then
            if [ "$drive" = "$ROOT_DEV" ]; then
                echo $(red "$drive is mounted at / it's the drive you are booted on.  Not a good idea")
            else
                echo "$drive not found on system. Exiting..."
            fi
            exit 1
        fi
        out_usb=$drive
    fi

    [ -z "$out_usb" ] && echo "Something went wrong no destination device selected... exiting" && exit 1

    # umount device if currently mounted
    cur_mounts=($(mount | grep "/dev/${out_usb}p\?[1|2]\s" | awk '{print $3}'))
    for mnt in "${cur_mounts[@]}"; do
        echo "$mnt is mounted un-mounting"
        umount $mnt
    done

    [ -z "$img_file" ] && do_detect_download_image  # if img_file set it was set via --image argument

    if [[ $img_file =~ bullseye ]] || [[ $img_file =~ jessie ]] || [[ $img_file =~ stretch ]]; then
        PRE_BOOKWORM=true
    elif [[ $img_file =~ bookworm ]]; then
        PRE_BOOKWORM=false
    fi

    if [ -z "$PRE_BOOKWORM" ]; then
        # This assumes image is in format yyyy-mm-dd-raspios-bookworm-armhf-lite.img
        img_date=$(echo "$img_file" | cut -d- -f-2)
        if [ "${#img_date}" -ne 7 ]; then
            # something not right about the image file assume bookworm+
            PRE_BOOKWORM=false
        else
            img_year=${img_date/-*}
            if [ "$img_year" -lt 2023 ]; then
                PRE_BOOKWORM=true
            elif [ "$img_year" -gt 2023 ]; then
                PRE_BOOKWORM=false
            else
                # raspberry pi OS went to bookworm with Oct 2023 release
                [ "${img_date/*-}" -lt 10 ] && PRE_BOOKWORM=true || PRE_BOOKWORM=false
            fi
        fi
    fi


    # ----------------------------------- // Burn raspios image to device (micro-sd) \\ -----------------------------------
    echo -e "\n\n${_red}${_blink}!!! Last chance to abort !!!${_norm}"
    get_input "About to write image $(cyan ${img_file}) to $(green ${out_usb}), Continue?"
    ! $input && echo 'Exiting Script based on user input' && exit 1
    header -c
    echo -e "\nNow Writing image $(cyan ${img_file}) to $(green ${out_usb}) standby...\n This takes a few minutes\n"

    if ! $NODD; then  # NODD is dev/testing flag to expedite testing of the script (doesn't write image to sd-card)
        dd bs=4M if="${img_file}" of=/dev/${out_usb} conv=fsync status=progress &&
            echo -e "\n\n$(bold Image written to flash - no Errors)\n\n" ||
            ( echo -e "\n\n$(red Error writing image to falsh)\n\n" ; exit 1 )
    fi

    # Create some mount-points if they don't exist already.  Script will remove them if it has to create them, they will remain if they were already there
    [[ ! -d /mnt/usb1 ]] && sudo mkdir /mnt/usb1 && usb1_existed=false || usb1_existed=true
    [[ ! -d /mnt/usb2 ]] && sudo mkdir /mnt/usb2 && usb2_existed=false || usb2_existed=true

    # Mount boot partition
    #TODO see raspi-config do_expand_rootfs using findmnt... more elegant way to get the correct mount, and detect if it's the active boot
    dots "mounting boot partition"
    for i in {1..2}; do
        [[ $out_usb =~ "mmcblk" ]] && res=$(sudo mount /dev/${out_usb}p1 /mnt/usb1 2>&1) || res=$(sudo mount /dev/${out_usb}1 /mnt/usb1  2>&1) ; rc=$?
        if [[ $rc == 0 ]]; then
            break
        else
            # mmcblk device would fail on laptop after image creation re-run with --no-dd and was fine
            echo "Sleep then Retry"
            sleep 3
            dots "mounting boot partition"
        fi
    done
    do_error $rc "$res"

    # Create empty file ssh in boot partition
    dots "enable ssh on image"
    touch /mnt/usb1/ssh ; do_error $?

    # Create userconf to configure default user
    if ! $IMG_ONLY; then
        dots "staging consolepi user for userconf"
        printf "consolepi:$(echo $CONSOLEPI_PASS | openssl passwd -6 -stdin)" > /mnt/usb1/userconf ; do_error $?
    fi

    # Done with boot partition unmount
    dots "unmount boot partition"
    sync && umount /mnt/usb1 ; do_error $?

    # EXIT IF img_only option = true
    $IMG_ONLY && echo -e "\nimage only option configured.  No Pre-Staging will be done. \n$(green 'Consolepi image ready')\n\a" && exit 0

    # mount system partition to pre-stage the ConsolePi installer
    dots "mounting system partition to pre-configure consolePi image"
    [[ $out_usb =~ "mmcblk" ]] && res=$(sudo mount /dev/${out_usb}p2 /mnt/usb2 2>&1) || res=$(sudo mount /dev/${out_usb}2 /mnt/usb2 2>&1)
    do_error $? "$res"

    # -- create home directory for default user 'consolepi' with uid:gid = 1000:1000
    dots "create consolepi home dir on image"
    mkdir -p $IMG_HOME ; do_error $?

    dots "copy skel files to consolepi home dir"
    sudo cp /mnt/usb2/etc/skel/.bashrc $IMG_HOME; local rc=$?
    sudo cp /mnt/usb2/etc/skel/.profile $IMG_HOME; ((rc+=$?))
    sudo cp /mnt/usb2/etc/skel/.bash_logout $IMG_HOME; do_error $((rc+=$?))

    dots "chmod skel files staged in consolepi home"
    sudo chmod 644 $IMG_HOME/.bashrc; rc=$?
    sudo chmod 644 $IMG_HOME/.profile; ((rc+=$?))
    sudo chmod 644 $IMG_HOME/.bash_logout; do_error $((rc+=$?))

    dots "set ownership of consolepi home dir"
    chown -R $IMG_UGID $IMG_HOME ; do_error $?

    # TODO move to func and use EOF << redirection
    # Configure simple psk SSID based args or config file

    if $CONFIGURE_WPA_SUPPLICANT; then
        if $PRE_BOOKWORM; then
            dots "configuring wpa_supplicant.conf | defining ${SSID}"
            sudo echo "country=${WLAN_COUNTRY}" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
            sudo echo "network={" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
            sudo echo "    ssid=\"${SSID}\"" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
            sudo echo "    psk=\"${PSK}\"" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
            [[ $PRIORITY > 0 ]] && sudo echo "    priority=${PRIORITY}" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
            sudo echo "}" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
            [ -f /mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf ] && green OK || red ERROR
        else
            dots "NetworkManager pre-config only supported via import file" ; echo "skipped"
        fi
    fi

    # Configure consolepi user to auto-launch ConsolePi installer on first-login
    if $AUTO_INSTALL; then
        dots "configure auto launch installer on first login"
        local auto_install_file=/mnt/usb2/usr/local/bin/consolepi-install
        echo '#!/usr/bin/env bash' > $auto_install_file

        if $LOCAL_DEV || ( [ ! -z "$1" ] && [[ "$1" =~ "dev" ]] ) ; then
            echo '[ ! -f $HOME/.ssh/id_rsa.pub ] && ssh-keygen && ssh-copy-id wade@consolepi-dev' >> $auto_install_file
            echo 'sudo ls -1 /root/.ssh | grep -q id_rsa.pub || ( sudo ssh-keygen && sudo ssh-copy-id wade@consolepi-dev )' >> $auto_install_file
            echo 'sftp wade@consolepi-dev:/etc/ConsolePi/installer/install.sh /tmp/ConsolePi && sudo bash /tmp/ConsolePi "${@}" && sudo rm -f /tmp/ConsolePi' >> $auto_install_file
        else
            echo 'wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/install.sh -O /tmp/ConsolePi && sudo bash /tmp/ConsolePi "${@}" && sudo rm -f /tmp/ConsolePi' >> $auto_install_file
        fi

        $LOCAL_DEV && cmd_line="--dev ${cmd_line#"--dev "}"
        grep -q "consolepi-install" $IMG_HOME/.profile || echo "consolepi-install ${cmd_line}" >> $IMG_HOME/.profile

        # make install command/script executable
        sudo chmod +x $auto_install_file &&
            green OK && echo "     Configured with the following args $(cyan ${cmd_line})" ||
            ( red "ERROR"; echo -e "\tERROR making consolepi-install command executable" )
    fi

    # -- pre-stage-configs --
    do_import_configs

    # -- warn if no wlan config --
    [ ! -f /mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf ] && echo -e "\nwarning ~ WLAN configuration not provided, WLAN has *not* been pre-configured"

    # -- Custom Post Image Creation Script --
    local found=$(get_staged_file_path consolepi-image-creator-post.sh)
    if [ -n "$found" ]; then
        echo -e "\nCustom Post image creation script (consolepi-image-creator-post.sh) found in $(dirname $found) Executing...\n--"
        . $found && rc=$? ; echo -e "-- return code: $rc\n"
    fi

    # Done prepping system partition un-mount
    sync && umount /mnt/usb2

    # Remove our mount_points if they didn't happen to already exist when the script started
    ! $usb1_existed && rmdir /mnt/usb1
    ! $usb2_existed && rmdir /mnt/usb2

    green "\nConsolePi image ready\n\a"
    ! $AUTO_INSTALL && echo "Boot RaspberryPi with this image use $(cyan 'consolepi-install') to deploy ConsolePi" || true # prevents exit with error code
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
    # hash consolepi-image 2>/dev/null && local cmd=consolepi-image || local cmd=$(echo $SUDO_COMMAND | cut -d' ' -f1)
    [ -x /etc/ConsolePi/src/consolepi-commands/consolepi-image ] && local cmd=consolepi-image || local cmd="sudo $(echo $SUDO_COMMAND | cut -d' ' -f1)"
    echo -e "\n$(green USAGE:) $cmd [OPTIONS]\n"
    echo -e "$(cyan Available Options)"
    _help "-h|--help" "Display this help text"
    _help "-C <location of config file>" "Look @ Specified config file loc to get command line values vs. the default consolepi-image-creator.conf (in cwd)"
    _help "--ssid <ssid>" "Configure SSID on image (configure wpa_supplicant.conf)"
    _help "--psk '<psk>'" "Use single quotes: psk for SSID (must be provided if ssid is provided)"
    _help "--wlan-country <2 char country code>" "wlan regulatory domain (Default: US)"
    _help "--priority <priority>" "wlan priority if specifying psk SSID via --ssid and --psk flags (Default 0)"
    _help "--img-type <lite|desktop|full>" "Type of RaspiOS image to write to media (Default: lite)"
    _help "--img-only" "Only install RaspiOS, no pre-staging will be done other than enabling SSH (Default: false)"
    _help "--[no-]auto-install" "image will not be configured to auto launch the installer on first login (Default true)"
    _help "--[no-]import" "whether or not to import files from this system to the image, if this is a ConsolePi.  Prompted if not set."
    _help "--[no-]edit" "Skips prompt asking if you want to edit (nano) the imported ConsolePi.yaml."
    _help "-H|--hostname" "pre-configure hostname on image."
    _help "-I|--image" "Use specified image (full path or file in cwd)"
    _help "-p|--passwd <consolepi password>" "The password to set for the consolepi user."
    _help "--cmd-line '<cmd_line arguments>'" "*Use single quotes* cmd line arguments passed on to 'consolepi-install' cmd/script on image"
    if [ -n "$1" ] && [ "$1" = "dev" ]; then  # hidden dev flags --help dev to display them.
        echo -e "\n$(green Dev Options)\n"
        _help "-D|--dev" "Install from ConsolePi-dev using dev branch"
        _help "--cp-only" "import consolepi-stage dir as __consolepi-stage.  So it's there, but won't be picked up by installer."
        _help "--no-dd" "Don't actually write the image, for repeat testing of this script."
        _help "--debug" "Additional logging"
    fi
    echo
    echo -e "The consolepi-image-creator will also look for consolepi-image-creator.conf in the current working directory for the above settings"
    echo
    echo -e "$(cyan Examples:)"
    echo "  This example overrides the default RaspiOS image type (lite) in favor of the desktop image and configures a psk SSID (use single quotes if special characters exist)"
    echo -e "\tsudo ./consolepi-image-creator.sh --img-type desktop --ssid MySSID --psk 'ConsolePi!!!'"
    echo "  This example passes the -C option to the installer (telling it to get some info from the specified config) as well as the silent install option (no prompts)"
    echo -e "\tsudo ./consolepi-image-creator.sh --cmd-line='-C /home/consolepi/consolepi-stage/installer.conf --silent'"
    echo
}


missing_param(){
    echo $1 requires an argument. >&2
    show_usage
    exit 1
}


parse_args() {
    # echo "DEBUG: ${@}"  ## -- DEBUG LINE --
    [[ ! "${@}" =~ "-C" ]] && [ -f consolepi-image-creator.conf ] && . consolepi-image-creator.conf
    while (( "$#" )); do
        # echo -e "DEBUG ~ Currently evaluating: '$1'"
        case "$1" in
            -h|--help)
                show_usage $2
                exit 0
                ;;
            -C) # override the default location script looks for config file (consolepi-image-creator.conf)
                if [ -f "$2" ]; then
                    . "$2"
                    shift 2
                else
                    echo -e "Config File $2 not found"
                    exit 1
                fi
                ;;
            -H|--hostname) # preconfigure hostname on image.  Handy as installer looks for files in $HOME/consolepi-stage/$HOSTNAME
                [ -n "$2" ] && img_hostname=$2 || missing_param $1
                shift 2
                ;;
            -I|--image) # Use specified image must be in cwd
                [ -n "$2" ] && img_file=$2 || missing_param $1
                shift 2
                ;;
            -p|--passwd) # consolepi pass prompted if not provided
                [ -n "$2" ] && consolepi_pass=$2 || missing_param $1
                shift 2
                ;;
            -D|-*dev) # used for development/testing
                local_dev=true
                shift
                ;;
            --cmd-line) # arguments passed on to install script (auto-install)
                [ -n "$2" ] && cmd_line=$2 || missing_param $1
                shift 2
                ;;
            --cp-only) # copy stage dir prefixed with __ so the files are there but installer doesn't import them
                cp_only=true
                shift
                ;;
            --debug) # used for development/testing
                debug=true
                shift
                ;;
            --no-dd) # used for development/testing
                nodd=true
                shift
                ;;
            --ssid) # psk ssid to pre-configure on img
                [ -n "$2" ] && ssid=$2 || missing_param $1
                shift
                ;;
            --psk) # psk of ssid (both must be specified)
                [ -n "$2" ] && psk=$2 || missing_param $1
                shift
                ;;
            --wlan-country) # for pre-configured ssid defaults to US
                [ -n "$2" ] && wlan_country=$2 || missing_param $1
                shift 2
                ;;
            --priority) # for pre-configured ssid defaults to 0
                [ -n "$2" ] && priority=$2 || missing_param $1
                shift 2
                ;;
            --img-type) # Type of raspiOS to write to img, defaults to lite
                [ -n "$2" ] && img_type=$2 || missing_param $1
                shift 2
                ;;
            --img-only) # Only deploy img (and enable SSH) no further pre-config beyond that default to false
                img_only=true
                shift
                ;;
            --auto-install) # configure image to launch installer on first login
                auto_install=true
                shift
                ;;
            --no-auto-install) # configure image to launch installer on first login
                auto_install=false
                shift
                ;;
            --import) # import from this system to the image (if this is a ConsolePi)
                import=true
                shift
                ;;
            --no-import) # import from this system to the image (if this is a ConsolePi)
                import=false
                shift
                ;;
            -*edit) # skip do you want to edit prompt that appears if script imports a ConsolePi.yaml
                [ "$1" = "--no-edit" ] && edit=false || edit=true
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
            echo -e "\nNew Working Directory $(pwd)\n"
        else
            echo -e "\n${_lred}Failed to change Working Directory${_norm}"
        fi
        sleep 3
    fi
}

iam=`whoami`
if [ "${iam}" = "root" ]; then
    set +H
    check_dir
    parse_args "$@"
    do_defaults
    $DEBUG && ( set -o posix ; set ) | grep -v _xspecs | grep -v LS_COLORS  | less +G
    verify_local_dev
    main
else
    printf "\n${_lred}Script should be ran as root"
    [[ "${@,,}" =~ "help" ]] && ( echo -e ".${_norm}"; show_usage ) || echo -e " exiting.${_norm}\n"
fi
