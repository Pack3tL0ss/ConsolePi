#!/usr/bin/env bash

# Common functions used by ConsolePi's various scripts
# Author: Wade Wells

# -- Installation Defaults --
cur_dir=$(pwd)
iam=${SUDO_USER:-$(who -m | awk '{ print $1 }')}
tty_cols=$(stty -a 2>/dev/null | grep -o "columns [0-9]*" | awk '{print $2}')
consolepi_dir="/etc/ConsolePi/"
src_dir="${consolepi_dir}src/"
bak_dir="${consolepi_dir}bak/"
home_dir=$(grep "^${iam}:" /etc/passwd | cut -d: -f6)  # TODO NO TRAILING / make others that way
stage_dir="${home_dir}/consolepi-stage"                # TODO NO TRAILING / make others that way
default_config="/etc/ConsolePi/ConsolePi.conf"      # TODO Double check, should be able to remove
wpa_supplicant_file="/etc/wpa_supplicant/wpa_supplicant.conf"
tmp_log="/tmp/consolepi_install.log"
final_log="/var/log/ConsolePi/install.log"
cloud_cache="/etc/ConsolePi/cloud.json"
override_dir="/etc/ConsolePi/overrides" # TODO NO TRAILING / make others that way
py3ver=$(python3 -V | cut -d. -f2)
yml_script="/etc/ConsolePi/src/yaml2bash.py"
tmp_src="/tmp/consolepi-temp"
warn_cnt=0
INIT="$(ps --no-headers -o comm 1)"
DEV_USER=${dev_user:-wade}  # User to use for ssh/sftp/git to local dev
if [ "$(systemctl is-active NetworkManager.service)" == "active" ] && hash nmcli 2>/dev/null && [ $(nmcli -t dev | grep -v "p2p-dev\|:lo" | wc -l) -gt 0 ]; then
    uses_nm=true
else
    uses_nm=false
fi

# Unused for now interface logic
# _gw=$(ip route get 8.8.8.8 | awk -- '{printf $5}')
# all_ifaces=($(ls /sys/class/net | grep -v lo))
# wlan_ifaces=($(cat /proc/net/wireless | tail +3 | cut -d':' -f1))
# wired_ifaces=();for _iface in "${all_ifaces[@]}"; do
#     [[ ! "${wlan_ifaces[@]}" =~ "${_iface}" ]] && [[ ! $_iface =~ "tun" ]] && wired_ifaces+=($_iface)
# done

_DEBUG_=${_DEBUG_:-false}  # verbose debugging for testing process_args
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

is_ssh() {
  if pstree -p | egrep --quiet --extended-regexp ".*sshd.*\($$\)"; then
    return 0
  else
    return 1
  fi
}

( [ -f "$final_log" ] && ( [ -z "$upgrade" ] || $upgrade ) ) && upgrade=true || upgrade=false

# log file is referenced thoughout the script.  During install dest changes from tmp to final
# location is configured in install.sh do_logging
$upgrade && log_file=$final_log || log_file=$tmp_log


# -- External Sources --
consolepi_source="https://github.com/Pack3tL0ss/ConsolePi.git"

