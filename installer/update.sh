#!/usr/bin/env bash

# ------------------------------------------------------------------------------------------------------------------------------------------------- #
# --                                                 ConsolePi Installation Script Stage 3                                                       -- #
# --  Wade Wells - Pack3tL0ss                                                                                                                    -- #
# --    report any issues/bugs on github or fork-fix and submit a PR                                                                             -- #
# --                                                                                                                                             -- #
# --  This script aims to automate the installation of ConsolePi.                                                                                -- #
# --  For more detail visit https://github.com/Pack3tL0ss/ConsolePi                                                                              -- #
# --                                                                                                                                             -- #
# --------------------------------------------------------------------------------------------------------------------------------------------------#

_verify_nmconnection_perms() {
    # $1 = file to verify will ensure it is owned by root with 600 perms
    [ ! -f "/etc/NetworkManager/system-connections/$1" ] && logit "Error verifying nmconnection file perms $1 File does not exist" "ERROR"
    logit "Verify/Set permissions $1"
    local rc=0

    if [ ! "$(stat /etc/NetworkManager/system-connections/$1 -c '%u%a')" -eq 0600 ]; then
        chown root:root "/etc/NetworkManager/system-connections/$1" >>$log_file 2>&1; ((rc+=$?))
        chmod 600 "/etc/NetworkManager/system-connections/$1" >>$log_file 2>&1; ((rc+=$?))
        [ "$rc" -eq 0 ] && logit "Success - set permissions $1" || logit "Error set permissions $1" "WARNING"
    else
        logit "$1 permissions already OK"
    fi

    return $rc
}

update_hosts_file() {
    process="Update hosts file"
    logit "Updating hosts file based on hotspot/wired-dhcp configuration"

    if [ -f /etc/hosts ]; then
        local hostn=$(tr -d " \t\n\r" < /etc/hostname)
        # local_domain can be nul j2 template has conditionals to handle it.
        convert_template hosts /etc/hosts wlan_ip=${wlan_ip} wired_ip=${wired_ip} hostname=${hostn} domain=${local_domain} hotspot=${hotspot} wired_dhcp=${wired_dhcp}
    else
        logit "skipping as /etc/hosts file does not appear to exist" "WARNING"
    fi

    unset process
}

set_hostname() {
    process="Change Hostname"
    hostn=$(tr -d " \t\n\r" < /etc/hostname)
    if [ "${hostn}" = "raspberrypi" ]; then

        # -- collect desired hostname from user - bypass collection if set via cmd line or config --
        [ -n "$hostname" ] && newhost=$hostname && unset hostname
        if [ -z "$newhost" ]; then
            if $silent; then
                logit "Set hostname bypassed silent install with no desired hostname provided"
            else
                header
                valid_response=false
                while ! $valid_response; do
                    # Display existing hostname
                    read -ep "Current hostname $hostn. Do you want to configure a new hostname (y/n)?: " response
                    response=${response,,}    # tolower
                    ( [[ "$response" =~ ^(yes|y)$ ]] || [[ "$response" =~ ^(no|n)$ ]] ) && valid_response=true || valid_response=false
                done

                if [[ "$response" =~ ^(yes|y)$ ]]; then
                    # Ask for new hostname $newhost
                    ok_do_hostname=false
                    while ! $ok_do_hostname; do
                        read -ep "Enter new hostname: " newhost
                        valid_response=false
                        while ! $valid_response; do
                            printf "New hostname: ${_green}$newhost${_norm} Is this correect (y/n)?: " ; read -e response
                            response=${response,,}    # tolower
                            ( [[ "$response" =~ ^(yes|y)$ ]] || [[ "$response" =~ ^(no|n)$ ]] ) && valid_response=true || valid_response=false
                        done
                        [[ "$response" =~ ^(yes|y)$ ]] && ok_do_hostname=true || ok_do_hostname=false
                    done
                fi
            fi
        fi

        # -- apply new hostname --
        if [ -n "$newhost" ]; then
            # change hostname in /etc/hosts & /etc/hostname
            sed -i "s/$hostn/$newhost/g" /etc/hosts
            sed -i "s/$hostn\.$(grep -o "$hostn\.[0-9A-Za-z].*" /etc/hosts | cut -d. -f2-)/$newhost.$local_domain/g" /etc/hosts

            # change hostname via command
            if [ "$INIT" = "systemd" ]; then
                hostnamectl set-hostname "$newhost"; rc=$?
            else
                hostname "$newhost" 1>&2 2>>/dev/null; rc=$?
            fi

            [ $rc -gt 0 ] && logit "Error returned from hostname command" "WARNING"

            # add hotspot IP to hostfile for DHCP connected clients to resolve this host
            #wlan_hostname_exists=$(grep -c "$wlan_ip" /etc/hosts)
            #[ $wlan_hostname_exists == 0 ] && echo "$wlan_ip       $newhost" >> /etc/hosts
            #sed -i "s/$hostn/$newhost/g" /etc/hostname

            logit "New hostname set $newhost"
        fi

    else
        logit "Hostname ${hostn} is not default, assuming it is desired hostname"
    fi
    unset process
}

# -- set timezone --
set_timezone() {
    process="Configure ConsolePi TimeZone"
    cur_tz=$(date +"%Z")
    if [ ! -z "$tz" ]; then
        # -- // SILENT timezone passed in via config or cmd line arg \\ --
        if [ ! -f "/usr/share/zoneinfo/$tz" ]; then
            logit "Unable to Change TimeZone Silently. Invalid TimeZone ($tz) Provided" "WARNING"
        elif [[ "$tz" == "$(head -1 /etc/timezone)" ]]; then
            logit "Timezone Already Configured ($tz)"
        else
            rm /etc/localtime
            echo "$tz" > /etc/timezone
            dpkg-reconfigure -f noninteractive tzdata 2>>$log_file &&
                logit "Set new TimeZone to $(date +"%Z") based on tz arg/config option Success" ||
                    logit "FAILED to set new TimeZone based on tz arg/config option" "WARNING"
        fi
        unset tz
    elif ! $silent; then
        if [ $cur_tz == "GMT" ] || [ $cur_tz == "BST" ]; then
            # -- // INTERACTIVE PROMPT  \\ --
            header

            prompt="Current TimeZone $cur_tz. Do you want to configure the timezone"
            set_tz=$(user_input_bool)

            if $set_tz; then
                echo "Launching, standby..." && dpkg-reconfigure tzdata 2>> $log_file && header && logit "Set new TimeZone to $(date +"%Z") Success" ||
                    logit "FAILED to set new TimeZone" "WARNING"
            fi
        else
            logit "TimeZone ${cur_tz} not default (GMT) assuming set as desired."
        fi
    else
        logit "Set TimeZone bypassed silent install with no desired tz provided"
    fi
    unset process
}

# -- if ipv6 is enabled present option to disable it --
disable_ipv6()  {
    process="Disable ipv6"
    [ -f /etc/sysctl.d/99-noipv6.conf ] && no_ipv6=true # just bypases prompt when testing using -install flag
    if ! $silent; then
        if [ -z "$no_ipv6" ]; then
            prompt="Do you want to disable ipv6"
            no_ipv6=$(user_input_bool)
        fi
    elif [ -z "$no_ipv6" ]; then
        no_ipv6=false
        logit "Disable IPv6 bypassed silent install with no desired state provided"
    fi

    if $no_ipv6; then
        file_diff_update "${src_dir}99-noipv6.conf" /etc/sysctl.d/99-noipv6.conf
    fi
    unset process
}

