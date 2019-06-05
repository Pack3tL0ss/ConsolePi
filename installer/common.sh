#!/usr/bin/env bash

# Common functions used by ConsolePi's various scripts
# Author: Wade Wells
# Last Update: June 4 2019

# -- Installation Defaults --
INSTALLER_VER=23
CFG_FILE_VER=3
cur_dir=$(pwd)
iam=$(who am i | awk '{print $1}')
consolepi_dir="/etc/ConsolePi/"
src_dir="${consolepi_dir}src/"
orig_dir="${consolepi_dir}originals/"
home_dir="/home/${iam}/"
stage_dir="${home_dir}ConsolePi_stage/"
default_config="/etc/ConsolePi/ConsolePi.conf"
wpa_supplicant_file="/etc/wpa_supplicant/wpa_supplicant.conf"
tmp_log="/tmp/consolepi_install.log" 
final_log="/var/log/ConsolePi/install.log"
boldon="\033[1;32m"
boldoff="$*\033[m"

[[ $( ps -o comm -p $PPID | tail -1 ) == "sshd" ]] && ssh=true || ssh=false
[[ -f $final_log ]] && upgrade=true || upgrade=false

# log file is referenced thoughout the script.  During install changes from tmp to final after final log
# location is configured in install.sh do_logging
$upgrade && log_file=$final_log || log_file=$tmp_log


# -- External Sources --
# ser2net_source="https://sourceforge.net/projects/ser2net/files/latest/download" ## now points to gensio not ser2net
ser2net_source="https://sourceforge.net/projects/ser2net/files/ser2net/ser2net-3.5.1.tar.gz/download"
consolepi_source=" --single-branch --branch Clustering https://github.com/Pack3tL0ss/ConsolePi.git"


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
        echo "$(date +'%b %d %T') ${process} [${status}] Last Error is fatal, script exiting Please review log in /etc/ConsolePi/installer" && exit 1
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
        read -p "${prompt}" result
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
        read -p "${prompt}? (Y/N): " response
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
