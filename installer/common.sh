#!/usr/bin/env bash

# Common functions used by ConsolePi's various scripts
# Author: Wade Wells
# Last Update: June 4 2019

# -- Installation Defaults --
INSTALLER_VER=30
CFG_FILE_VER=4
cur_dir=$(pwd)
iam=$(who | awk '{print $1}')
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
boldon="\033[1;32m"
boldoff="$*\033[m"

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


header() {
    clear
    echo "                                                                                                                                                ";
    echo "                                                                                                                                                ";
    echo "        CCCCCCCCCCCCC                                                                     lllllll                   PPPPPPPPPPPPPPPPP     iiii  ";
    echo "     CCC::::::::::::C                                                                     l:::::l                   P::::::::::::::::P   i::::i ";
    echo "   CC:::::::::::::::C                                                                     l:::::l                   P::::::PPPPPP:::::P   iiii  ";
    echo "  C:::::CCCCCCCC::::C                                                                     l:::::l                   PP:::::P     P:::::P        ";
    echo " C:::::C       CCCCCC   ooooooooooo   nnnn  nnnnnnnn        ssssssssss      ooooooooooo    l::::l     eeeeeeeeeeee    P::::P     P:::::Piiiiiii ";
    echo "C:::::C               oo:::::::::::oo n:::nn::::::::nn    ss::::::::::s   oo:::::::::::oo  l::::l   ee::::::::::::ee  P::::P     P:::::Pi:::::i ";
    echo "C:::::C              o:::::::::::::::on::::::::::::::nn ss:::::::::::::s o:::::::::::::::o l::::l  e::::::eeeee:::::eeP::::PPPPPP:::::P  i::::i ";
    echo "C:::::C              o:::::ooooo:::::onn:::::::::::::::ns::::::ssss:::::so:::::ooooo:::::o l::::l e::::::e     e:::::eP:::::::::::::PP   i::::i ";
    echo "C:::::C              o::::o     o::::o  n:::::nnnn:::::n s:::::s  ssssss o::::o     o::::o l::::l e:::::::eeeee::::::eP::::PPPPPPPPP     i::::i ";
    echo "C:::::C              o::::o     o::::o  n::::n    n::::n   s::::::s      o::::o     o::::o l::::l e:::::::::::::::::e P::::P             i::::i ";
    echo "C:::::C              o::::o     o::::o  n::::n    n::::n      s::::::s   o::::o     o::::o l::::l e::::::eeeeeeeeeee  P::::P             i::::i ";
    echo " C:::::C       CCCCCCo::::o     o::::o  n::::n    n::::nssssss   s:::::s o::::o     o::::o l::::l e:::::::e           P::::P             i::::i ";
    echo "  C:::::CCCCCCCC::::Co:::::ooooo:::::o  n::::n    n::::ns:::::ssss::::::so:::::ooooo:::::ol::::::le::::::::e        PP::::::PP          i::::::i";
    echo "   CC:::::::::::::::Co:::::::::::::::o  n::::n    n::::ns::::::::::::::s o:::::::::::::::ol::::::l e::::::::eeeeeeeeP::::::::P          i::::::i";
    echo "     CCC::::::::::::C oo:::::::::::oo   n::::n    n::::n s:::::::::::ss   oo:::::::::::oo l::::::l  ee:::::::::::::eP::::::::P          i::::::i";
    echo "        CCCCCCCCCCCCC   ooooooooooo     nnnnnn    nnnnnn  sssssssssss       ooooooooooo   llllllll    eeeeeeeeeeeeeePPPPPPPPPP          iiiiiiii";
    echo "                                                                                                                                                ";
    echo "                                                                                                                                                ";
}

# -- Logging function prints to terminal and log file assign value of process prior to calling logit --
logit() {
    # Logging Function: logit <process|string> <message|string> [<status|string>]
    # usage:
    #   process="Install ConsolePi"
    #   logit "building package" <"WARNING">
    [ -z "$process" ] && process="UNDEFINED"
    message=$1                                      # 1st arg = the log message
    fatal=false                                     # fatal is determined by status. default to false.  true if status = ERROR
    if [[ -z "${2}" ]]; then                        # 2nd argument is status default to INFO
        status="INFO"
    else
        status=$2
        [[ "${status}" == "ERROR" ]] && fatal=true
    fi
    
    # Log to stdout and log-file
    echo "$(date +"%b %d %T") ${process} [${status}] ${message}" | tee -a $log_file
    # if status was ERROR which means FATAL then log and exit script
    if $fatal ; then
        # move_log
        echo "$(date +'%b %d %T') ${process} [${status}] Last Error is fatal, script exiting Please review log ${log_file}" && exit 1
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
    if [[ -f /etc/ConsolePi/src/systemd/${1}.service ]] && [[ -f /etc/systemd/system/${1}.service ]]; then
        mdns_diff=$(diff -s /etc/ConsolePi/src/systemd/${1}.service /etc/systemd/system/${1}.service) 
    else
        mdns_diff="doit"
    fi

    # -- if systemd file doesn't exist or doesn't match copy and enable from the source directory
    if [[ ! "$mdns_diff" = *"identical"* ]]; then
        if [[ -f /etc/ConsolePi/src/systemd/${1}.service ]]; then 
            sudo cp /etc/ConsolePi/src/systemd/${1}.service /etc/systemd/system 1>/dev/null 2>> $log_file &&
                logit "${1} systemd service created/updated" || 
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
}

# arg1 = full path of src file, arg2 = full path of file in final path
file_diff_update() {
    # -- If both files exist check if they are different --
    if [[ -f ${1} ]] && [[ -f ${2} ]]; then
        this_diff=$(diff -s ${1} ${2}) 
    else
        this_diff="doit"
    fi

    # -- if file on system doesn't exist or doesn't match src copy and enable from the source directory
    if [[ ! "$this_diff" = *"identical"* ]]; then
        if [[ -f ${1} ]]; then 
            if [ -f ${2} ]; then        # if dest file exists but doesn't match stash in bak dir
                sudo cp $2 $bak_dir 1>/dev/null 2>> $log_file &&
                    logit "${2} backed up to bak dir" || 
                    logit "FAILED to backup existing ${2}" "WARNING"
            fi

            if [ ! -d ${2%/*} ]; then
                logit "Creating ${2%/*} directory as it doesn't exist"
                sudo mkdir -p ${2%/*} || logit "Error Creating ${2%/*} directory"
            fi

            sudo cp ${1} ${2} 1>/dev/null 2>> $log_file &&
                logit "${2} created/updated" || 
                logit "FAILED to create/update ${2}" "WARNING"
        else
            logit "${1} file not found in src directory.  git pull failed?" "WARNING"
        fi
    else
        logit "${2} is current"
    fi
}

get_ser2net() {
    mapfile -t _aliases < <( cat /etc/ser2net.conf | grep ^70[0-9][0-9] | grep ^70[0-9][0-9]: | cut -d'/' -f3 | cut -d':' -f1 )
    mapfile -t _ports < <( cat /etc/ser2net.conf | grep ^70[0-9][0-9] | grep ^70[0-9][0-9]: | cut -d':' -f1 )
}

# Hung Terminal Helper
do_kill_hung_ssh() {
    dev_name=${1##*/}
    echo $HOSTNAME $dev_name - ${1}
    sudo pkill -SIGTERM -ns $(ps auxf | grep -v grep | grep $dev_name | awk '{print $2}')
}