get_staged_imports(){
    # additional imports occur in related functions if import file exists
    process="Staged imports"

    # -- ssh authorized keys --
    found_path=$(get_staged_file_path "authorized_keys")
    if [[ $found_path ]]; then
        logit "pre-staged ssh authorized keys found - importing"
        file_diff_update $found_path /root/.ssh/authorized_keys
        file_diff_update $found_path ${home_dir}/.ssh/authorized_keys
            chown $iam:$iam ${home_dir}/.ssh/authorized_keys
    fi

    # -- ssh known hosts --
    found_path=$(get_staged_file_path "known_hosts")
    if [[ $found_path ]]; then
        logit "pre-staged ssh known_hosts file found - importing"
        file_diff_update $found_path /root/.ssh/known_hosts
        file_diff_update $found_path ${home_dir}/.ssh/known_hosts
            chown $iam:$iam ${home_dir}/.ssh/known_hosts
    fi

    # -- pre staged cloud creds --
    if $cloud; then
        found_path=$(get_staged_file_path ".credentials" '-d')
        [ -z "$found_path" ] && found_path=$(get_staged_file_path "${cloud_svc}/.credentials" '-d')
        [ -z "$found_path" ] && found_path=$(get_staged_file_path "cloud/${cloud_svc}/.credentials" '-d')
        if [ -n "$found_path" ]  && [ $(ls -1 $found_path | wc -l) -gt 0 ]; then
            mv $found_path/* "/etc/ConsolePi/cloud/${cloud_svc}/.credentials" 2>> $log_file &&
                logit "Found ${cloud_svc} credentials. Moved to /etc/ConsolePi/cloud/${cloud_svc}/.credentials"  ||
                logit "Error occurred moving your ${cloud_svc} credentials files" "WARNING"
        elif [ ! -f "$CLOUD_CREDS_FILE" ]; then
            desktop_msg="Use 'consolepi-menu cloud' then select the 'r' (refresh) option to authorize ConsolePi in ${cloud_svc}"
            lite_msg="RaspiOS-lite detected. Refer to the GitHub for instructions on how to generate credential files from another system"
        fi
    fi

    # -- custom overlay file for PoE hat (fan control) --
    # TODO looks like there is a gpiofan overlay now.
    found_path=$(get_staged_file_path "rpi-poe-overlay.dts")
    if [ -n "$found_path" ]; then
        logit "overlay file found creating dtbo"
        dtc -@ -I dts -O dtb -o /tmp/rpi-poe.dtbo $found_path >> $log_file 2>&1 &&
            overlay_success=true || overlay_success=false
            if $overlay_success; then
                mv /tmp/rpi-poe.dtbo /boot/overlays 2>> $log_file &&
                    logit "Success moved overlay file, will activate on boot" ||
                    logit "Failed to move overlay file"
            else
                logit "Failed to create Overlay file from dts"
            fi
    fi

    # TODO may need to adjust once fully automated
    # -- wired-dhcp configurations --
    found_path=$(get_staged_file_path "wired-dhcp" '-d')
    [ -z "$found_path" ] && found_path=$(get_staged_file_path "dnsmasq.d/wired-dhcp" '-d')
    if [ -n "$found_path" ]; then
        logit "Staged wired-dhcp directory found copying contents to ConsolePi wired-dchp dir"
        logit -L "copying wired-dhcp from $found_path"
        cp -r ${found_path}/. /etc/ConsolePi/dnsmasq.d/wired-dhcp/ &&
        logit "Success - copying staged wired-dchp configs" ||
            logit "Failure - copying staged wired-dchp configs" "WARNING"
    fi

    # -- ztp configurations --
    found_path=$(get_staged_file_path "ztp" '-d')
    if [ -n "$found_path" ]; then
        logit "Staged ztp directory found copying contents to ConsolePi ztp dir"
        logit -L "copying ztp from $found_path"
        cp -r ${found_path}/. ${consolepi_dir}ztp/ 2>>$log_file &&
        logit "Success - copying staged ztp configs" ||
            logit "Failure - copying staged ztp configs" "WARNING"

        if [ $(ls -1 ${consolepi_dir}ztp | grep -vi README | wc -l) -gt 0 ]; then
            check_perms ${consolepi_dir}ztp
        fi
    fi

    # -- autohotspot dhcp configurations --
    found_path=$(get_staged_file_path "autohotspot" '-d')
    [ -z "$found_path" ] && found_path=$(get_staged_file_path "dnsmasq.d/autohotspot" '-d')
    if [ -n "$found_path" ]; then
        logit "Staged autohotspot (dhcp) directory found copying contents to ConsolePi autohotspot dchp dir"
        logit -L "copying autohotspot dhcp configs from $found_path"
        cp -r ${found_path}/. /etc/ConsolePi/dnsmasq.d/autohotspot/ &&
        logit "Success - copying staged autohotspot (dchp) configs" ||
            logit "Failure - copying staged autohotspot-dchp configs" "WARNING"
    fi

    # -- udev rules - serial port mappings --
    found_path=$(get_staged_file_path "10-ConsolePi.rules")
    if [ -n "$found_path" ]; then
        logit "udev rules file found ${found_path} enabling provided udev rules"
        if [ -f /etc/udev/rules.d/10-ConsolePi.rules ]; then
            file_diff_update $found_path /etc/udev/rules.d/10-ConsolePi.rules
        else
            sudo cp $found_path /etc/udev/rules.d
            sudo udevadm control --reload-rules && sudo udevadm trigger
        fi
    fi
    unset process
}

install_ser2net () {
    # TODO add check to see if already installed / update
    process="Install ser2net via apt"
    logit "${process} - Starting"
    ser2net_ver=$(ser2net -v 2>> /dev/null | cut -d' ' -f3 && installed=true || installed=false)
    if [ -z "$ser2net_ver" ]; then
        process_cmds -apt-install "ser2net"
        ser2net_ver=$(ser2net -v 2>> /dev/null | cut -d' ' -f3 && installed=true || installed=false)
    else
        logit "Ser2Net ${ser2net_ver} is current"
    fi

    ser2net_major_ver=$(echo $ser2net_ver | cut -d'.' -f1)
    if [ "$ser2net_major_ver" -eq 4 ]; then
        ser2net_conf="ser2net.yaml"
        ser2net_alt="ser2net.conf"
    else
        ser2net_conf="ser2net.conf"
        ser2net_alt="ser2net.yaml"
    fi

    do_ser2net=true
    if ! $upgrade; then
        found_path=$(get_staged_file_path "$ser2net_conf")
        [ -z "$found_path" ] && found_path=$(get_staged_file_path "$ser2net_alt")
        if [ -n "$found_path" ]; then
            if cp $found_path "/etc"; then
                logit "Found ser2net config in ${found_path}.  Copying to /etc"
            else
                logit "Error Copying your pre-staged ${found_path} file" "WARNING"
                do_ser2net=false
            fi
        fi
    fi

    if $do_ser2net; then
        if [ "$ser2net_major_ver" -eq 3 ] && ( [ ! -f /etc/ser2net.conf ] || [[ ! $(head -1 /etc/ser2net.conf 2>>$log_file) =~ "ConsolePi" ]] ); then
            logit "Building ConsolePi Config for ser2netv3"
            _go=true
        elif [ "$ser2net_major_ver" -eq 4 ] && ( [ ! -f /etc/ser2net.yaml ] || [[ ! $(head -3 /etc/ser2net.yaml | tail -1 2>>$log_file) =~ "ConsolePi" ]] ); then
            logit "Building ConsolePi Config for ser2netv4"
            _go=true
        else
            if [ -n "$ser2net_major_ver" ]; then
                logit "ser2net v$ser2net_major_ver installed... already prepped for ConsolePi Skipping config" "INFO"
            else
                logit "Unable to determine ser2net version skipping related configs" "WARNING"
            fi
            _go=false
        fi

        if $_go; then
            if [ -f "/etc/$ser2net_conf" ]; then
                cp /etc/$ser2net_conf $bak_dir  || logit "Failed to backup default ser2net to bak dir" "WARNING"
            fi
            cp /etc/ConsolePi/src/$ser2net_conf /etc/ 2>> $log_file ||
                logit "ser2net Failed to copy config file from ConsolePi src" "ERROR"
        fi
    fi

    systemctl daemon-reload ||
        logit "systemctl failed to reload daemons" "WARNING"

    logit "${process} - Complete"
    unset process
}

do_hook_nm() {
    # // NetworkManager systems (bookworm+)
    process="Configure nm-dispather"
    local dispatch_src="/etc/ConsolePi/src/02-consolepi"
    local dispatch_dest="/etc/NetworkManager/dispatcher.d/02-consolepi"
    if [ -f $dispatch_dest ] && grep -q $dispatch_src $dispatch_dest; then
        logit "dispatch script already exists, pointer verified"
    else
        echo '[ -x /etc/ConsolePi/src/02-consolepi ] && /etc/ConsolePi/src/02-consolepi "$@" || echo "ERROR: ConsolePi network dispatcher not found or not executable"' > $dispatch_dest

        # -- Must be executable, ownded by root on not writable by group or other --
        if [ "$(stat $dispatch_dest -c %a 2>/dev/null)" -eq 755 ]; then
            logit "dispatch script perms verified"
        else
            chmod 755 $dispatch_dest 2>>$log_file && logit "Success setting dispatch script perms" ||
                logit "Error occured setting dispatch script permissions" "WARNING"
        fi

        if [ "$(stat $dispatch_dest -c %u 2>/dev/null)" -eq 0 ]; then
            logit "dispatch script ownership verified"
        else
            chown root:root $dispatch_dest 2>>$log_file && logit "Success set dispatch script ownership" ||
                logit "Error occured setting dispatch script ownership" "WARNING"
        fi
    fi

    logit "${process} - Complete"
    unset process
}

do_hook_old() {
    # // PRE-BOOkWORM OR SYSTEMS NOT RUNNING NetworkManager
    process="Configure dhcpcd.exit-hook"
    hook_file="/etc/ConsolePi/src/dhcpcd.exit-hook"
    logit "${process} - Starting"
    if [ -f /etc/dhcpcd.exit-hook ]; then
        if grep -q $hook_file  /etc/dhcpcd.exit-hook; then
            logit "exit-hook already configured [File Found and Pointer exists]"  #exit-hook exists and line is already there
        else
            echo "$hook_file \"\$@\"" > "/tmp/dhcpcd.exit-hook"
            file_diff_update /tmp/dhcpcd.exit-hook /etc/dhcpcd.exit-hook
            rm /tmp/dhcpcd.exit-hook >/dev/null 2>>$log_file
        fi
    else
        echo "$hook_file \"\$@\"" > "/etc/dhcpcd.exit-hook" || logit "Failed to create exit-hook script" "ERROR"
    fi

    # -- Make Sure exit-hook is executable --
    if [ -x /etc/dhcpcd.exit-hook ]; then
        logit "check executable: exit-hook file already executable"
    else
        sudo chmod +x /etc/dhcpcd.exit-hook 2>> $log_file || logit "Failed to make dhcpcd.exit-hook executable" "ERROR"
    fi
    logit "${process} - Complete"
    unset process
}

# sub used by do_consolepi_cleanup
sub_remove_old_cleanup() {
    if /lib/systemd/systemd-sysv-install is-enabled ConsolePi_cleanup; then
        logit "Deprecated cleanup init script found disabling"
        if /lib/systemd/systemd-sysv-install disable ConsolePi_cleanup 2>>$log_file; then
            logit "Success disable deprecated cleanup init script"
        else
            logit "Error removing deprecated cleanup init script check $log_file for details" "WARNING"
        fi
    fi
    [ -f /etc/init.d/ConsolePi_cleanup ] && rm /etc/init.d/ConsolePi_cleanup 2>>$log_file
}

do_consolepi_cleanup() {
    # ConsolePi_cleanup is an init script that runs on startup / shutdown.  On startup it removes tmp files used by ConsolePi script to determine if the ip
    # address of an interface has changed (PB notifications only occur if there is a change). So notifications are always sent after a reboot.
    process="consolepi-cleanup"
    sub_remove_old_cleanup
    systemd_diff_update consolepi-cleanup
    if [ "$( systemctl is-enabled consolepi-cleanup.service )" != "enabled" ]; then
        systemctl enable consolepi-cleanup 2>>$log_file && logit "Success enable consolepi-cleanup" || logit "Error enabling consolepi-cleanup" "WARNING"
    fi
    unset process
}

#sub process used by install_ovpn_old
sub_check_vpn_config(){
    if [ -f /etc/openvpn/client/ConsolePi.ovpn ]; then
        if $push; then
            if [ $(sudo grep -c "script-security 2" /etc/openvpn/client/ConsolePi.ovpn) -eq 0 ]; then
                sudo echo -e "#\n# run push script to send notification of successful VPN connection\nscript-security 2" 1>> /etc/openvpn/client/ConsolePi.ovpn 2>>$log_file &&
                logit "Enabled script-security 2 in ConsolePi.ovpn" || logit "Unable to Enable script-security 2 in ConsolePi.ovpn" "WARNING"
            fi
            if [ $(sudo grep -c 'up "/etc/ConsolePi' /etc/openvpn/client/ConsolePi.ovpn) -eq 0 ]; then
                sudo echo 'up "/etc/ConsolePi/src/dhcpcd.exit-hook OVPN' 1>> /etc/openvpn/client/ConsolePi.ovpn 2>>$log_file &&
                logit "Added Pointer to on-up script in ConsolePi.ovpn" || logit "Failed to Add Pointer to on-up script in ConsolePi.ovpn" "WARNING"
            else
                sudo sed -i '/up\s\"\/etc\/ConsolePi\/.*/c\up \"\/etc\/ConsolePi\/src\/dhcpcd.exit-hook OVPN\"' /etc/openvpn/client/ConsolePi.ovpn &&
                logit "Succesfully Verified/Updated ovpn up Pointer" || logit "Failed to update ovpn up pointer" "WARNING"
            fi
        fi
    fi
}

