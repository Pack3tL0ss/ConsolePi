#!/usr/bin/env bash

# ------------------------------------------------------------------------------------------------------------------------------------------------- #
# --                                                 ConsolePi Installation Script Stage 2                                                       -- #
# --  Wade Wells - Aug 2019                                                                                                                      -- #
# --    report any issues/bugs on github or fork-fix and submit a PR                                                                             -- #
# --                                                                                                                                             -- #
# --  This script aims to automate the installation of ConsolePi.                                                                                -- #
# --  For more detail visit https://github.com/Pack3tL0ss/ConsolePi                                                                              -- #
# --                                                                                                                                             -- #
# --------------------------------------------------------------------------------------------------------------------------------------------------#

# -- Find path for any files pre-staged in user home or ConsolePi_stage subdir --
get_staged_file_path() {
    [[ -z $1 ]] && logit "FATAL Error find_path function passed NUL value" "CRITICAL"
    if [[ -f "${home_dir}${1}" ]]; then
        found_path="${home_dir}${1}"
    elif [[ -f ${stage_dir}$1 ]]; then
        found_path="${home_dir}ConsolePi_stage/${1}"
    else
        found_path=
    fi
    echo $found_path
}

# -- Build Config File and Directory Structure - Read defaults from config
get_config() {
    process="get config"
    bypass_verify=false
    selected_prompts=false
    logit "Starting get/build Configuration"
    if [[ ! -f $default_config ]] && [[ ! -f "/home/${iam}/ConsolePi.conf" ]] && [[ ! -f ${stage_dir}ConsolePi.conf ]]; then
        logit "No Existing Config found - building default"
        # This indicates it's the first time the script has ran
        echo "cfg_file_ver=${CFG_FILE_VER}                  # Do Not Delete or modify this line"  > "${default_config}"
        echo "push=true                                    # PushBullet Notifications: true - enable, false - disable" >> "${default_config}"
        echo "push_all=true                                    # PushBullet send notifications to all devices: true - yes, false - send only to device with iden specified by push_iden" >> "${default_config}"
        echo "push_api_key=\"PutYourPBAPIKeyHereChangeMe:\"    # PushBullet API key" >> "${default_config}"
        echo "push_iden=\"putyourPBidenHere\"                    # iden of device to send PushBullet notification to if not push_all" >> "${default_config}"
        echo "ovpn_enable=true                                    # if enabled will establish VPN connection" >> "${default_config}"
        echo "vpn_check_ip=\"10.0.150.1\"                        # used to check VPN (internal) connectivity should be ip only reachable via VPN" >> "${default_config}"
        echo "net_check_ip=\"8.8.8.8\"                               # used to check internet connectivity" >> "${default_config}"
        echo "local_domain=\"arubalab.net\"                        # used to bypass VPN. evals domain sent via dhcp option if matches this var will not establish vpn" >> "${default_config}"
        echo "wlan_ip=\"10.3.0.1\"                        # IP of ConsolePi when in hotspot mode" >> "${default_config}"
        echo "wlan_ssid=\"ConsolePi\"                        # SSID used in hotspot mode" >> "${default_config}"
        echo "wlan_psk=\"ChangeMe!!\"                        # psk used for hotspot SSID" >> "${default_config}"
        echo "wlan_country=\"US\"                        # regulatory domain for hotspot SSID" >> "${default_config}"
        echo "cloud=false                                                   # enable ConsolePi clustering / cloud config sync" >> "${default_config}"
        echo 'cloud_svc="gdrive"                                            # Future - only Google Drive / Google Sheets supported currently - must be "gdrive"' >> "${default_config}"
        echo 'power=false                                                    # Adds support for Power Outlet control' >> "${default_config}"
        # echo 'tftpd=false                                                    # Enables tftpd-hpa with create rights and root folder /srv/tftp' >> "${default_config}"
        echo "debug=false                                                   # turns on additional debugging" >> "${default_config}"
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
            . "$default_config" || 
                logit "Error Loading Configuration defaults" "WARNING"
        else
            header
            echo "Please edit config in ${default_config} using editor (i.e. nano) and re-run install script"
            echo "i.e. \"sudo nano ${default_config}\""
            echo
            # move_log
            exit 0
        fi
    # If Config exists in /etc/ConsolePi/ConsolePi.conf it takes precedence
    elif [[ -f "${default_config}" ]]; then
        logit "Using existing Config found in ${consolepi_dir}"
        . "$default_config" || 
            logit "Error Loading Configuration defaults" "WARNING"
        if [ -z $cfg_file_ver ] || [ $cfg_file_ver -lt $CFG_FILE_VER ]; then
            bypass_verify=true         # bypass verify function
            input=false                # so collect function will run (while loop in main)
            selected_prompts=true
            echo "-- NEW OPTIONS HAVE BEEN ADDED DATA COLLECTION PROMPTS WILL DISPLAY --"
        fi
    # For first run if no config exists in default location look in user home_dir and stage_dir for pre-config file
    elif [[ -f "/home/${iam}/ConsolePi.conf" ]] || [[ -f ${stage_dir}ConsolePi.conf ]]; then
        found_path=$(get_staged_file_path "ConsolePi.conf")
        if [[ $found_path ]]; then
            logit "using provided config: ${found_path}"
            sudo mv $found_path $default_config && ok_import=true || ok_import=false
            ! $ok_import && logit "Error Moving provided config: ${found_path}" "WARNING"
            $ok_import && . "$default_config" || 
                logit "Error Loading Configuration defaults" "WARNING"
        else
            logit "NUL Return from found_path: ${found_path}" "ERROR"
        fi
    fi
    hotspot_dhcp_range
    unset process
}

