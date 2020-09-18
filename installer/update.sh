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

set_hostname() {
    process="Change Hostname"
    hostn=$(cat /etc/hostname)
    if [[ "${hostn}" == "raspberrypi" ]]; then

        # -- collect desired hostname from user - bypass collection if set via cmd line or config --
        [ ! -z "$hostname" ] && newhost=$hostname && unset hostname
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
        if [ ! -z "$newhost" ]; then
            # change hostname in /etc/hosts & /etc/hostname
            sed -i "s/$hostn/$newhost/g" /etc/hosts
            sed -i "s/$hostn\.$(grep -o "$hostn\.[0-9A-Za-z].*" /etc/hosts | cut -d. -f2-)/$newhost.$local_domain/g" /etc/hosts

            # change hostname via command
            hostname "$newhost" 1>&2 2>>/dev/null
            [ $? -gt 0 ] && logit "Error returned from hostname command" "WARNING"

            # add hotspot IP to hostfile for DHCP connected clients to resolve this host
            wlan_hostname_exists=$(grep -c "$wlan_ip" /etc/hosts)
            [ $wlan_hostname_exists == 0 ] && echo "$wlan_ip       $newhost" >> /etc/hosts
            sed -i "s/$hostn/$newhost/g" /etc/hostname

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
    [ -f /etc/sysctl.d/99-noipv6.conf ] && dis_ipv6=true # just bypases prompt when testing using -install flag
    if ! $silent; then
        if [ -z "$dis_ipv6" ]; then
            prompt="Do you want to disable ipv6"
            dis_ipv6=$(user_input_bool)
        fi
    elif [ -z "$dis_ipv6" ]; then
        dis_ipv6=false
        logit "Disable IPv6 bypassed silent install with no desired state provided"
    fi

    if $dis_ipv6; then
        file_diff_update "${src_dir}99-noipv6.conf" /etc/sysctl.d/99-noipv6.conf
    fi
    unset process
}