install_ovpn_old() {
    process="OpenVPN"
    ovpn_ver=$(openvpn --version 2>/dev/null| head -1 | awk '{print $2}')
    if [ -z "$ovpn_ver" ]; then
        process_cmds -stop -apt-install "openvpn" -nostart -pf "Enable OpenVPN" '/lib/systemd/systemd-sysv-install enable openvpn'
    else
        logit "OpenVPN ${ovpn_ver} Already Installed/Current"
    fi

    if [ -f /etc/openvpn/client/ConsolePi.ovpn ]; then
        logit "Retaining existing ConsolePi.ovpn"
        $push && sub_check_vpn_config
    else
        found_path=$(get_staged_file_path "ConsolePi.ovpn")
        if [[ $found_path ]]; then
            cp $found_path "/etc/openvpn/client" &&
                logit "Found ${found_path}.  Copying to /etc/openvpn/client" ||
                logit "Error occurred Copying your ovpn config" "WARNING"
            $push && [ -f /etc/openvpn/client/ConsolePi.ovpn ] && sub_check_vpn_config
        else
            [[ ! -f "/etc/openvpn/client/ConsolePi.ovpn.example" ]] && sudo cp "${src_dir}ConsolePi.ovpn.example" "/etc/openvpn/client" ||
                logit "Retaining existing ConsolePi.ovpn.example file. See src dir for original example file."
        fi
    fi

    if [ -f /etc/openvpn/client/ovpn_credentials ]; then
        logit "Retaining existing openvpn credentials"
    else
        found_path=$(get_staged_file_path "ovpn_credentials")
        if [[ $found_path ]]; then
            mv $found_path "/etc/openvpn/client" &&
            logit "Found ovpn_credentials ${found_path}. Moving to /etc/openvpn/client"  ||
            logit "Error occurred moving your ovpn_credentials file" "WARNING"
        else
            [[ ! -f "/etc/openvpn/client/ovpn_credentials" ]] && cp "${src_dir}ovpn_credentials" "/etc/openvpn/client" ||
                logit "Retaining existing ovpn_credentials file. See src dir for original example file."
        fi
    fi

    sudo chmod 600 /etc/openvpn/client/* 1>/dev/null 2>> $log_file || logit "Failed chmod 600 openvpn client files" "WARNING"

    systemd_diff_update "ovpn-graceful-shutdown"
    unset process
}

# TODO add additonal cmdline flag --ovpn (assumed false if flag not provided and silent mode, prompted if autovpn_enabled)
# TODO add documentation consolepi-autovpn id.
install_ovpn_nm() {
    process="OpenVPN"
    if ! dpkg -l | grep -q "^ii\s*network-manager-openvpn"; then
        process_cmds -apt-install "network-manager-openvpn"
    fi
    unset process
}

do_nm_conf() {
    process="Deploy ConsolePi NM conf"
    local conf_dest="/etc/NetworkManager/conf.d/01-consolepi.conf"
    convert_template 01-consolepi.conf "$conf_dest" ovpn_enable=${ovpn_enable}

    if [ ! "$(stat $conf_dest -c '%u%a')" -eq 0644 ]; then
        logit "Updating perms for NM ConsolePi conf file"
        rc=0
        chown root:root $conf_dest >>$log_file 2>&1; ((rc+=$?))
        chmod 0644 $conf_dest >>$log_file 2>&1; ((rc+=$?))
        [ "$rc" -eq 0 ] && logit "Updated - Success" || logit "Error occured check logs" "WARNING"
    else
        logit "ConsolePi NM permissions already OK"
    fi
}

install_autohotspot_old() {
    process="AutoHotSpotN"
    logit "Install/Update AutoHotSpotN"

    systemd_diff_update autohotspot
    if ! head -1 /etc/dnsmasq.conf 2>/dev/null | grep -q 'ConsolePi installer' ; then
        logit "Using New autohotspot specific dnsmasq instance"
        systemctl -q is-active consolepi-autohotspot-dhcp && was_active=true || was_active=false
        systemd_diff_update consolepi-autohotspot-dhcp
        if ! $was_active && systemctl -q is-active consolepi-autohotspot-dhcp; then
            systemctl stop consolepi-autohotspot-dhcp 2>>$log_file ||
                logit "Failed to stop consolepi-autohotspot-dhcp.service check log" "WARNING"
        fi
        if systemctl -q is-enabled consolepi-autohotspot-dhcp; then
            systemctl disable consolepi-autohotspot-dhcp 2>>$log_file &&
                logit "consolepi-autohotspot-dhcp autostart disabled Successfully, startup handled by autohotspot" ||
                logit "Failed to disable consolepi-autohotspot-dhcp.service check log" "WARNING"
        fi
    else
        logit "Using old autohotspot system default dnsmasq instance"
    fi

    if ! $(which hostapd >/dev/null); then
        process_cmds -apt-install hostapd
    else
        hostapd_ver=$(hostapd -v 2>&1| head -1| awk '{print $2}')
        logit "hostapd ${hostapd_ver} already installed"
    fi

    # -- override_dir set in common.sh
    [[ -f ${override_dir}/hostapd.service ]] && hostapd_override=true || hostapd_override=false
    # [[ -f ${override_dir}/dnsmasq.service ]] && dnsmasq_override=true || dnsmasq_override=false  # No Longer Used
    if ! $hostapd_override ; then
        logit "disabling hostapd (handled by AutoHotSpotN)."
        sudo systemctl unmask hostapd.service 1>/dev/null 2>> $log_file &&
            logit "Verified hostapd.service is unmasked" ||
                logit "failed to unmask hostapd.service" "WARNING"
        sudo systemctl disable hostapd 1>/dev/null 2>> $log_file &&
            logit "hostapd autostart disabled Successfully" ||
                logit "An error occurred disabling hostapd autostart - verify after install" "WARNING"
    else
        logit "${_cyan}skipped hostapd disable - hostapd.service is overriden${_norm}"
    fi

    logit "Create/Configure hostapd.conf"
    convert_template hostapd.conf /etc/hostapd/hostapd.conf wlan_ssid=${wlan_ssid} wlan_psk=${wlan_psk} wlan_country=${wlan_country}
    sudo chmod +r /etc/hostapd/hostapd.conf 2>> $log_file || logit "Failed to make hostapd.conf readable - verify after install" "WARNING"

    file_diff_update ${src_dir}hostapd /etc/default/hostapd
    file_diff_update ${src_dir}interfaces /etc/network/interfaces

    which iw >/dev/null 2>&1 && iw_ver=$(iw --version 2>/dev/null | awk '{print $3}') || iw_ver=0
    if [ "$iw_ver" == 0 ]; then
        process_cmds -apt-install iw
    else
        logit "iw $iw_ver already installed/current."
    fi

    # TODO place update in sysctl.d same as disbale ipv6
    logit "Enable IP-forwarding (/etc/sysctl.conf)"
    if $(! grep -q net.ipv4.ip_forward=1 /etc/sysctl.conf); then
    sed -i '/^#net\.ipv4\.ip_forward=1/s/^#//g' /etc/sysctl.conf 1>/dev/null 2>> $log_file && logit "Enable IP-forwarding - Success" ||
        logit "FAILED to enable IP-forwarding verify /etc/sysctl.conf 'net.ipv4.ip_forward=1'" "WARNING"
    else
        logit "ip forwarding already enabled"
    fi

    logit "${process} Complete"
    unset process
}

disable_autohotspot_old() {
    process="Verify Auto HotSpot is disabled"
    local rc=0
    if systemctl -q is-active autohotspot; then
        systemctl stop autohotspot >/dev/null 2>>$log_file ; ((rc+=$?))
    fi

    if systemctl -q is-enabled autohotspot 2>/dev/null; then  # /dev/null as it's possible the autohotspot.service file does not exist if they installed with hotspot disabled.
        systemctl disable autohotspot >/dev/null 2>>$log_file ; ((rc+=$?))
    fi

    if grep -q "except-interface=$wlan_iface" /etc/dnsmasq.d/01-consolepi 2>/dev/null; then
        sed -i "/except-interface=$wlan_iface/d" /etc/dnsmasq.d/01-consolepi 2>>$log_file ||
            logit "sed returned an error removing except-interface=$wlan_iface from /etc/dnsmasq.d/01-consolepi" "WARNING"
    fi

    [[ $rc -eq 0 ]] && logit "Success Auto HotSpot Service is Disabled" || logit "Error Disabling Auto HotSpot Service" "WARNING"
    unset process
}

install_hotspot_nm() {
    process="Auto Hotspot NM"
    logit "Install/Update Auto HotSpot"
    local uuid=$(nmcli -g connection.uuid con show hotspot 2>/dev/null)
    if [ -z "$uuid" ]; then
        hash uuid 2>/dev/null && local uuid=$(uuid)
        local uuid=${uuid:-5ad644a6-b80e-11ee-952a-bf1313596c84}
    fi
    local hotspot_con_file=/etc/NetworkManager/system-connections/hotspot.nmconnection
    [ -f /etc/sysctl.d/99-noipv6.conf ] && local v6_method=disabled || local v6_method=auto

    convert_template hotspot.nmconnection "$hotspot_con_file" uuid=${uuid} wlan_iface=${wlan_iface:-wlan0} \
        wlan_ssid=${wlan_ssid} wlan_psk=${wlan_psk} wlan_ip=${wlan_ip} v6_method=${v6_method}

    #verify
    if [ -f "$hotspot_con_file" ] && grep -q "address1=${wlan_ip}" $hotspot_con_file; then
        logit "Success"
        _verify_nmconnection_perms ${hotspot_con_file##*/}
    else
        logit "Error occured, validate the contents of ${hotspot_con_file##*/}" "WARNING"
        logit "verify contents of $hotspot_con_file"
    fi
    unset process
}