# Update Config file with Collected values
update_config() {
    echo "cfg_file_ver=${CFG_FILE_VER}   # ---- Do Not Delete or modify this line ---- #"  > "${default_config}"
    echo "push=${push}                                                       # PushBullet Notifications: true - enable, false - disable" >> "${default_config}"
    echo "push_all=${push_all}                                                   # PushBullet send notifications to all devices: true - yes, false - send only to device with iden specified by push_iden" >> "${default_config}"
    echo "push_api_key=\"${push_api_key}\"   # PushBullet API key" >> "${default_config}"
    echo "push_iden=\"${push_iden}\"                              # iden of device to send PushBullet notification to if not push_all" >> "${default_config}"
    echo "ovpn_enable=${ovpn_enable}                                                # if enabled will establish VPN connection" >> "${default_config}"
    echo "vpn_check_ip=\"${vpn_check_ip}\"                                       # used to check VPN (internal) connectivity should be ip only reachable via VPN" >> "${default_config}"
    echo "net_check_ip=\"${net_check_ip}\"                                          # used to check Internet connectivity" >> "${default_config}"
    echo "local_domain=\"${local_domain}\"                                       # used to bypass VPN. evals domain sent via dhcp option if matches this var will not establish vpn" >> "${default_config}"
    echo "wlan_ip=\"${wlan_ip}\"                                              # IP of ConsolePi when in hotspot mode" >> "${default_config}"
    echo "wlan_ssid=\"${wlan_ssid}\"                                           # SSID used in hotspot mode" >> "${default_config}"
    echo "wlan_psk=\"${wlan_psk}\"                                             # psk used for hotspot SSID" >> "${default_config}"
    echo "wlan_country=\"${wlan_country}\"                                               # regulatory domain for hotspot SSID" >> "${default_config}"
    echo "cloud=${cloud}                                                      # enable ConsolePi clustering / cloud config sync" >> "${default_config}"
    echo "cloud_svc=\"${cloud_svc}\"                                              # Future - only Google Drive / Google Sheets supported currently - must be \"gdrive\"" >> "${default_config}"
    echo "power=${power}                                                     # Adds support for Power Outlet Control" >> "${default_config}"
    # echo "tftpd=${tftpd}                                                     # Enables tftpd-hpa with create rights and root folder /srv/tftp" >> "${default_config}"
}

# Update Config overrides: write any supported custom override variables back to file
update_config_overrides() {
    [ ! -z $wlan_wait_time ] && echo "wlan_wait_time=${wlan_wait_time}       # hotspot wait for ssid connect b4 reverting back to hotspot" >> "${default_config}"
    echo "debug=${debug}                                                     # turns on additional debugging" >> "${default_config}"
}

# Update ConsolePi Banner to display ConsolePi ascii logo at login
update_banner() {
    process="update motd"
    if [ -f /etc/motd ]; then
        grep -q "PPPPPPPPPPPPPPPPP" /etc/motd && motd_exists=true || motd_exists=false
        if $motd_exists; then 
            mv /etc/motd /bak && sudo touch /etc/motd &&
                logit "Clear old motd - Success" ||
                logit "Failed to Clear old motd" "WARNING"
        fi
    fi
    if [ ! -f /etc/profile.d/consolepi.sh ]; then
        cp ${src_dir}consolepi.sh /etc/profile.d/ &&
            logit "Deploy consolepi.sh profile script with banner text - Success" ||
            logit "Failed to move consolepi.sh from src to /etc/profile.d/" "WARNING"
    else
        logit "consolepi profile script already deployed"
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
            user_input $push_api_key "${prompt}"
            push_api_key=$result
            
            # -- Push to All Devices --
            header
            echo "Do you want to send PushBullet Messages to all PushBullet devices?"
            echo "Answer 'N'(no) to send to just 1 device "
            echo
            prompt="Send PushBullet Messages to all devices"
            user_input $push_all "${prompt}"
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
   
    # -- power Control --
    if ! $selected_prompts || [ -z $power ]; then
        header
        prompt="Do you want to enable ConsolePi Power Outlet Control"
        [ -z $power ] && power=false
        user_input $power "${prompt}"
        power=$result
        if $power; then
            echo -e "\nTo Complete Power Control Setup you need to populate /etc/ConsolePi/power.json" 
            echo -e "You can copy and edit power.json.example.  Ensure you follow proper json format"
            echo -e "\nI Suggest you verify your JSON using an online validator such as https://codebeautify.org/jsonvalidator"
            echo -e "\nConsolePi currently supports Control of GPIO controlled Power Outlets (relays), IP connected"
            echo -e "outlets running tasmota firmware, and digital-loggers web/ethernet Power Switches."
            echo -e "See GitHub for more details.\n"
            read -n 1 -p "Press any key to continue"
        fi
    fi

    # # -- tftpd --
    # if ! $selected_prompts || [ -z $tftpd ]; then
    #     header
    #     [ -z $tftpd ] && tftpd=false
    #     user_input $tftpd "Do you want to enable a tftp server"
    #     tftpd=$result
    # fi
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
    echo " ConsolePi Hot Spot SSID:                                 $wlan_ssid"
    echo " ConsolePi Hot Spot psk:                                  $wlan_psk"
    echo " ConsolePi Hot Spot regulatory domain:                    $wlan_country"
    echo " ConsolePi Cloud Support:                                 $cloud"
    $cloud && echo " ConsolePi Cloud Service:                                 $cloud_svc"
    echo " ConsolePi Power Control Support:                         $power"
    # echo " tftp server:                                             $tftpd"
    echo
    echo "----------------------------------------------------------------------------------------------------------------"
    echo
    echo "Enter Y to Continue N to make changes"
    echo
    prompt="Are Values Correct"
    input=$(user_input_bool)
    # ! $input && selected_prompts=false
}