# header reqs 144 cols to display properly
header() {
    $silent && return 0 # No Header for silent install
    [ -z $1 ] && clear -x # pass anything as an argument to prevent screen clear
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

dump_vars() {
    # debug tool. Dump all variables in the environment
    logit "dump vars called.  dumping variables from the environment"
    ( set -o posix; set ) | grep --color=auto -v "_xspecs\|LS_COLORS\|^PS.*" >> $log_file
}

menu_print() {
    # -- send array of strings to function and it will print a formatted menu
    # Args: -L|-len: set line length, this needs to be the first Argument in the first call to this function default: 121
    #            line_len is unset if you use -foot, needs to be handled by calling function if not using foot
    #       -head: str that follows is header
    #       -foot: str that follows is footer (Also unsets line_len)
    #       -li: list item 'str' becomes '  - str'
    #       -nl: new line (echo a blank line)
    #
    # Used to print post-install message
    line_len=${line_len:=121}
    while (( "$#" )); do
        case "$1" in
            -c)
                style="$2"
                shift 2
                ;;
            -L|-len)
                line_len=$2
                shift 2
                ;;
            -head)
                style=${style:-'*'}
                str=" $2 "
                len=${#str}
                [[ "$str" =~ "\e[" ]] && ((len-=11))
                [[ "$str" =~ ';1m' ]] && ((len-=2))
                left=$(( ((line_len-len))/2 ))
                [[ $((left+len+left)) -eq $line_len ]] && right=$left || right=$((left+1))
                printf -v pad_left "%*s" $left && pad_left=${pad_left// /$style}
                printf -v pad_right "%*s" $right && pad_right=${pad_right// /$style}
                printf "%s%b%s\n" "$pad_left" "$str" "$pad_right"
                shift 2
                ;;
            -foot)
                str="${style}${style}$2"
                len=${#str}
                right=$(( ((line_len-len)) ))
                printf -v pad_right "%*s" $right && pad_right=${pad_right// /$style}
                printf "%s%s\n" "$str" "$pad_right"
                shift 2
                unset line_len; unset style
                ;;
            -nl|-li|*)
                if [[ "$1" == "-nl" ]]; then
                    str=" "
                elif [[ "$1" == "-li" ]]; then
                    str="  - ${2}"
                    shift
                else
                    str="$1"
                fi
                len=${#str}
                [[ "$str" =~ "\e[" ]] && ((len-=11))
                [[ "$str" =~ ';1m' ]] && ((len-=2))
                pad_len=$(( ((line_len-len-5)) ))
                printf -v pad "%*s" $pad_len
                printf '%s %b %s %s\n' "$style" "$str" "$pad" "$style"
                shift
                ;;
        esac
    done
}

logit() {
    # Logging Function: logit <message|string> [<status|string>] [Flags (can be anywhere)]
    # usage:
    #   process="Install ConsolePi"  # Define prior to calling this func otherwise it will display UNDEFINED
    #   logit "building package" "WARNING"
    #
    #   FLAGS:
    #      -L    write to log only don't echo to stdout
    #      -E    Only echo to stdout don't write to log
    #      -t <process> set tag($cprocess) (does not change process in global scope)
    #
    # NOTE: Sending a status of "ERROR" results in the script exiting (unless called by network hook/dispatcher)
    #       default status is INFO if none provided.
    if [[ $(basename "$0" 2>/dev/null) == 'dhcpcd.exit-hook' ]] || [[ $(basename "$0" 2>/dev/null) == '02-consolepi' ]]; then
        local stop_on_error=false
    else
        local stop_on_error=true
    fi

    local args=()
    while (( "$#" )); do
        case "$1" in
            -L)
                local log_only=true
                shift
            ;;
            -E)
                local echo_only=true
                shift
            ;;
            -t)
                local process="$2"
                shift 2
            ;;
            *)
                local args+=("$1")
                shift
            ;;
        esac
    done
    set -- "${args[@]}"

    local log_only=${log_only:-false}
    local echo_only=${echo_only:-false}

    local process=${process:-"UNDEFINED"}
    local message="${1}"                                      # 1st arg = the log message

    [ -z "${2}" ] && local status="INFO" || local status=${2^^}     # 2nd Arg the log-lvl (to upper); Default: INFO
    [[ "${status}" == "DEBUG" ]] && ! $debug && return 0  # ignore / return if a DEBUG message & debug=false

    local fatal=false                                     # fatal is determined by status. default to false.  true if status = ERROR
    if [ "${status}" == "ERROR" ] || [ "${status}" == "CRITICAL" ]; then
        $stop_on_error && local fatal=true || ((warn_cnt+=1))
        local status="${_red}${status}${_norm}"
    elif [[ "${status}" != "INFO" ]]; then
        [[ "${status}" == "WARNING" ]] && ((warn_cnt+=1))
        local status="${_yellow}${status}${_norm}"
    fi

    local log_msg="$(date +"%b %d %T") [$$][${status}][${process}] ${message}"
    if $log_only; then
        echo -e "$log_msg" >> $log_file
    elif $echo_only; then
        echo -e "$log_msg"
    else
        echo -e "$log_msg" | tee -a $log_file
    fi

    # grabs the formatted date of the first log created during this run - used to parse log and re-display warnings after the install
    [ -z "$log_start" ] && log_start=$(echo "$log_msg" | cut -d'[' -f1)

    # if status was ERROR which means FATAL then log and exit script
    if $fatal ; then
        echo -e "$(date +'%b %d %T') [$$][${status}][${process}] Last Error is fatal, script exiting Please review log ${log_file}"
        echo -e "\n${_red}---- Error Detail ----${_norm}"
        grep -A 999 "${log_start}" $log_file | grep -v "^WARNING: Retrying " | grep -v "apt does not have a stable CLI interface" | grep "ERROR" -B 10 | grep -v "INFO"
        echo '--'
        $DEBUG && dump_vars  # set @ top when needed
        exit 1
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

