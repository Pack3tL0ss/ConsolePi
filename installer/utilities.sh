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
    # -- TFTP --
    UTIL_VER['tftpd']=$(in.tftpd -V 2>/dev/null | awk '{print $2}'|cut -d, -f1)
    PKG_EXPLAIN['tftpd']="tftp server"

    # -- LLDP --
    UTIL_VER['lldpd']=$(lldpd -v 2>/dev/null)
    PKG_EXPLAIN['lldpd']="Enables lldp on wired ports, for discovery of ConsolePi info from lldp capable device it's connected to"

    # -- ANSIBLE --
    # Add local users PATH as ansible is only exposed in users PATH (not root)
    [ -d "${home_dir}/.local/bin" ] && PATH="$PATH:${home_dir}/.local/bin"
    [ "$iam" != "consolepi" ] && [ -d "/home/consolepi/.local/bin" ] && PATH="$PATH:/home/consolepi/.local/bin"
    which ansible >/dev/null 2>&1 && ansible --version > /tmp/ansible_ver 2>/dev/null
    [ -f /tmp/ansible_ver ] && UTIL_VER['ansible']=$(head -1 /tmp/ansible_ver | tr -d '[]' | cut -d' ' -f3) || UTIL_VER['ansible']=""
    PKG_EXPLAIN['ansible']="open source automation framework/engine."

    # This checks for the collection under the current user consolepi user and global locations
    # ansible-galaxy collection list wouldn't work as script is ran as root and
    # FIXME  these rely on /tmp/ansible_ver which may not be installed at this point.  Need collection installer to figure it out when it goes to install
    if [ -f /tmp/ansible_ver ]; then
        col_dirs=$(cat /tmp/ansible_ver | grep "collection location" | cut -d= -f2 | tr -d ' ' | sed "s|/root|${home_dir}|")
        [ "$iam" != "consolepi" ] && col_dirs=$col_dirs:$(cat /tmp/ansible_ver | grep "collection location" | cut -d= -f2 | cut -d: -f1 | tr -d ' ' | sed "s|/root|/home/consolepi|")
        col_dirs=($(echo ${col_dirs//:/' '}))

        cx_mod_installed=false ; sw_mod_installed=false ; cen_mod_installed=false
        for d in ${col_dirs[@]}; do
            if [ -d $d/ansible_collections/arubanetworks ]; then
                ! $cx_mod_installed && ls -1 $d/ansible_collections/arubanetworks | grep -q aoscx && cx_mod_installed=true
                ! $sw_mod_installed && ls -1 $d/ansible_collections/arubanetworks | grep -q aos_switch && sw_mod_installed=true
                ! $cen_mod_installed && ls -1 $d/ansible_collections/arubanetworks | grep -q aruba_central && cen_mod_installed=true
            fi
            $cx_mod_installed && $sw_mod_installed && $cen_mod_installed && break
        done

        i=0;for var in "$cx_mod_installed" "$sw_mod_installed" "$cen_mod_installed"; do
            [ "$var" == true ] && ((i+=1))
        done

        if [ $i -eq 0 ]; then
            unset a_mod_status
        elif [ $i -gt 2 ]; then
            a_mod_status="installed"
        else
            a_mod_status="partially installed"
        fi
    else
        cx_mod_installed=false
        sw_mod_installed=false
        cen_mod_installed=false
        a_mod_status=""
    fi


    UTIL_VER['aruba_ansible_collections']=$( echo $a_mod_status )
    PKG_EXPLAIN['aruba_ansible_collections']="Aruba Networks collections for ansible"
    # warn if aruba-ansible-modules is not completely installed and add option to menu to install
    if [[ $a_mod_status == 'partially installed' ]]; then
        process="build utilities menu"
        ! $cx_mod_installed && UTIL_VER['aruba_ansible_cx_mod']= &&
            logit "aruba-ansible-collections are partially installed, the aoscx collection available on ansible-galaxy is missing" "WARNING"
        ! $sw_mod_installed && UTIL_VER['aruba_ansible_sw_mod']= &&
            logit "aruba-ansible-collections are partially installed, the aos_switch collection available on ansible-galaxy is missing" "WARNING"
        ! $cen_mod_installed && UTIL_VER['aruba_ansible_cen_mod']= &&
            logit "aruba-ansible-collections are partially installed, the aruba_central collection available on ansible-galaxy is missing" "WARNING"
        unset process
    fi
    [ -z "$model_pretty" ] && get_pi_info > /dev/null
    if [ "$is_pi" == "false" ] || is_speedtest_compat ; then
        UTIL_VER['speed_test']=$( [ -f /var/www/speedtest/speedtest.js ] && echo installed )
        PKG_EXPLAIN['speed_test']="self-hosted network speed-test"
    else
        process='consolepi-extras'
        logit "consolepi-extras (optional utilities/packages installer) omitted speed test option not >= Pi 4"
        unset process
    fi

    # -- COCKPIT --
    cpit_status=$(dpkg -l | grep " cockpit " | awk '{print $1,$3}')
    [[ "$cpit_status" =~ "ii" ]] && UTIL_VER['cockpit']="${cpit_status/ii }" || UTIL_VER['cockpit']=
    PKG_EXPLAIN['cockpit']="Glanceable Web DashBoard with web tty (reach it on port 9090)"

    # UTIL_VER['wireshark~tshark']=$( which wireshark )
    # PKG_EXPLAIN['wireshark~tshark']="packet capture software"

    # sort menu options
    util_list_i=($(for u in ${!UTIL_VER[@]}; do echo $u; done | sort))
    util_list_f=($(for u in ${!UTIL_VER[@]}; do echo $u; done | sort -rn))

    sep=': '; i=0; for u in ${util_list_i[@]}; do
        pretty=${u//_/ }
        case "$u" in
            aruba_ansible_cx_mod)
                pretty="Install Missing aos-cx Ansible Collection" && sep=''
                ;;
            aruba_ansible_sw_mod)
                pretty="Install Missing aos-switch Ansible Collection" && sep=''
                ;;
            aruba_ansible_cen_mod)
                pretty="Install Missing aruba-central Ansible Collection" && sep=''
                ;;
            *)
                sep=': '
                ;;
        esac
        # [[ "$u" =~ "sw_mod" ]] && pretty="Install Missing aos-switch Ansible Collection" && sep=''
        # [[ "$u" =~ "cx_mod" ]] && pretty="Install Missing aos-cx Ansible Collection" && sep=''
        # [[ "$u" =~ "cen_mod" ]] && pretty="Install Missing aruba-central Ansible Collection" && sep=''
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
        if [[ " ${utils[@]} " =~ ' aruba_ansible_collections ' ]] && [[ ! " ${utils[@]} " =~ " ansible " ]] && [[ -z "${UTIL_VER['ansible']}" ]]; then
                process="aruba-ansible-collections"
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
                if hash pipx 2>/dev/null; then
                    cmd_list=()
                else
                    cmd_list=(
                        "-stop" "-apt-install" "pipx" \
                        "-s" "-u" "pipx ensurepath" \
                        "-s" "-u" "[ -d \"${home_dir}/.bash_completions\" ] || mkdir ${home_dir}/.bash_completions" \
                        "-nostart" "-pf" "Create bash completions file for pipx" "-u" "register-python-argcomplete pipx > ${home_dir}/.bash_completions/pipx.sh"
                    )
                fi
                cmd_list+=(
                    "-l" "!! NOTICE: Long wait here on some platforms as ansible requirements need to be built, install may appear to hang, but is still working in background" \
                    "-stop" "-pf" "pipx install ansible (long wait here)" "-u" "--stderr" "$(readlink /dev/fd/0)" "pipx install --verbose --include-deps ansible" \
                    "-nostart" "-pf" "pipx inject... make available in PATH" "-u" "pipx inject --include-apps ansible argcomplete" \
                    "-nostart" "-pf" "activate completion for ansible" "-u" "activate-global-python-argcomplete --user --dest ${home_dir}/.bash_completions/"
                )
            elif [[ $2 == "remove" ]]; then
                    # "-s" "-nolog" "rm ${home_dir}/.bash_completions/ansible*" \
                cmd_list=(
                    "-s" "-u" "-stop" "pipx uninstall $apt_pkg_name" \
                    '-logit' "ansible removed however the hidden directory (.ansible) created in the ${home_dir}/.ansible retained." \
                    "-l" "Completion file ${home_dir}/.bash_completions/_python-argcomplete, created during the ansible install, is useful for any program that uses argparse/argcomplete.  It was not removed."
                    )
            fi
            ;;
        aruba_ansible_collections|aruba_ansible_cx_mod|aruba_ansible_sw_mod|aruba_ansible_cen_mod)
            if [[ $2 == "install" ]]; then
                declare -a cmd_list
                case $1 in
                    aruba_ansible_collections)
                        # install all aruba collections
                        cmd_list=(
                            '-pf' 'Install aos-cx collection from ansible-galaxy' "su -w PATH $iam -c \"export PATH="$PATH:$home_dir/.local/bin"; ansible-galaxy collection install arubanetworks.aoscx\"" \
                            '-pf' 'Install aos-switch collection from ansible-galaxy' "su -w PATH $iam -c \"export PATH="$PATH:$home_dir/.local/bin"; ansible-galaxy collection install arubanetworks.aos_switch\"" \
                            '-pf' 'Install aruba_central collection from ansible-galaxy' "su -w PATH $iam -c \"export PATH="$PATH:$home_dir/.local/bin"; ansible-galaxy collection install arubanetworks.aruba_central\""
                        )
                        ;;
                    aruba_ansible_cx_mod)
                        # install all aruba collections
                        cmd_list=(
                            '-pf' 'Install aos-cx collection from ansible-galaxy' "su -w PATH $iam -c \"export PATH="$PATH:$home_dir/.local/bin"; ansible-galaxy collection install arubanetworks.aoscx\""
                        )
                        ;;
                    aruba_ansible_sw_mod)
                        # install all aruba collections
                        cmd_list=(
                            '-pf' 'Install aos-switch collection from ansible-galaxy' "su -w PATH $iam -c \"export PATH="$PATH:$home_dir/.local/bin"; ansible-galaxy collection install arubanetworks.aos_switch\""
                        )
                        ;;
                    aruba_ansible_cen_mod)
                        # install all aruba collections
                        cmd_list=(
                            '-pf' 'Install aruba-central collection from ansible-galaxy' "su -w PATH $iam -c \"export PATH="$PATH:$home_dir/.local/bin"; ansible-galaxy collection install arubanetworks.aruba_central\""
                        )
                        ;;
                esac
            elif [[ $2 == "remove" ]]; then
                cmd_list=()
                for d in ${col_dirs[@]}; do
                    if [ -d $d/ansible_collections/arubanetworks ]; then
                        cmd_list+=(
                            "-pf" "remove Aruba ansible collections found in $d/ansible_collections/arubanetworks" "rm -r \"$d/ansible_collections/arubanetworks*\""
                        )
                    fi
                done
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
                    "-apt-install" "$apt_pkg_name" "--pretty=CockPit"
                )
                if ! ${uses_nm:-true}; then
                    cmd_list+=("--exclude=cockpit-networkmanager")
                fi
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
                            if [[ " ${INSTALLED[@]} " =~ " aruba_ansible_collections " ]]; then
                                ! $aruba_ansible_collections && util_exec "aruba_ansible_collections" "remove"
                                ! ${!u} && util_exec $u "remove" || true  # prevent non selected items from returning non-zero return code
                                skip_mod=true
                            else
                                ! ${!u} && util_exec $u "remove" || true  # prevent non selected items from returning non-zero return code
                                skip_mod=false
                            fi
                            ;;
                        aruba_ansible_collections)
                            $skip_mod || ( ! ${!u} && util_exec $u "remove" )
                            ;;
                        *)
                            ! ${!u} && util_exec $u "remove" || true  # prevent non selected items from returning non-zero return code
                            ;;
                    esac
                else
                    ${!u} && util_exec $u "install" || true  # prevent non selected items from returning non-zero return code
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
                    logit "$u already installed"
                fi
            fi
        done
    fi
}

# -- // SCRIPT ROOT \\ --
if [[ ! $0 == *"ConsolePi" ]] && [[ $0 == *"utilities.sh"* ]] &&  [[ ! "$0" =~ "update.sh" ]]; then
    backtitle="ConsolePi Extras"
    PATH=$PATH:"${home_dir}/.local/bin"
    util_main ${@}
else
    $debug && process="utilities script start" && logit "script called from ${0}" "DEBUG"
    unset process
    backtitle="ConsolePi Installer"
    return 0
fi
