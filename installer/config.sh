#!/usr/bin/env bash

# ConsolePi ~ Get Configuration details from user (stage 2 of install)
# Author: Wade Wells

# wired_dhcp=false  # Temp until this is added as config option

get_static() {
    process="get static vars"
    process_yaml static
    [ -z "$CONFIG_FILE_YAML" ] && logit "Unable to load static variables" "ERROR" ||
        logit "load static vars from .static.yaml Successful"
}

get_config() {
    process="get config"
    bypass_verify=false
    selected_prompts=false
    logit "Starting get/build Configuration"
    if [ ! -f "$CONFIG_FILE" ] && [ ! -f "$CONFIG_FILE_YAML" ]; then
        found_path=$(get_staged_file_path "ConsolePi.yaml")
        [ -z "$found_path" ] && found_path=$(get_staged_file_path "ConsolePi.conf")
        if [ ! -z "$found_path" ] ; then
            logit "using provided config: ${found_path}"
            mv $found_path $consolepi_dir 2>>$log_file || logit "Error Moving staged config @ $found_path to $consolepi_dir" "WARNING"
        else
            do_default_config
        fi
    fi
    process_yaml
    if [ -z "$cfg_file_ver" ] || [ "$cfg_file_ver" -lt "$CFG_FILE_VER" ]; then
        bypass_verify=true         # bypass verify function
        input=false                # so collect function will run (while loop in main)
        selected_prompts=true
        echo "-- NEW OPTIONS HAVE BEEN ADDED DATA COLLECTION PROMPTS WILL DISPLAY --"
    fi
    hotspot_dhcp_range
    wired_dhcp_range
    unset process
}

do_default_config() {
    echo -e "%YAML 1.2\n---\nCONFIG:" > "$CONFIG_FILE_YAML"
    echo "  cfg_file_ver: ${CFG_FILE_VER} # ---- Do Not Delete or modify this line ---- #" >> "$CONFIG_FILE_YAML"
    # TODO remove the btmode exclusion after btmode implemented
    [[ -f $CONFIG_FILE_YAML.example ]] && sed -n '/cfg_file_ver/,/^ *$/p' $CONFIG_FILE_YAML.example | tail -n +2 | grep -v btmode >> $CONFIG_FILE_YAML
    [[ -f $CONFIG_FILE_YAML.example ]] && sed -n '/OVERRIDES:/,/^ *$/p' $CONFIG_FILE_YAML.example >> $CONFIG_FILE_YAML
    # -- // Prompt for interactive Mode \\ --
    header
    echo "Configuration File Created with default values. Enter y to continue in Interactive Mode"
    echo "which will prompt you for each value. Enter n to exit the script so you can modify the"
    echo "defaults directly then re-run the script."
    echo
    prompt="Continue in Interactive mode"
    user_input true "${prompt}"
    go=$result
    if $go ; then
        bypass_verify=true         # bypass verify function
        input=false                # so collect function will run (while loop in main)
    else
        header
        echo "Please edit config in ${CONFIG_FILE_YAML} using editor (i.e. nano) and re-run install script 'consolepi-install'"
        echo "i.e. sudo nano ${CONFIG_FILE_YAML}"
        cat /etc/ConsolePi/src/consolepi-commands/consolepi-upgrade > /usr/local/bin/consolepi-install
        chmod +x /usr/local/bin/consolepi-install
        [ -f $final_log ] && mv $final_log $final_log.1  # This will cause script to run as an install vs. upgrade when re-ran
        echo
        exit 0
    fi
}

