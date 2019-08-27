#!/usr/bin/env bash

# Common functions used by ConsolePi's various scripts
# Author: Wade Wells
# Last Update: June 4 2019

# -- Installation Defaults --
INSTALLER_VER=32
CFG_FILE_VER=6
cur_dir=$(pwd)
iam=$(who | awk '{print $1}')
tty_cols=$(stty -a | grep -o "columns [0-9]*" | awk '{print $2}')
consolepi_dir="/etc/ConsolePi/"
src_dir="${consolepi_dir}src/"
bak_dir="${consolepi_dir}bak/"
if [ "$iam" = "root" ]; then
    home_dir="/${iam}/"
else
    home_dir="/home/${iam}/"
fi
stage_dir="${home_dir}ConsolePi_stage/"
default_config="/etc/ConsolePi/ConsolePi.conf"
wpa_supplicant_file="/etc/wpa_supplicant/wpa_supplicant.conf"
tmp_log="/tmp/consolepi_install.log" 
final_log="/var/log/ConsolePi/install.log"
cloud_cache="/etc/ConsolePi/cloud.data"
override_dir="/etc/ConsolePi/src/override"

# Terminal coloring
_norm='\e[0m'
_bold='\033[1;32m'
_blink='\e[5m'
_red='\e[31m'
_blue='\e[34m'
_lred='\e[91m'
_yellow='\e[33;1m'
_green='\e[32m'
_cyan='\e[96m' # technically light cyan

# vpn_dest=$(sudo grep -G "^remote\s.*" /etc/openvpn/client/ConsolePi.ovpn | awk '{print $2}')

[[ $( ps -o comm -p $PPID | tail -1 ) == "sshd" ]] && ssh=true || ssh=false
[[ -f $final_log ]] && upgrade=true || upgrade=false

# log file is referenced thoughout the script.  During install changes from tmp to final after final log
# location is configured in install.sh do_logging
$upgrade && log_file=$final_log || log_file=$tmp_log


# -- External Sources --
# ser2net_source="https://sourceforge.net/projects/ser2net/files/latest/download" ## now points to gensio not ser2net
ser2net_source="https://sourceforge.net/projects/ser2net/files/ser2net/ser2net-3.5.1.tar.gz/download"
ser2net_source_version="3.5.1"
# ser2net_source="https://sourceforge.net/projects/ser2net/files/ser2net/ser2net-4.0.tar.gz/download"
consolepi_source="https://github.com/Pack3tL0ss/ConsolePi.git"