chg_password() {
    if [[ $iam == "pi" ]] && [ -e /run/sshwarn ]; then 
        header
        echo "You are logged in as pi, and the default password has not been changed"
        prompt="Do You want to change the password for user pi"
        response=$(user_input_bool)
        if $response; then
            match=false
            while ! $match; do
                read -sep "Enter new password for user pi: " pass && echo
                read -sep "Re-Enter new password for user pi: " pass2 && echo
                [[ "${pass}" == "${pass2}" ]] && match=true || match=false
                ! $match && echo -e "ERROR: Passwords Do Not Match\n"
            done
            process="pi user password change"
            echo "pi:${pass}" | sudo chpasswd 2>> $log_file && logit "Success" || 
            ( logit "Failed to Change Password for pi user" "WARNING" &&
            echo -e "\n!!! There was an issue changing password.  Installation will continue, but continue to use existing password and update manually !!!" )
            unset pass && unset pass2 && unset process
        fi
    fi
}

set_hostname() {
    process="Change Hostname"
    hostn=$(cat /etc/hostname)
    if [[ "${hostn}" == "raspberrypi" ]]; then
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
                    read -ep "New hostname: $newhost Is this correect (y/n)?: " response
                    response=${response,,}    # tolower
                    ( [[ "$response" =~ ^(yes|y)$ ]] || [[ "$response" =~ ^(no|n)$ ]] ) && valid_response=true || valid_response=false
                done
                [[ "$response" =~ ^(yes|y)$ ]] && ok_do_hostname=true || ok_do_hostname=false
            done

            # change hostname in /etc/hosts & /etc/hostname
            sed -i "s/$hostn/$newhost/g" /etc/hosts
            sed -i "s/$hostn\.$(grep -o "$hostn\.[0-9A-Za-z].*" /etc/hosts | cut -d. -f2-)/$newhost.$local_domain/g" /etc/hosts
            # change hostname via command
            hostname "$newhost" 1>&2 2>>/dev/null
            [ $? -gt 0 ] && logit "Error returned from hostname command" "WARNING"
            # add wlan hotspot IP to hostfile for DHCP connected clients to resolve this host
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
    if [ $cur_tz == "GMT" ] || [ $cur_tz == "BST" ]; then
        header

        prompt="Current TimeZone $cur_tz. Do you want to configure the timezone"
        set_tz=$(user_input_bool)

        if $set_tz; then
            echo "Launching, standby..." && sudo dpkg-reconfigure tzdata 2>> $log_file && header && logit "Set new TimeZone to $(date +"%Z") Success" ||
                logit "FAILED to set new TimeZone" "WARNING"
        fi
    else
        logit "TimeZone ${cur_tz} not default (GMT) assuming set as desired."
    fi
    unset process
}

# -- if ipv6 is enabled present option to disable it --
disable_ipv6()  {
    if ! sudo grep -q "net.ipv6.conf.all.disable_ipv6 = 1" /etc/sysctl.conf; then
        process="Disable ipv6"
            prompt="Do you want to disable ipv6"
            dis_ipv6=$(user_input_bool)

            if $dis_ipv6; then
                if sudo grep -q "net.ipv6.conf.all.disable_ipv6 = 1" /etc/sysctl.conf; then
                    logit "ipv6 aleady disabled"
                else
sudo cat << EOF | sudo tee -a /etc/sysctl.conf  > /dev/null

# Disable ipv6
net.ipv6.conf.all.disable_ipv6 = 1 
net.ipv6.conf.default.disable_ipv6 = 1
net.ipv6.conf.lo.disable_ipv6 = 1
EOF
                    if sudo grep -q "net.ipv6.conf.all.disable_ipv6 = 1" /etc/sysctl.conf; then
                        logit "Disable ipv6 Success"
                    else
                        logit "FAILED to disable ipv6" "WARNING"
                    fi
                fi
            fi
        unset process
    fi
}