disable_hotspot_nm() {
    process="Verify Auto HotSpot is disabled"
    local hotspot_con_file=/etc/NetworkManager/system-connections/hotspot.nmconnection
    if [ -f $hotspot_con_file ]; then
        if grep -q "autoconnect=true" $hotspot_con_file; then
            sed -i 's/autoconnect=.*/autoconnect=false/' $hotspot_con_file &&
                logit "Disabled automatic fallback to hotspot" || logit "Error occured disabling automatic fallback to hotspot" "WARNING"
        fi
    fi
    unset process
}

check_install_dnsmasq() {
    # only applies to pre-bookworm install/upgrade
    process="dnsmasq"
    logit "Verify / Install dnsmasq"

    dnsmasq_ver=$(dnsmasq -v 2>/dev/null | head -1 | awk '{print $3}')
    if [[ -z "$dnsmasq_ver" ]]; then
        process_cmds -apt-install dnsmasq
        # disable dnsmasq only if we just installed it
        systemctl stop dnsmasq 1>/dev/null 2>> $log_file &&
            logit "dnsmasq stopped Successfully" ||
                logit "An error occurred stopping dnsmasq - verify after install" "WARNING"
        sudo systemctl disable dnsmasq 1>/dev/null 2>> $log_file &&
            logit "dnsmasq autostart disabled Successfully" ||
                logit "An error occurred disabling dnsmasq autostart - verify after install" "WARNING"
    else
        logit "dnsmasq v${dnsmasq_ver} already installed"
    fi
    unset process
}

do_wired_dhcp() {
    process="wired-dhcp"
    convert_template dnsmasq.eth0 /etc/ConsolePi/dnsmasq.d/wired-dhcp/wired-dhcp.conf dhcp_start="${wired_dhcp_start}" dhcp_end="${wired_dhcp_end}" wired_iface="${wired_iface}"
    # -- using file_diff_update vs systemd_diff_update as we don not want the service enabled.  It is activated by exit-hook/nm-dispatcher
    file_diff_update ${src_dir}systemd/consolepi-wired-dhcp.service /etc/systemd/system/consolepi-wired-dhcp.service
}