misc_imports(){
    # additional imports occur in related functions if import file exists
    process="Perform misc imports"

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
    if $cloud && [[ -f ${stage_dir}/.credentials/credentials.json ]]; then
        found_path=${stage_dir}/.credentials
        mv $found_path/* "/etc/ConsolePi/cloud/${cloud_svc}/.credentials" 2>> $log_file &&
        logit "Found ${cloud_svc} credentials. Moving to /etc/ConsolePi/cloud/${cloud_svc}/.credentials"  ||
        logit "Error occurred moving your ${cloud_svc} credentials files" "WARNING"
    elif $cloud ; then
        if [ ! -f "$CLOUD_CREDS_FILE" ]; then
            desktop_msg="Use 'consolepi-menu cloud' then select the 'r' (refresh) option to authorize ConsolePi in ${cloud_svc}"
            lite_msg="RaspiOS-lite detected. Refer to the GitHub for instructions on how to generate credential files off box"
        fi
    fi

    # -- custom overlay file for PoE hat (fan control) --
    found_path=$(get_staged_file_path "rpi-poe-overlay.dts")
    [[ $found_path ]] && logit "overlay file found creating dtbo"
    if [[ $found_path ]]; then
        sudo dtc -@ -I dts -O dtb -o /tmp/rpi-poe.dtbo $found_path >> $log_file 2>&1 &&
            overlay_success=true || overlay_success=false
            if $overlay_success; then
                sudo mv /tmp/rpi-poe.dtbo /boot/overlays 2>> $log_file &&
                    logit "Success moved overlay file, will activate on boot" ||
                    logit "Failed to move overlay file"
            else
                logit "Failed to create Overlay file from dts"
            fi
    fi

    # TODO may need to adjust once fully automated
    # -- wired-dhcp configurations --
    if [[ -d ${stage_dir}/wired-dhcp ]]; then
        logit "Staged wired-dhcp directory found copying contents to ConsolePi wired-dchp dir"
        cp -r ${stage_dir}/wired-dhcp/. /etc/ConsolePi/dnsmasq.d/wired-dhcp/ &&
        logit "Success - copying staged wired-dchp configs" ||
            logit "Failure - copying staged wired-dchp configs" "WARNING"
    fi

    # -- ztp configurations --
    if [[ -d ${stage_dir}/ztp ]]; then
        logit "Staged ztp directory found copying contents to ConsolePi ztp dir"
        cp -r ${stage_dir}/ztp/. ${consolepi_dir}ztp/ 2>>$log_file &&
        logit "Success - copying staged ztp configs" ||
            logit "Failure - copying staged ztp configs" "WARNING"
        if [[ $(ls -1 | grep -vi "README" | wc -l ) > 0 ]]; then
            check_perms ${consolepi_dir}ztp
        fi
    fi

    # -- autohotspot dhcp configurations --
    if [[ -d ${stage_dir}/autohotspot-dhcp ]]; then
        logit "Staged autohotspot-dhcp directory found copying contents to ConsolePi autohotspot dchp dir"
        cp -r ${stage_dir}/autohotspot-dhcp/. /etc/ConsolePi/dnsmasq.d/autohotspot/ &&
        logit "Success - copying staged autohotspot-dchp configs" ||
            logit "Failure - copying staged autohotspot-dchp configs" "WARNING"
    fi

    # -- udev rules - serial port mappings --
    found_path=$(get_staged_file_path "10-ConsolePi.rules")
    if [[ $found_path ]]; then
        logit "udev rules file found ${found_path} enabling provided udev rules"
        if [ -f /etc/udev/rules.d/10-ConsolePi.rules ]; then
            file_diff_update $found_path /etc/udev/rules.d/10-ConsolePi.rules
        else
            sudo cp $found_path /etc/udev/rules.d
            sudo udevadm control --reload-rules && sudo udevadm trigger
        fi
    fi

    # -- imported elsewhere during the install
    # /etc/ser2net.conf in install_ser2net()
    # /etc/openvpn/client/ConsolePi.ovpn and ovpn_credentials in install_openvpn()
    # /etc/wpa_supplicant/wpa_supplicant.conf in get_known_ssids()
    #
    # -- imported in phase 1 (install.sh)
    # /home/pi/.ssh/known_hosts
    # /home/pi/.ssh/authorized_keys
    # /home/<user>/. for non pi user contents of <stage-dir>/home/<user> is imported after the user is created

    unset process
}

install_ser2net () {
    # To Do add check to see if already installed / update
    process="Install ser2net via apt"
    logit "${process} - Starting"
    ser2net_ver=$(ser2net -v 2>> /dev/null | cut -d' ' -f3 && installed=true || installed=false)
    if [[ -z "$ser2net_ver" ]]; then
        process_cmds -apt-install "ser2net"
    else
        logit "Ser2Net ${ser2net_ver} is current"
    fi

    do_ser2net=true
    if ! $upgrade; then
        found_path=$(get_staged_file_path "ser2net.conf")
        if [[ $found_path ]]; then
        cp $found_path "/etc" &&
            logit "Found ser2net.conf in ${found_path}.  Copying to /etc" ||
            logit "Error Copying your pre-staged ${found_path} file" "WARNING"
            do_ser2net=false
        fi
    fi

    if $do_ser2net && [[ ! $(head -1 /etc/ser2net.conf 2>>$log_file) =~ "ConsolePi" ]] ; then
        logit "Building ConsolePi Config for ser2net"
        [[ -f "/etc/ser2net.conf" ]]  && cp /etc/ser2net.conf $bak_dir  ||
            logit "Failed to Back up default ser2net to back dir" "WARNING"
        cp /etc/ConsolePi/src/ser2net.conf /etc/ 2>> $log_file ||
            logit "ser2net Failed to copy config file from ConsolePi src" "ERROR"
    fi

    systemctl daemon-reload ||
        logit "systemctl failed to reload daemons" "WARNING"

    logit "${process} - Complete"
    unset process
}

dhcp_run_hook() {
    process="Configure dhcp.exit-hook"
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

# TODO place ConsolePi_cleanup in src dir and change to systemd
ConsolePi_cleanup() {
    # ConsolePi_cleanup is an init script that runs on startup / shutdown.  On startup it removes tmp files used by ConsolePi script to determine if the ip
    # address of an interface has changed (PB notifications only occur if there is a change). So notifications are always sent after a reboot.
    process="Deploy ConsolePi cleanup init Script"
        file_diff_update /etc/ConsolePi/src/systemd/ConsolePi_cleanup /etc/init.d/ConsolePi_cleanup
    unset process
}

#sub process used by install_ovpn
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

install_ovpn() {
    process="OpenVPN"
    ovpn_ver=$(openvpn --version 2>/dev/null| head -1 | awk '{print $2}')
    if [[ -z "$ovpn_ver" ]]; then
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

install_autohotspotn () {
    process="AutoHotSpotN"
    logit "Install/Update AutoHotSpotN"

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

    systemd_diff_update autohotspot
    if ! head -1 /etc/dnsmasq.conf 2>/dev/null | grep -q 'ConsolePi installer' ; then
        logit "Using New autohotspot specific dnsmasq instance"
        systemctl is-active consolepi-autohotspot-dhcp >/dev/null 2>&1 && was_active=true || was_active=false
        systemd_diff_update consolepi-autohotspot-dhcp
        if ! $was_active && systemctl is-active consolepi-autohotspot-dhcp >/dev/null 2>&1; then
            systemctl stop consolepi-autohotspot-dhcp 2>>$log_file ||
                logit "Failed to stop consolepi-autohotspot-dhcp.service check log" "WARNING"
        fi
        if systemctl is-enabled consolepi-autohotspot-dhcp >/dev/null 2>&1; then
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

    # update hosts file based on supplied variables - this comes into play for devices connected to hotspot (dnsmasq will be able to resolve hostname to wlan IP)
    if [ -z "$local_domain" ]; then
        convert_template hosts /etc/hosts wlan_ip=${wlan_ip} hostname=$(head -1 /etc/hostname)
    else
        convert_template hosts /etc/hosts wlan_ip=${wlan_ip} hostname=$(head -1 /etc/hostname) domain=${local_domain}
    fi
    # file_diff_update /tmp/hosts /etc/hosts
    # rm /tmp/hosts >/dev/null 2>&1

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

disable_autohotspot() {
    process="Verify Auto HotSpot is disabled"
    rc=0
    if systemctl is-active autohotspot >/dev/null 2>&1; then
        systemctl stop autohotspot >/dev/null 2>>$log_file ; ((rc+=$?))
    fi

    if systemctl is-enabled autohotspot >/dev/null 2>&1; then
        systemctl disable autohotspot >/dev/null 2>>$log_file ; ((rc+=$?))
    fi
    [[ $rc -eq 0 ]] && logit "Success Auto HotSpot Service is Disabled" || logit "Error Disabling Auto HotSpot Service" "WARNING"
    unset process
}

do_wired_dhcp() {
    process="wired-dhcp"
    convert_template dnsmasq.eth0 /etc/ConsolePi/dnsmasq.d/wired-dhcp/wired-dhcp.conf dhcp_start="${wired_dhcp_start}" dhcp_end="${wired_dhcp_end}"
        # -- using this vs systemd_diff_update as we don't want the service enabled.  It's activated by exit-hook
    file_diff_update ${src_dir}systemd/consolepi-wired-dhcp.service /etc/systemd/system/consolepi-wired-dhcp.service
}

gen_dnsmasq_conf () {
    process="Configure dnsmasq"
    logit "Generating Files for dnsmasq."
    # check if they are using old method where dnsmasq.conf was used to control dhcp on wlan0
    if head -1 /etc/dnsmasq.conf 2>/dev/null | grep -q 'ConsolePi installer' ; then
        convert_template dnsmasq.conf /etc/dnsmasq.conf wlan_dhcp_start=${wlan_dhcp_start} wlan_dhcp_end=${wlan_dhcp_end}
        ahs_unique_dnsmasq=false
    else
        convert_template dnsmasq.wlan0 /etc/ConsolePi/dnsmasq.d/autohotspot/autohotspot wlan_dhcp_start=${wlan_dhcp_start} wlan_dhcp_end=${wlan_dhcp_end}
        ahs_unique_dnsmasq=true
    fi

    if $ahs_unique_dnsmasq ; then
        if $hotspot && $wired_dhcp ; then
            grep -q 'except-interface=wlan0' /etc/dnsmasq.d/01-consolepi 2>/dev/null ; rc=$?
            grep -q 'except-interface=eth0' /etc/dnsmasq.d/01-consolepi 2>/dev/null ; ((rc+=$?))
            if [[ $rc -gt 0 ]] ; then
                convert_template 01-consolepi /etc/dnsmasq.d/01-consolepi "except_if_lines=except-interface=wlan0{{cr}}except-interface=eth0"
            fi
        elif $hotspot ; then
            grep -q 'except-interface=wlan0' /etc/dnsmasq.d/01-consolepi 2>/dev/null ||
                convert_template 01-consolepi /etc/dnsmasq.d/01-consolepi "except_if_lines=except-interface=wlan0"
        elif $wired_dhcp ; then
            grep -q 'except-interface=eth0' /etc/dnsmasq.d/01-consolepi 2>/dev/null ||
                convert_template 01-consolepi /etc/dnsmasq.d/01-consolepi "except_if_lines=except-interface=eth0"
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
    convert_template dhcpcd.conf /etc/dhcpcd.conf wlan_ip=${wlan_ip} wired_ip=${wired_ip} wired_dhcp=${wired_dhcp} noipv6=${noipv6}
    unset process
}

do_blue_config() {
    process="Bluetooth Console"
    logit "${process} Starting"

    # [ "$btmode" == "serial" ] && local btsrc="${src_dir}systemd/bluetooth.service" || local btsrc="${src_dir}systemd/bluetooth_pan.service"
    btsrc="${src_dir}systemd/bluetooth.service"  # Temp until btpan configuration vetted/implemented
    file_diff_update $btsrc /lib/systemd/system/bluetooth.service

    # create /etc/systemd/system/rfcomm.service to enable
    # the Bluetooth serial port from systemctl
    systemd_diff_update rfcomm

    # enable the new rfcomm service
    do_systemd_enable_load_start rfcomm

    # add blue user and set to launch menu on login
    if $(! grep -q ^blue:.* /etc/passwd); then
        echo -e 'ConsoleP1!!\nConsoleP1!!\n' | sudo adduser --gecos "" blue 1>/dev/null 2>> $log_file &&
        logit "BlueTooth User created" ||
        logit "FAILED to create Bluetooth user" "WARNING"
    else
        logit "BlueTooth User already exists"
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

    # Install picocom
    if [[ $(picocom --help 2>/dev/null | head -1) ]]; then
        logit "$(picocom --help 2>/dev/null | head -1) is already installed"
    else
        process_cmds -apt-install picocom
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
        _error=false
        if ! systemctl status "$d" | grep -q disabled ; then
            [[ "$d" =~ "socket" ]] && logit "disabling ${d%.*} ConsolePi has it's own mdns daemon"
            systemctl stop "$d" >/dev/null 2>&1 || _error=true
            systemctl disable "$d" 2>/dev/null || _error=true
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
        found_path=$(get_staged_file_path "wpa_supplicant.conf")
        if [[ -f $found_path ]]; then
            logit "Found stage file ${found_path} Applying"
            # ToDo compare the files ask user if they want to import if they dont match
            [[ -f $wpa_supplicant_file ]] && sudo cp $wpa_supplicant_file $bak_dir
            sudo mv $found_path $wpa_supplicant_file
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
    prompt="Do You want to configure${word} WLAN SSIDs"
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

misc_stuff() {
    if $hotspot && [ ${wlan_country^^} == "US" ]; then
        process="Set Keyboard Layout"
        logit "${process} - Starting"
        sudo sed -i "s/gb/${wlan_country,,}/g" /etc/default/keyboard &&
            logit "Success - KeyBoard Layout changed to ${wlan_country,,}" ||
            logit "${process} - Failed ~ verify contents of /etc/default/keyboard" "WARNING"
        unset process
    fi

    # -- Commented out for now because it apparently didn't work as expected, get occasional error msg
    # -- set locale -- # if US haven't verified others use same code as wlan_country
    # if [ ${wlan_country^^} == "US" ]; then
    #     process="Set locale"
    #     logit "${process} - Starting"
    #     sudo sed -i "s/GB/${wlan_country^^}/g" /etc/default/locale && logit "all locale vars changed to en_${wlan_country^^}.UTF-8" &&
    #     grep -q LANGUAGE= /etc/default/locale || echo LANGUAGE=en_${wlan_country^^}.UTF-8 >> /etc/default/locale
    #     grep -q LC_ALL= /etc/default/locale || echo LC_ALL=en_${wlan_country^^}.UTF-8 >> /etc/default/locale
    #     ! $(grep -q GB /etc/default/locale) && grep -q LANGUAGE= /etc/default/locale && grep -q LC_ALL= /etc/default/locale &&
    #         logit "${process} - Success" || logit "${process} - Failed ~ verify contents of /etc/default/locale" "WARNING"
    #     unset process
    # fi
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
    echo -e "-    of an adapter or if you only plan to use a single adapter.  Otherwise setting predictable aliases is           -"
    echo -e "-    ${_lred}highly recommended${_norm}.                                                                                            -"
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
        if [ -d "$dir" ]; then
            basename "$(dirname "$dir")"
        fi
    done
}

do_wifi_country() {
    process="Set WiFi Country"
    IFACE="$(list_wlan_interfaces | head -n 1)"
    [ -z "$IFACE" ] && $IFACE=wlan0

    if ! wpa_cli -i "$IFACE" status > /dev/null 2>&1; then
        logit "Could not communicate with wpa_supplicant ~ normal if there is no wlan interface" "WARNING"
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

    # -- always check to see if rfkill is blocking wifi --
    if hash rfkill 2> /dev/null; then
        rfkill unblock wifi
    fi
    unset process
}

# -- run custom post install script --
custom_post_install_script() {
    if ! $upgrade; then
        found_path=$(get_staged_file_path "consolepi-post.sh")
        if [[ $found_path ]]; then
            process="Run Custom Post-install script"
            logit "Post Install Script ${found_path} Found. Executing"
            $found_path && logit "Post Install Script Complete No Errors" ||
                logit "Error Code returned by Post Install Script" "WARNING"
            unset process
        fi
    fi
}

# -- Display Post Install Message --
post_install_msg() {
    clear;echo
    declare -a _msg=(
            -head "${_green}Installation Complete${_norm}"
            "${_bold}Next Steps/Info${_norm}"
            -nl
            " ${_bold}Cloud Sync:${_norm}"
            "  if you plan to use cloud sync.  You will need to do some setup on the Google side and Authorize ConsolePi"
            "  refer to the GitHub for more details"
            -nl
            " ${_bold}OpenVPN:${_norm}"
            "  if you are using the Automatic VPN feature you should Configure the ConsolePi.ovpn and ovpn_credentials files in"
            "  /etc/openvpn/client.  Then run 'consolepi-upgrade' which will add a few lines to the config to enable some"
            "  ConsolePi functionality.  There is a .example file for reference as well."
            "  !! You should \"sudo chmod 600 <filename>\" both of the files for added security !!"
            -nl
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
            -li "${_cyan}consolepi-addssids${_norm}: Add additional known ssids. Alternatively you can add entries to wpa_supplicant manually"
            -li "${_cyan}consolepi-addconsole${_norm}: Configure serial adapter to telnet port rules"
            -li "${_cyan}consolepi-showaliases${_norm}: Shows Configured adapter aliases, helps identify any issues with aliases"
            -li "${_cyan}consolepi-logs${_norm}: Displays ConsolePi logs (Note this will install mutli-tail the first time it's ran)"
            "     valid args: 'all' (will cat consolepi.log), any other argument is passed to tail as a flag."
            "                 If no arguments are specified, script will follow tail on consolepi-log, and syslog (with filters)"
            "     examples: \"consolepi-logs all\", \"consolepi-logs -f\", \"consolepi-logs -20\", \"consolepi-logs 20\""
            -li "${_cyan}consolepi-killvpn${_norm}: Gracefully terminate openvpn tunnel if one is established"
            -li "${_cyan}consolepi-autohotspot${_norm}: Manually invoke AutoHotSpot function which will look for known SSIDs and connect if found"
            "     then fall-back to HotSpot mode if not found or unable to connect"
            -li "${_cyan}consolepi-testhotspot${_norm}: Disable/Enable the SSIDs ConsolePi tries to connect to before falling back to hotspot"
            "     Used to test hotspot function.  Script Toggles state if enabled it will disable and vice versa"
            -li "${_cyan}consolepi-bton${_norm}: Make BlueTooth Discoverable and pairable - this is the default behavior on boot"
            -li "${_cyan}consolepi-btoff${_norm}: Disable BlueTooth Discoverability.  You can still connect if previously paired"
            -li "${_cyan}consolepi-details${_norm}: Refer to GitHub for usage, but in short dumps the data the ConsolePi would run with based"
            "     on configuration, discovery, etc.  Dumps everything if no args"
            "     valid args: adapters, interfaces, outlets, remotes, local, <hostname of remote>.  GitHub for more detail"
            -nl
            -foot "ConsolePi Installation Script v${INSTALLER_VER}"
        )
    menu_print "${_msg[@]}"

    # Display any warnings if they exist
    if [ "$warn_cnt" -gt 0 ]; then
        echo -e "\n${_red}---- warnings exist ----${_norm}"
        grep -A 999 "${log_start}" $log_file | grep -v "^WARNING: Retrying " | grep -v "apt does not have a stable CLI interface" | grep "WARNING\|failed"
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
        misc_imports
    fi
    install_ser2net
    dhcp_run_hook
    ConsolePi_cleanup
    $ovpn_enable && install_ovpn
    if $hotspot ; then
        install_autohotspotn
        gen_dnsmasq_conf
        gen_dhcpcd_conf
    else
        disable_autohotspot
    fi
    $wired_dhcp && do_wired_dhcp
    do_blue_config
    do_consolepi_api
    do_consolepi_mdns
    ! $upgrade && misc_stuff
    do_resize
    if ( [ ! -z "$skip_utils" ] && $skip_utils ) || $silent; then
        logit -t "optional utilities installer" "utilities menu bypassed by config variable"
    else
        get_utils
        util_main
    fi

    if ! $silent; then
        get_known_ssids
        get_serial_udev
    else
        logit -t "Configure WLAN - Predictable Console Ports" "Prompts bypassed due to -silent flag"
    fi
    custom_post_install_script
    process=Complete
    if ! $silent; then
        post_install_msg
    else
        _msg="Success Silent Install Complete a reboot is required."
        [[ "$warn_cnt" > 0 ]] && logit "$_msg\n ${_red}Warnings Occurred During Install ($warn_cnt)${_norm}." | cut -d']' -f4- || echo "$_msg"
    fi
    $silent && $do_reboot && echo -e "\n${_green}Install Complete${_norm}\n  system will reboot in 10 seconds (CTRL+C to abort reboot)" && sleep 10 && reboot
}

# ( set -o posix ; set ) | grep -v _xspecs | grep -v LS_COLORS # DEBUG Line