update_config() {
    process="Updating Config"
    yml_temp="/tmp/yml_temp"
    echo "%YAML 1.2" > $yml_temp
    echo "---" >> $yml_temp
    echo "CONFIG:" >> $yml_temp
    echo "  cfg_file_ver: ${CFG_FILE_VER} # ---- Do Not Delete or modify this line ----" "#" >> $yml_temp
    spaces "push: ${push}" "# PushBullet Notifications: true - enable, false - disable" >> $yml_temp
    spaces "push_all: ${push_all}" "# PushBullet send notifications to all devices: true - yes, false - send only to device with iden specified by push_iden" >> $yml_temp
    spaces "push_api_key: \"${push_api_key}\"" "# PushBullet API key" >> $yml_temp
    spaces "push_iden: \"${push_iden}\"" "# iden of device to send PushBullet notification to if not push_all" >> $yml_temp
    spaces "ovpn_enable: ${ovpn_enable}" "# if enabled will establish VPN connection" >> $yml_temp
    spaces "vpn_check_ip: ${vpn_check_ip}" "# used to check VPN (internal) connectivity should be ip only reachable via VPN" >> $yml_temp
    spaces "net_check_ip: ${net_check_ip}" "# used to check Internet connectivity" >> $yml_temp
    spaces "local_domain: ${local_domain}" "# used to bypass VPN. evals domain sent via dhcp option if matches this var will not establish vpn" >> $yml_temp
    spaces "hotspot: ${hotspot}" "# wheather to enable AutoHotSpot Feature" >> $yml_temp
    spaces "wlan_ip: ${wlan_ip}" "# IP of ConsolePi when in hotspot mode" >> $yml_temp
    spaces "wlan_ssid: ${wlan_ssid}" "# SSID used in hotspot mode" >> $yml_temp
    spaces "wlan_psk: ${wlan_psk}" "# psk used for hotspot SSID" >> $yml_temp
    spaces "wlan_country: ${wlan_country}" "# regulatory domain for hotspot SSID" >> $yml_temp
    spaces "wired_dhcp: ${wired_dhcp}" "# Run dhcp on eth interface (after trying as client)" >> $yml_temp
    spaces "wired_ip: ${wired_ip}" "# Fallback IP for eth interface" >> $yml_temp
    # spaces "btmode: ${btmode}" "# Bluetooth Mode: 'serial' or 'pan'" >> $yml_temp  # Not Implemented yet
    spaces "cloud: ${cloud}" "# enable ConsolePi cloud sync for Clustering (mdns enabled either way)" >> $yml_temp
    spaces "cloud_svc: ${cloud_svc}" "# must be gdrive (all that is supported now)" >> $yml_temp
    spaces "rem_user: ${rem_user}" "# The user account remotes should use to access this ConsolePi" >> $yml_temp
    spaces "power: ${power}" "# Enable Power Outlet Control" >> $yml_temp
    spaces "debug: ${debug}" "# Turns on additional debugging" >> $yml_temp
    # echo "" >> $yml_temp
    if [[ -f $CONFIG_FILE_YAML ]] ; then

        # get all other optional config sections from existing config (POWER, HOSTS, TTYAMA, LOCALTTY)
        awk 'matched; /^  debug:/ { matched = 1 } ' $CONFIG_FILE_YAML | awk '/^[A-Z]*$/ { matched = 1 } matched' >> $yml_temp
    fi

    file_diff_update $yml_temp $CONFIG_FILE_YAML
    rm $yml_temp

    # TODO Move this to common as a function
    group=$(stat -c '%G' $CONFIG_FILE_YAML)
    if [ ! $group == "consolepi" ]; then
        sudo chgrp consolepi $CONFIG_FILE_YAML 2>> $log_file &&
            logit "Successfully Updated Config File Group Ownership" ||
            logit "Failed to Update Config File Group Ownership (consolepi)" "WARNING"
    else
        logit "Config File Group ownership already OK"
    fi
    if [ ! $(stat -c "%a" $CONFIG_FILE_YAML) == 664 ]; then
        sudo chmod g+w $CONFIG_FILE_YAML &&
            logit "Config File Permissions Updated (group writable)" ||
            logit "Failed to make Config File group writable" "WARNING"
    else
        logit "Config File Group Permissions already OK"
    fi


    if [[ -f $CONFIG_FILE ]] ; then
        echo "ConsolePi now supports a new Configuration format and is configured via ConsolePi.yaml"
        echo -e "The Legacy configuration ConsolePi.conf has been converted to ConsolePi.yaml\n"
        mv $CONFIG_FILE $bak_dir && logit "Legacy Config ConsolePi.conf found moving to bak dir." ||
            logit "Failed to Back up legacy ConsolePi.conf to bak dir"
    fi
    if [[ -f $POWER_FILE ]] ; then
        logit "Legacy power config file power.json found.  You should move Power Settings to the new ConsolePi.yaml"
        echo -e "\n-- FOUND LEGACY OUTLET CONFIGURATION power.json --"
        echo -e "\nConsolePi now supports a sinlge all in one configuration file ConsolePi.yaml"
        echo -e "Power outlet and manual host definitions can now be defined in ConsolePi.yaml"
        echo -e "refer to the example file and the ReadMe for formatting."
        echo -e "\nAn existing power.json was found, which *should* continue to work but it is reccomended"
        echo -e "to move your outlet deffinitions to ConsolePi.yaml\n"
        echo -e "\nOnce Power Configuration has been migrated to ConsolePi.yaml, move or delete power.json"
        echo -e "from $consolepi_dir to git rid of this warning.\n"
        read -n 1 -p "Press any key to continue"
    fi
    if [[ -f $REM_HOST_FILE ]] ; then
        logit "Legacy host file hosts.json found.  You should move these Settings to the new ConsolePi.yaml"
        echo -e "\nConsolePi now supports a sinlge all in one configuration file ConsolePi.yaml"
        echo -e "\n-- FOUND LEGACY HOST CONFIGURATION hosts.json --"
        echo -e "Power outlet and manual host definitions can now be defined in ConsolePi.yaml"
        echo -e "refer to the example file and the ReadMe for formatting."
        echo -e "\nAn existing host.json was found, which *should* continue to work but it is reccomended"
        echo -e "to move your host deffinitions to ConsolePi.yaml\n"
        echo -e "\nOnce Host Configuration has been migrated to ConsolePi.yaml, move or delete hosts.json"
        echo -e "from $consolepi_dir to git rid of this warning.\n"
        read -n 1 -p "Press any key to continue"
    fi
}

