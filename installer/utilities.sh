#!/usr/bin/env bash

# Source Common Functions
if [ -f "/etc/ConsolePi/installer/common.sh" ]; then
    if ! type -t logit >/dev/null; then
        . /etc/ConsolePi/installer/common.sh || (echo "ERROR utilities.sh not and unable to source common.sh" && exit 1)
    fi
else
    echo "This Script depends on common.sh from ConsolePi repo"
    exit 1
fi


get_util_status () {
    UTIL_VER['tftpd']=$(in.tftpd -V 2>/dev/null | awk '{print $2}'|cut -d, -f1)
    PKG_EXPLAIN['tftpd']="tftp server"

    UTIL_VER['lldpd']=$(lldpd -v 2>/dev/null)
    PKG_EXPLAIN['lldpd']="Enables lldp on wired ports, for discovery of ConsolePi info from lldp capable device it's connected to"

    which ansible >/dev/null 2>&1 && ansible --version > /tmp/ansible_ver 2>/dev/null
    [ -f /tmp/ansible ] && UTIL_VER['ansible']=$(head -1 /tmp/ansible_ver | awk '{print $2}') || UTIL_VER['ansible']=""
    PKG_EXPLAIN['ansible']="open source automation framework/engine."

    a_role="${home_dir}/.ansible/roles/arubanetworks.aoscx_role"
    [ -f /tmp/ansible ] && aoss_dir=$(grep "ansible python module location" /tmp/ansible_ver | cut -d'=' -f 2 | cut -d' ' -f 2)/modules/network/arubaoss ||
        aoss_dir=""
    [ -f /tmp/ansible ] && pycmd=python$(tail -1 /tmp/ansible_ver | awk '{print $4}' | cut -d'.' -f 1) || pycmd=python
    which $pycmd >/dev/null 2>&1 || ( logit "Failed to determine Ansible Python Ver" "WARNING" -t "Ansible" && pycmd=python)

    cpit_status=$(dpkg -l | grep " cockpit " | awk '{print $1,$3}')
    [[ "$cpit_status" =~ "ii" ]] && UTIL_VER['cockpit']="${cpit_status/ii }" || UTIL_VER['cockpit']=
    PKG_EXPLAIN['cockpit']="Glanceable Web DashBoard with web tty (reach it on port 9090)"

    if [[ ! -z $a_role ]] && [[ -d $a_role ]]; then
        cx_mod_installed=true
    else
        cx_mod_installed=false
    fi

    if [[ ! -z $aoss_dir ]] && [[ -d $aoss_dir ]]; then
        sw_mod_installed=true
    else
        sw_mod_installed=false
    fi
    ( $cx_mod_installed || $sw_mod_installed ) && a_mod_status='partially installed' || unset a_mod_status
    ( $cx_mod_installed && $sw_mod_installed ) && a_mod_status='installed'
    UTIL_VER['aruba_ansible_modules']=$( echo $a_mod_status )
    PKG_EXPLAIN['aruba_ansible_modules']="Aruba Networks modules for ansible"
    # warn if aruba-ansible-modules is not completely installed and add option to menu to install
    if [[ $a_mod_status == 'partially installed' ]]; then
        process="build utilities menu"
        ! $cx_mod_installed && UTIL_VER['aruba_ansible_cx_mod']= &&
            logit "aruba-ansible-modules is partially installed, the aoscx_role available on ansible-galaxy is missing" "WARNING"
        ! $sw_mod_installed && UTIL_VER['aruba_ansible_sw_mod']= &&
            logit "aruba-ansible-modules is partially installed, the aos-sw modules deployed via aruba-ansible-module-installer.py is missing" "WARNING"
        unset process
    fi
    [ -z "$model_pretty" ] && get_pi_info > /dev/null
    if [ "$is_pi" == "false" ] || [[ "$model_pretty" =~ "Pi 4" ]] ; then
        UTIL_VER['speed_test']=$( [ -f /var/www/speedtest/speedtest.js ] && echo installed )
        PKG_EXPLAIN['speed_test']="self-hosted network speed-test"
    else
        process='consolepi-extras'
        logit "consolepi-extras (optional utilities/packages installer) omitted speed test option not >= Pi 4"
        unset process
    fi
    # UTIL_VER['wireshark~tshark']=$( which wireshark )
    # PKG_EXPLAIN['wireshark~tshark']="packet capture software"
    util_list_i=($(for u in ${!UTIL_VER[@]}; do echo $u; done | sort))
    util_list_f=($(for u in ${!UTIL_VER[@]}; do echo $u; done | sort -rn))

    sep=': '; i=0; for u in ${util_list_i[@]}; do
        pretty=${u//_/ }
        [[ "$u" =~ "sw_mod" ]] && pretty="Install Missing aos-switch Ansible Module" && sep=''
        [[ "$u" =~ "cx_mod" ]] && pretty="Install Missing aos-cx Ansible Module" && sep=''
        ASK_OPTIONS[$i]=$u; ((i+=1)) # hidden tag
        if [ -z "${UTIL_VER[$u]}" ]; then
            ASK_OPTIONS[$i]="${pretty}${sep}${PKG_EXPLAIN[$u]}"; ((i+=1)) # item text formatted version of tag
            ASK_OPTIONS[$i]=NO; ((i+=1)) # item not checked (not installed)
        else
            if [[ ${UTIL_VER[$u]} = [0-9]* ]]; then
                ASK_OPTIONS[$i]="$pretty (v${UTIL_VER[$u]} currently installed)"; ((i+=1)) # item text tag + version
            else
                ASK_OPTIONS[$i]="$pretty (${UTIL_VER[$u]})"; ((i+=1)) # item text tag + version formatted when v# doesn't apply
            fi
            ASK_OPTIONS[$i]=YES; ((i+=1)) # item is checked (installed)
            INSTALLED+=($u) # add item to installed array for change comparison after selection
        fi
    done
    # echo -e "---\nDEBUG\n${ASK_OPTIONS[@]}\n---" # -- DEBUG LINE --

    # -- CLEANUP --
    [ -f /tmp/ansible_ver ] && rm /tmp/ansible_ver 2>>$log_file
}

do_ask() {
    list_len=${#UTIL_VER[@]}
    if [ ! -z "$ASK_OPTIONS" ]; then
        # height width list-height
        utils=$(whiptail --notags --nocancel --separate-output --title "Optional Packages/Tools" --backtitle "$backtitle"  \
        --checklist "\nUse SpaceBar to toggle\nSelect item to Install, Un-Select to Remove" $((list_len+10)) 125 $list_len \
        "${ASK_OPTIONS[@]}" 3>&1 1>&2 2>&3)
        # return to util_main if user pressed esc
        ret=$? && [[ $ret != 0 ]] && return $ret
        utils=($utils)
        # add ansible if aruba-ansible-modules was selected without selecting ansible
        if [[ " ${utils[@]} " =~ ' aruba_ansible_modules ' ]] && [[ ! " ${utils[@]} " =~ " ansible " ]] && [[ -z "${UTIL_VER['ansible']}" ]]; then
                process="aruba-ansible-modules"
                utils+=('ansible')
                logit "adding ansible to install list - reqd for aruba-ansible-modules"
                unset process
        fi
        for u in ${!UTIL_VER[@]}; do
            [[ " ${utils[@]} " =~ " ${u} " ]] && printf -v "$u" true || printf -v "$u" false
        done
        return 0
    else
        return 1
    fi
}

util_exec() {
    util=$1
    [[ -z $PROCESS ]] && process=${util//_/ } || process=$PROCESS
    apt_pkg_name=$(get_apt_pkg_name $util)
    case "$1" in
        tftpd)

            if [[ $2 == "install" ]]; then

                sudo netstat -lnpu | grep -q ":69\s.*" && in_use=true || in_use=false
                if $in_use; then
                    logit "tftpd package is not installed, but the port is in use tftpd-hpa will likely fail to start" "WARNING"
                    logit "Investigate after the install.  Check for uncommented lines in /etc/inetd.conf or /etc/xinetd.conf"
                fi

                cmd_list=(
                    "-apt-install" "$apt_pkg_name" "--pretty=tftpd" \
                    "-pf" "Configure tftpd defaults" "file_diff_update ${src_dir}tftpd-hpa /etc/default/tftpd-hpa" \
                    "-nostart" "-pf" "Restart tftpd-hpa service" "sudo systemctl restart tftpd-hpa" \
                    "-nostart" "-pf" "change ownership on tftp root dir /srv/tftp" "sudo chown -R tftp:consolepi /srv/tftp" \
                    "-nostart" "-pf" "change permissions on tftp root dir /srv/tftp" "sudo chmod -R g+w /srv/tftp" \
                )

            elif [[ $2 == "remove" ]]; then
                cmd_list=(
                    "-apt-purge" "$apt_pkg_name" "--pretty=tftpd" \
                    "-logit" "The directory (/srv/tftp) created for tftp and any files in it was left unchanged" \
                )
            fi
            ;;
        lldpd)
            if [[ $2 == "install" ]]; then
                cmd_list=(
                    "-apt-install" "$apt_pkg_name" \
                    "-s" "-pf" "configure consolepi-lldp.conf" "file_diff_update ${src_dir}consolepi-lldpd.conf /etc/lldpd.d/consolepi-lldpd.conf" \
                    "-s" "-pf" "Restart lldpd service" "sudo systemctl restart lldpd" \
                )
            elif [[ $2 == "remove" ]]; then
                if [ -f /etc/lldpd.d/consolepi-lldpd.conf ]; then
                    sudo rm /etc/lldpd.d/consolepi-lldpd.conf 2>/dev/null || logit "Error returned while attempting to remove /etc/lldpd.d/consolepi-lldpd.conf" "WARNING"
                fi
                cmd_list=(
                    "-apt-purge" "$apt_pkg_name" \
                )
            fi
            ;;
        ansible)
            if [[ $2 == "install" ]]; then
                cmd_list=(
                    "-l" "adding ansible repo to apt sources"
                    "-s" "-f" "failed to update apt sources with ansible repo" 'echo "deb http://ppa.launchpad.net/ansible/ansible/ubuntu trusty main" > /etc/apt/sources.list.d/ansible.list' \
                    "-s" "apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 93C4A3FD7BB9C367" \
                    "apt update" \
                    "-apt-install" "$apt_pkg_name"
                    )
            elif [[ $2 == "remove" ]]; then
                cmd_list=(
                    "-apt-purge" "$apt_pkg_name" \
                    "-s" "rm /etc/apt/sources.list.d/ansible.list" \
                    '-logit' "ansible removed however the hidden directory (.ansible) created in the /home/<user>/.ansible and any files in it were retained" \
                    )
            fi
            ;;
        aruba_ansible_modules|aruba_ansible_cx_mod|aruba_ansible_sw_mod)
            if [[ $2 == "install" ]]; then
                declare -a cmd_list
                if [[ $1 == "aruba_ansible_modules" ]] || [[ $1 == "aruba_ansible_cx_mod" ]] ; then
                    cmd_list=('-stop' '-u' '-pf' 'Install aoscx_role from ansible-galaxy' "ansible-galaxy install arubanetworks.aoscx_role")
                fi

                if [[ $1 == "aruba_ansible_modules" ]] || [[ $1 == "aruba_ansible_sw_mod" ]] ; then
                    if [[ ! -d "${home_dir}/aruba-ansible-modules" ]]; then
                        cmd_list+=('-stop' '-pf' "Clone aruba-ansible-modules from Git Repo" "-u" "git clone https://github.com/aruba/aruba-ansible-modules.git ${home_dir}/aruba-ansible-modules")
                    else
                        cmd_list+=('-logit' 'Aruba Ansible Modules repo appears to exist already, Updating (git pull)'
                                '-s' "pushd ${home_dir}/aruba-ansible-modules" \
                                '-stop' '-u' '-pf' 'Update aruba-ansible-modules (Git)' 'git pull' \
                                '-s' 'popd')
                    fi
                    cmd_list+=("-pf" "execute aruba_module_installer.py" "sudo python ${home_dir}/aruba-ansible-modules/aruba_module_installer/aruba_module_installer.py")
                fi

            elif [[ $2 == "remove" ]]; then
                cmd_list=('-stop' '-u' '-pf' 'remove aoscx_role from ansible roles path' "ansible-galaxy remove arubanetworks.aoscx_role")
                if [[ -f ${home_dir}/aruba-ansible-modules/aruba_module_installer/aruba_module_installer.py ]]; then
                    cmd_list+=("-pf" "remove everything deployed by aruba_module_installer.py" "sudo $pycmd ${home_dir}/aruba-ansible-modules/aruba_module_installer/aruba_module_installer.py -r")
                else
                    cmd_list+=('-logit' "Unable to find aruba_module_installer exec to remove modules installed via script - Ensure you are logged in w/ the same user used to install" "WARNING")
                fi
            fi
            ;;
        speed_test)
            if [[ $2 == "install" ]]; then
                cmd_list=(
                    "-stop" "-u" "-s" "-f" "failed to created directory .git_repos" "mkdir -p ${home_dir}/.git_repos"
                )

                if [ ! -d ${home_dir}/.git_repos/speedtest/.git ] ; then
                    cmd_list+=(
                        "-stop" "-pf" "Clone speedtest from GitHub" "-u"
                            "git clone https://github.com/librespeed/speedtest.git ${home_dir}/.git_repos/speedtest"
                    )
                else
                    cmd_list+=(
                        "-s" "pushd ${home_dir}/.git_repos/speedtest"
                        "-stop" "-u" "-pf" "Update speedtest (GitHub)" "git pull"
                        "-s" "popd"
                        )
                fi

                cmd_list+=(
                    "-logit" 'Configuring SpeedTest...'
                    "-s" "mkdir -p /var/www/speedtest"
                    "-s" "pushd ${home_dir}/.git_repos/speedtest"
                    "-stop" "-s" "cp -R backend examples/example-singleServer-gauges.html *.js /var/www/speedtest"
                    "-s" "pushd /var/www/speedtest"
                    "-s" "mv example-singleServer-gauges.html index.html"
                    "-s" "sed -i 's/LibreSpeed Example/ConsolePi SpeedTest/' /var/www/speedtest/index.html"
                    "-s" "sed -i 's/Source code/LibreSpeed on GitHub/' /var/www/speedtest/index.html"
                    "-s" "-pf" "Updating Permissions" "chown -R www-data * "
                    "-s" "popd && popd"
                    "-apt-install" "apache2"
                    "-apt-install" "php"
                    "-apt-install" "libapache2-mod-php"
                    "-stop" "-s" "a2dissite 000-default"
                    "-pf" "Move apache2 SpeedTest conf file into sites-available"
                        "file_diff_update ${src_dir}010-speedtest.conf /etc/apache2/sites-available/010-speedtest.conf"
                    "-pf" "Enable apache2 SpeetTest conf" "a2ensite 010-speedtest"
                    "systemctl restart apache2"
                    )
            elif [[ $2 == "remove" ]]; then
                echo -e "\n\t-------------------------------------------------"
                echo -e "\t speed-test removal not implemented yet"
                echo -e "\t remove speed-test files in /var/www/speedtest"
                echo -e "\t remove packages: apache2 php libapache2-mod-php"
                echo -e "\t rmdir .git-repos/speedtest from home dir"
                echo -e "\t-------------------------------------------------\n"
                return 1
            fi
            ;;
        cockpit)
            if [[ $2 == "install" ]]; then
                cmd_list=(
                    "-s" "-pf" "Update /etc/bash/bashrc for cockpit ~ ConsolePi"
                    "echo -e \"# read consolepi profile script for cockpit tty\\nif [ ! -z \\\$COCKPIT_REMOTE_PEER ] && [[ ! \\\"\\\$PATH\\\" =~ \\\"consolepi-commands\\\" ]] ; then\\n\\t[ -f \\\"/etc/ConsolePi/src/consolepi.sh\\\" ] && . /etc/ConsolePi/src/consolepi.sh\\nfi\" >>/etc/bash.bashrc"
                    "-logit" 'Installing cockpit this will take a few...'
                    "-apt-install" "$apt_pkg_name" "--pretty=CockPit" "--exclude=cockpit-networkmanager"
                )
            elif [[ $2 == "remove" ]]; then
                cmd_list=(
                    "-logit" 'Removing cockpit this will take a few...'
                    "-s" "-f" "remove cockpit ~ ConsolePi lines from /etc/bash/bashrc"
                        "sed -i '/consolepi profile script for cockpit tty/,/fi/d' /etc/bash.bashrc"
                    "-apt-purge" "$apt_pkg_name"
                )
            fi
            ;;
        *)
            if [[ $2 == "install" ]]; then
                cmd_list=("-apt-install" "$apt_pkg_name")
            elif [[ $2 == "remove" ]]; then
                cmd_list=("-apt-purge" "$apt_pkg_name")
            fi
            ;;
    esac
    if [[ $2 == "remove" ]] && ! $FORCE; then
        prompt="Please Confirm - Remove $util from system"
        ch=$(user_input_bool)
    else
        ch=true
    fi
    $ch && process_cmds "${cmd_list[@]}" && logit "Done - $2 $process Completed without issue." || logit "Done - $2 $process Completed WARNINGS Occurred." "WARNING"
}