misc_imports(){
    process="Perform misc imports"
    if ! $upgrade; then
        # -- ssh authorized keys --
        found_path=$(get_staged_file_path "authorized_keys")
        [[ $found_path ]] && logit "pre-staged ssh authorized keys found - importing"
        if [[ $found_path ]]; then 
            file_diff_update $found_path /root/.ssh/authorized_keys
            file_diff_update $found_path ${home_dir}.ssh/authorized_keys
        fi

        # -- pre staged cloud creds --
        if $cloud && [[ -d ${stage_dir}.credentials ]]; then 
            found_path=${stage_dir}.credentials
            mv $found_path/* "/etc/ConsolePi/cloud/${cloud_svc}/.credentials" 2>> $log_file &&
            logit "Found ${cloud_svc} credentials. Moving to /etc/ConsolePi/cloud/${cloud_svc}/.credentials"  ||
            logit "Error occurred moving your ${cloud_svc} credentials files" "WARNING"
        else
            logit "ConsolePi will be Authorized for ${cloud_svc} when you launch consolepi-menu"
            logit "raspbian-lite users refer to the GitHub for instructions on how to generate credential files off box"
        fi

        found_path=$(get_staged_file_path "rpi-poe-overlay.dts")
        [[ $found_path ]] && logit "overlay file found creating dtbo"
        if [[ $found_path ]]; then 
            sudo dtc -@ -I dts -O dtb -o /tmp/rpi-poe.dtbo $found_path >> $log_file 2>&1 &&
                overlay_success=true || overlay_success=false
                if $overlay_success; then
                    sudo mv /tmp/rpi-poe.dtbo /boot/overlays 2>> $log_file &&
                        logit "Successfully moved overlay file, will activate on boot" ||
                        logit "Failed to move overlay file"
                else
                    logit "Failed to create Overlay file from dts"
                fi
        fi

        # -- power.json --
        if $power && [[ -d ${stage_dir}power.json ]]; then 
            found_path=${stage_dir}power.json
            mv $found_path $consolepi_dir 2>> $log_file &&
            logit "Found power control definitions @ ${found_path} Moving into $consolepi_dir"  ||
            logit "Error occurred moving your ${found_path} into $consolepi_dir " "WARNING"
        fi

    fi
    unset process
}

install_ser2net () {
    # To Do add check to see if already installed / update
    process="Install ser2net"
    logit "${process} - Starting"
    ser2net_ver=$(ser2net -v 2>> /dev/null | cut -d' ' -f3 && installed=true || installed=false)
    # if [[ -z $ser2net_ver ]] || ( [ ! -z $ser2net_ver ] && [ ! "$ser2net_ver" = "$ser2net_source_version" ] ); then
    if [[ -z $ser2net_ver ]]; then
        logit "Installing ser2net from source"
        cd /usr/local/bin

        logit "Retrieve and extract package"
        wget -q "${ser2net_source}" -O ./ser2net.tar.gz 1>/dev/null 2>> $log_file && 
            logit "Successfully pulled ser2net from source" || logit "Failed to pull ser2net from source" "ERROR"

        tar -zxvf ser2net.tar.gz 1>/dev/null 2>> $log_file &&
            logit "ser2net extracted" ||
            logit "Failed to extract ser2net from source" "ERROR"

        rm -f /usr/local/bin/ser2net.tar.gz || logit "Failed to remove tar.gz" "WARNING"
        cd ser2net-${ser2net_source_version}/

        logit "./configure ser2net"
        ./configure 1>/dev/null 2>> $log_file &&
            logit "./configure ser2net Success" ||
            logit "ser2net ./configure Failed" "ERROR"

        logit "ser2net make - be patient, this takes a few."
        make 1>/dev/null 2>> $log_file &&
            logit "ser2net make Success" ||
            logit "ser2net make Failed" "ERROR"
            
        logit "ser2net make install, make clean"
        make install 1>/dev/null 2>> $log_file &&
            logit "ser2net make install Success" ||
            logit "ser2net make install Failed" "ERROR"

        make clean 1>/dev/null 2>> $log_file &&
            logit "ser2net make clean Success" ||
            logit "ser2net make clean Failed" "WARNING"
        cd $cur_dir
        
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

        if $do_ser2net; then
            logit "Building ConsolePi Config for ser2net"
            cp /etc/ConsolePi/src/ser2net.conf /etc/ 2>> $log_file || 
                logit "ser2net Failed to copy config file from ConsolePi src" "ERROR"
        fi

        
        logit "Building init for ser2net"
        cp /etc/ConsolePi/src/systemd/ser2net.init /etc/init.d/ser2net 2>> $log_file || 
            logit "ser2net Failed to copy init file from ConsolePi src" "ERROR"
            
        chmod +x /etc/init.d/ser2net 2>> $log_file || 
            logit "ser2net Failed to make init executable" "WARNING"
        
        logit "ser2net Enable init"
        /lib/systemd/systemd-sysv-install enable ser2net 1>/dev/null 2>> $log_file && 
            logit "ser2net init file enabled" ||
            logit "ser2net failed to enable init file (start on boot)" "WARNING"
            
        systemctl daemon-reload || 
            logit "systemctl failed to reload daemons" "WARNING"
    else
        logit "Ser2Net ${ser2net_ver} already installed. No Action Taken re ser2net"
        logit "Ser2Net Upgrade is a Potential future function of this script"
    fi
        
    logit "${process} - Complete"
    unset process
}

dhcp_run_hook() {
    process="Configure dhcp.exit-hook"
    hook_file="/etc/ConsolePi/src/dhcpcd.exit-hook"
    logit "${process} - Starting"
    [[ -f /etc/dhcpcd.exit-hook ]] && exists=true || exists=false                      # find out if exit-hook file already exists
    if $exists; then
        is_there=`grep -c $hook_file  /etc/dhcpcd.exit-hook`  # find out if it's already pointing to ConsolePi script
        if [ $is_there -gt 0 ]; then
            logit "exit-hook already configured [File Found and Pointer exists]"  #exit-hook exists and line is already there
        else
            sudo sed -i '/.*\/etc\/ConsolePi\/.*/c\\/etc\/ConsolePi\/src\/dhcpcd.exit-hook "$@"' /etc/dhcpcd.exit-hook &&
            logit "Successfully Updated exit-hook Pointer" || logit "Failed to update exit-hook pointer" "ERROR"
        fi
    else
        sudo echo "$hook_file \"\$@\"" > "/etc/dhcpcd.exit-hook" || logit "Failed to create exit-hook script" "ERROR"
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
    ! $upgrade && logit "Install OpenVPN" || logit "Verify OpenVPN is installed"
    ovpn_ver=$(openvpn --version 2>/dev/null| head -1 | awk '{print $2}')
    if [[ -z $ovpn_ver ]]; then
        sudo apt-get -y install openvpn 1>/dev/null 2>> $log_file && logit "OpenVPN installed Successfully" || logit "FAILED to install OpenVPN" "WARNING"
        if ! $ovpn_enable; then
            logit "You've chosen not to use the OpenVPN function.  Disabling OpenVPN. Package will remain installed. '/lib/systemd/systemd-sysv-install enable openvpn' to enable"
            /lib/systemd/systemd-sysv-install disable openvpn 1>/dev/null 2>> $log_file && logit "OpenVPN Disabled" || logit "FAILED to disable OpenVPN" "WARNING"
        else
            /lib/systemd/systemd-sysv-install enable openvpn 1>/dev/null 2>> $log_file && logit "OpenVPN Enabled" || logit "FAILED to enable OpenVPN" "WARNING"
        fi
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
    unset process
}

ovpn_graceful_shutdown() {
    process="OpenVPN Graceful Shutdown"
    systemd_diff_update "ovpn-graceful-shutdown"
    unset process
}