# -- Automatically set the DHCP range based on the hotspot IP provided --
hotspot_dhcp_range() {
    if [ -z "$wlan_ip" ] || [ "$wlan_ip" == "None" ]; then
        wlan_ip=10.110.0.1
    fi
    baseip=`echo $wlan_ip | cut -d. -f1-3`   # get first 3 octets of wlan_ip
    wlan_dhcp_start=$baseip".101"
    wlan_dhcp_end=$baseip".150"
}

# -- Automatically set the DHCP range based on the eth IP provided --
wired_dhcp_range() {
    if [ -z "$wired_ip" ] || [ "$wired_ip" == "None" ]; then
        wired_ip=10.30.0.1
    fi
    baseip=`echo $wired_ip | cut -d. -f1-3`   # get first 3 octets of wired_ip
    wired_dhcp_start=$baseip".101"
    wired_dhcp_end=$baseip".150"
}

collect() {
    # -- PushBullet  --
    if ! $selected_prompts || [ -z "$push" ]; then
        header
        prompt="Configure ConsolePi to send notifications via PushBullet"
        user_input $push "${prompt}"
        push=$result
        if $push; then

            # -- PushBullet API Key --
            header
            prompt="PushBullet API key"
            user_input "$push_api_key" "${prompt}"
            push_api_key=$result

            # -- Push to All Devices --
            header
            echo "Do you want to send PushBullet Messages to all PushBullet devices?"
            echo "Answer 'N'(no) to send to just 1 device "
            echo
            prompt="Send PushBullet Messages to all devices"
            user_input "$push_all" "${prompt}"
            push_all=$result

            # -- PushBullet device iden --
            if ! $push_all; then
                [ ${#push_iden} -gt 0 ] && default="[${push_iden}]"
                header
                prompt="Provide the iden of the device you would like PushBullet Messages sent to"
                user_input $push_iden "${prompt}"
                push_iden=$result
            else
                push_iden="NotUsedSendToAll"
            fi
        fi
    fi


    # -- OpenVPN --
    # TODO break into seperate prompts/variables for new_upper Q auto_vpn (bool) and if auto_vpn=true then prompt for ovpn_enable to determine if plugin needs to be installed
    if ! $selected_prompts || [ -z "$ovpn_enable" ]; then
        header
        prompt="Enable Auto-Connect OpenVPN"
        user_input $ovpn_enable "${prompt}"
        ovpn_enable=$result

        # -- VPN Check IP --
        if $ovpn_enable; then
            header
            echo "Provide an IP address used to check vpn connectivity (an IP only reachable once VPN is established)"
            echo "Typically you would use the OpenVPN servers inside interface IP."
            echo
            prompt="IP Used to verify reachability inside OpenVPN tunnel"
            user_input $vpn_check_ip "${prompt}"
            vpn_check_ip=$result

            # -- Net Check IP --
            header
            prompt="Provide an IP address used to verify Internet connectivity"
            user_input $net_check_ip "${prompt}"
            net_check_ip=$result

            # -- Local Lab Domain --
            header
            echo "ConsolePi uses the domain provided by DHCP to determine if it's on your local network"
            echo "If you are connected locally (No VPN will be established)"
            echo
            prompt="Local Lab Domain"
            user_input $local_domain "${prompt}"
            local_domain=$result
        fi
    fi

    # -- HotSpot  --
    if ! $selected_prompts || [ -z "$hotspot" ]; then
        header
        echo -e "\nWith the Auto HotSpot Feature Enabled ConsolePi will do the following on boot:"
        echo "  - Scan for configured SSIDs and attempt to connect as a client."
        echo -e "  - If no configured SSIDs are found, it will Fallback to HotSpot Mode and act as an AP.\n"
        prompt="Enable Automatic Fallback to HotSpot on $wlan_iface"
        # [[ -z "$hotspot" ]] && hotspot=true
        hotspot=${hotspot:-true}
        user_input $hotspot "${prompt}"
        hotspot=$result

        # -- HotSpot IP --
        if $hotspot ; then
            header
            prompt="What IP do you want to assign to ConsolePi when acting as HotSpot"
            user_input $wlan_ip "${prompt}"
            wlan_ip=$result
            hotspot_dhcp_range

            # -- HotSpot SSID --
            header
            prompt="What SSID do you want the HotSpot to Broadcast when in HotSpot mode"
            user_input $wlan_ssid "${prompt}"
            wlan_ssid=$result

            # -- HotSpot psk --
            header
            prompt="Enter the psk used for the HotSpot SSID"
            user_input $wlan_psk "${prompt}"
            wlan_psk=$result
        fi
    fi

    # -- wifi/hotspot country --
    if ! $selected_prompts || [ -z "$wlan_country" ]; then
        header
        prompt="Enter the 2 character regulatory domain (country code) used for the HotSpot SSID"
        user_input "US" "${prompt}"
        wlan_country=$result
    fi

    # -- Enable DHCP on eth interface --
    if ! $selected_prompts || [ -z "$wired_ip" ]; then
        header
        echo -e "\nWith the ${_green}Wired fallback to DHCP Server${_norm} Feature Enabled ConsolePi will do the following when the wired interface is connected ($wired_iface):"
        echo -e "  - Use native dhcpcd mechanism to fallback to Static IP if no address is recieved from a DHCP Server"
        echo -e "  - Start a DHCP Server on the wired interface (ConsolePi will act as a DHCP server for other clients on the network)"
        echo -e "  - If WLAN is connected and has internet access, wired traffic will NAT out the wlan interface.\n"
        echo
        echo -e "  This feature is intented to aid the configuration of Factory Default hardware or via oobm/isolated network."
        echo -e "\n  *** ${_lred}${_blink}Use with caution${_norm} ***\n"
        echo -e "  Running a DHCP server on a production network can lead to client connectivity issues."
        echo -e "  This function relies on a fall-back mechanism, only enabling the DHCP server after failure to receive an address"
        echo -e "  as a client.  However care should still be taken.\n"
        echo -e "  * The current behavior is once it has fallen back, and the DHCP Server is started, it stays that way until reboot"
        echo -e "    or you disable it manually ${_cyan}sudo systemctl stop consolepi-wired-dhcp${_norm}\n"
        # echo -e "  - If an openvpn tunnel is established, The Tunnel network will be shared with wired clients."
        prompt="Do you want to run DHCP Server on $wired_iface (Fallback if no address as client)"
        wired_dhcp=${wired_dhcp:-false}
        user_input $wired_dhcp "${prompt}"
        wired_dhcp=$result
        if $wired_dhcp; then
            prompt="What IP do you want to assign to $wired_iface"
            user_input ${wired_ip:-"10.12.0.1"} "${prompt}"
            wired_ip=$result
            wired_dhcp_range
        fi
    fi

    # -- Bluetooth Mode --
    # if ! $selected_prompts || [ -z "$btmode" ]; then
    #     header
    #     echo -e "\nBluetooth Configuration Options:\n"
    #     echo -e "  1. Serial: BT client would connect to ConsolePi via rfcomm/virtual com port"
    #     echo -e "  2. PAN (personal area network): BT Client would connect to ConsolePi via SSH"
    #     echo
    #     [ -z "$btmode" ] && btmode=serial
    #     while [ "$result" != "1" ] && [ "$result" != "2" ]; do
    #         prompt="How do you want BlueTooth Configured (1/2)"
    #         user_input "NUL" "${prompt}"
    #         [ "$result" != "1" ] && [ "$result" != "2" ] &&
    #             echo -e "\n${_lred}Invalid Response $result${_norm}: Enter 1 for Serial or 2 for PAN\n"
    #     done
    #     [ $result == "1" ] && btmode=serial || btmode=pan
    # fi

    # -- cloud --
    if ! $selected_prompts || [ -z "$cloud" ]; then
        header
        # [ -z "$cloud" ] && cloud=false
        cloud=${cloud:-false}
        user_input $cloud "Do you want to enable ConsolePi Cloud Sync with Gdrive"
        cloud=$result
        cloud_svc="gdrive" # only supporting gdrive for cloud sync
    fi

    # -- rem_user --
    if ! $selected_prompts || [ -z "$rem_user" ]; then
        header
        [ -z "$rem_user" ] && rem_user=$iam
        echo "If you have multiple ConsolePis they can discover each other over the network via mdns"
        echo "and if enabled can sync via Google Drive."
        echo
        echo "The Remote User is typically consolepi but can be any user given they are members of"
        echo "the dialout and consolepi groups.  Remotes connect via ssh."
        echo
        user_input $rem_user "What user should remote ConsolePis use to connect to this ConsolePi"
        rem_user=$result
        if ! groups $rem_user 2>>$log_file | grep dialout| grep -q consolepi ; then
            logit "$rem_user is lacking membership to consolepi and/or dialout groups, please verify after install"
        fi
    fi

    # -- power Control --
    if ! $selected_prompts || [ -z "$power" ]; then
        header
        prompt="Do you want to enable ConsolePi Power Outlet Control"
        # [ -z "$power" ] && power=false
        power=${power:-false}
        user_input $power "${prompt}"
        power=$result
        if $power; then
            echo -e "\nTo Complete Power Control Setup you need to populate the ${_cyan}POWER:${_norm} section of /etc/ConsolePi/ConsolePi.yaml"
            echo -e "Refer to GitHub or ConsolePi.yaml.example for examples.  Ensure you follow proper yaml format"
            echo -e "\nConsolePi currently supports Control of GPIO controlled Power Outlets (relays), IP connected"
            echo -e "outlets flashed with espHome or tasmota firmware, and digital-loggers web/ethernet Power Switches."
            echo -e "See GitHub for more details.\n"
            read -n 1 -p "Press any key to continue"
        fi
    fi
}

verify() {
    selected_prompts=false
    header
    echo "-------------------------------------------->>PLEASE VERIFY VALUES<<--------------------------------------------"
    echo
    dots "Send Notifications via PushBullet?" "$push"
    if $push; then
        dots "PushBullet API Key" "${push_api_key}"
        dots "Send Push Notification to all devices?" "$push_all"
        ! $push_all &&
        dots "iden of device to receive PushBullet Notifications" "${push_iden}"
    fi

    dots "Enable Automatic VPN?" "$ovpn_enable"
    if $ovpn_enable; then
        dots "IP used to verify VPN is connected" "$vpn_check_ip"
        dots "IP used to verify Internet connectivity" "$net_check_ip"
        dots "Local Lab Domain" "$local_domain"
    fi

    dots "Enable Automatic HotSpot ($wlan_iface)" "$hotspot"
    if $hotspot ; then
        dots "ConsolePi Hot Spot IP" "$wlan_ip"
        dots " *hotspot DHCP Range" "${wlan_dhcp_start} to ${wlan_dhcp_end}"
        dots "ConsolePi HotSpot SSID" "$wlan_ssid"
        dots "ConsolePi HotSpot psk" "$wlan_psk"
    fi
    dots "ConsolePi WLAN regulatory domain" "$wlan_country"
    dots "Wired ~ Fallback to DHCP Server" "$wired_dhcp"
    if $wired_dhcp; then
        dots "Wired Fallback IP" "$wired_ip"
        dots " *Wired DHCP Range" "${wired_dhcp_start} to ${wired_dhcp_end}"
    fi
    dots "ConsolePi Cloud Support" "$cloud"
    $cloud && dots "ConsolePi Cloud Service" "$cloud_svc"
    dots "User used by Remotes to connect to this ConsolePi" "$rem_user"
    dots "ConsolePi Power Control Support" "$power"
    echo
    echo "----------------------------------------------------------------------------------------------------------------"
    echo
    echo "Enter Y to Continue N to make changes"
    echo
    prompt="Are Values Correct"
    input=$(user_input_bool)
}

config_main() {
    get_static
    get_config
    get_interfaces # provides $wired_iface and $wlan_iface in global scope
    if ! $silent; then
        ! $bypass_verify && verify
        while ! $input; do
            collect
            verify
        done
    fi
    update_config
}