# header reqs 144 cols to display properly
header() {
    clear
    if [ $tty_cols -gt 144 ]; then
        echo "                                                                                                                                                ";
        echo "                                                                                                                                                ";
        echo -e "${_cyan}        CCCCCCCCCCCCC                                                                     lllllll                   ${_lred}PPPPPPPPPPPPPPPPP     iiii  ";
        echo -e "${_cyan}     CCC::::::::::::C                                                                     l:::::l                   ${_lred}P::::::::::::::::P   i::::i ";
        echo -e "${_cyan}   CC:::::::::::::::C                                                                     l:::::l                   ${_lred}P::::::PPPPPP:::::P   iiii  ";
        echo -e "${_cyan}  C:::::CCCCCCCC::::C                                                                     l:::::l                   ${_lred}PP:::::P     P:::::P        ";
        echo -e "${_cyan} C:::::C       CCCCCC   ooooooooooo   nnnn  nnnnnnnn        ssssssssss      ooooooooooo    l::::l     eeeeeeeeeeee    ${_lred}P::::P     P:::::Piiiiiii ";
        echo -e "${_cyan}C:::::C               oo:::::::::::oo n:::nn::::::::nn    ss::::::::::s   oo:::::::::::oo  l::::l   ee::::::::::::ee  ${_lred}P::::P     P:::::Pi:::::i ";
        echo -e "${_cyan}C:::::C              o:::::::::::::::on::::::::::::::nn ss:::::::::::::s o:::::::::::::::o l::::l  e::::::eeeee:::::ee${_lred}P::::PPPPPP:::::P  i::::i ";
        echo -e "${_cyan}C:::::C              o:::::ooooo:::::onn:::::::::::::::ns::::::ssss:::::so:::::ooooo:::::o l::::l e::::::e     e:::::e${_lred}P:::::::::::::PP   i::::i ";
        echo -e "${_cyan}C:::::C              o::::o     o::::o  n:::::nnnn:::::n s:::::s  ssssss o::::o     o::::o l::::l e:::::::eeeee::::::e${_lred}P::::PPPPPPPPP     i::::i ";
        echo -e "${_cyan}C:::::C              o::::o     o::::o  n::::n    n::::n   s::::::s      o::::o     o::::o l::::l e:::::::::::::::::e ${_lred}P::::P             i::::i ";
        echo -e "${_cyan}C:::::C              o::::o     o::::o  n::::n    n::::n      s::::::s   o::::o     o::::o l::::l e::::::eeeeeeeeeee  ${_lred}P::::P             i::::i ";
        echo -e "${_cyan} C:::::C       CCCCCCo::::o     o::::o  n::::n    n::::nssssss   s:::::s o::::o     o::::o l::::l e:::::::e           ${_lred}P::::P             i::::i ";
        echo -e "${_cyan}  C:::::CCCCCCCC::::Co:::::ooooo:::::o  n::::n    n::::ns:::::ssss::::::so:::::ooooo:::::ol::::::le::::::::e        ${_lred}PP::::::PP          i::::::i";
        echo -e "${_cyan}   CC:::::::::::::::Co:::::::::::::::o  n::::n    n::::ns::::::::::::::s o:::::::::::::::ol::::::l e::::::::eeeeeeee${_lred}P::::::::P          i::::::i";
        echo -e "${_cyan}     CCC::::::::::::C oo:::::::::::oo   n::::n    n::::n s:::::::::::ss   oo:::::::::::oo l::::::l  ee:::::::::::::e${_lred}P::::::::P          i::::::i";
        echo -e "${_cyan}        CCCCCCCCCCCCC   ooooooooooo     nnnnnn    nnnnnn  sssssssssss       ooooooooooo   llllllll    eeeeeeeeeeeeee${_lred}PPPPPPPPPP          iiiiiiii";
        echo -e "${_blue}                                                     https://github.com/Pack3tL0ss/ConsolePi${_norm}";
        echo "                                                                                                                                                ";
    else
        echo -e "${_cyan}   ______                       __    ${_lred} ____  _ "
        echo -e "${_cyan}  / ____/___  ____  _________  / /__  ${_lred}/ __ \(_)"
        echo -e "${_cyan} / /   / __ \/ __ \/ ___/ __ \/ / _ \\\\${_lred}/ /_/ / / "
        echo -e "${_cyan}/ /___/ /_/ / / / (__  ) /_/ / /  __${_lred}/ ____/ /  "
        echo -e "${_cyan}\____/\____/_/ /_/____/\____/_/\___${_lred}/_/   /_/   "
        echo -e "${_blue}  https://github.com/Pack3tL0ss/ConsolePi${_norm}"
        echo -e ""
    fi
}

# -- Logging function prints to terminal and log file assign value of process prior to calling logit --
logit() {
    # Logging Function: logit <message|string> [<status|string>]
    # usage:
    #   process="Install ConsolePi"  # Define prior to calling or UNDEFINED or last used will be displayed in the log
    #   logit "building package" <"WARNING">
    # NOTE: Sending a status of "ERROR" results in the script exiting
    #       default status is INFO if none provided.
    [ -z "$process" ] && process="UNDEFINED"
    message=$1                                      # 1st arg = the log message
    [ -z "${2}" ] && status="INFO" || status=$2
    fatal=false                                     # fatal is determined by status. default to false.  true if status = ERROR
    if [[ "${status}" == "ERROR" ]]; then
        fatal=true
        status="${_red}${status}${_norm}"
    elif [[ ! "${status}" == "INFO" ]]; then
        status="${_yellow}${status}${_norm}"
    fi
    
    # Log to stdout and log-file
    echo -e "$(date +"%b %d %T") [${status}][${process}] ${message}" | tee -a $log_file
    # if status was ERROR which means FATAL then log and exit script
    if $fatal ; then
        echo -e "$(date +'%b %d %T') [${status}][${process}] Last Error is fatal, script exiting Please review log ${log_file}" && exit 1
    fi
}