do_wired_dhcp_nm() {
    process="wired-dhcp NM"
    logit "Install/Update Wired static fallback with DHCP"

    # -- Check for existing DHCP (client) NetworkManager connection profiles on the wired interface --
    # We skip any nmconnection files not in /etc/NetworkManager as NM auto-creates defaults that are overriden with /etc/NetworkManager once
    # any customization are made
    readarray -t wired_con_info < <(nmcli -t -f NAME,DEVICE,TYPE,FILENAME connection show | grep ":802-3-ethernet:/etc/NetworkManager/system-")
    dhcp_con_exists=false
    for con in "${wired_con_info[@]}"; do
        local iface="$(echo $con | cut -d: -f2)"
        local name="$(echo $con | cut -d: -f1)"
        local file="${con/*:}"
        [ -z "$iface" ] && iface=$(nmcli -g connection.interface-name con show "$name")

        if [ "$iface" != "$wired_iface" ]; then
            logit "Skipping $name as $iface is not $wired_iface"
            continue
        fi

        local profile_opts=($(nmcli -t -f ipv4.method,connection.autoconnect,connection.autoconnect-priority con show "${name}"))
        local method=${profile_opts[0]/*:}
        local autocon=${profile_opts[1]/*:}
        local autocon_pri=${profile_opts[2]/*:}
        if [ "$method" == "auto" ] && [ "$autocon" == "yes" ]; then
            if [ "$autocon_pri" -gt 0 ]; then
                dhcp_con_exists=true
            else
                logit "existing NetworkManager connection profile $name found with default autoconnect-profile:0 (lowest priority)"
                logit "Increasing autoconnect-priority of $name to 1"
                if nmcli con modify "$name" connection.autoconnect-priority 1 2>>$log_file ; then
                    logit "Success set $name autoconnect-priority to 1"
                    dhcp_con_exists=true
                else
                    logit "Error occured setting $name autoconnect-priority to 1" "WARNING"
                    logit "Check the contents of $file" "WARNING"
                    logit "Ensure autoconnect-priority=N where N is any value higher than 0" "CRITICAL"  # EXIT ON FAIL
                fi
            fi
        else
            logit "skipping $name ($method,$autocon,$autocon_pri) will not interfere with static fallback"
        fi
    done

    # Deploy wired DHCP (client) connection profile if one doesn't already exist
    # process="Wired Static Fallback with DHCP (ZTP)"
    if ! $dhcp_con_exists; then
        local _msg="Install/Update dhcp profile"
        logit "$_msg"
        local uuid=$(nmcli -g connection.uuid con show dhcp 2>/dev/null)
        if [ -z "$uuid" ]; then
            hash uuid 2>/dev/null && local uuid=$(uuid)
            local uuid=${uuid:-17afb1e2-ba86-11ee-96a0-cf199142a9f5}
        fi
        local file=dhcp.nmconnection
        local dest="/etc/NetworkManager/system-connections/$file"
        [ -f /etc/sysctl.d/99-noipv6.conf ] && wired_v6_method=disabled || wired_v6_method=auto

        convert_template "$file" $dest uuid=${uuid} wired_iface=${wired_iface:-setme} \
            wired_v6_method=${wired_v6_method} 2>>$log_file

        #verify
        if [ -f "$dest" ] && grep -q "autoconnect-priority=" "$dest"; then
            logit "Success - $_msg"
            _verify_nmconnection_perms "$file"
        else
            logit "Error - $_msg" "WARNING"
            logit "verify contents of $dest" "ERROR"
        fi
    fi

    # deploy static fallback connection profile for Wired DHCP (server) for ZTP
    local _msg="Install/Update static profile"
    logit "$_msg"
    local uuid=$(nmcli -g connection.uuid con show static 2>/dev/null)
    if [ -z "$uuid" ]; then
        hash uuid 2>/dev/null && local uuid=$(uuid)
        local uuid=${uuid:-6292dec6-b9b1-11ee-a979-e7aa8dbd16e6}
    fi
    local file=static.nmconnection
    local dest="/etc/NetworkManager/system-connections/$file"

    convert_template "$file" "$dest" uuid=${uuid} wired_iface=${wired_iface:-setme} \
        wired_ip=${wired_ip} 2>>$log_file

    #verify
    if [ -f "$dest" ] && grep -q "address1=${wired_ip}" "$dest"; then
        logit "Success - $_msg"
        _verify_nmconnection_perms "$file"
    else
        logit "Error - $_msg" "WARNING"
        logit "verify contents of $dest" "ERROR"
    fi

    unset process
}

disable_wired_dhcp_nm() {
    process="Verify wired_dhcp disabled"
    local static_con_file=/etc/NetworkManager/system-connections/static.nmconnection
    if [ -f $static_con_file ]; then
        if grep -q "autoconnect=true" $static_con_file; then
            sed -i 's/autoconnect=.*/autoconnect=false/' $static_con_file &&
                logit "Disabled wired automatic fallback to static" || logit "Error occured disabling wired automatic fallback to static" "WARNING"
        elif grep -q "autoconnect=false" $static_con_file; then
            logit "Wired dhcp fallback already disabled"
        else  # original template was missing autoconnect lines so just remove the connection file
            rm $static_con_file &&
                logit "Disabled wired automatic fallback to static" || logit "Error occured disabling wired automatic fallback to static" "WARNING"
        fi
    fi
    unset process
}

gen_dnsmasq_conf() {
    process="Configure dnsmasq"
    logit "Generating Files for dnsmasq."
    # check if they are using old method where dnsmasq.conf was used to control dhcp on wlan interface
    if head -1 /etc/dnsmasq.conf 2>/dev/null | grep -q 'ConsolePi installer' ; then
        convert_template dnsmasq.conf /etc/dnsmasq.conf wlan_dhcp_start=${wlan_dhcp_start} wlan_dhcp_end=${wlan_dhcp_end} wlan_iface=${wlan_iface}
        ahs_unique_dnsmasq=false
    else
        convert_template dnsmasq.wlan0 /etc/ConsolePi/dnsmasq.d/autohotspot/autohotspot wlan_dhcp_start=${wlan_dhcp_start} wlan_dhcp_end=${wlan_dhcp_end} wlan_iface=${wlan_iface}
        ahs_unique_dnsmasq=true
    fi

    if $ahs_unique_dnsmasq ; then
        if $hotspot && $wired_dhcp ; then
            grep -q "except-interface=$wlan_iface" /etc/dnsmasq.d/01-consolepi 2>/dev/null ; rc=$?
            grep -q "except-interface=$wired_iface" /etc/dnsmasq.d/01-consolepi 2>/dev/null ; ((rc+=$?))
            if [[ $rc -gt 0 ]] ; then
                convert_template 01-consolepi /etc/dnsmasq.d/01-consolepi "except_if_lines=except-interface=$wlan_iface{{cr}}except-interface=$wired_iface"
            fi
        elif $hotspot ; then
            grep -q "except-interface=$wlan_iface" /etc/dnsmasq.d/01-consolepi 2>/dev/null ||
                convert_template 01-consolepi /etc/dnsmasq.d/01-consolepi "except_if_lines=except-interface=$wlan_iface"
        elif $wired_dhcp ; then
            grep -q "except-interface=$wired_iface" /etc/dnsmasq.d/01-consolepi 2>/dev/null ||
                convert_template 01-consolepi /etc/dnsmasq.d/01-consolepi "except_if_lines=except-interface=$wired_iface"
        else
            if [ -f /etc/dnsmasq.d/01-consolepi ] ; then
                logit "Hotspot and wired_dhcp are disabled but consolepi specific dnsmasq config found moving to bak dir"
                mv /etc/dnsmasq.d/01-consolepi $bak_dir 2>>$log_file
            fi
        fi
    fi
    unset process
}

gen_dhcpcd_conf () {
    process="dhcpcd.conf"
    logit "configure dhcp client and static fallback"
    [ -f /etc/sysctl.d/99-noipv6.conf ] && noipv6=true || noipv6=false
    convert_template dhcpcd.conf /etc/dhcpcd.conf wlan_ip=${wlan_ip} wired_ip=${wired_ip} hotspot=${hotspot} wired_dhcp=${wired_dhcp} noipv6=${noipv6}
    unset process
}

_handle_blue_symlink() {
    # disable / enable bluetooth.service to remove symlink to original bluetooth unit file in lib dir
    [ ! -f /etc/systemd/system/bluetooth.service ] && return 0  # They are not using the ConsolePi bluetooth unit

    local rc=0
    if [ "$(ls -l /etc/systemd/system | grep bluetooth.service | grep dbus | grep "^l.*" | cut -d'/' -f2)" == "lib" ]; then
        systemctl disable bluetooth.service 2>/dev/null; local rc=$?
        [ $rc -eq 0 ] && systemctl enable bluetooth.service 2>/dev/null; local rc=$?
    fi

    [ $rc -eq 0 ] || logit "Error returned disable/enable bluetooth.service to remove dbus symlink to original unit file" "WARNINNG"
    return $rc
}

do_blue_config() {
    ! $do_blue && logit "Skipping bluetooth serial setup based on --no-blue flag" && return 0

    process="Bluetooth Console"
    logit "${process} Starting"

    # [ "$btmode" == "serial" ] && local btsrc="${src_dir}systemd/bluetooth.service" || local btsrc="${src_dir}systemd/bluetooth_pan.service"
    # btsrc="${src_dir}systemd/bluetooth.service"  # Temp until btpan configuration vetted/implemented
    # file_diff_update $btsrc /lib/systemd/system/bluetooth.service
    bt_exec=$(grep 'ExecStart=' /lib/systemd/system/bluetooth.service |grep bluetoothd| cut -d'=' -f2|awk '{print $1}')
    systemctl is-enabled bluetooth.service >/dev/null && bt_enabled=true || bt_enabled=false
    if [ ! -z "$bt_exec" ]; then
        if [ ! -f "$bt_exec" ]; then
            [ -f /usr/libexec/bluetooth/bluetoothd ] && bt_exec=/usr/libexec/bluetooth/bluetoothd
        fi
    else
        logit "Unable to extract bluetoothd (lib) exec path from default /lib/systemd/system/bluetooth.service" "WARNING"
    fi

    if [ ! -z "$bt_exec" ] && [ -f "$bt_exec" ]; then
        convert_template bluetooth.service /etc/systemd/system/bluetooth.service bt_exec=${bt_exec}
        systemd_diff_update 'bthelper@'
    else
        logit "Unable to find bluetoothd (lib) exec path" "WARNING"
    fi

    # create /etc/systemd/system/rfcomm.service to enable
    # the Bluetooth serial port from systemctl
    # TODO make autologin blue user optional (can do now via override and modified rfcomm.service file)
    systemd_diff_update rfcomm

    # if bluetooth.service was disabled we only update the files, we don't enable bluetooth.service or rfcomm.service
    # prevents failed services on rpis that lack bt
    if $bt_enabled; then
        logit "Reloading bluetooth service"
        systemctl daemon-reload
        _handle_blue_symlink
        systemctl restart bluetooth.service >>$log_file 2>&1
        # enable the new rfcomm service
        do_systemd_enable_load_start rfcomm
    fi

    # add blue user and set to launch menu on login
    if getent passwd blue >/dev/null; then
        logit "BlueTooth User already exists"
    else
        echo -e 'ConsoleP1!!\nConsoleP1!!\n' | sudo adduser --gecos "" blue 1>/dev/null 2>> $log_file &&
        logit "BlueTooth User created" ||
        logit "FAILED to create Bluetooth user" "WARNING"
    fi

    # add blue user to dialout group so they can access /dev/ttyUSB_ devices
    #   and to consolepi group so they can access logs and data files for ConsolePi
    for group in dialout consolepi; do
        if [[ ! $(groups blue | grep -o $group) ]]; then
        sudo usermod -a -G $group blue 2>> $log_file && logit "BlueTooth User added to ${group} group" ||
            logit "FAILED to add Bluetooth user to ${group} group" "WARNING"
        else
            logit "BlueTooth User already in ${group} group"
        fi
    done

    # Remove old blue user default tty cols/rows
    grep -q stty /home/blue/.bashrc &&
        sed -i 's/^stty rows 70 cols 150//g' /home/blue/.bashrc &&
        logit "blue user tty row col configuration removed - Success"

    # Configure blue user to auto-launch consolepi-menu on login (blue user is automatically logged in when connection via bluetooth is established)
    if [[ ! $(sudo grep consolepi-menu /home/blue/.bashrc) ]]; then
        sudo echo /etc/ConsolePi/src/consolepi-menu.sh | sudo tee -a /home/blue/.bashrc > /dev/null &&
            logit "BlueTooth User Configured to launch menu on Login" ||
            logit "FAILED to enable menu on login for BlueTooth User" "WARNING"
    else
        sudo sed -i 's/^consolepi-menu/\/etc\/ConsolePi\/src\/consolepi-menu.sh/' /home/blue/.bashrc &&
            logit "blue user configured to launch menu on Login" ||
            logit "blue user autolaunch bashrc error" "WARNING"
    fi

    # Configure blue user alias for consolepi-menu command (overriding the symlink to the full menu with cloud support)
    # TODO change this to use .bash_login or .bash_profile bashrc works lacking those files, more appropriate to use .profile over .bashrc anyway
    if [[ ! $(sudo grep "alias consolepi-menu" /home/blue/.bashrc) ]]; then
        sudo echo alias consolepi-menu=\"/etc/ConsolePi/src/consolepi-menu.sh\" | sudo tee -a /home/blue/.bashrc > /dev/null &&
            logit "BlueTooth User consolepi-menu alias Updated to use \"lite\" menu" ||
            logit "FAILED to update BlueTooth User consolepi-menu alias" "WARNING"
    else
        logit "blue user consolepi-menu alias already configured"
    fi

    logit "${process} Complete"
    unset process
}

get_utils() {
    if [ -f "${consolepi_dir}installer/utilities.sh" ]; then
        . "${consolepi_dir}installer/utilities.sh"
    else
        echo "FATAL ERROR utilities.sh not found exiting"
        exit 1
    fi
}

do_resize () {
    # Install xterm cp the binary into consolepi-commands directory (which is in path) then remove xterm
    process="xterm ~ resize"
    if ! hash resize 2>/dev/null; then
        if [ ! -f ${src_dir}consolepi-commands/resize ]; then
            cmd_list=("-apt-install" "xterm" "--pretty=${process}" "--exclude=x11-utils" \
                    '-s' "export rsz_loc=\$(which resize)" \
                    "-stop" "-nostart" "-p" "Copy resize binary from xterm" "-f" "Unable to find resize binary after xterm install" \
                        "[ ! -z \$rsz_loc ] && sudo cp \$(which resize) ${src_dir}consolepi-commands/resize" \
                    "-l" "xterm will now be removed as we only installed it to get resize" \
                    "-apt-purge" "xterm"
                    )
            process_cmds "${cmd_list[@]}"
        else
            logit "resize utility already present"
        fi
    elif [ ! -f ${src_dir}consolepi-commands/resize ]; then  # If resize is already available (typicall non rpi), cp it for safekeeping
        local rsz_bin=$(which resize)
        cp "$rsz_bin" "${src_dir}consolepi-commands/resize" && logit "Success - Copy existing resize binary" || logit "Error occured  - Copy existing resize binary" "WARNING"
    fi
    unset process
}

# Create or Update ConsolePi API startup service (systemd)
do_consolepi_api() {
    process="ConsolePi API (systemd)"
    if [ $py3ver -ge 6 ] ; then
        systemd_diff_update consolepi-api
    else
        ! $upgrade && systemd_diff_update consolepi-api-flask
        logit "A newer version of the ConsolePi API is available but it requires Python>=3.6 ($(python3 -V) is installed) keeping existing API" "WARNING"
    fi
    unset process
}

# Create or Update ConsolePi mdns startup service (systemd)
do_consolepi_mdns() {
    process="ConsolePi mDNS (systemd)"
    systemd_diff_update consolepi-mdnsreg
    systemd_diff_update consolepi-mdnsbrowse
    for d in 'avahi-daemon.socket' 'avahi-daemon.service' ; do
        if ! systemctl is-enabled "$d" | grep -q "disabled"; then
            [ "${d/*.}" == "socket" ] && logit "disabling ${d%.*} ConsolePi has it's own mdns daemon"
            _error=false
            systemctl stop "$d" >/dev/null 2>>$log_file || _error=true
            systemctl disable "$d" 2>>$log_file || _error=true
            $_error && logit "Error occurred: stop - disable $d Check daemon status" "warning"
        fi
    done
    unset process
}

# Configure ConsolePi with the SSIDs it will attempt to connect to as client prior to falling back to hotspot
get_known_ssids() {
    process="Configure WLAN"
    logit "${process} Started"
    header
    if [ -f $wpa_supplicant_file ] && [[ $(cat $wpa_supplicant_file|grep -c network=) > 0 ]] ; then
        echo
        echo "----------------------------------------------------------------------------------------------"
        echo "wpa_supplicant.conf already exists with the following configuration"
        echo "----------------------------------------------------------------------------------------------"
        cat $wpa_supplicant_file
        echo "----------------------------------------------------------------------------------------------"
        word=" additional"
    else
        # if wpa_supplicant.conf exist in stage dir cp it to /etc/wpa_supplicant
        # if EAP-TLS SSID is configured in wpa_supplicant extract EAP-TLS cert details and cp certs (not a loop only good to pre-configure 1)
        #   certs should be in 'consolepi-stage/cert, subdir cert_names are extracted from the pre-staged wpa_supplicant.conf.
        # TODO consider moving to get_staged_imports()
        found_path=$(get_staged_file_path "wpa_supplicant.conf")
        if [[ -f $found_path ]]; then
            logit "Found stage file ${found_path} Applying"
            # ToDo compare the files ask user if they want to import if they dont match
            [[ -f $wpa_supplicant_file ]] && sudo cp $wpa_supplicant_file $bak_dir
            cp $found_path $wpa_supplicant_file
            client_cert=$(grep client_cert= $found_path | cut -d'"' -f2| cut -d'"' -f1)
            if [[ ! -z "$client_cert" ]]; then
                cert_path=${client_cert%/*}
                ca_cert=$(grep ca_cert= $found_path | cut -d'"' -f2| cut -d'"' -f1)
                private_key=$(grep private_key= $found_path | cut -d'"' -f2| cut -d'"' -f1)
                if [[ -d ${stage_dir}/cert ]]; then
                    pushd ${stage_dir}/cert >/dev/null
                    [[ ! -d $cert_path ]] && sudo mkdir -p "${cert_path}"
                    [[ -f ${client_cert##*/} ]] && sudo cp ${client_cert##*/} "${cert_path}/${client_cert##*/}"
                    [[ -f ${ca_cert##*/} ]] && sudo cp ${ca_cert##*/} "${cert_path}/${ca_cert##*/}"
                    [[ -f ${private_key##*/} ]] && sudo cp ${private_key##*/} "${cert_path}/${private_key##*/}"
                    popd >/dev/null
                fi
            fi

            if [ -f $wpa_supplicant_file ] && [[ $(cat $wpa_supplicant_file|grep -c network=) > 0 ]] ; then
                echo
                echo "----------------------------------------------------------------------------------------------"
                echo "wpa_supplicant.conf was imported with the following configuration"
                echo "----------------------------------------------------------------------------------------------"
                cat $wpa_supplicant_file
                echo "----------------------------------------------------------------------------------------------"
                word=" additional"
            fi
        fi
    fi

    $hotspot && echo -e "\nConsolePi will attempt to connect to configured SSIDs prior to going into HotSpot mode.\n"
    prompt="Do you want to configure${word} WLAN SSIDs"
    user_input false "${prompt}"
    continue=$result

    if $continue; then
        if [ -f ${consolepi_dir}src/consolepi-addssids.sh ]; then
            . ${consolepi_dir}src/consolepi-addssids.sh
            known_ssid_init
            known_ssid_main
            mv $wpa_supplicant_file $bak_dir 1>/dev/null 2>> $log_file ||
                logit "Failed to backup existing file to originals dir" "WARNING"
            mv "$wpa_temp_file" "$wpa_supplicant_file" 1>/dev/null 2>> $log_file ||
                logit "Failed to move collected ssids to wpa_supplicant.conf Verify Manually" "WARNING"
        else
            logit "SSID collection script not found in ConsolePi src dir" "WARNING"
        fi
    else
        logit "User chose not to configure SSIDs via script.  You can run consolepi-addssids to invoke script after install"
    fi
    logit "${process} Complete"
    unset process
}

# -- these funcs and only apply if wifi-country set to US
do_locale() {
    if [ -n "$locale" ] && [ "${locale^^}" == "US" ]; then
        # -- keyboard change relies on raspi-config
        if hash raspi-config 2>/dev/null; then
            # -- update keyboard layout --
            if ! grep XKBLAYOUT /etc/default/keyboard | grep -q ${locale,,}; then
                process="Set Keyboard Layout"
                logit "${process} - Starting"
                sudo raspi-config nonint do_configure_keyboard ${locale,,} >/dev/null

                grep XKBLAYOUT /etc/default/keyboard | grep -q ${locale,,} &&
                    logit "Success - KeyBoard Layout changed to ${locale,,}" ||
                    logit "${process} - Failed ~ verify contents of /etc/default/keyboard" "WARNING"
                unset process
            fi
        else
            logit -t "set keyboard to US" "keyboard change utilizes raspi-config which was not found.  Skipping"
        fi

        # -- update locale --
        # logic adapted from raspi-config https://github.com/RPi-Distro/raspi-config
        new_locale="en_${locale^^}.UTF-8"
        cur_locale=$(locale | head -1 | cut -d'=' -f2)
        if [ "$cur_locale" != "$new_locale" ]; then
            process="Set locale $new_locale"
            logit "$process - Starting"
            if ! LOCALE_LINE="$(grep -E "^$new_locale( |$)" /usr/share/i18n/SUPPORTED)"; then
                return 1
            fi
            export LC_ALL=C
            export LANG=C
            LG="/etc/locale.gen"
            [ -L "$LG" ] && [ "$(readlink $LG)" = "/usr/share/i18n/SUPPORTED" ] && rm -f "$LG"
            echo "$LOCALE_LINE" > /etc/locale.gen
            update-locale --no-checks LANG >>$log_file 2>&1
            rc=0
            update-locale --no-checks "LANG=$new_locale" >>$log_file 2>&1; ((rc+=$?))
            dpkg-reconfigure -f noninteractive locales >>$log_file 2>&1; ((rc+=$?))
            [ "$rc" -eq 0 ] && logit "Success - set locale $new_locale $1" || logit "Error set locale $new_locale" "WARNING"
        fi
    fi
}

get_serial_udev() {
    process="Predictable Console Ports"
    logit "${process} Starting"
    header
    echo
    echo -e "--------------------------------------------- ${_green}Predictable Console ports${_norm} ---------------------------------------------"
    echo "-                                                                                                                   -"
    echo "- Predictable Console ports allow you to configure ConsolePi so that each time you plug-in a specific adapter it    -"
    echo "- will have the same name in consolepi-menu and will be reachable via the same TELNET port.                         -"
    echo "-                                                                                                                   -"
    echo "- The behavior if you do *not* define Predictable Console Ports is the adapters will use the root device names      -"
    echo "-   ttyUSB# or ttyACM# where the # starts with 0 and increments for each adapter of that type plugged in. The names -"
    echo "-   won't necessarily be consistent between reboots nor will the TELNET port.  This method is OK for temporary use  -"
    echo -e "-   of an adapter or if you only plan to use a single adapter.  Otherwise setting predictable aliases is            -"
    echo -e "-   ${_lred}highly recommended${_norm}.                                                                                             -"
    echo "-                                                                                                                   -"
    echo "- Defining the ports with this utility is also how device specific serial settings are configured.  Otherwise       -"
    echo "-   they will use the default which is 9600 8N1                                                                     -"
    echo "-                                                                                                                   -"
    echo "-                                                                                                                   -"
    echo -e "-  This function can be called anytime from the shell via ${_cyan}consolepi-addconsole${_norm} and is available from                -"
    echo -e "-    ${_cyan}consolepi-menu${_norm} via the 'rn' (rename) option.                                                                   -"
    echo "-                                                                                                                   -"
    echo "---------------------------------------------------------------------------------------------------------------------"
    echo
    echo "You need to have the serial adapters available"
    prompt="Would you like to configure predictable serial port aliases now"
    $upgrade && user_input false "${prompt}" || user_input true "${prompt}"
    if $result ; then
        if [ -f ${consolepi_dir}src/consolepi-commands/consolepi-menu ]; then
            sudo ${consolepi_dir}src/consolepi-commands/consolepi-menu rn
        else
            logit "ERROR consolepi-menu not found" "WARNING"
        fi
    fi
    logit "${process} Complete"
    unset process
}

list_wlan_interfaces() {
    for dir in /sys/class/net/*/wireless; do
        [ -d "$dir" ] && basename "$(dirname "$dir")"
    done
}

do_wifi_country() {
    process="Set WiFi Country"
    IFACE="$(list_wlan_interfaces | head -n 1)"
    [ -z "$IFACE" ] && logit "Skipping no WLAN interfaces found." && return 1

    if ! wpa_cli -i "$IFACE" status > /dev/null 2>&1; then
        logit "Could not communicate with wpa_supplicant" "WARNING"
        # return 1
    fi

    if [[ $(wpa_cli -i $IFACE get country) == "$wlan_country" ]]; then
        logit "$IFACE country already set to $wlan_country"
    else
        wpa_cli -i "$IFACE" set country "$wlan_country" > /dev/null 2>&1
        wpa_cli -i "$IFACE" save_config > /dev/null 2>&1
        iw reg set "$wlan_country" > /dev/null 2>>$log_file &&
            logit "Wi-fi country set to $wlan_country" ||
            logit "Error Code returned when setting WLAN country" "WARNING"
    fi

    # -- Always check to see if rfkill is blocking wifi --
    if hash rfkill 2> /dev/null; then
        rfkill unblock wifi
    fi
    unset process
}

# -- run custom post install script --
custom_post_install_script() {
    if $do_consolepi_post || ! $upgrade; then
        found_path=$(get_staged_file_path "consolepi-post.sh")
        if [ -n  "$found_path" ]; then
            process="Run Custom Post-install script"
            logit "Post Install Script ${found_path} Found. Executing"
            $found_path && logit "Post Install Script Complete No Errors" ||
                logit "Error Code returned by Post Install Script" "WARNING"
            unset process
        fi
    fi
}

# -- a debugging command to dump all ser vars to log file
dump_vars() {
    echo "---- Install Script var dump -----" >> $log_file
    ( set -o posix ; set ) | grep -v _xspecs | grep -v LS_COLORS >> $log_file
    echo "---------" >> $log_file
}

# -- Display Post Install Message --
post_install_msg() {
    clear -x ;echo
    declare -a _msg=(
            -head "${_green}Installation Complete${_norm}"
            "${_bold}Next Steps/Info${_norm}"
            -nl
            " ${_bold}Cloud Sync:${_norm}"
            "  if you plan to use cloud sync.  You will need to do some setup on the Google side and Authorize ConsolePi"
            "  refer to the GitHub for more details"
            -nl
    )
    if $uses_nm; then
        _msg+=(
            " ${_bold}Auto VPN:${_norm}"
            "  if you are using the Automatic VPN feature you should Configure a NetworkManager connection profile"
            "  (type=vpn, dev=tun) in /etc/NetworkManager/system-connections.  ConsolePi will automatically turn up the connection"
            "  if the an any interface comes up and the internet is reachable."
            "  Verify the profile can be turned up manually with 'nmcli con up <vpn-profile-name>'"
            "  you may need the '--ask' option to store secrets, the first time you connect."
            "  !! All NM connection profiles should be owned by root with 600 (-rw-------) permissions !!"
            -nl
        )
    else
        _msg+=(
            " ${_bold}OpenVPN:${_norm}"
            "  if you are using the Automatic VPN feature you should Configure the ConsolePi.ovpn and ovpn_credentials files in"
            "  /etc/openvpn/client.  Then run 'consolepi-upgrade' which will add a few lines to the config to enable some"
            "  ConsolePi functionality.  There is a .example file for reference as well."
            "  !! You should \"sudo chmod 600 <filename>\" both of the files for added security !!"
            -nl
        )
    fi
    _msg+=(
            " ${_bold}ser2net Usage:${_norm}"
            "  Serial Ports are available starting with telnet port 8001 (ttyUSB#) or 9001 (ttyACM#) incrementing with each"
            "  adapter plugged in.  if you configured predictable ports for specific serial adapters those start with 7001."
            "  **OR** just launch the ${_cyan}consolepi-menu${_norm} for a menu w/ detected adapters (there is a rename option in the menu)."
            -nl
            "  The Console Server has a control port on telnet 7000 type \"help\" for a list of commands available"
            -nl
            " ${_bold}BlueTooth:${_norm}"
            "  ConsolePi should be discoverable (after reboot if this is the initial installation)."
            -li "Configure Bluetooth serial on your device and pair with ConsolePi"
            -li "On client device attach to the com port created after the step above was completed"
            -li "Once Connected the Console Menu will automatically launch allowing you to connect to any serial devices found"
            "  NOTE: The Console Menu is available from any shell session (Bluetooth or SSH) via the ${_cyan}consolepi-menu${_norm} command"
            -nl
            " ${_bold}Logging${_norm}"
            "  The bulk of logging for ConsolePi ends up in /var/log/ConsolePi/consolepi.log"
            "  The tags 'puship', 'puship-ovpn', 'autohotspotN' and 'dhcpcd' are of key interest in syslog"
            -li "openvpn logs are sent to /var/log/ConsolePi/ovpn.log you can tail this log to troubleshoot any issues with ovpn"
            -li "pushbullet responses (json responses to curl cmd) are sent to /var/log/ConsolePi/push_response.log"
            -li "An install log can be found in ${consolepi_dir}installer/install.log"
            -nl
            " ${_bold}ConsolePi Commands:${_norm}"
            "  **Refer to the GitHub for the most recent & most complete list of convenience commands"
            -nl
            -li "${_cyan}consolepi-menu${_norm}: Launch Console Menu which will provide connection options for connected serial adapters."
            "     Menu also displays connection options for discovered remote ConsolePis, as well as power control options, etc."
            -nl
            -li "${_cyan}consolepi-help${_norm}: Extract and display the ConsolePi Commands section of the ReadMe"
            -li "${_cyan}consolepi-version${_norm}: Display version information"
            -li "${_cyan}consolepi-config${_norm}: Opens ConsolePi.yaml with nano with -ET2 option (best for yaml)"
            -li "${_cyan}consolepi-status${_norm}: Display status of ConsolePi daemons, and system daemons related to ConsolePi"
            -li "${_cyan}consolepi-upgrade${_norm}: Upgrade ConsolePi. This is the supported update method"
            -li "${_cyan}consolepi-leases${_norm}: Shows dnsmasq (dhcp) leases.  Typically clients connected to HotSpot"
            -li "${_cyan}consolepi-extras${_norm}: Launch optional utilities installer (tftp, ansible, lldp, cockpit, speedtest...)"
            -li "${_cyan}consolepi-addconsole${_norm}: Configure serial adapter to telnet port rules"
            -li "${_cyan}consolepi-showaliases${_norm}: Shows Configured adapter aliases, helps identify any issues with aliases"
            -li "${_cyan}consolepi-logs${_norm}: Displays ConsolePi logs (Note this will install mutli-tail the first time it's ran)"
            "     valid args: 'all' (will cat consolepi.log), any other argument is passed to tail as a flag."
            "                 If no arguments are specified, script will follow tail on consolepi-log, and syslog (with filters)"
            "     examples: \"consolepi-logs all\", \"consolepi-logs -f\", \"consolepi-logs -20\", \"consolepi-logs 20\""
    )
    if ! $uses_nm; then
        _msg+=(
            -li "${_cyan}consolepi-killvpn${_norm}: Gracefully terminate openvpn tunnel if one is established"
            -li "${_cyan}consolepi-autohotspot${_norm}: Manually invoke AutoHotSpot function which will look for known SSIDs and connect if found"
            "     then fall-back to HotSpot mode if not found or unable to connect"
        )
    fi
    _msg+=(
            -li "${_cyan}consolepi-testhotspot${_norm}: Disable/Enable the SSIDs ConsolePi tries to connect to before falling back to hotspot"
            "     Used to test hotspot function.  Script Toggles state if enabled it will disable and vice versa"
            -li "${_cyan}consolepi-bton${_norm}: Make BlueTooth Discoverable and pairable - this is the default behavior on boot"
            -li "${_cyan}consolepi-btoff${_norm}: Disable BlueTooth Discoverability.  You can still connect if previously paired"
            -li "${_cyan}consolepi-details${_norm}: Refer to GitHub for usage, but in short dumps the data the ConsolePi would run with based"
            "     on configuration, discovery, etc.  Dumps everything if no args"
            "     valid args: adapters, interfaces, outlets, remotes, local, <hostname of remote>.  GitHub for more detail"
            -li "${_cyan}consolepi-convert${_norm}: ser2net v3 to ser2net v4 migration tool"
            -nl
            " ${_bold}DEPRECATED Commands:${_norm} These commands will work on pre-bookworm systems, but not on current images."
            -li "${_cyan}consolepi-addssids${_norm}: Add additional known ssids. Alternatively you can add entries to wpa_supplicant manually"
            -nl
            -foot "ConsolePi Installation Script v${INSTALLER_VER}"
    )
    menu_print "${_msg[@]}"

    # Display any warnings if they exist
    if [ "$warn_cnt" -gt 0 ]; then
        echo -e "\n${_red}---- warnings exist ----${_norm}"
        grep -A 999 "${log_start}" -a $log_file | grep -v "^WARNING: Retrying " | grep -v "apt does not have a stable CLI interface" | grep "WARNING\|failed"
        # sed -n "/${log_start}/,//p" $log_file | grep -v "^WARNING: Retrying " | grep -v "apt does not have a stable CLI interface" | grep "WARNING\|failed"
        echo
    fi

    # Script Complete Prompt for reboot if first install
    if $upgrade; then
        echo -e "\nConsolePi Upgrade Complete, a Reboot may be required if config options where changed during upgrade\n"
    else
        echo
        prompt="A reboot is required, do you want to reboot now"
        go_reboot=$(user_input_bool)
        $go_reboot && sudo reboot || echo -e "\nConsolePi Install script Complete, Reboot is required"
    fi
}

update_main() {
    # -- install.sh does --
    # get_common                          # get and import common functions script
    # get_pi_info                         # (common.sh func) Collect some version info for logging
    # remove_first_boot                   # if auto-launch install on first login is configured remove
    # do_apt_update                       # apt-get update the pi
    # do_apt_deps                         # install dependencies via apt
    # pre_git_prep                        # process upgrade tasks required prior to git pull
    # git_ConsolePi                       # git clone or git pull ConsolePi
    # $upgrade && post_git                # post git changes
    # do_pyvenv                           # build upgrade python3 venv for ConsolePi
    # do_logging                          # Configure logging and rotation
    # $upgrade && do_remove_old_consolepi_commands    # Remove consolepi-commands from old version of ConsolePi
    # update_banner                       # ConsolePi login banner update

    # -- config.sh does --
    # get_static
    # get_config
    # ! $bypass_verify && verify
    # while ! $input; do
    #     collect
    #     verify
    # done
    # update_config

    if ! $upgrade; then
        set_hostname
        set_timezone
        disable_ipv6
        do_wifi_country
        get_staged_imports
    fi
    install_ser2net

    if $uses_nm; then
        if $hotspot || $wired_dhcp || $ovpn_enable || $push; then
            get_interfaces  # provides wlan_iface and wired_iface in global profile
            do_hook_nm  # no real need to remove once deployed, it verifies config prior to taking any action
        fi

        if $wired_dhcp || $hotspot; then
            check_install_dnsmasq
            gen_dnsmasq_conf
        fi

        $hotspot && install_hotspot_nm || disable_hotspot_nm

        if $wired_dhcp; then
            do_wired_dhcp_nm
            do_wired_dhcp  # setup up the dnsmasq conf in ConsolePi dir applies to both nm and dhcpcd
        else
            disable_wired_dhcp_nm
        fi

        $ovpn_enable && install_ovpn_nm
        do_nm_conf
    elif [ "$(systemctl is-active dhcpcd.service)" == "active" ]; then
        if $hotspot || $wired_dhcp || $ovpn_enable; then
            get_interfaces  # Using in old flow because gen_dnsmasq_conf has been updated to use detected iface names
            do_hook_old
        fi

        if $no_ipv6 || $hotspot || $wired_dhcp; then
            gen_dhcpcd_conf
        fi

        if $wired_dhcp || $hotspot; then
            check_install_dnsmasq
            gen_dnsmasq_conf
        fi

        $wired_dhcp && do_wired_dhcp
        $hotspot && install_autohotspot_old || disable_autohotspot_old
        $ovpn_enable && install_ovpn_old
    else
        if $hotspot || $wired_dhcp || $ovpn_enable; then
            logit "system does not appear to be using NetworkManager or dhcpcd skipping Network Automations (hotspot/wire-dhcp(ztp))" "WARNING"
        fi
    fi

    update_hosts_file # uses wlan_ip wired_ip local_domain along with hotspot and wired_dhcp from config.  Allows connected clients to resolve by hostname
    do_blue_config
    do_consolepi_cleanup
    do_consolepi_api
    do_consolepi_mdns
    do_resize

    if ( [ -n "$skip_utils" ] && $skip_utils ) || $silent; then
        logit -t "optional utilities installer" "utilities menu bypassed by config variable"
    else
        get_utils
        util_main
    fi

    if ! $silent; then
        ! $uses_nm && get_known_ssids  # pre-bookworm only
        get_serial_udev
    else
        logit -t "Configure WLAN - Predictable Console Ports" "Prompts bypassed due to -silent flag"
    fi

    ! $upgrade && do_locale
    custom_post_install_script
    process=Complete
    $local_dev && dump_vars
    if ! $silent; then
        post_install_msg
    else
        _msg="Success Silent Install Complete a reboot is required."
        [[ "$warn_cnt" > 0 ]] && logit "$_msg\n ${_red}Warnings Occurred During Install ($warn_cnt)${_norm}." | cut -d']' -f4- || echo "$_msg"
    fi
    $silent && $do_reboot && echo -e "\n${_green}Install Complete${_norm}\n  system will reboot in 10 seconds (CTRL+C to abort reboot)" && sleep 10 && reboot
}