ask_pass(){
    match=false; while ! $match; do
        read -sep "New password: " _pass && echo "$_pass" | echo  # sed -r 's/./*/g'
        read -sep "Retype new password: " _pass2 && echo "$_pass2" | echo  # sed -r 's/./*/g'
        [[ "${_pass}" == "${_pass2}" ]] && match=true || match=false
        ! $match && echo -e "ERROR: Passwords Do Not Match\n"
    done
    unset _pass2
}

get_interfaces() {
    # >> Determine interfaces to act on (fallback to hotspot/wired-dhcp (ztp))
    # provides wired_iface and wlan_iface in global scope
    if $uses_nm; then
        local wired_ifaces=($(nmcli -t dev | grep ":ethernet:" | cut -d: -f1))
        local wlan_ifaces=($(nmcli -t dev | grep ":wifi:" | cut -d: -f1))
    else
        # all_ifaces gets physical interfaces only
        local all_ifaces=($(find /sys/class/net -type l -not -lname '*virtual*' -printf '%f\n'))
        local wlan_ifaces=($(cat /proc/net/wireless | tail +3 | cut -d':' -f1 | tr -d ' '))
        local wired_ifaces=()
        for i in ${all_ifaces[@]}; do [[ ! "${wlan_ifaces[@]}" =~ "${i}" ]] && wired_ifaces+=($i); done
    fi

    if [ "${#wired_ifaces[@]}" -eq 1 ]; then
        wired_iface=${wired_ifaces[0]}
    elif [[ ${wired_ifaces[0]} =~ eth0 ]]; then
        wired_iface=eth0
    else
        local _first_iface=${wired_ifaces[0]}
        wired_iface=${_first_iface:-eth0}
    fi

    if [ "${#wlan_ifaces[@]}" -eq 1 ]; then
        wlan_iface=${wlan_ifaces[0]}
    elif [[ ${wlan_ifaces[0]} =~ wlan0 ]]; then
        wlan_iface=wlan0
    else
        local _first_iface=${wlan_ifaces[0]}
        wlan_iface=${_first_iface:-wlan0}
    fi
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
                if ! systemctl -q is-enabled ${1}.service; then
                    if [[ -f /etc/systemd/system/${1}.service ]]; then
                        sudo systemctl enable ${1}.service 1>/dev/null 2>> $log_file &&
                            logit "Success enable $1 service" ||
                            logit "FAILED to enable ${1} systemd service" "WARNING"
                    else
                        logit "Failed ${1}.service file not found in systemd after move"
                    fi
                fi
                # -- if the service is enabled and active currently restart the service --
                if [ "$(systemctl is-enabled ${1}.service 2>> $log_file)" == "enabled" ]; then
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

    # -- if file on system does not exist or does not match src copy and enable from the source directory
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
                logit "file_diff_update src file ${1} not found. You should verify contents of $2. (Please Report this eror on GitHub)" "WARNING"
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

is_speedtest_compat() {
    declare -A hw_array && compat_bash=true || compat_bash=false
    rev=$(cat /proc/cpuinfo | grep 'Revision' | awk '{print $3}')
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
        hw_array["c03130"]="Raspberry Pi 400 hw rev 1.0  4 GB  (Mfg by Sony)"
        hw_array["902120"]="Raspberry Pi Zero 2 W hw rev 1.0 512MB (Mfg by Sony UK)"
    else
        return 0
    fi
    [ -z "${hw_array[$rev]}" ] && return 0 || return 1
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
        hw_array["c03112"]="Raspberry Pi 4 Model B  hw rev 1.2  4 GB  (Mfg by Sony)"
        hw_array["c03114"]="Raspberry Pi 4 Model B  hw rev 1.4  4 GB  (Mfg by Sony)"
        hw_array["d03114"]="Raspberry Pi 4 Model B  hw rev 1.4  8 GB  (Mfg by Sony)"
        hw_array["c03130"]="Raspberry Pi 400 hw rev 1.0  4 GB  (Mfg by Sony)"
        hw_array["a03140"]="Raspberry Pi Compute Module 4 hw rev 1.0 1GB (Mfg by Sony UK)"
        hw_array["b03140"]="Raspberry Pi Compute Module 4 hw rev 1.0 2GB (Mfg by Sony UK)"
        hw_array["c03140"]="Raspberry Pi Compute Module 4 hw rev 1.0 4GB (Mfg by Sony UK)"
        hw_array["d03140"]="Raspberry Pi Compute Module 4 hw rev 1.0 8GB (Mfg by Sony UK)"
        hw_array["902120"]="Raspberry Pi Zero 2 W hw rev 1.0 512MB (Mfg by Sony UK)"
        hw_array["c04170"]="Raspberry Pi 5 Model B Rev 1.0 4GB (Mfg by Sony UK)"
        hw_array["d04170"]="Raspberry Pi 5 Model B Rev 1.0 8GB (Mfg by Sony UK)"
    fi
    $compat_bash && echo ${hw_array["$1"]} || echo $1
}

# Gather Some info about the Pi useful in triage of issues
get_pi_info() {
    process="Collect Pi Info"
    [ ! -z $branch ] && [ $branch != "master" ] && logit "Running alternate branch: ${_green}$branch${_norm}"
    git_rem=$(pushd /etc/ConsolePi >/dev/null 2>&1 && git remote -v | head -1 | cut -d '(' -f-1 ; popd >/dev/null 2>&1)
    [[ ! -z $git_rem ]] && [[ $(echo $git_rem | awk '{print $2}') != $consolepi_source ]] && logit "Using alternative repo: ${_green}$git_rem${_norm}"
    cpu=$(cat /proc/cpuinfo | grep 'Hardware' | awk '{print $3}')
    rev=$(cat /proc/cpuinfo | grep 'Revision' | awk '{print $3}')
    model_pretty=$(get_pi_info_pretty $rev 2>/dev/null)
    if [ -n "$model_pretty" ]; then
        is_pi=true
    else
        is_pi=false
        if hash dmidecode 2>/dev/null; then
            . <(dmidecode | grep "^System Information" -A2 | tail -n +2 | sed 's/: /="/' | sed 's/ /_/' | sed 's/$/"/' | tr -d "\t")
            model_pretty="$Manufacturer $Product_Name"
        fi
    fi
    logit "$model_pretty"
    [ -f /etc/os-release ] && . /etc/os-release && logit "$NAME $(head -1 /etc/debian_version) ($VERSION_CODENAME) running on $cpu Revision: $rev"
    logit "$(uname -a)"
    dpkg -l | grep -q raspberrypi-ui && (desktop=true && logit "RaspiOS with Desktop") || (desktop=false && logit "RaspiOS Lite")
    logit "Python 3 Version $(python3 -V)"
    [ $py3ver -lt 6 ] && logit "${_red}DEPRICATION WARNING:${_norm} Python 3.5 and lower is no longer be supported." "warning" &&
        logit "You should re-image ConsolePi using the current RaspiOS release" "warning"
    unset process
}

convert_template() {
    /etc/ConsolePi/src/j2render.py "$@"
    file_diff_update /tmp/${1} $2
    rm /tmp/${1} >/dev/null 2>>$log_file
}

process_yaml() {
    . <($yml_script "${@}" 2>>$log_file) ||
        logit "Error returned from yaml config import ($yml_script ${@}), check $log_file" "ERROR"
}

do_systemd_enable_load_start() {
    # provide a single argument the systemd service name without the .service extension
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

# -- Find path for any files pre-staged in user home or consolepi-stage subdir --
# default is to check for file, pass -d as 2nd arg to check for dir
get_staged_file_path() {
    [ -z "$1" ] && logit "FATAL Error find_path function passed NUL value" "CRITICAL"
    local flag=${2:-'-f'}
    if [ $flag "${home_dir}/${1}" ]; then
        found_path="${home_dir}/${1}"
    elif [ $flag "${stage_dir}/$HOSTNAME/$1" ]; then
        found_path="${stage_dir}/$HOSTNAME/${1}"  # Need to verify this is updated in update.sh set_hostname so it's valid to use here.
    elif [ $flag "${stage_dir}/$1" ]; then
        found_path="${stage_dir}/${1}"
    else
        found_path=
    fi
    echo $found_path
}

check_perms() {
    check_list=("$@")
    [[ "${check_list[@]}" =~ "-s" ]] && local silent=true || local silent=false
    for d in "${check_list[@]}"; do
        [[ "$d" == "-s" ]] && continue
        [ "$(stat -c '%G' $d)" == "consolepi" ] && grpok=true || grpok=false
        stat -c %A $d |grep -q "^....rw....$" && modok=true || modok=false
        if ! $grpok || ! $modok; then
            chgrp -R consolepi ${d} 2>> $log_file ; local rc=$?
            chmod g+w -R ${d} 2>> $log_file ; ((rc+=$?))
            [[ $rc > 0 ]] && logit "Error Returned while setting perms for $d" "WARNING" ||
                logit "Success ~ Update Permissions for $d"
        elif ! $silent; then
            logit "Permissions for $d already OK"
        fi
    done
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
    reset_vars=('cmd' 'pmsg' 'fmsg' 'cmd_pfx' 'fail_lvl' '_silent' 'out' 'stop' 'err' 'showstart' 'pname' 'pexclude' 'pkg' 'do_apt_install')
    local do_autoremove=false  # TODO check if the return is necessary may be relic from early testing
    $_DEBUG_ && echo "DEBUG: ${@}"  ## -- DEBUG LINE --
    while (( "$#" )); do
        if $_DEBUG_; then
            echo -e "DEBUG:\n\tcmd=${cmd}\n\t_silent=$_silent\n\tpmsg=${pmsg}\n\tfmsg=${fmsg}\n\tfail_lvl=$fail_lvl"
            echo -e "DEBUG TOP ~ Currently evaluating: '$1'"
        fi
        case "$1" in
            -*stop) # will stop function from exec remaining commands on failure (witout exit 1)
                local stop=true
                shift
                ;;
            -e) # will result in exit 1 if cmd fails
                local fail_lvl="ERROR"
                shift
                ;;
            -s) # only show msg if cmd fails
                local _silent=true
                shift
                ;;
            -u) # Run Command as logged in User
                [ -z "$iam" ] && iam=${SUDO_USER:-$(who -m | awk '{ print $1 }')} && logit "iam had no value" "DEV-WARNING"
                local cmd_pfx="sudo -u $iam"
                shift
                ;;
            -*nolog|-*no-log) # Don't log stderr anywhere default is to log_file
                local err="/dev/null"
                shift
                ;;
            -*stderr) # log stderr to fd specified default is to log_file
                local err="$2"
                shift 2
                ;;
            -*logit|-l) # Used to simply log a message, does not echo to tty
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
            -*nostart|--no-start) # elliminates the process start msg
                local showstart=false
                shift
                ;;
            -*apt-install) # install pkg via apt  # TODO parse params after --apt-install flag allow multiple in same line (until next -)
                local do_apt_install=true
                shift
                local go=true; while (( "$#" )) && $go ; do
                    $_DEBUG_ && echo -e "DEBUG apt -y install '$1'"
                    case "$1" in
                        --pretty=*)
                            local pname=${1/*=}
                            shift
                            ;;
                        --exclude=*)
                            local pexclude=${1/*=}
                            shift
                            ;;
                        *)
                            if [[ -z $pkg ]] ; then
                                local pkg=$1
                                [[ -z $pname ]] && local pname=$1
                                shift
                            else
                                local go=false
                            fi
                            ;;
                    esac
                done
                local pmsg=${pmsg:-"Success - install $pname (apt)"}
                local fmsg=${fmsg:-"Error - install $pname (apt)"}
                local stop=true
                [[ ! -z $pexclude ]] && local cmd="sudo apt -y install $pkg ${pexclude}-" ||
                    local cmd="sudo apt -y install $pkg"
                ;;
            -*apt-purge) # purge pkg followed by autoremove
                case "$3" in
                    --pretty=*)
                        local pname=${3/*=}
                        _shift=3
                        ;;
                    *)
                        local pname=$2
                        _shift=2
                        ;;
                esac
                local pmsg=${pmsg:-"Success - Remove $pname (apt)"}
                local fmsg=${fmsg:-"Error - Remove $pname (apt)"}
                local cmd="sudo apt -y purge $2"
                local do_autoremove=true
                shift $_shift
                ;;
            -o) # redirect stdout default is /dev/null
                local out="$2"
                shift 2
                ;;
            -*pf|-*fp) # msg template for both success and failure in 1
                local pmsg="Success - $2"
                local fmsg="Error - $2"
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
                local cmd="$1"
                shift
                ;;
        esac
        # if cmd is set process cmd
        # use defaults if flag not set
        if [[ ! -z $cmd ]]; then
            local pcmd=${cmd/sudo /} ; local pcmd=${pcmd/-y /}
            local pmsg=${pmsg:-"Success - $pcmd"}
            unset pcmd
            # local pmsg=${pmsg:-"Success - ${cmd/-y /}"}
            local fmsg=${fmsg:-"Error - $cmd  See details in $log_file"}
            local fail_lvl=${fail_lvl:-"WARNING"}
            local _silent=${_silent:-false}
            local stop=${stop:-false}
            local err=${err:-$log_file}
            local out=${out:-'/dev/null'}
            local showstart=${showstart:-true}
            local do_apt_install=${do_apt_install:-false}
            [[ ! -z $cmd_pfx ]] && local cmd="$cmd_pfx $cmd"
            if $_DEBUG_; then
                echo -e "DEBUG:\n\tcmd=$cmd\n\tpname=$pname\n\t_silent=$_silent\n\tpmsg=${pmsg}\n\tfmsg=${fmsg}\n\tfail_lvl=$fail_lvl\n\tout=$out\n\tstop=$stop\n\tret=$ret\n"
                echo "------------------------------------------------------------------------------------------"
            fi
            # -- // PROCESS THE CMD \\ --
            ! $_silent && $showstart && logit -E "Starting - ${pmsg/Success - /}"
            logit -L "process_cmds executing: $cmd"
            if eval "$cmd" >>"$out" 2> >(grep -v "^$\|^WARNING: apt does not.*CLI.*$" >>"$err") ; then # <-- Do the command
                local cmd_failed=false
                ! $_silent && logit "$pmsg"
                unset cmd
            else
                local cmd_failed=true
                if $do_apt_install ; then
                    local x=1; while [[ $(tail -2 "$log_file" | grep "^E:" | tail -1) =~ "is another process using it?" ]] && ((x<=3)); do
                        logit "dpkg appears to be in use pausing 5 seconds... before attempting retry $x" "WARNING"
                        sleep 5
                        logit "Starting ${pmsg/Success - /} ~ retry $x"
                        logit -L "process_cmds executing: $cmd"
                        if eval "$cmd" >>"$out" 2> >(grep -v "^$\|^WARNING: apt does not.*CLI.*$" >>"$err"); then
                            local cmd_failed=false
                            ! $_silent && logit "$pmsg"
                        fi
                        ((x+=1))
                    done
                fi
            fi

            if $cmd_failed ; then
                logit "$fmsg" "$fail_lvl" && ((ret+=1))
                $stop && logit "aborting remaining tasks due to previous failure" && cd $cur_dir && break
            fi
            $_DEBUG_ && echo "------------------------------------------------------------------------------------------" # -- DEBUG Line --

            # -- // unset all flags so none are passed to next cmd if sent in one big array \\ --
            for c in "${reset_vars[@]}"; do
                unset ${c}
            done
        fi

    done

    # if apt purge was in cmd list -->apt autoremove
    if $do_autoremove; then
        logit "Tidying Up packages that are no longer in use (apt autoremove)"
        sudo apt autoremove -y >/dev/null 2> >(grep -v "^$\|^WARNING: apt does not.*CLI.*$" >>$log_file) &&
            logit "Success - All Tidy Now" ||
            logit "Error - apt autoremove returned error-code" "WARNING"
    fi

    ! $cmd_failed && return 0 || return 1
}
