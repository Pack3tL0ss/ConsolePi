#!/usr/bin/env bash

# ConsolePi ~ Get Configuration details from user (stage 2 of install)
# Author: Wade Wells

process_yaml() {
    $yml_script "${@}" > $tmp_src 2>>$log_file && . $tmp_src && rm $tmp_src
}

get_static() {
    process="get static vars"
    process_yaml static
    [[ -z $CONFIG_FILE_YAML ]] && logit "Unable to load static variables" "ERROR" ||
        logit "load static vars from .static.yaml Successful"
}

get_config() {
    process="get config"
    bypass_verify=false
    selected_prompts=false
    logit "Starting get/build Configuration"
    if [[ ! -f $CONFIG_FILE ]] && [[ ! -f $CONFIG_FILE_YAML ]]; then
        found_path=$(get_staged_file_path "ConsolePi.yaml")
        [[ -z $found_path ]] && found_path=$(get_staged_file_path "ConsolePi.conf")
        if [[ ! -z $found_path ]] ; then
            logit "using provided config: ${found_path}"
            mv $found_path $consolepi_dir 2>>$log_file || logit "Error Moving staged config @ $found_path to $consolepi_dir" "WARNING"
        else
            do_default_config
        fi
    fi
    process_yaml
    if [ -z $cfg_file_ver ] || [ $cfg_file_ver -lt $CFG_FILE_VER ]; then
        bypass_verify=true         # bypass verify function
        input=false                # so collect function will run (while loop in main)
        selected_prompts=true
        echo "-- NEW OPTIONS HAVE BEEN ADDED DATA COLLECTION PROMPTS WILL DISPLAY --"
    fi
    hotspot_dhcp_range
    unset process
}