# -- Collect User Input --
# arg 1 is required use NUL if you don't want a default value
# prompt doesn't have to be defined as long as it's been set (bash is global)
user_input() {
    # Get default value and prompt text from args
    # $1 = NUL = No default Value
    unset default
    pass=0
    [ ! -z "$1" ] && [[ ! "$1" == "NUL" ]] && default="$1"
    [ ! -z "$2" ] && prompt="$2" || prompt="ERROR: No Prompt was set"
    
    # Determine if bool (default value true|false)
    case $1 in
        true|false)
            bool=true
        ;;
        *)
            bool=false
        ;;
    esac

    # Format full prompt
    if [ ! -z $default ]; then
        if $bool; then
            prompt+="? (Y/N)"
            $default && prompt+=" [Y]: " || prompt+=" [N]: "
        else
            prompt+=" [${default}]: "
        fi
    else
        prompt+=": "
    fi
    
    # Prompt until a valid entry is collected
    valid_result=false
    while ! $valid_result; do
        [ $pass -gt 0 ] && echo "Invalid Entry ${result}"
        read -ep "${prompt}" result
        if $bool; then
            result=${result,,}    # tolower
            if [ ${#result} -gt 0 ]; then        # If they enter text ensure it's y/n otherwise accept default
                if [[ "$result" =~ ^(yes|y)$ ]]; then
                    result=true && valid_result=true
                elif [[ "$result" =~ ^(no|n)$ ]]; then
                    result=false && valid_result=true
                fi
            else
                result=$default && valid_result=true
            fi
        else
            if [ ${#result} -gt 0 ]; then
                result=$result && valid_result=true
            elif [ ${#default} -gt 0 ]; then
                result=$default && valid_result=true
            else
                valid_result=false
            fi
        fi
        ((pass++))
    done
    unset prompt
    # returns $result
}

# user input function that accepts y|yes|n|no (not case sensitive) and loops until a valid response is entered. No default
user_input_bool() {
    valid_response=false
    while ! $valid_response; do
        read -ep "${prompt}? (Y/N): " response
        logger -t DEBUG $response - $valid_response
        response=${response,,}    # tolower
        if [[ "$response" =~ ^(yes|y)$ ]]; then
            response=true && valid_response=true
        elif [[ "$response" =~ ^(no|n)$ ]]; then
            response=false && valid_response=true
        else
            valid_response=false
        fi
    done
    logger -t DEBUG $response - $valid_response
    echo $response
}

# arg1 = systemd file without the .service suffix
systemd_diff_update() {
    # -- If both files exist check if they are different --
    dst_file="/etc/systemd/system/${1}.service"
    if [ -f ${override_dir}/${1}.service ]; then
        override=true
        logit "override file found for ${1}.service ... Skipping no changes will be made"
    else
        override=false
        src_file="${src_dir}systemd/${1}.service"
        if [[ -f "$src_file" ]] && [[ -f "$dst_file" ]]; then
            mdns_diff=$(diff -s ${src_file} ${dst_file}) 
        else
            mdns_diff="doit"
        fi
    fi

    # -- if systemd file doesn't exist or doesn't match copy and enable from the source directory
    if ! $override; then
        if [[ ! "$mdns_diff" = *"identical"* ]]; then
            if [[ -f "/etc/ConsolePi/src/systemd/${1}.service" ]]; then
                if [ -f /etc/systemd/system/${1}.service ]; then
                    sudo cp /etc/systemd/system/${1}.service "$bak_dir${1}.service.$(date +%F_%H%M)" 1>/dev/null 2>> $log_file &&
                        logit "existing $1 unit file backed up to bak dir" || 
                        logit "FAILED to backup existing $1 unit file" "WARNING"
                fi
                sudo cp /etc/ConsolePi/src/systemd/${1}.service /etc/systemd/system 1>/dev/null 2>> $log_file &&
                    logit "${1} systemd unit file created/updated" || 
                    logit "FAILED to create/update ${1} systemd service" "WARNING"
                sudo systemctl daemon-reload 1>/dev/null 2>> $log_file || logit "Failed to reload Daemons: ${1}" "WARNING"
                if [[ ! $(sudo systemctl list-unit-files ${1}.service | grep enabled) ]]; then
                    if [[ -f /etc/systemd/system/${1}.service ]]; then
                        sudo systemctl disable ${1}.service 1>/dev/null 2>> $log_file
                        sudo systemctl enable ${1}.service 1>/dev/null 2>> $log_file ||
                            logit "FAILED to enable ${1} systemd service" "WARNING"
                    else
                        logit "Failed ${1}.service file not found in systemd after move"
                    fi
                fi
                [[ $(sudo systemctl list-unit-files ${1}.service | grep enabled) ]] &&
                    sudo systemctl restart ${1}.service 1>/dev/null 2>> $log_file || 
                    logit "FAILED to restart ${1} systemd service" "WARNING"
            else
                logit "${1} file not found in src directory.  git pull failed?" "WARNING"
            fi
        else
            logit "${1} systemd file is current"
        fi
    fi
}

# arg1 = full path of src file, arg2 = full path of file in final path
file_diff_update() {
    # -- If both files exist check if they are different --
    if [ -f ${override_dir}/${1##*/} ]; then
        override=true
        logit "override file found for ${1} ... Skipping no changes will be made"
    else
        override=false
        if [[ -f ${1} ]] && [[ -f ${2} ]]; then
            this_diff=$(diff -s ${1} ${2}) 
        else
            this_diff="doit"
        fi
    fi

    # -- if file on system doesn't exist or doesn't match src copy and enable from the source directory
    if ! $override; then
        if [[ ! "$this_diff" = *"identical"* ]]; then
            if [[ -f ${1} ]]; then 
                if [ -f ${2} ]; then        # if dest file exists but doesn't match stash in bak dir
                    sudo cp $2 "$bak_dir${2##*/}.$(date +%F_%H%M)" 1>/dev/null 2>> $log_file &&
                        logit "${2} backed up to bak dir" || 
                        logit "FAILED to backup existing ${2}" "WARNING"
                fi

                if [ ! -d ${2%/*} ]; then
                    logit "Creating ${2%/*} directory as it doesn't exist"
                    sudo mkdir -p ${2%/*} || logit "Error Creating ${2%/*} directory"
                fi

                sudo cp ${1} ${2} 1>/dev/null 2>> $log_file &&
                    logit "${2} Updated" || 
                    logit "FAILED to create/update ${2}" "WARNING"
            else
                logit "${1} file not found in src directory.  git pull failed?" "WARNING"
            fi
        else
            logit "${2} is current"
        fi
    fi
}

get_ser2net() {
    mapfile -t _aliases < <( cat /etc/ser2net.conf | grep ^70[0-9][0-9] | grep ^70[0-9][0-9]: | cut -d'/' -f3 | cut -d':' -f1 )
    mapfile -t _ports < <( cat /etc/ser2net.conf | grep ^70[0-9][0-9] | grep ^70[0-9][0-9]: | cut -d':' -f1 )
}

# Hung Terminal Helper
do_kill_hung_ssh() {
    dev_name=${1##*/}
    echo $HOSTNAME $dev_name - ${1} - $0
    proc=$(ps auxf | grep -v grep | grep -v "${0##*-}" | grep "$dev_name" | awk '{print $2}')
    sudo pkill -SIGTERM -ns $proc
    ps auxf
    echo $proc
}

get_pi_info_pretty() {
    declare -A hw_array && compat_bash=true || compat_bash=false
    if $compat_bash; then
        hw_array["Beta"]="Raspberry Pi Model B hw rev Beta 256 MB"
        hw_array["0002"]="Raspberry Pi Model B hw rev 1.0  256 MB"
        hw_array["0003"]="Raspberry Pi Model B (ECN0001) hw rev 1.0 256 MB Fuses mod and D14 removed"
        hw_array["0004"]="Raspberry Pi Model B  hw rev 2.0  256 MB  (Mfg by Sony)"
        hw_array["0005"]="Raspberry Pi Model B  hw rev 2.0  256 MB  (Mfg Qisda)"
        hw_array["0006"]="Raspberry Pi Model B  hw rev 2.0  256 MB  (Mfg Egoman)"
        hw_array["0007"]="Raspberry Pi Model A  hw rev 2.0  256 MB  (Mfg Egoman)"
        hw_array["0008"]="Raspberry Pi Model A  hw rev 2.0  256 MB  (Mfg Sony)"
        hw_array["0009"]="Raspberry Pi Model A  hw rev 2.0  256 MB  (Mfg Qisda)"
        hw_array["000d"]="Raspberry Pi Model B  hw rev 2.0  512 MB  (Mfg Egoman)"
        hw_array["000e"]="Raspberry Pi Model B  hw rev 2.0  512 MB  (Mfg Sony)"
        hw_array["000f"]="Raspberry Pi Model B  hw rev 2.0  512 MB  (Mfg Qisda)"
        hw_array["0010"]="Raspberry Pi Model B+  hw rev 1.0  512 MB  (Mfg Sony)"
        hw_array["0011"]="Raspberry Pi Compute Module 1  hw rev 1.0  512 MB  (Mfg by Sony)"
        hw_array["0012"]="Raspberry Pi Model A+ hw rev 1.1  256 MB  (Mfg by Sony)"
        hw_array["0013"]="Raspberry Pi Model B+  hw rev 1.2  512 MB  (Mfg by Embest)"
        hw_array["0014"]="Raspberry Pi Compute Module 1 hw rev 1.0  512 MB  (Mfg by Embest)"
        hw_array["0015"]="Raspberry Pi Model A+ 1.1 hw rev 256 MB / 512 MB  (Mfg by Embest)"
        hw_array["a01040"]="Raspberry Pi 2 Model B hw rev 1.0  1 GB  (Mfg by Sony)"
        hw_array["a01041"]="Raspberry Pi 2 Model B hw rev 1.1  1 GB  (Mfg by Sony)"
        hw_array["a21041"]="Raspberry Pi 2 Model B hw rev 1.1  1 GB  (Mfg by Embest)"
        hw_array["a22042"]="Raspberry Pi 2 Model B (with BCM2837) hw rev 1.2 1 GB (Mfg by Embest)"
        hw_array["900021"]="Raspberry Pi A+  hw rev 1.1  512 MB  (Mfg by Sony)"
        hw_array["900032"]="Raspberry Pi B+  hw rev 1.2  512 MB  (Mfg by Sony)"
        hw_array["900092"]="Raspberry Pi Zero hw rev 1.2 512 MB (Mfg by Sony)"
        hw_array["900093"]="Raspberry Pi Zero hw rev 1.3 512 MB (Mfg by Sony)"
        hw_array["920093"]="Raspberry Pi Zero hw rev 1.3 512 MB  (Mfg by Embest)"
        hw_array["9000c1"]="Raspberry Pi Zero W  hw rev 1.1 512 MB (Mfg by Sony)"
        hw_array["a02082"]="Raspberry Pi 3 Model B  hw rev 1.2 1 GB  (Mfg by Sony)"
        hw_array["a020a0"]="Raspberry Pi Compute Module 3 (and CM3 Lite)  hw rev 1.0    1 GB (Mfg by Sony)"
        hw_array["a22082"]="Raspberry Pi 3 Model B  hw rev 1.2  1 GB  (Mfg by Embest)"
        hw_array["a32082"]="Raspberry Pi 3 Model B  hw rev 1.2  1 GB  (Mfg by Sony Japan)"
        hw_array["a020d3"]="Raspberry Pi 3 Model B+  hw rev 1.3  1 GB  (Mfg by Sony)"
        hw_array["9020e0"]="Raspberry Pi 3 Model A+  hw rev 1.0  512 MB  (Mfg by Sony)"
        hw_array["a03111"]="Raspberry Pi 4 Model B  hw rev 1.1  1 GB  (Mfg by Sony)"
        hw_array["b03111"]="Raspberry Pi 4 Model B  hw rev 1.1  2 GB  (Mfg by Sony)"
        hw_array["c03111"]="Raspberry Pi 4 Model B  hw rev 1.1  4 GB  (Mfg by Sony)"
    fi            
    $compat_bash && echo ${hw_array["$1"]} || echo $1
}

# Gather Some info about the Pi useful in triage of issues
get_pi_info() {
    # uname -a
    # cat /etc/os-release
    ver_full=$(head -1 /etc/debian_version)
    ver=$(echo $ver_full | cut -d. -f1)

    if [ $ver -eq 10 ]; then
        version="Raspbian $ver_full (Buster)"
    elif [ $ver -eq 9 ]; then
        version="Raspbian $ver_full (Stretch)" 
    elif [ $ver -eq 8 ]; then 
        version="Raspbian $ver_full (Jessie)" 
    else 
        version="Raspbian $ver_full (Wheezy)"
    fi

    cpu=$(cat /proc/cpuinfo | grep 'Hardware' | awk '{print $3}')
    rev=$(cat /proc/cpuinfo | grep 'Revision' | awk '{print $3}' | sed 's/^1000//')
    pretty=$(get_pi_info_pretty $rev)
    echo -e "$version running on $cpu Revision: $rev\n    $pretty"
}

convert_template() {
    /etc/ConsolePi/j2render.py "$@"
    file_diff_update /tmp/${1} $2
    rm /tmp/${1} >/dev/null 2>>$log_file
}

do_systemd_enable_load_start() {
    status=$(systemctl is-enabled $1 2>&1)
    if [ "$status" == "disabled" ]; then
        sudo systemctl enable $1 1>/dev/null 2>> $log_file  && logit "${1} systemd unit file enabled" || 
                    logit "FAILED to enable ${1} systemd unit file" "WARNING"
    elif [ "$status" == "enabled" ]; then
        logit "$1 unit file already enabled"
    elif [[ "$status" =~ "No such file or directory" ]]; then
        logit "$1 unit file not found" "ERROR" 
    fi
    # Will only exectue if systemd script enabled
    sudo systemctl daemon-reload 2>> $log_file || logit "daemon-reload failed, check logs" "WARNING"
    sudo systemctl stop $1 >/dev/null 2>&1
    sudo systemctl start $1 1>/dev/null 2>> $log_file || logit "$1 failed to start, may be normal depending on service/hardware" "WARNING"
}