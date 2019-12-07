#!/usr/bin/env bash

if [ -f "/etc/ConsolePi/installer/common.sh" ]; then
    if ! type -t logit >/dev/null; then
        . /etc/ConsolePi/installer/common.sh || (echo "ERROR utilities.sh not and unable to source common.sh" && exit 1)
    fi
else
    echo "This Script depends on common.sh from ConsolePi repo"
    exit 1
fi
DEBUG=$debug
process=

get_util_status () {
    FORCE=false
    UTIL_VER['tftpd']=$(in.tftpd -V 2>/dev/null | awk '{print $2}'|cut -d, -f1)
    UTIL_VER['lldpd']=$(lldpd -v 2>/dev/null)
    UTIL_VER['ansible']=$(ansible --version 2>/dev/null | head -1 | awk '{print $2}')
    # UTIL_VER['speed_test']=$(echo placeholder speed_test not automated yet)
    # UTIL_VER['tshark']=$(echo placeholder tshark not automated yet)

    i=0; for u in ${!UTIL_VER[@]}; do
        ASK_OPTIONS[$i]=$u; ((i+=1))
        if [ -z "${UTIL_VER[$u]}" ]; then
            ASK_OPTIONS[$i]=$u; ((i+=1))
            ASK_OPTIONS[$i]=NO; ((i+=1))
        else
            ASK_OPTIONS[$i]="$u (v${UTIL_VER[$u]} currently installed)"; ((i+=1))
            ASK_OPTIONS[$i]=YES; ((i+=1))
            INSTALLED+=($u)
        fi
    done
}

do_ask() {
    if [ ! -z "$ASK_OPTIONS" ]; then
        utils=$(whiptail --separate-output --notags --nocancel --title "Optional Packages/Tools" --backtitle "ConsolePi-Installer"  \
        --checklist "\nUse SpaceBar to toggle\nSelect item to Install, Un-Select to Remove\n\nMake No Changes to Continue without change" 15 50 5 \
        "${ASK_OPTIONS[@]}" 3>&1 1>&2 2>&3)
        for u in ${!UTIL_VER[@]}; do
            [[ $utils =~ "$u" ]] && printf -v "$u" true || printf -v "$u" false
        done
    fi
}

do_pre() {
    case "$1" in
        tftpd)
            if [[ $2 == "install" ]]; then
                sudo netstat -lnpu | grep -q ":69\s.*" && in_use=true || in_use=false
                if $in_use; then
                    logit "tftpd package is not installed, but the port is in use tftpd-hpa will likely fail to start" "WARNING"
                    logit "Investigate after the install.  Check for uncommented lines in /etc/inetd.conf or /etc/xinetd.conf"
                fi
            fi
            ;;
        lldpd)
            if [[ $2 == "remove" ]]; then
                if [ -f /etc/lldpd.d/consolepi-lldpd.conf ]; then
                    sudo rm /etc/lldpd.d/consolepi-lldpd.conf || logit "Error returned while attempting to remove /etc/lldpd.d/consolepi-lldpd.conf" "WARNING"
                fi
            fi
            ;;
        *)
            ;;
    esac
}

do_post() {
    case "$1" in
        tftpd)
            if [[ $2 == "install" ]]; then
                file_diff_update ${src_dir}tftpd-hpa /etc/default/tftpd-hpa || logit "Error returned while attempting to copy tftpd-hpa to /etc/default/" "WARNING"
                sudo systemctl restart tftpd-hpa && logit "tftpd-hpa service started" || logit "failed to start tftpd-hpa service" "WARNING"
                sudo chown -R tftp:consolepi /srv/tftp && sudo chmod -R g+w /srv/tftp || logit "Failed to change ownership/permissions on tftp root dir /srv/tftp" "WARNING"
            elif [[ $2 == "remove" ]]; then
                logit "The directory (/srv/tftp) created for tftp and any files in it will remain after removal"
            fi
            ;;
        lldpd)
            if [[ $2 == "install" ]]; then
                file_diff_update ${src_dir}consolepi-lldpd.conf /etc/lldpd.d/consolepi-lldpd.conf || logit "Error returned while attempting to copy consolepi-lldp.conf" "WARNING"
                sudo systemctl restart lldpd && logit "lldpd started" || logit "failed to start lldpd service" "WARNING"
            fi
            ;;
        tftpd)
            if [[ $2 == "install" ]]; then
                pass=null # placeholder
            elif [[ $2 == "remove" ]]; then
                logit "The hidden directory (.ansible) created in the user home dir and any files in it will remain after removal"
            fi
            ;;
        *)
            ;;
    esac
}