do_default_config() {
    echo -e "%YAML 1.2\n---\nCONFIG:" > "$CONFIG_FILE_YAML"
    echo "  cfg_file_ver: ${CFG_FILE_VER} # ---- Do Not Delete or modify this line ---- #" >> "$CONFIG_FILE_YAML"
    # -- Put this in thinking, self, what if the user mv / renames the example file 
    # -- but then I was like, self, that's dumb, the git-pull will grab it again.
    # echo "  push: true # PushBullet Notifications: true - enable, false - disable" >> "$CONFIG_FILE_YAML"
    # echo "  push_all: true # PushBullet send notifications to all devices: true - yes, false - send only to device with iden specified by push_iden" >> "$CONFIG_FILE_YAML"
    # echo "  push_api_key: __PutYourPBAPIKeyHereChangeMe__ # PushBullet API key" >> "$CONFIG_FILE_YAML"
    # echo "  push_iden: __putyourPBidenHere__ # iden of device to send PushBullet notification to if not push_all" >> "$CONFIG_FILE_YAML"
    # echo "  ovpn_enable: false # if enabled will establish VPN connection" >> "$CONFIG_FILE_YAML"
    # echo "  vpn_check_ip: 10.0.150.1 # used to check VPN (internal) connectivity should be ip only reachable via VPN" >> "$CONFIG_FILE_YAML"
    # echo "  net_check_ip: 8.8.8.8 # used to check internet connectivity" >> "$CONFIG_FILE_YAML"
    # echo "  local_domain: example.com # used to bypass VPN. evals domain sent via dhcp option if matches this var will not establish vpn" >> "$CONFIG_FILE_YAML"
    # echo "  wlan_ip: 10.3.0.1 # IP of ConsolePi when in hotspot mode" >> "$CONFIG_FILE_YAML"
    # echo "  wlan_ssid: ConsolePi # SSID used in hotspot mode" >> "$CONFIG_FILE_YAML"
    # echo "  wlan_psk: ChangeMe!! # psk used for hotspot SSID" >> "$CONFIG_FILE_YAML"
    # echo "  wlan_country: US # regulatory domain for hotspot SSID" >> "$CONFIG_FILE_YAML"
    # echo "  cloud: false # enable ConsolePi clustering / cloud config sync" >> "$CONFIG_FILE_YAML"
    # echo '  cloud_svc: gdrive # Currently only option is "gdrive"' >> "$CONFIG_FILE_YAML"
    # echo '  power: false # Adds support for Power Outlet control' >> "$CONFIG_FILE_YAML"
    # echo -e "  debug: false # turns on additional debugging\n" >> "$CONFIG_FILE_YAML"
    [[ -f $CONFIG_FILE_YAML.example ]] && sed -n '/cfg_file_ver/,/# --- The Remaining/p' $CONFIG_FILE_YAML.example | tail -n +2 | head -n -1 >> $CONFIG_FILE_YAML
    [[ -f $CONFIG_FILE_YAML.example ]] && sed -n '/OVERRIDES:/,/^#.*$/p' $CONFIG_FILE_YAML.example | head -n -1 >> $CONFIG_FILE_YAML
    # -- // Prompt for interactive Mode \\ --
    header
    echo "Configuration File Created with default values. Enter y to continue in Interactive Mode"
    echo "which will prompt you for each value. Enter n to exit the script so you can modify the"
    echo "defaults directly then re-run the script."
    echo
    prompt="Continue in Interactive mode"
    user_input true "${prompt}"
    continue=$result
    if $continue ; then
        bypass_verify=true         # bypass verify function
        input=false                # so collect function will run (while loop in main)
    else
        header
        echo "Please edit config in ${$CONFIG_FILE_YAML} using editor (i.e. nano) and re-run install script"
        echo "i.e. sudo nano ${$CONFIG_FILE_YAML}"
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
    echo "  cfg_file_ver: ${CFG_FILE_VER} # ---- Do Not Delete or modify this line ---- #" >> $yml_temp
    echo "  push: ${push} # PushBullet Notifications: true - enable, false - disable" >> $yml_temp
    echo "  push_all: ${push_all} # PushBullet send notifications to all devices: true - yes, false - send only to device with iden specified by push_iden" >> $yml_temp
    echo "  push_api_key: /"${push_api_key}/" # PushBullet API key" >> $yml_temp
    echo "  push_iden: /"${push_iden}/" # iden of device to send PushBullet notification to if not push_all" >> $yml_temp
    echo "  ovpn_enable: ${ovpn_enable} # if enabled will establish VPN connection" >> $yml_temp
    echo "  vpn_check_ip: ${vpn_check_ip} # used to check VPN (internal) connectivity should be ip only reachable via VPN" >> $yml_temp
    echo "  net_check_ip: ${net_check_ip} # used to check Internet connectivity" >> $yml_temp
    echo "  local_domain: ${local_domain} # used to bypass VPN. evals domain sent via dhcp option if matches this var will not establish vpn" >> $yml_temp
    echo "  wlan_ip: ${wlan_ip} # IP of ConsolePi when in hotspot mode" >> $yml_temp
    echo "  wlan_ssid: ${wlan_ssid} # SSID used in hotspot mode" >> $yml_temp
    echo "  wlan_psk: ${wlan_psk} # psk used for hotspot SSID" >> $yml_temp
    echo "  wlan_country: ${wlan_country} # regulatory domain for hotspot SSID" >> $yml_temp
    echo "  cloud: ${cloud} # enable ConsolePi cloud sync for Clustering (mdns enabled either way)" >> $yml_temp
    echo "  cloud_svc: ${cloud_svc} # must be gdrive (all that is supported now)" >> $yml_temp
    echo "  rem_user: ${rem_user} # The user account remotes should use to access this ConsolePi" >> $yml_temp
    echo "  power: ${power} # Enable Power Outlet Control" >> $yml_temp
    echo "  debug: ${debug} # Turns on additional debugging" >> $yml_temp
    echo "" >> $yml_temp
    if [[ -f $CONFIG_FILE_YAML ]] ; then
        sed -n '/debug:/,//p' $CONFIG_FILE_YAML | tail -n +2 >> $yml_temp
    fi
    if [[ -f $CONFIG_FILE_YAML ]] ; then
        cp $CONFIG_FILE_YAML $bak_dir && logit "Backed up existing ConsolePi.yaml to bak dir" ||
            logit "Failed to Back up existing ConsolePi.yaml to bak dir"
        
    fi
    # -- // Move updated yaml to Config.yaml \\ --
    if cat $yml_temp >> $CONFIG_FILE_YAML ; then
        chgrp consolepi $CONFIG_FILE_YAML 2>>$log_file || logit "Failed to chg group for ConsolePi.yaml to consolepi group" "WARNING"
        chmod g+w $CONFIG_FILE_YAML 2>>$log_file || logit "Failed to make ConsolePi.yaml group writable" "WARNING"
        rm $yml_temp
    else
        logit "Failed to Copy updated yaml Config to ConsolePi.yaml" "ERROR"
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

# Automatically set the DHCP range based on the hotspot IP provided
hotspot_dhcp_range() {
    baseip=`echo $wlan_ip | cut -d. -f1-3`   # get first 3 octets of wlan_ip
    wlan_dhcp_start=$baseip".101"
    wlan_dhcp_end=$baseip".150"
}

collect() {
    # -- PushBullet  --
    if ! $selected_prompts || [ -z $push ]; then
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
    if ! $selected_prompts || [ -z $ovpn_enable ]; then
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
    if ! $selected_prompts || [ -z $wlan_ip ]; then
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
        
        # -- HotSpot country --
        header
        prompt="Enter the 2 character regulatory domain (country code) used for the HotSpot SSID"
        user_input "US" "${prompt}"
        wlan_country=$result
    fi

    # -- cloud --
    if ! $selected_prompts || [ -z $cloud ]; then
        header
        [ -z $cloud ] && cloud=false
        user_input $cloud "Do you want to enable ConsolePi Cloud Sync with Gdrive"
        cloud=$result
        cloud_svc="gdrive" # only supporting gdrive for cloud sync
    fi

    # -- rem_user --
    if ! $selected_prompts || [ -z $rem_user ]; then
        header
        [ -z $rem_user ] && rem_user=$iam
        echo
        echo "If you have multiple ConsolePis they can discover each other over the network via mdns"
        echo "and if enabled can sync via Google Drive."
        echo
        echo "The Remote User is typically pi but can be any user given they are members of"
        echo "the dialout and consolepi groups.  Remotes connect via ssh"
        echo
        user_input $rem_user "What user should remote ConsolePis use to connect to this ConsolePi"
        rem_user=$result
        if ! groups $rem_user 2>>$log_file | grep dialout| grep -q consolepi ; then
            logit "$rem_user is lacking membership to consolepi and/or dialout groups, please verify after install"
        fi     
    fi

    # -- power Control --
    if ! $selected_prompts || [ -z $power ]; then
        header
        prompt="Do you want to enable ConsolePi Power Outlet Control"
        [ -z $power ] && power=false
        user_input $power "${prompt}"
        power=$result
        if $power; then
            echo -e "\nTo Complete Power Control Setup you need to populate the power section of /etc/ConsolePi/ConsolePi.yaml" 
            echo -e "You can copy and edit ConsolePi.yaml.example.  Ensure you follow proper yaml format"
            echo -e "\nConsolePi currently supports Control of GPIO controlled Power Outlets (relays), IP connected"
            echo -e "outlets running tasmota firmware, and digital-loggers web/ethernet Power Switches."
            echo -e "See GitHub for more details.\n"
            read -n 1 -p "Press any key to continue"
        fi
    fi
}

verify() {
    header
    echo "-------------------------------------------->>PLEASE VERIFY VALUES<<--------------------------------------------"
    echo                                                                  
    echo     " Send Notifications via PushBullet?:                      $push"
    if $push; then
        echo " PushBullet API Key:                                      ${push_api_key}"
        echo " Send Push Notification to all devices?:                  $push_all"
        ! $push_all && \
        echo " iden of device to receive PushBullet Notifications:      ${push_iden}"
    fi

    echo " Enable Automatic VPN?:                                   $ovpn_enable"
    if $ovpn_enable; then
        echo " IP used to verify VPN is connected:                      $vpn_check_ip"
        echo " IP used to verify Internet connectivity:                 $net_check_ip"
        echo " Local Lab Domain:                                        $local_domain"
    fi

    echo " ConsolePi Hot Spot IP:                                   $wlan_ip"
    echo "  *hotspot DHCP Range:                                    ${wlan_dhcp_start} to ${wlan_dhcp_end}"
    echo " ConsolePi HotSpot SSID:                                  $wlan_ssid"
    echo " ConsolePi HotSpot psk:                                   $wlan_psk"
    echo " ConsolePi HotSpot regulatory domain:                     $wlan_country"
    echo " ConsolePi Cloud Support:                                 $cloud"
    $cloud && echo " ConsolePi Cloud Service:                                 $cloud_svc"
    echo " User used by Remotes to connect to this ConsolePi:       $rem_user"
    echo " ConsolePi Power Control Support:                         $power"
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
    ! $bypass_verify && verify
    while ! $input; do
        collect
        verify
    done
    update_config
}
