#!/usr/bin/env bash

# Common functions used by ConsolePi's various scripts
# Author: Wade Wells

# -- Installation Defaults --
INSTALLER_VER=46
CFG_FILE_VER=8
cur_dir=$(pwd)
iam=$(who -m |  awk '{print $1}')
[ -z $iam ] && iam=$SUDO_USER # cockpit shell
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
cloud_cache="/etc/ConsolePi/cloud.json"
override_dir="/etc/ConsolePi/overrides" # TODO NO TRAILING / make others that way
py3ver=$(python3 -V | cut -d. -f2)
yml_script="/etc/ConsolePi/src/yaml2bash.py"
tmp_src="/tmp/consolepi-temp"
warn_cnt=0

# Terminal coloring
_norm='\e[0m'
_bold='\e[32;1m'
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
    [ -z $1 ] && clear # pass anything as an argument to prevent screen clear
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


menu_print() {
    # -- send array of strings to function and it will print a formatted menu
    # Args: -head: str that follows is header
    #       -foot: str that follows is footer
    #
    # Used to print post-install message
    # NOTE: Line Length of 121 is currently hardcoded
    line_len=121
    while (( "$#" )); do
        case "$1" in
            -head)
                str=" $2 "
                len=${#str}
                left=$(( ((line_len-len))/2 ))
                [[ $((left+len+right)) -eq $line_len ]] && right=$left || right=$((left-1))
                printf -v pad_left "%*s" $left && pad_left=${pad_left// /*}
                printf -v pad_right "%*s" $right && pad_right=${pad_right// /*}
                printf "%s %s %s\n" "$pad_left" "$str" "$pad_right"
                shift 2
                ;;
            -foot)
                str="**$2"
                len=${#str}
                right=$(( ((line_len-len+1)) ))
                printf -v pad_right "%*s" $right && pad_right=${pad_right// /*}
                printf "%s%s\n" "$str" "$pad_right"
                shift 2
                ;;
            -nl|-li|*)
                if [[ "$1" == "-nl" ]]; then
                    str=" "
                elif [[ "$1" == "-li" ]]; then
                    str="  -${2}"
                    shift
                else
                    str="$1"
                fi
                len=${#str}
                [[ "$str" =~ "\e[" ]] && ((len-=11))
                [[ "$str" =~ ';1m' ]] && ((len-=2))
                pad_len=$(( ((line_len-len-4)) ))
                printf -v pad "%*s" $pad_len # && pad=${pad// /-}
                printf '* %b %s *\n' "$str" "$pad"
                shift
                ;;
        esac
    done
}

# -- Logging function prints to terminal and log file assign value of process prior to calling logit --
logit() {
    # Logging Function: logit <message|string> [<status|string>]
    # usage:
    #   process="Install ConsolePi"  # Define prior to calling or UNDEFINED or last used will be displayed in the log
    #   logit "building package" <"WARNING">
    # NOTE: Sending a status of "ERROR" results in the script exiting
    #       default status is INFO if none provided.
    [[ "${1}" == '-start' ]] && start=true && shift || start=false
    [ -z "$process" ] && process="UNDEFINED"
    message="${1}"                                      # 1st arg = the log message
    [ -z "${2}" ] && status="INFO" || status=${2^^} # to upper
    fatal=false                                     # fatal is determined by status. default to false.  true if status = ERROR
    if [[ "${status}" == "ERROR" ]]; then
        fatal=true
        status="${_red}${status}${_norm}"
    elif [[ ! "${status}" == "INFO" ]]; then
        status="${_yellow}${status}${_norm}"
        [[ "${status}" == "WARNING" ]] && ((warn_cnt+=1))
    fi

    log_msg="$(date +"%b %d %T") [${status}][${process}] ${message}"
    if ! $start; then
        # Log to stdout and log-file
        echo -e "$log_msg" | tee -a $log_file
    else
        # log_start is used to parse log file and display warnings after the matching start-line
        echo -e "$log_msg" >> $log_file
        log_start=$(echo "$log_msg" | cut -d'[' -f1)
    fi

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
    if [ ! -z "$default" ]; then
        if $bool; then
            prompt+="? (Y/N)"
            "$default" && prompt+=" [Y]: " || prompt+=" [N]: "
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
# TODO add -e flag for exit option
user_input_bool() {
    valid_response=false
    while ! $valid_response; do
        read -ep "${prompt}? (Y/N): " response
        response=${response,,}    # tolower
        if [[ "$response" =~ ^(yes|y)$ ]]; then
            response=true && valid_response=true
        elif [[ "$response" =~ ^(no|n)$ ]]; then
            response=false && valid_response=true
        else
            valid_response=false
        fi
    done

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
            file_diff=$(diff -s ${src_file} ${dst_file})
        else
            file_diff="doit"
        fi
    fi

    # -- if systemd file doesn't exist or doesn't match copy and enable from the source directory
    if ! $override; then
        if [[ ! "$file_diff" = *"identical"* ]]; then
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
                # TODO consider logic change. to only enable on upgrade if we find it in enabled state
                #  This logic would appear to always enable the service in some cases we don't want that
                #  installer will disable / enable after if necessary, but this would retain user customizations
                if [[ ! $(sudo systemctl list-unit-files ${1}.service | grep enabled) ]]; then
                    if [[ -f /etc/systemd/system/${1}.service ]]; then
                        # sudo systemctl disable ${1}.service 1>/dev/null 2>> $log_file  # TODO this seems unnecessary reason for it or just copy / paste error?
                        sudo systemctl enable ${1}.service 1>/dev/null 2>> $log_file ||
                            logit "FAILED to enable ${1} systemd service" "WARNING"
                    else
                        logit "Failed ${1}.service file not found in systemd after move"
                    fi
                fi
                # -- if the service is enabled and active currently restart the service --
                if systemctl is-enabled ${1}.service >/dev/null ; then
                    if systemctl is-active ${1}.service >/dev/null ; then
                        # sudo systemctl daemon-reload 2>>$log_file # redundant
                        if [[ ! "${1}" =~ "autohotspot" ]] ; then
                            sudo systemctl restart ${1}.service 1>/dev/null 2>> $log_file ||
                                logit "FAILED to restart ${1} systemd service" "WARNING"
                        fi
                    fi
                fi
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
        logit "override file found ${1##*/} ... Skipping no changes will be made"
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
    process="Collect Pi Info"
    [ ! -z $branch ] && [ $branch != "master" ] && logit "Running alternate branch: ${_green}$branch${_norm}"
    git_rem=$(pushd /etc/ConsolePi >/dev/null 2>&1 && git remote -v | head -1 | cut -d '(' -f-1 ; popd >/dev/null 2>&1)
    [[ ! -z $git_rem ]] && [[ $(echo $git_rem | awk '{print $2}') != $consolepi_source ]] && logit "Using alternative repo: ${_green}$git_rem${_norm}"
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
    model_pretty=$(get_pi_info_pretty $rev)
    # echo -e "$version running on $cpu Revision: $rev\n    $model_pretty"
    logit "$model_pretty"
    logit "$version running on $cpu Revision: $rev"
    logit "$(uname -a)"
    dpkg -l | grep -q raspberrypi-ui && logit "Raspbian with Desktop" || logit "Raspbian Lite"
    logit "Python 3 Version $(python3 -V)"
    [ $py3ver -lt 6 ] && logit "${_red}DEPRICATION WARNING:${_norm} Python 3.5 will no longer be supported by ConsolePi in a future release." "warning" &&
        logit "You should re-image ConsolePi using the current Raspbian release" "warning"
    unset process
}

convert_template() {
    /etc/ConsolePi/src/j2render.py "$@"
    file_diff_update /tmp/${1} $2
    rm /tmp/${1} >/dev/null 2>>$log_file
}

process_yaml() {
    $yml_script "${@}" > $tmp_src 2>>$log_file && . $tmp_src && rm $tmp_src ||
        logit "Error returned from yaml config import ($yml_script ${@}), check $log_file" "ERROR"
}

do_systemd_enable_load_start() {
    if [[ ! -f "${override_dir}/${1}.service" ]] ; then
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
    else
        logit "Skipping enable and start $1 - override found"
    fi
}

# -- Find path for any files pre-staged in user home or ConsolePi_stage subdir --
get_staged_file_path() {
    [[ -z $1 ]] && logit "FATAL Error find_path function passed NUL value" "CRITICAL"
    if [[ -f "${home_dir}${1}" ]]; then
        found_path="${home_dir}${1}"
    elif [[ -f ${stage_dir}$1 ]]; then
        found_path="${home_dir}ConsolePi_stage/${1}"
    else
        found_path=
    fi
    echo $found_path
}

dots() {
    local pad=$(printf "%0.1s" "."{1..51})
    printf " %s%*.*s" "$1" 0 $((51-${#1})) "$pad" "$2"; echo
    return 0;
}

spaces() {
    local pad=$(printf "%0.1s" " "{1..70})
    printf "  %s%*.*s" "$1" 0 $((70-${#1})) "$pad" "$2"; echo
    return 0;
}

process_cmds() {
    reset_vars=('cmd' 'pmsg' 'fmsg' 'cmd_pfx' 'fail_lvl' 'silent' 'out' 'stop' 'err' 'showstart' 'pname' 'pexclude' 'pkg' 'do_apt_install')
    ret=0
    # echo "DEBUG: ${@}"  ## -- DEBUG LINE --
    while (( "$#" )); do
        # echo -e "DEBUG:\n\tcmd=${cmd}\n\tsilent=$silent\n\tpmsg=${pmsg}\n\tfmsg=${fmsg}\n\tfail_lvl=$fail_lvl"
        # echo -e "DEBUG TOP ~ Currently evaluating: '$1'"
        case "$1" in
            -stop) # will stop function from exec remaining commands on failure (witout exit 1)
                stop=true
                shift
                ;;
            -e) # will result in exit 1 if cmd fails
                fail_lvl="ERROR"
                shift
                ;;
            -s) # only show msg if cmd fails
                silent=true
                shift
                ;;
            -u) # Run Command as logged in User
                cmd_pfx="sudo -u $iam"
                shift
                ;;
            -nolog) # Don't log stderr anywhere default is to log_file
                err="/dev/null"
                shift
                ;;
            -logit|-l) # Used to simply log a message
                case "$3" in
                    WARNING|ERROR)
                        logit "$2" "$3"
                        shift 3
                        ;;
                    *)
                        logit "$2"
                        shift 2
                        ;;
                esac
                ;;
            -nostart) # elliminates the process start msg
                showstart=false
                shift
                ;;
            -apt-install) # install pkg via apt
                local do_apt_install=true
                shift
                go=true; while (( "$#" )) && $go ; do
                    # echo -e "DEBUG apt-install ~ Currently evaluating: '$1'" # -- DEBUG LINE --
                    case "$1" in
                        --pretty=*)
                            pname=${1/*=}
                            shift
                            ;;
                        --exclude=*)
                            pexclude=${1/*=}
                            shift
                            ;;
                        *)
                            if [[ -z $pkg ]] ; then
                                pkg=$1
                                [[ -z $pname ]] && pname=$1
                                shift
                            else
                                go=false
                            fi
                            ;;
                    esac
                done
                pmsg="Success - Install $pname (apt)"
                fmsg="Error - Install $pname (apt)"
                stop=true
                [[ ! -z $pexclude ]] && cmd="sudo apt-get -y install $pkg ${pexclude}-" ||
                    cmd="sudo apt-get -y install $pkg"
                # shift $_shift
                ;;
            -apt-purge) # purge pkg followed by autoremove
                case "$3" in
                    --pretty=*)
                        pname=${3/*=}
                        _shift=3
                        ;;
                    *)
                        pname=$2
                        _shift=2
                        ;;
                esac
                pmsg="Success - Remove $pname (apt)"
                fmsg="Error - Remove $pname (apt)"
                cmd="sudo apt-get -y purge $2"
                shift $_shift
                ;;
            -o) # redirect stdout default is /dev/null
                out="$2"
                shift 2
                ;;
            -pf|-fp) # msg template for both success and failure in 1
                pmsg="Success - $2"
                fmsg="Error - $2"
                shift 2
                ;;
            -p) # msg displayed if command successful
                local pmsg="Success - $2"
                shift 2
                ;;
            -f) # msg displayed if command fails
                local fmsg="Error - $2"
                shift 2
                ;;
            -*|--*=) # unsupported flags
                echo "Error: Unsupported flag passed to process_cmds $1" >&2
                exit 1
                ;;
            *) # The command to execute, all flags should precede the commands otherwise defaults for those items
                cmd="$1"
                shift
                ;;
        esac
        # if cmd is set process cmd
        # use defaults if flag not set
        if [[ ! -z $cmd ]]; then
            [[ -z $pmsg ]] && pmsg="Success - $cmd"
            [[ -z $fmsg ]] && fmsg="Error - $cmd  See details in $log_file"
            [[ -z $fail_lvl ]] && fail_lvl="WARNING"
            [[ -z $silent ]] && silent=false
            [[ -z $stop ]] && stop=false
            [[ -z $err ]] && err=$log_file
            [[ ! -z $cmd_pfx ]] && cmd="$cmd_pfx $cmd"
            [[ -z $out ]] && out='/dev/null'
            [[ -z $showstart ]] && showstart=true
            [[ -z $do_apt_install ]] && do_apt_install=false
            # echo -e "DEBUG:\n\tcmd=$cmd\n\tpname=$pname\n\tsilent=$silent\n\tpmsg=${pmsg}\n\tfmsg=${fmsg}\n\tfail_lvl=$fail_lvl\n\tout=$out\n\tstop=$stop\n\tret=$ret\n"
            # echo "------------------------------------------------------------------------------------------" # -- DEBUG Line --
            # -- // PROCESS THE CMD \\ --
            ! $silent && $showstart && logit "Starting ${pmsg/Success - /}"
            if eval "$cmd" >>"$out" 2>>"$err"; then
                cmd_failed=false
                ! $silent && logit "$pmsg"
                # if cmd was an apt-get purge - automatically issue autoremove to clean unnecessary deps
                # TODO re-factor to only do purge at the end of all other proccesses
                if [[ "$cmd" =~ "purge" ]]; then
                    logit "Tidying Up packages that are no longer in use (apt autoremove)"
                    sudo apt-get -y autoremove >/dev/null 2>>$log_file &&
                        logit "Success - All Tidy Now" ||
                        logit "Error - apt autoremove returned error-code" "WARNING"
                fi
            else
                cmd_failed=true
                if $do_apt_install ; then
                    x=1
                    while [[ $(tail -2 /var/log/ConsolePi/install.log | grep "^E:" | tail -1) =~ "is another process using it?" ]] && ((x<=3)); do
                        logit "dpkg appears to be in use pausing 5 seconds... before attempting retry $x" "WARNING"
                        sleep 5
                        logit "Starting ${pmsg/Success - /} ~ retry $x"
                        if eval "$cmd" >>"$out" 2>>"$err"; then
                            cmd_failed=false
                            ! $silent && logit "$pmsg"
                        fi
                        ((x+=1))
                        done
                fi
            fi

            if $cmd_failed ; then
                logit "$fmsg" "$fail_lvl" && ((ret+=1))
                $stop && logit "aborting remaining tasks due to previous failure" && cd $cur_dir && break
            fi
            # echo "------------------------------------------------------------------------------------------" # -- DEBUG Line --
            # -- // unset all flags \\ --
            for c in "${reset_vars[@]}"; do
                unset ${c}
            done
        fi

    done
    return $ret
}