get_apt_pkg_name() {
    [[ $1 == "tftpd" ]] && echo tftpd-hpa || echo $1
}

do_util_install() {
    util=$1
    # process=$util
    echo "$FUNCNAME process $process"
    # check to see if util is already installed
    [ -z "${UTIL_VER[$util]}" ] && util_installed=false || util_installed=true
    # process any pre-checks
    do_pre $util "install"

    logit "Installing $util"
    apt_pkg_name=$(get_apt_pkg_name $util)
    sudo apt-get -y install $apt_pkg_name >/dev/null 2>>$log_file && install_success=true || install_success=false
    if $install_success; then
        logit "Success - $apt_pkg_name Installed"
        do_post $util "install"
    else
        logit "Failed to install $apt_pkg_name" "WARNING"
    fi

    $install_success && return 0 || return 1
}

do_util_uninstall() {
    util=$1
    # process=$util
    $FORCE && go=true || (
        $(prompt="Uninstall $util"; user_input_bool) && go=true || go=false
    )

    if $go; then
        logit "UnInstalling $util"
        do_pre $util "remove"
        apt_pkg_name=$(get_apt_pkg_name $util)
        sudo apt-get -y purge $apt_pkg_name >/dev/null 2>>$log_file && remove_success=true || remove_success=false
        if $remove_success; then
            logit "Success - $apt_pkg_name Removed"
        else
            logit "Failed to remove $apt_pkg_name check log @ $log_file" "WARNING"
        fi
    fi
}

util_main() {
    # when script is called without arguments present menu to select pre-selected optional
    # Utilities to install otherwise install/uninstall packages given in arguments
    # where install/uninstall determination will be the inverse of the current installed state
    if [ -z $1 ]; then
    # -- // GLOBALS \\ --
        declare -A UTIL_VER
        declare -a INSTALLED
        declare -a ASK_OPTIONS
        get_util_status
        do_ask
        # perform install / uninstall based on selections
        for u in ${!UTIL_VER[@]}; do
            if [[ "${INSTALLED[@]}" =~ "$u" ]]; then
                ! ${!u} && do_util_uninstall $u
            else
                ${!u} && do_util_install $u
            fi
        done
    else
        argparse "${@}"
        # [[ ${@} =~ '-F' ]] && FORCE=true
        # ARGS=${@/'-F'/}
        # ARGS=${ARGS/'-I'/}
        [[ ! -z $PROCESS ]] && process=$PROCESS || process=""
        for u in $PARAMS; do
            which $u >/dev/null && is_installed=true || is_installed=false
            if $is_installed && ! $FORCE_INSTALL; then
                do_util_uninstall $u
            else
                if ! $is_installed; then
                    do_util_install $u 
                else
                    [[ -z $process ]] && process=$u
                    logit "$u already installed"
                fi
            fi
        done
    fi

    unset process
}

argparse() {
    PARAMS=""
    PROCESS=""
    while (( "$#" )); do
    case "$1" in
        -p)
        PROCESS=$2
        shift 2
        ;;
        -F)
        FORCE=true
        shift
        ;;
        -I)
        FORCE_INSTALL=true
        shift
        ;;
        --) # end argument parsing
        shift
        break
        ;;
        -*|--*=) # unsupported flags
        echo "Error: Unsupported flag $1" >&2
        exit 1
        ;;
        *) # preserve positional arguments
        PARAMS="$PARAMS $1"
        shift
        ;;
    esac
    done
    # set positional arguments in their proper place
    eval set -- "$PARAMS"
}

if [[ ! $0 == *"ConsolePi" ]] && [[ $0 == *"src/consolepi-addconsole.sh"* ]] &&  [[ ! "$0" =~ "install2.sh" ]]; then
    util_main ${@}
else
    $DEBUG && process="utilities script start" && logit "script called from ${0}" "DEBUG"
fi