install_autohotspotn () {
    process="AutoHotSpotN"
    logit "Install/Update AutoHotSpotN"
    
    systemd_diff_update autohotspot
    logit "Enabling Startup script."
    systemctl enable autohotspot.service 1>/dev/null 2>> $log_file &&
    logit "Successfully enabled autohotspot.service" ||
    logit "Failed to enable autohotspot.service" "WARNING"

    logit "Installing hostapd via apt."
    if ! $(which hostapd >/dev/null); then
        apt-get -y install hostapd 1>/dev/null 2>> $log_file &&
            logit "hostapd install Success" ||
            logit "hostapd install Failed" "WARNING"
    else
        hostapd_ver=$(hostapd -v 2>&1| head -1| awk '{print $2}')
        logit "hostapd ${hostapd_ver} already installed"
    fi
    
    logit "Installing dnsmasq via apt."
    dnsmasq_ver=$(dnsmasq -v 2>/dev/null | head -1 | awk '{print $3}')
    if [[ -z $dnsmasq_ver ]]; then
        apt-get -y install dnsmasq 1>/dev/null 2>> $log_file &&
            logit "dnsmasq install Success" ||
            logit "dnsmasq install Failed" "WARNING"
    else
        logit "dnsmasq v${dnsmasq_ver} already installed"
    fi
    
    logit "disabling hostapd and dnsmasq autostart (handled by AutoHotSpotN)."
    sudo systemctl unmask hostapd.service 1>/dev/null 2>> $log_file && logit "ensured hostapd.service is unmasked" || logit "failed to unmask hostapd.service" "WARNING"
    sudo /lib/systemd/systemd-sysv-install disable hostapd 1>/dev/null 2>> $log_file && res=$?
    sudo /lib/systemd/systemd-sysv-install disable dnsmasq 1>/dev/null 2>> $log_file && ((res=$?+$res))
    [[ $res == 0 ]] && logit "hostapd and dnsmasq autostart disabled Successfully" ||
        logit "An error occurred disabling hostapd and/or dnsmasq autostart - verify after install" "WARNING"

    logit "Create/Configure hostapd.conf"
    convert_template hostapd.conf /etc/hostapd/hostapd.conf wlan_ssid=${wlan_ssid} wlan_psk=${wlan_psk} wlan_country=${wlan_country}
    sudo chmod +r /etc/hostapd/hostapd.conf 2>> $log_file || logit "Failed to make hostapd.conf readable - verify after install" "WARNING"
    
    file_diff_update ${src_dir}hostapd /etc/default/hostapd
    file_diff_update ${src_dir}interfaces /etc/network/interfaces

    # update hosts file based on supplied variables - this comes into play for devices connected to hotspot (dnsmasq will be able to resolve hostname to wlan IP)
    if [ -z $local_domain ]; then
        convert_template hosts /etc/hosts wlan_ip=${wlan_ip} hostname=$(head -1 /etc/hostname)
    else
        convert_template hosts /etc/hosts wlan_ip=${wlan_ip} hostname=$(head -1 /etc/hostname) domain=${local_domain}
    fi

    logit "Verify iw is installed on system."
    which iw >/dev/null 2>&1 && iw_ver=$(iw --version 2>/dev/null | awk '{print $3}') || iw_ver=0
    if [ $iw_ver == 0 ]; then
        logit "iw not found, Installing iw via apt."
        ( sudo apt-get -y install iw 1>/dev/null 2>> $log_file && logit "iw installed Successfully" ) || 
            logit "FAILED to install iw" "WARNING"
    else
        logit "iw $iw_ver already installed/current."
    fi
        
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

gen_dnsmasq_conf () {
    process="Configure dnsmasq"
    logit "Generating Files for dnsmasq."
    convert_template dnsmasq.conf /etc/dnsmasq.conf wlan_dhcp_start=${wlan_dhcp_start} wlan_dhcp_end=${wlan_dhcp_end}
    unset process
}

dhcpcd_conf () {
    process="dhcpcd.conf"
    logit "configure dhcp client and static fallback"
    convert_template dhcpcd.conf /etc/dhcpcd.conf wlan_ip=${wlan_ip}
    unset process
}

do_blue_config() {
    process="Bluetooth Console"
    logit "${process} Starting"
    ## Some Sections of the bluetooth configuration from https://hacks.mozilla.org/2017/02/headless-raspberry-pi-configuration-over-bluetooth/
    file_diff_update ${src_dir}systemd/bluetooth.service /lib/systemd/system/bluetooth.service

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

    # Give Blue user limited sudo rights to consolepi-commands
    if [ ! -f /etc/sudoers.d/010_blue-consolepi ]; then
        echo 'blue ALL=(ALL) NOPASSWD: /etc/ConsolePi/src/*' > /etc/sudoers.d/010_blue-consolepi && 
        logit "BlueTooth User given sudo rights for consolepi-commands" || 
        logit "FAILED to give Bluetooth user limited sudo rights" "WARNING"
    fi

    # Remove old blue user default tty cols/rows
    grep -q stty /home/blue/.bashrc &&
        sed -i 's/^stty rows 70 cols 150//g' /home/blue/.bashrc &&
        logit "blue user tty row col configuration removed - Success"
    # if [[ ! $(sudo grep stty /home/blue/.bashrc) ]]; then
    #     sudo echo stty rows 70 cols 150 | sudo tee -a /home/blue/.bashrc > /dev/null && 
    #         logit "Changed default Bluetooth tty rows cols" || 
    #         logit "FAILED to change default Bluetooth tty rows cols" "WARNING"
    # else
    #     logit "blue user tty rows cols already configured"
    # fi

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
    if [[ ! $(sudo grep "alias consolepi-menu" /home/blue/.bashrc) ]]; then
        sudo echo alias consolepi-menu=\"/etc/ConsolePi/src/consolepi-menu.sh\" | sudo tee -a /home/blue/.bashrc > /dev/null && 
            logit "BlueTooth User Configured to launch menu on Login" || 
            logit "FAILED to enable menu on login for BlueTooth User" "WARNING"
    else
        logit "blue user consolepi-menu alias already configured"
    fi
    
    # Install picocom
    if [[ $(picocom --help 2>/dev/null | head -1) ]]; then 
        logit "$(picocom --help 2>/dev/null | head -1) is already installed"
    else
        logit "Installing picocom"
        sudo apt-get -y install picocom 1>/dev/null 2>> $log_file && logit "Install picocom Success" || 
                logit "FAILED to Install picocom" "WARNING"
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
    process="xterm | resize"
    if [[ -f ${src_dir}resize ]]; then
        logit "resize utility already present"
    else
        util_main xterm -I -p "xterm | resize"
        [[ -f ${src_dir}resize ]] && sudo cp $(which resize) ${src_dir}consolepi-commands/resize && good=true || good=false
        if $good; then
            # process="get resize binary from xterm"
            logit "Success - Copy resize binary from xterm"
            logit "xterm will now be removed as we only installed it to get resize"
            util_main xterm -F -p "xterm | resize"
            # process="get resize binary from xterm"
            apt-get -y autoremove 1>/dev/null 2>> $log_file && logit "Success removing xterm left-over deps" || logit "apt-get autoremove after xterm FAILED" "WARNING"
        else
            logit "Unable to fine resize binary after xterm install" "WARNING"
        fi
    fi
    unset process
}

# Create or Update ConsolePi API startup service (systemd)
do_consolepi_api() {
    process="ConsolePi API (systemd)"
    systemd_diff_update consolepi-api
    unset process
}

# Create or Update ConsolePi mdns startup service (systemd)
do_consolepi_mdns() {
    process="ConsolePi mDNS (systemd)"
    systemd_diff_update consolepi-mdnsreg
    systemd_diff_update consolepi-mdnsbrowse
    unset process
}

# Configure ConsolePi with the SSIDs it will attempt to connect to as client prior to falling back to hotspot
get_known_ssids() {
    process="Get Known SSIDs"
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
        # if wpa_supplicant.conf exist in script dir cp it to ConsolePi image.
        # if EAP-TLS SSID is configured in wpa_supplicant extract EAP-TLS cert details and cp certs (not a loop only good to pre-configure 1)
        #   certs should be in user home dir, 'cert' subdir, 'ConsolePi_stage/cert, subdir cert_names are extracted from the wpa_supplicant.conf file found in script dir
        found_path=$(get_staged_file_path "wpa_supplicant.conf")
        if [[ -f $found_path ]]; then
            logit "Found stage file ${found_path} Applying"
            # ToDo compare the files ask user if they want to import if they dont match
            [[ -f $wpa_supplicant_file ]] && sudo cp $wpa_supplicant_file $bak_dir
            sudo mv $found_path $wpa_supplicant_file
            client_cert=$(grep client_cert= $found_path | cut -d'"' -f2| cut -d'"' -f1)
            if [[ ! -z $client_cert ]]; then
                cert_path=${client_cert%/*}
                ca_cert=$(grep ca_cert= $found_path | cut -d'"' -f2| cut -d'"' -f1)
                private_key=$(grep private_key= $found_path | cut -d'"' -f2| cut -d'"' -f1)
                if [[ -d /home/${iam}/cert ]]; then
                    cd /home/$iam/cert     # if user home contains cert subdir look there for certs - otherwise look in stage subdir
                elif [[ -d ${stage_dir}cert ]]; then
                    cd ${stage_dir}cert
                fi
                    
                [[ ! -d $cert_path ]] && sudo mkdir -p "${cert_path}"
                [[ -f ${client_cert##*/} ]] && sudo cp ${client_cert##*/} "${cert_path}/${client_cert##*/}"
                [[ -f ${ca_cert##*/} ]] && sudo cp ${ca_cert##*/} "${cert_path}/${ca_cert##*/}"
                [[ -f ${private_key##*/} ]] && sudo cp ${private_key##*/} "${cert_path}/${private_key##*/}"
                cd "${cur_dir}"
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

    echo -e "\nConsolePi will attempt to connect to configured SSIDs prior to going into HotSpot mode.\n"
    prompt="Do You want to configure${word} SSIDs"
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

do_consolepi_commands() {
    process="Remove old consolepi-commands from /usr/local/bin"
    if [ $(ls -l /usr/local/bin/consolepi* 2>/dev/null | wc -l) -ne 0 ]; then
        sudo cp /usr/local/bin/consolepi-* $bak_dir 2>>$log_file || logit "Failed to Backup potentially custom consolepi-commands in /usr/local/bin"
        sudo rm /usr/local/bin/consolepi-* > /dev/null 2>&1
        sudo unlink /usr/local/bin/consolepi-* > /dev/null 2>&1
        [ $(ls -l /usr/local/bin/consolepi* 2>/dev/null | wc -l) -eq 0 ] &&
            logit "Success - Removing convenience command links created by older version" ||
            logit "Failure - Verify old consolepi-command scripts/symlinks were removed from /usr/local/bin after the install" "WARNING"  
    fi

    process="Update PATH for consolepi-commands"
    [ $(grep -c "consolepi-commands" /etc/profile) -eq 0 ] && 
        sudo echo 'export PATH="$PATH:/etc/ConsolePi/src/consolepi-commands"' >> /etc/profile &&
        logit "PATH Updated" || logit "PATH contains consolepi-commands dir, No Need for update"

    unset process
}

## -- MOVED TO utilities.sh --
# do_tftpd_server() {
#     process="tftpd-hpa"
#     # check to see if tftpd-hpa is already installed
#     which in.tftpd >/dev/null && tftpd_installed=true || tftpd_installed=false
#     $tftpd_installed && tftpd_ver=$(in.tftpd -V | awk '{print $2}'|cut -d, -f1)
#     # check to see if port is in use
#     if ! $tftpd_installed; then
#         sudo netstat -lnpu | grep -q ":69\s.*" && in_use=true || in_use=false
#         if $in_use; then
#             logit "tftpd package is not installed, but the port is in use tftpd-hpa will likely fail to start" "WARNING"
#             logit "Investigate after the install.  Check for uncommented lines in /etc/inetd.conf or /etc/xinetd.conf"
#         fi
#         logit "Installing tftpd-hpa"
#         sudo apt-get -y install tftpd-hpa >/dev/null 2>>$log_file && logit "Success - tftpd-hpa Installed" ||
#             logit "Failed to install tftpd-hpa" "WARNING"
#         file_diff_update ${src_dir}tftpd-hpa /etc/default/tftpd-hpa
#         sudo systemctl restart tftpd-hpa && logit "tftpd-hpa service restarted" || logit "failed to restart tftpd-hpa service" "WARNING"
#         sudo chown -R tftp:consolepi /srv/tftp && sudo chmod -R g+w /srv/tftp || logit "Failed to change ownership/permissions on tftp root dir /srv/tftp"
#     else
#         logit "tftpd-hpa verison ${tftpd_ver} already installed assuming configured as desired, config file verification not part of upgrade."
#     fi    
# }

misc_stuff() {
    if [ ${wlan_country^^} == "US" ]; then
        process="Set Keyboard Layout"
        logit "${process} - Starting"
        sudo sed -i "s/gb/${wlan_country,,}/g" /etc/default/keyboard && logit "KeyBoard Layout changed to ${wlan_country,,}"
        logit "${process} - Success" || logit "${process} - Failed ~ verify contents of /etc/default/keyboard" "WARNING"
        unset process
    fi

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
    
    # -- if pre-stage file provided during install enable it --
    if ! $upgrade; then
        found_path=$(get_staged_file_path "10-ConsolePi.rules")
        if [[ $found_path ]]; then
            logit "udev rules file found ${found_path} enabling provided udev rules"
            if [ -f /etc/udev/rules.d/10-ConsolePi.rules ]; then
                file_diff_update $found_path /etc/udev/rules.d
            else
                sudo cp $found_path /etc/udev/rules.d
                sudo udevadm control --reload-rules
            fi
        fi
    fi
    
    echo
    echo -e "--------------------------------------------- \033[1;32mPredictable Console ports$*\033[m ---------------------------------------------"
    echo "-                                                                                                                   -"
    echo "- Predictable Console ports allow you to configure ConsolePi so that each time you plug-in a specific adapter it    -"
    echo "- will have the same name in consolepi-menu and will be reachable via the same TELNET port.                         -"
    echo "-                                                                                                                   -"
    echo "- This is useful if you plan to use multiple adapters/devices, or if you are using a multi-port pig-tail adapter.   -"
    echo '- Also useful if this is being used as a stationary solution.  So you can name the adaper "NASHDC-Rack12-SW3"       -'
    echo "-   rather than have them show up as ttyUSB0.                                                                       -"
    echo "-                                                                                                                   -"
    echo "- The behavior if you do *not* define Predictable Console Ports is the adapters will use the root device names      -"
    echo "-   ttyUSB# or ttyACM# where the # starts with 0 and increments for each adapter of that type plugged in. The names -"
    echo "-   won't necessarily be consistent between reboots.                                                                -"
    echo "-                                                                                                                   -"
    echo "- Defining the ports with this utility is also how device specific serial settings are configured.  Otherwise       -"
    echo "-   they will use the default which is 96008N1                                                                      -"
    echo "-                                                                                                                   -"
    echo "- As of Dec 2019 This uses a new mechanism with added support for more challengine adapters:                        -"
    echo "-   * Multi-Port Serial Adapters, where the adpater presents a single serial # for all ports                        -"
    echo "-   * Super Lame cheap crappy adapters that don't burn a serial# to the adapter at all:  (CODED NOT TESTED YET)     -"
    echo "-     If you have one of these.  First Check online with the manufacturer of the chip used in the adapter to see    -"
    echo "-     if they have a utility to flash the EEPROM, some manufacturers do which would allow you to write a serial #   -"
    echo "-     For example if the adapter uses an FTDI chip (which I reccomend) they have a utility called FT_PROG           -"
    echo "-     Most FTDI based adapters have serial #s, I've only seen the lack of serial # on dev boards.                   -"
    echo "-     ---- If you're interested I reccomend adapters that use FTDI chips. ----                                      -"
    echo "-                                                                                                                   -"
    echo '-  !! suppport for adapters that lack serial ports is not tested at all, so I probably goofed someplace.            -'
    echo "-     I need to find a lame adapter to test                                                                         -"
    echo "-                                                                                                                   -"
    echo '-  This function can be called anytime from the shell via `consolepi-addconsole` and is available from              -'
    echo '-    `consolepi-menu` as the `rn` (rename) option.                                                                  -'
    echo "-                                                                                                                   -"
    echo "---------------------------------------------------------------------------------------------------------------------"
    echo
    echo "You need to have the serial adapters you want to map to specific telnet ports available"
    prompt="Would you like to configure predictable serial ports now"
    $upgrade && user_input false "${prompt}" || user_input true "${prompt}"
    # if $result ; then
    #     if [ -f ${consolepi_dir}src/consolepi-addconsole.sh ]; then
    #         . ${consolepi_dir}src/consolepi-addconsole.sh
    #         udev_main
    #     else
    #         logit "ERROR consolepi-addconsole.sh not available in src directory" "WARNING"
    #     fi
    # fi
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

# -- run custom post install script --
custom_post_install_script() {
    if ! $upgrade; then
        found_path=$(get_staged_file_path "ConsolePi_init.sh")
        if [[ $found_path ]]; then
            process="Run Custom Post-install script"
            logit "Post Install Script ${found_path} Found. Executing"
            sudo $found_path && logit "Post Install Script Complete No Errors" || 
                logit "Error Code returned by Post Install Script" "WARNING"
            unset process
        fi
    fi
}

# -- Display Post Install Message --
post_install_msg() {
    echo
    echo "*********************************************** Installation Complete ***************************************************"
    echo "*                                                                                                                       *"
    echo -e "* \033[1;32mNext Steps/Info$*\033[m                                                                                                       *"
    echo "*                                                                                                                       *"
    echo -e "* \033[1;32mCloud Sync:$*\033[m                                                                                                           *"
    echo "*   if you plan to use cloud sync.  You will need to do some setup on the Google side and Authorize ConsolePi           *"
    echo "*   refer to the GitHub for more details                                                                                *"
    echo "*                                                                                                                       *"
    echo -e "* \033[1;32mOpenVPN:$*\033[m                                                                                                              *"
    echo "*   if you are using the Automatic VPN feature you should Configure the ConsolePi.ovpn and ovpn_credentials files in    *"
    echo "*   /etc/openvpn/client.  Then run 'consolepi-upgrade' which will add a few lines to the config to enable some          *"
    echo "*   ConsolePi functionality.  There is a .example file for reference as well.                                           *"
    echo "*     You should \"sudo chmod 600 <filename>\" both of the files for added security                                       *"
    echo "*                                                                                                                       *"
    echo -e "* \033[1;32mser2net Usage:$*\033[m                                                                                                        *"
    echo "*   Serial Ports are available starting with telnet port 8001 (ttyUSB#) or 9001 (ttyACM#) incrementing with each        *"
    echo "*   adapter plugged in.  if you configured predictable ports for specific serial adapters those start with 7001.        *"
    echo "*   **OR** just launch the consolepi-menu for a menu w/ detected adapters                                               *"
    echo "*                                                                                                                       *"
    echo "*   The Console Server has a control port on telnet 7000 type \"help\" for a list of commands available                   *"
    echo "*                                                                                                                       *"
    echo -e "* \033[1;32mBlueTooth:$*\033[m                                                                                                            *"
    echo "*   ConsolePi should be discoverable (after reboot if this is the initial installation).                                *"
    echo "*   - Configure bluetooth serial on your device and pair with ConsolePi                                                 *"
    echo "*   - On client device attach to the com port created after the step above was completed                                *"
    echo "*   - Once Connected the Console Menu will automatically launch allowing you to connect to any serial devices found     *"
    echo "*   NOTE: The Console Menu is available from any shell session (bluetooth or SSH) via the consolepi-menu command        *"
    echo "*                                                                                                                       *"
    echo -e "* \033[1;32mLogging:$*\033[m                                                                                                              *"
    echo "*   The bulk of logging for remote discovery, adapter detection cloud updates... end up in /var/log/ConsolePi/cloud.log *"
    echo "*   The tags 'puship', 'puship-ovpn', 'autohotspotN' and 'dhcpcd' are of key interest in syslog                         *"
    echo "*   - openvpn logs are sent to /var/log/ConsolePi/ovpn.log you can tail this log to troubleshoot any issues with ovpn   *"
    echo "*   - pushbullet responses (json responses to curl cmd) are sent to /var/log/ConsolePi/push_response.log                *"
    echo "*   - An install log can be found in ${consolepi_dir}installer/install.log                                               *"
    echo "*                                                                                                                       *"
    echo -e "* \033[1;32mConsolePi Commands:$*\033[m                                                                                                   *"
    echo "*   **Refer to the GitHub for the most recent complete list**                                                           *"
    echo "*   - consolepi-upgrade: upgrade ConsolePi. - supported update method.                                                  *"
    echo "*   - consolepi-addssids: Add additional known ssids. same as doing sudo /etc/ConsolePi/ssids.sh                        *"
    echo "*   - consolepi-addconsole: Configure serial adapter to telnet port rules. same as doing sudo /etc/ConsolePi/udev.sh    *"
    echo "*   - consolepi-menu: Launch Console Menu which will provide connection options for connected serial adapters           *"
    echo "*       if cloud config feature is enabled menu will also show adapters on reachable remote ConsolePis                  *"
    echo "*   - consolepi-killvpn: Gracefully terminate openvpn tunnel if one is established                                      *"
    echo "*   - consolepi-autohotspot: Manually invoke AutoHotSpot function which will look for known SSIDs and connect if found  *"
    echo "*       then fall-back to HotSpot mode if not found or unable to connect.                                               *"
    echo "*   - consolepi-testhotspot: Disable/Enable the SSIDs ConsolePi tries to connect to before falling back to hotspot.     *"
    echo "*       Used to test hotspot function.  Script Toggles state if enabled it will disable and vice versa.                 *"
    echo "*   - consolepi-bton: Make BlueTooth Discoverable and Pairable - this is the default behavior on boot.                  *"
    echo "*   - consolepi-btoff: Disable BlueTooth Discoverability.  You can still connect if previously paired.                  *"
    echo "*   - consolepi-details: Refer to GitHub for usage, but in short dumps the data the ConsolePi would run with based      *"
    echo "*       on configuration, discovery, etc.  Dumps everything if no args,                                                 *"
    echo "*        valid args: adapters, interfaces, outlets, remotes, local, <hostname of remote>.  GitHub for more detail       *"
    echo "*                                                                                                                       *"
    echo "**ConsolePi Installation Script v${INSTALLER_VER}**************************************************************************************"
    echo -e "\n\n"
    # Script Complete Prompt for reboot if first install
    if $upgrade; then
        echo "ConsolePi Upgrade Complete, a Reboot may be required if config options where changed during upgrade"
    else
        prompt="A reboot is required, do you want to reboot now"
        go_reboot=$(user_input_bool)
        $go_reboot && sudo reboot || echo "ConsolePi Install script Complete, Reboot is required"
    fi
}

install2_main() {
    # remove_first_boot
    # updatepi
    # pre_git_prep
    # gitConsolePi
    get_config
    ! $bypass_verify && verify
    while ! $input; do
        collect
        verify
    done
    update_config
    update_config_overrides
    if ! $upgrade; then
        chg_password
        set_hostname
        set_timezone
        disable_ipv6
    fi
    misc_imports
    install_ser2net
    dhcp_run_hook
    ConsolePi_cleanup
    install_ovpn
    ovpn_graceful_shutdown
    # ovpn_logging
    install_autohotspotn
    gen_dnsmasq_conf
    dhcpcd_conf
    update_banner
    do_blue_config
    do_consolepi_api
    do_consolepi_mdns
    do_consolepi_commands
    # $tftpd && do_tftpd_server
    ! $upgrade && misc_stuff
    get_utils
    do_resize
    util_main
    get_known_ssids
    get_serial_udev
    custom_post_install_script
    # move_log
    post_install_msg
}