# translate menu tag to pkg name when a prettier name is used in the menu
get_apt_pkg_name() {
    case "$1" in
    tftpd)
        echo tftpd-hpa
        ;;
    *)
        echo $1
        ;;
    esac
}

argparse() {
    PARAMS=""
    PROCESS=""
    FORCE=false
    FORCE_INSTALL=false
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

util_main() {
    # when script is called without arguments present menu to select pre-selected optional
    # Utilities to install otherwise install/uninstall packages given in arguments
    # where install/uninstall determination will be the inverse of the current installed state
    if [ -z $1 ]; then
    # -- // GLOBALS \\ --
        declare -A UTIL_VER
        declare -A PKG_EXPLAIN
        declare -a INSTALLED
        declare -a ASK_OPTIONS
        get_util_status
        if do_ask; then
            # perform install / uninstall based on selections
            for u in ${!UTIL_VER[@]}; do
                if [[ " ${INSTALLED[@]} " =~ " $u " ]]; then
                    case "$u" in
                        ansible) # hackish work-around to ensure modules are uninstalled first if both ansible and the modules are selected for uninstall
                            if [[ " ${INSTALLED[@]} " =~ " aruba_ansible_modules " ]]; then
                                ! $aruba_ansible_modules && util_exec "aruba_ansible_modules" "remove"
                                ! ${!u} && util_exec $u "remove"
                                skip_mod=true
                            else
                                skip_mod=false
                            fi
                            ;;
                        aruba_ansible_modules)
                            $skip_mod || ( ! ${!u} && util_exec $u "remove" )
                            ;;
                        *)
                            ! ${!u} && util_exec $u "remove"
                            ;;
                    esac
                else
                    ${!u} && util_exec $u "install"
                fi
            done
        fi
    else
        argparse "${@}"
        for u in $PARAMS; do
            which $u >/dev/null && is_installed=true || is_installed=false
            [[ -z $PROCESS ]] && process=$u || process=$PROCESS
            if $is_installed && ! $FORCE_INSTALL; then
                util_exec $u "remove"
            else
                if ! $is_installed; then
                    util_exec $u "install"
                else
                    # [[ -z $PROCESS ]] && process=$u || process=$PROCESS
                    logit "$u already installed"
                fi
            fi
        done
    fi

    # unset process
}

# -- // SCRIPT ROOT \\ --
if [[ ! $0 == *"ConsolePi" ]] && [[ $0 == *"utilities.sh"* ]] &&  [[ ! "$0" =~ "update.sh" ]]; then
    backtitle="ConsolePi Extras"
    util_main ${@}
else
    $debug && process="utilities script start" && logit "script called from ${0}" "DEBUG"
    unset process
    backtitle="ConsolePi Installer"
    return 0
fi
