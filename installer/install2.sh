#!/usr/bin/env bash

# ------------------------------------------------------------------------------------------------------------------------------------------------- #
# --                                                 ConsolePi Installation Script Stage 2                                                       -- #
# --  Wade Wells - Jul 2019                                                                                                                      -- #
# --    report any issues/bugs on github or fork-fix and submit a PR                                                                             -- #
# --                                                                                                                                             -- #
# --  This script aims to automate the installation of ConsolePi.                                                                                -- #
# --  For manual setup instructions and more detail visit https://github.com/Pack3tL0ss/ConsolePi                                                -- #
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
    logit "Starting get/build Configuration"
    if [[ ! -f $default_config ]] && [[ ! -f "/home/${iam}/ConsolePi.conf" ]] && [[ ! -f ${stage_dir}ConsolePi.conf ]]; then
        logit "No Existing Config found - building default"
        # This indicates it's the first time the script has ran
        echo "# Do Not Delete this line. ConsolePi Configuration File ver ${CFG_FILE_VER}"  > "${default_config}"
        echo "push=true                                    # PushBullet Notifications: true - enable, false - disable" > "${default_config}"
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
        # echo 'api=true                                                      # API used so ConsolePis can update other DHCP Discovery' >> "${default_config}"
        echo "debug=false                                                   # turns on additional debugging" >> "${default_config}"
        header
        echo "Configuration File Created with default values. Enter y to continue in Interactive Mode"
        echo "which will prompt you for each value. Enter n to exit the script, so you can modify the"
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
            echo "Please edit config in ${default_config} using editor (i.e. nano) and re-run install script"
            echo "i.e. \"sudo nano ${default_config}\""
            echo
            # move_log
            exit 0
        fi
    # If Config exists in /etc/ConsolePi/ConsolePi.conf it takes precedence
    elif [[ -f "${default_config}" ]]; then
        logit "Using existing Config found in ${consolepi_dir}"
    # For first run if no config exists in default location look in user home_dir and stage_dir for pre-config file
    elif [[ -f "/home/${iam}/ConsolePi.conf" ]] || [[ -f ${stage_dir}ConsolePi.conf ]]; then
        found_path=$(get_staged_file_path "ConsolePi.conf")
        if [[ $found_path ]]; then
            logit "using provided config: ${found_path}"
            sudo mv $found_path $default_config ||
                logit "Error Moving provided config: ${found_path}" "WARNING"
        else
            logit "NUL Return from found_path: ${found_path}" "ERROR"
        fi
    fi
    . "$default_config" || 
        logit "Error Loading Configuration defaults" "WARNING"
    hotspot_dhcp_range
    unset process
}
 

# Process Changes that are required after the existing config is read in when doing upgrade
upgrade_prep() {
    # Update Config to include values for Cloud Config Function
    if [[ -f "${default_config}" ]]; then
        process="ConsolePi-Upgrade-Prep (Config Updates)"
        [ -z "$cloud" ] && cloud=false &&
            echo "cloud=false                                                   # enable ConsolePi clustering / cloud config sync" >> "${default_config}" &&
                logit "Updated Existing Config to support new Cloud Features.  Refer to gitHub for instructions on setup"
        [ -z "$cloud_svc" ] && cloud_svc="gdrive" &&
            echo 'cloud_svc="gdrive"                                            # Future - only Google Drive / Google Sheets supported currently - must be "gdrive"' >> "${default_config}"
        [ -z "$debug" ] && debug=false &&
            echo "debug=false                                                   # turns on additional debugging" >> "${default_config}"
    else
        logit "Error Configuration defaults not found. Unable to Upgrade to new version verify config includes cloud variables when complete" "WARNING"
    fi
}

# Update Config file with Collected values
update_config() {
    echo "# Do Not Delete this line. ConsolePi Configuration File ver ${CFG_FILE_VER}"  > "${default_config}"
    echo "push=${push}                                                                   # PushBullet Notifications: true - enable, false - disable" >> "${default_config}"
    echo "push_all=${push_all}                                                   # PushBullet send notifications to all devices: true - yes, false - send only to device with iden specified by push_iden" >> "${default_config}"
    echo "push_api_key=\"${push_api_key}\"   # PushBullet API key" >> "${default_config}"
    echo "push_iden=\"${push_iden}\"                                    # iden of device to send PushBullet notification to if not push_all" >> "${default_config}"
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
    # echo "api=${api}                                                           # API used so ConsolePis can update other DHCP Discovery" >> "${default_config}"
    echo "debug=${debug}                                                     # turns on additional debugging" >> "${default_config}"
}

# Update ConsolePi Banner to display ConsolePi ascii logo at login
update_banner() {
    process="update motd"
    count=$(grep -c "PPPPPPPPPPPPPPPPP" /etc/motd)
    if [[ $count == 0 ]]; then
        logit "Update motd with Custom ConsolePi Banner"
        sed -i '1s/^/        CCCCCCCCCCCCC                                                                     lllllll                   PPPPPPPPPPPPPPPPP     iiii  \n/' /etc/motd
        sed -i '2s/^/     CCC::::::::::::C                                                                     l:::::l                   P::::::::::::::::P   i::::i \n/' /etc/motd
        sed -i '3s/^/   CC:::::::::::::::C                                                                     l:::::l                   P::::::PPPPPP:::::P   iiii  \n/' /etc/motd
        sed -i '4s/^/  C:::::CCCCCCCC::::C                                                                     l:::::l                   PP:::::P     P:::::P        \n/' /etc/motd
        sed -i '5s/^/ C:::::C       CCCCCC   ooooooooooo   nnnn  nnnnnnnn        ssssssssss      ooooooooooo    l::::l     eeeeeeeeeeee    P::::P     P:::::Piiiiiii \n/' /etc/motd
        sed -i '6s/^/C:::::C               oo:::::::::::oo n:::nn::::::::nn    ss::::::::::s   oo:::::::::::oo  l::::l   ee::::::::::::ee  P::::P     P:::::Pi:::::i \n/' /etc/motd
        sed -i '7s/^/C:::::C              o:::::::::::::::on::::::::::::::nn ss:::::::::::::s o:::::::::::::::o l::::l  e::::::eeeee:::::eeP::::PPPPPP:::::P  i::::i \n/' /etc/motd
        sed -i '8s/^/C:::::C              o:::::ooooo:::::onn:::::::::::::::ns::::::ssss:::::so:::::ooooo:::::o l::::l e::::::e     e:::::eP:::::::::::::PP   i::::i \n/' /etc/motd
        sed -i '9s/^/C:::::C              o::::o     o::::o  n:::::nnnn:::::n s:::::s  ssssss o::::o     o::::o l::::l e:::::::eeeee::::::eP::::PPPPPPPPP     i::::i \n/' /etc/motd
        sed -i '10s/^/C:::::C              o::::o     o::::o  n::::n    n::::n   s::::::s      o::::o     o::::o l::::l e:::::::::::::::::e P::::P             i::::i \n/' /etc/motd
        sed -i '11s/^/C:::::C              o::::o     o::::o  n::::n    n::::n      s::::::s   o::::o     o::::o l::::l e::::::eeeeeeeeeee  P::::P             i::::i \n/' /etc/motd
        sed -i '12s/^/ C:::::C       CCCCCCo::::o     o::::o  n::::n    n::::nssssss   s:::::s o::::o     o::::o l::::l e:::::::e           P::::P             i::::i \n/' /etc/motd
        sed -i '13s/^/  C:::::CCCCCCCC::::Co:::::ooooo:::::o  n::::n    n::::ns:::::ssss::::::so:::::ooooo:::::ol::::::le::::::::e        PP::::::PP          i::::::i\n/' /etc/motd
        sed -i '14s/^/   CC:::::::::::::::Co:::::::::::::::o  n::::n    n::::ns::::::::::::::s o:::::::::::::::ol::::::l e::::::::eeeeeeeeP::::::::P          i::::::i\n/' /etc/motd
        sed -i '15s/^/     CCC::::::::::::C oo:::::::::::oo   n::::n    n::::n s:::::::::::ss   oo:::::::::::oo l::::::l  ee:::::::::::::eP::::::::P          i::::::i\n/' /etc/motd
        sed -i '16s/^/        CCCCCCCCCCCCC   ooooooooooo     nnnnnn    nnnnnn  sssssssssss       ooooooooooo   llllllll    eeeeeeeeeeeeeePPPPPPPPPP          iiiiiiii\n/' /etc/motd
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

    # -- OpenVPN --
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
    
    # -- HotSpot IP --
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

    # -- cloud --
    header
    prompt="Do you want to enable ConsolePi Cloud Config (Clustering) Function"
    user_input $cloud "${prompt}"
    cloud=$result

    # TODO - FUTURE - Currently it's on, but not used
    # -- api --
    # header
    # echo "ConsolePi has an API used for ConsolePis to exchange information"
    # echo "This is used for the DHCP automated Discovery.  i.e.: "
    # echo "    ConsolePiA acting as a hotspot"
    # echo "    ConsolePiB Connects to ConsolePiA via Hotspot"
    # echo "    ConsolePiA will automatically push/pull info to/from ConsolePiB via the API"
    # echo "In this scenario you can connect to either ConsolePi and the consolepi-menu will display"
    # echo "menu items for serial connections on both ConsolePi(s)"
    # echo ''
    # prompt="Do you want to enable ConsolePi API"
    # user_input $api "${prompt}"
    # api=$result

    # Future gdrive google sheets is only one supported currently likely ever, no need as gdrive works
    # -- cloud-svc --
    # header
    # prompt="What Cloud Service will you use"
    # cloud_svc_menu $cloud_svc "${prompt}"
    # cloud_svc=$result
    cloud_svc="gdrive"
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
    echo
    echo "----------------------------------------------------------------------------------------------------------------"
    echo
    echo "Enter Y to Continue N to make changes"
    echo
    prompt="Are Values Correct"
    input=$(user_input_bool)
}

chg_password() {
    if [[ $iam == "pi" ]]; then 
        header
        echo "You are logged in as pi, the default user."
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
            sudo sed -i "s/$hostn/$newhost/g" /etc/hosts
            sudo sed -i "s/$hostn\.$(grep -o "$hostn\.[0-9A-Za-z].*" /etc/hosts | cut -d. -f2-)/$newhost.$local_domain/g" /etc/hosts
            # change hostname via command
            sudo hostname "$newhost" 1>&2 2>>/dev/null
            [ $? -gt 0 ] && logit "Error returned from hostname command" "WARNING"
            # add wlan hotspot IP to hostfile for DHCP connected clients to resolve this host
            wlan_hostname_exists=$(grep -c "$wlan_ip" /etc/hosts)
            [ $wlan_hostname_exists == 0 ] && echo "$wlan_ip       $newhost" >> /etc/hosts
            sudo sed -i "s/$hostn/$newhost/g" /etc/hostname
            
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
    # address of an interface has changed (PB notifications only occur if there is a change). So notifications are always sent on reboot
    process="Deploy ConsolePi cleanup init Script"
    logit "${process} Starting"
    sudo cp "/etc/ConsolePi/src/systemd/ConsolePi_cleanup" "/etc/init.d" 1>/dev/null 2>> $log_file || 
        logit "Error Copying ConsolePi_cleanup init script." "WARNING"
    chmod +x /etc/init.d/ConsolePi_cleanup 1>/dev/null 2>> $log_file || 
        logit "Failed to make ConsolePi_cleanup init script executable." "WARNING"
    sudo /lib/systemd/systemd-sysv-install enable ConsolePi_cleanup 1>/dev/null 2>> $log_file || 
        logit "Failed to enable ConsolePi_cleanup init script." "WARNING"
        
    logit "${process} - Complete"
    unset process
}

#sub process used by install_ovpn
check_vpn_config(){
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
                logit "Succesfully Updated ovpn up Pointer" || logit "Failed to update ovpn up pointer" "WARNING"
            fi
        fi
    fi
}

install_ovpn() {
    process="OpenVPN"
    logit "Install OpenVPN"
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
        $push && check_vpn_config
    else
        found_path=$(get_staged_file_path "ConsolePi.ovpn")
        if [[ $found_path ]]; then 
            cp $found_path "/etc/openvpn/client" &&
                logit "Found ${found_path}.  Copying to /etc/openvpn/client" ||
                logit "Error occurred Copying your ovpn config" "WARNING"
            $push && [ -f /etc/openvpn/client/ConsolePi.ovpn ] && check_vpn_config
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
    # Can Remove portions of this and remove file in /usr/bin/ have pointed everything directly to the file in the repo
    process="AutoHotSpotN"
    logit "Install AutoHotSpotN"
    [[ -f "${src_dir}autohotspotN" ]] && cp "${src_dir}autohotspotN" /usr/bin 1>/dev/null 2>> $log_file
    [[ $? == 0 ]] && logit "Create/Update autohotspotN script Success" || logit "Failed to create autohotspotN script" "WARNING"
        
    chmod +x /usr/bin/autohotspotN 1>/dev/null 2>> $log_file ||
        logit "Failed to chmod autohotspotN script" "WARNING"
        
    logit "Installing hostapd via apt."
    hostapd_ver=$(hostapd -v 2>&1| head -1| awk '{print $2}')
    hostapd -v > /dev/null 2>&1
    if [ $? -gt 1 ]; then
        apt-get -y install hostapd 1>/dev/null 2>> $log_file &&
            logit "hostapd install Success" ||
            logit "hostapd install Failed" "WARNING"
    else
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
    sudo systemctl unmask hostapd.service 1>/dev/null 2>> $log_file && logit "hostapd.service unmasked" || logit "failed to unmask hostapd.service" "WARNING"
    sudo /lib/systemd/systemd-sysv-install disable hostapd 1>/dev/null 2>> $log_file && res=$?
    sudo /lib/systemd/systemd-sysv-install disable dnsmasq 1>/dev/null 2>> $log_file && ((res=$?+$res))
    [[ $res == 0 ]] && logit "hostapd and dnsmasq autostart disabled Successfully" ||
        logit "An error occurred disabling hostapd and/or dnsmasq autostart" "WARNING"

    logit "Create/Configure hostapd.conf"
    [[ -f "/etc/hostapd/hostapd.conf" ]] && sudo mv "/etc/hostapd/hostapd.conf" "${bak_dir}" && 
        logit "existing hostapd.conf found, backed up to bak folder"
    echo "driver=nl80211" > "/tmp/hostapd.conf"
    echo "ctrl_interface=/var/run/hostapd" >> "/tmp/hostapd.conf"
    echo "ctrl_interface_group=0" >> "/tmp/hostapd.conf"
    echo "beacon_int=100" >> "/tmp/hostapd.conf"
    echo "auth_algs=1" >> "/tmp/hostapd.conf"
    echo "wpa_key_mgmt=WPA-PSK" >> "/tmp/hostapd.conf"
    echo "ssid=${wlan_ssid}" >> "/tmp/hostapd.conf"
    echo "channel=1" >> "/tmp/hostapd.conf"
    echo "hw_mode=g" >> "/tmp/hostapd.conf"
    echo "wpa_passphrase=${wlan_psk}" >> "/tmp/hostapd.conf"
    echo "interface=wlan0" >> "/tmp/hostapd.conf"
    echo "wpa=2" >> "/tmp/hostapd.conf"
    echo "wpa_pairwise=CCMP" >> "/tmp/hostapd.conf"
    echo "country_code=${wlan_country}" >> "/tmp/hostapd.conf"
    echo "ieee80211n=1" >> "/tmp/hostapd.conf"
    mv /tmp/hostapd.conf /etc/hostapd/hostapd.conf 1>/dev/null 2>> $log_file &&
        logit "hostapd.conf Successfully configured." ||
        logit "hostapdapd.conf Failed to create config" "WARNING"
    
    logit "Making changes to /etc/hostapd/hostapd.conf"
    [[ -f "/etc/default/hostapd" ]] && mv "/etc/default/hostapd" "${bak_dir}" 
    echo "# Defaults for hostapd initscript" > "/tmp/hostapd"
    echo "#" >> "/tmp/hostapd"
    echo "# See /usr/share/doc/hostapd/README.Debian for information about alternative" >> "/tmp/hostapd"
    echo "# methods of managing hostapd." >> "/tmp/hostapd"
    echo "#" >> "/tmp/hostapd"
    echo "# Uncomment and set DAEMON_CONF to the absolute path of a hostapd configuration" >> "/tmp/hostapd"
    echo "# file and hostapd will be started during system boot. An example configuration" >> "/tmp/hostapd"
    echo "# file can be found at /usr/share/doc/hostapd/examples/hostapd.conf.gz" >> "/tmp/hostapd"
    echo "#" >> "/tmp/hostapd"
    echo "DAEMON_CONF=\"/etc/hostapd/hostapd.conf\"" >> "/tmp/hostapd"
    echo "" >> "/tmp/hostapd"
    echo "# Additional daemon options to be appended to hostapd command:-" >> "/tmp/hostapd"
    echo "#       -d   show more debug messages (-dd for even more)" >> "/tmp/hostapd"
    echo "#       -K   include key data in debug messages" >> "/tmp/hostapd"
    echo "#       -t   include timestamps in some debug messages" >> "/tmp/hostapd"
    echo "#" >> "/tmp/hostapd"
    echo "# Note that -B (daemon mode) and -P (pidfile) options are automatically" >> "/tmp/hostapd"
    echo "# configured by the init.d script and must not be added to DAEMON_OPTS." >> "/tmp/hostapd"
    echo "#" >> "/tmp/hostapd"
    echo "#DAEMON_OPTS=\"\"" >> "/tmp/hostapd"
    mv /tmp/hostapd /etc/default && \
        logit "Changes to /etc/hostapd/hostapd.conf made successfully" ||
        logit "Error making Changes to /etc/hostapd/hostapd.conf" "WARNING"
    
    logit "Verifying interface file."
    int_line=`cat /etc/network/interfaces |grep -v '^$\|^\s*\#'`
    if [[ ! "${int_line}" == "source-directory /etc/network/interfaces.d" ]]; then
        echo "# interfaces(5) file used by ifup(8) and ifdown(8)" >> "/tmp/interfaces"
        echo "# Please note that this file is written to be used with dhcpcd" >> "/tmp/interfaces"
        echo "# For static IP, consult /etc/dhcpcd.conf and 'man dhcpcd.conf'" >> "/tmp/interfaces"
        echo "# Include files from /etc/network/interfaces.d:" >> "/tmp/interfaces"
        echo "source-directory /etc/network/interfaces.d" >> "/tmp/interfaces"
        mv /etc/network/interfaces "${bak_dir}" 1>/dev/null 2>> $log_file ||
            logit "Failed to backup original interfaces file" "WARNING"
        mv "/tmp/interfaces" "/etc/network/" 1>/dev/null 2>> $log_file ||
            logit "Failed to move interfaces file" "WARNING"
    fi

    logit "Creating Startup script."
    echo "[Unit]" > "/tmp/autohotspot.service"
    echo "Description=Automatically generates an internet Hotspot when a valid ssid is not in range" >> "/tmp/autohotspot.service"
    echo "After=multi-user.target" >> "/tmp/autohotspot.service"
    echo "[Service]" >> "/tmp/autohotspot.service"
    echo "Type=oneshot" >> "/tmp/autohotspot.service"
    echo "RemainAfterExit=yes" >> "/tmp/autohotspot.service"
    echo "ExecStart=/usr/bin/autohotspotN" >> "/tmp/autohotspot.service"
    echo "[Install]" >> "/tmp/autohotspot.service"
    echo "WantedBy=multi-user.target" >> "/tmp/autohotspot.service"
    mv "/tmp/autohotspot.service" "/etc/systemd/system/" 1>/dev/null 2>> $log_file ||
            logit "Failed to create autohotspot.service init" "WARNING"
    logit "Enabling Startup script."
    systemctl enable autohotspot.service 1>/dev/null 2>> $log_file &&
        logit "Successfully enabled autohotspot.service" ||
        logit "Failed to enable autohotspot.service" "WARNING"
    
    logit "Verify iw is installed on system."
    if [[ ! $(dpkg -l iw | tail -1 |cut -d" " -f1) == "ii" ]]; then
        logit "iw not found, Installing iw via apt."
        ( apt-get -y install iw 1>/dev/null 2>> $log_file && logit "iw installed Successfully" &&  iw_inst=true ) || 
            logit "FAILED to install iw" "WARNING"
    else
        logit "iw is already installed/current."
    fi
        
    logit "Enable IP-forwarding (/etc/sysctl.conf)"
    sed -i '/^#net\.ipv4\.ip_forward=1/s/^#//g' /etc/sysctl.conf 1>/dev/null 2>> $log_file && logit "Enable IP-forwarding - Success" ||
        logit "FAILED to enable IP-forwarding verify /etc/sysctl.conf 'net.ipv4.ip_forward=1'" "WARNING"
    
    logit "${process} Complete"
    unset process
}

gen_dnsmasq_conf () {
    process="Configure dnsmasq"
    logit "Generating Files for dnsmasq."
    echo "# dnsmasq configuration created by ConsolePi installer" > /tmp/dnsmasq.conf
    echo "# modifications can be made but the 'dhcp-option-wlan0,3' line needs to exist" >> /tmp/dnsmasq.conf
    echo "# for the default-gateway on/off based on eth0 status function to work" >> /tmp/dnsmasq.conf
    echo "dhcp-script=/etc/ConsolePi/src/dhcp-trigger.py" >> /tmp/dnsmasq.conf
    common_text="interface=wlan0\nbogus-priv\ndomain-needed\ndhcp-range=${wlan_dhcp_start},${wlan_dhcp_end},255.255.255.0,12h\ndhcp-option=wlan0,3\n"
    echo -e "$common_text" >> /tmp/dnsmasq.conf
    [[ -f "/etc/dnsmasq.conf" ]] && mv "/etc/dnsmasq.conf" $bak_dir && logit "Existing dnsmasq.conf backed up to originals folder"
    mv "/tmp/dnsmasq.conf" "/etc/dnsmasq.conf" 1>/dev/null 2>> $log_file ||
            logit "Failed to Deploy ConsolePi dnsmasq.conf configuration" "WARNING"
    unset process
}

dhcpcd_conf () {
    process="dhcpcd.conf"
    logit "configure dhcp client and static fallback"
    [[ -f /etc/dhcpcd.conf ]] && sudo mv /etc/dhcpcd.conf $bak_dir
    sudo cp /etc/ConsolePi/src/dhcpcd.conf /etc/dhcpcd.conf 1>/dev/null 2>> $log_file
    res=$?
    if [[ $res == 0 ]]; then
        echo "" >> "/etc/dhcpcd.conf"
        echo "# wlan static fallback profile" >> "/etc/dhcpcd.conf"
        echo "profile static_wlan0" >> "/etc/dhcpcd.conf"
        echo "static ip_address=${wlan_ip}/24" >> "/etc/dhcpcd.conf"
        echo "" >> "/etc/dhcpcd.conf"
        echo "# wired static fallback profile" >> "/etc/dhcpcd.conf"
        echo "# defined - currently commented out/disabled" >> "/etc/dhcpcd.conf"
        echo "profile static_eth0" >> "/etc/dhcpcd.conf"
        echo "static ip_address=192.168.25.10/24" >> "/etc/dhcpcd.conf"
        echo "static routers=192.168.25.1" >> "/etc/dhcpcd.conf"
        echo "static domain_name_servers=1.0.0.1 8.8.8.8" >> "/etc/dhcpcd.conf"
        echo "" >> "/etc/dhcpcd.conf"
        echo "# Assign fallback to static profile on wlan0" >> "/etc/dhcpcd.conf"
        echo "interface wlan0" >> "/etc/dhcpcd.conf"
        echo "fallback static_wlan0" >> "/etc/dhcpcd.conf"
        echo "# For ConsolePi Discovery via DHCP" >> "/etc/dhcpcd.conf"
        echo 'vendorclassid "dhcpcd:ConsolePi"' >> "/etc/dhcpcd.conf"
        echo "interface eth0" >> "/etc/dhcpcd.conf"
        echo "# fallback static_eth0" >> "/etc/dhcpcd.conf"
        echo "# For ConsolePi Discovery via DHCP" >> "/etc/dhcpcd.conf"
        echo 'vendorclassid "dhcpcd:ConsolePi"' >> "/etc/dhcpcd.conf"
        echo "" >> "/etc/dhcpcd.conf"
        echo "#For AutoHotkeyN" >> "/etc/dhcpcd.conf"
        echo "nohook wpa_supplicant" >> "/etc/dhcpcd.conf"
        logit "Process Completed Successfully"
    else
        logit "Error Code (${res}) returned when attempting to mv dhcpcd.conf from ConsolePi src"
        logit "Verify dhcpcd.conf and configure manually after install completes"
    fi
    unset process
}

do_blue_config() {
    process="Bluetooth Console"
    logit "${process} Starting"
    ## Some Sections of the bluetooth configuration from https://hacks.mozilla.org/2017/02/headless-raspberry-pi-configuration-over-bluetooth/
    ## Edit /lib/systemd/system/bluetooth.service
    sudo sed -i: 's|^Exec.*toothd$| \
    ExecStart=/usr/lib/bluetooth/bluetoothd -C --noplugin=sap\
    ExecStartPost=/usr/bin/sdptool add SP \
    ExecStartPost=/bin/hciconfig hci0 piscan \
    |g' /lib/systemd/system/bluetooth.service

    # create /etc/systemd/system/rfcomm.service to enable 
    # the Bluetooth serial port from systemctl

sudo cat <<EOF | sudo tee /etc/systemd/system/rfcomm.service > /dev/null
[Unit]
Description=RFCOMM service
After=bluetooth.service
Requires=bluetooth.service

[Service]
ExecStart=/usr/bin/rfcomm watch hci0 1 setsid /sbin/agetty -L rfcomm0 115200 vt100 -a blue

[Install]
WantedBy=multi-user.target
EOF

    # enable the new rfcomm service
    sudo systemctl enable rfcomm 1>/dev/null 2>> $log_file  && logit "rfcomm systemd script enabled" || 
                logit "FAILED to enable rfcomm systemd script" "WARNING"

    # start the rfcomm service
    sudo systemctl stop rfcomm 1>/dev/null 2>> $log_file 
    sudo systemctl start rfcomm 1>/dev/null 2>> $log_file 
       
    # add blue user and set to launch menu on login
    if [[ ! $(cat /etc/passwd | grep -o blue | sort -u) ]]; then
        echo -e 'ConsoleP1!!\nConsoleP1!!\n' | sudo adduser --gecos "" blue 1>/dev/null 2>> $log_file && 
        logit "BlueTooth User created" || 
        logit "FAILED to create Bluetooth user" "WARNING"
    else
        logit "BlueTooth User already exists"
    fi
    
    # add blue user to dialout group so they can access /dev/ttyUSB_ devices
    if [[ ! $(groups blue | grep -o dialout) ]]; then
    sudo usermod -a -G dialout blue 2>> $log_file && logit "BlueTooth User added to dialout group" || 
        logit "FAILED to add Bluetooth user to dialout group" "WARNING"
    else
        logit "BlueTooth User already in dialout group" 
    fi

    # Configure blue user default tty cols/rows
    if [[ ! $(sudo grep stty /home/blue/.bashrc) ]]; then
        sudo echo stty rows 70 cols 150 | sudo tee -a /home/blue/.bashrc > /dev/null && 
            logit "Changed default Bluetooth tty rows cols" || 
            logit "FAILED to change default Bluetooth tty rows cols" "WARNING"
    else
        logit "blue user tty rows cols already configured"
    fi

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

# Create or Update ConsolePi API startup service (systemd)
do_consolepi_api() {
    process="Configure/Enable ConsolePi API (systemd)"
    systemd_diff_update "consolepi-api"
    unset process
}

# Create or Update ConsolePi mdns startup service (systemd)
do_consolepi_mdns() {
    process="Configure/Enable ConsolePi mDNS services (systemd)"
    systemd_diff_update "consolepi-mdnsreg"
    systemd_diff_update "consolepi-mdnsbrowse"
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
            # To To compare the files ask user if they want to import if they dont match
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
    logit "${process} - Starting"
    if [ $(ls -l /usr/local/bin/consolepi* 2>/dev/null | wc -l) -ne 0 ]; then
        sudo rm /usr/local/bin/consolepi-* > /dev/null 2>&1
        sudo unlink /usr/local/bin/consolepi-* > /dev/null 2>&1
    else
        logit "None Found, we're good."   
    fi
    logit "${process} - Complete"

    process="Update PATH for consolepi-commands"
    [ $(grep -c "consolepi-commands" /etc/profile) -eq 0 ] && 
        sudo echo 'export PATH="$PATH:/etc/ConsolePi/src/consolepi-commands"' >> /etc/profile &&
        logit "PATH Updated" || logit "PATH contains consolepi-commands dir, No Need for update"

    unset process
}

misc_stuff() {
    process="Set Keyboard Layout"
    logit "${process} - Starting"
    sudo sed -i "s/gb/${wlan_country,,}/g" /etc/default/keyboard && logit "KeyBoard Layout changed to ${wlan_country,,}"
    logit "${process} - Complete"
    unset process
}

get_serial_udev() {
    process="Predictable Console Ports"
    logit "${process} Starting."
    header
    
    # -- if pre-stage file provided during install enable it --
    if ! $upgrade; then
        found_path=$(get_staged_file_path "10-ConsolePi.rules")
        if [[ $found_path ]]; then
            logit "udev rules file found ${found_path} enabling provided udev rules"
            # [[ -f /etc/udev/rules.d/10-ConsolePi.rules ]] && cp /etc/udev/rules.d/10-ConsolePi.rules $bak_dir
            if [ -f /etc/udev/rules.d/10-ConsolePi.rules ]; then
                # logit "udev rules file found ${found_path} enabling provided udev rules"
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
    echo "- will always be reachable on a predictable telnet port (it's a good idea to label the adapters).                   -"
    echo "-                                                                                                                   -"
    echo "- This is handy if you ever plan to have multiple adapters, or if you are using a multi-port pig-tail adapter.      -"
    echo "-                                                                                                                   -"
    echo "---------------------------------------------------------------------------------------------------------------------"
    echo
    echo "You need to have the serial adapters you want to map to specific telnet ports available"
    prompt="Would you like to configure predictable serial ports now"
    $upgrade && user_input false "${prompt}" || user_input true "${prompt}"
    if $result ; then
        if [ -f ${consolepi_dir}src/consolepi-addconsole.sh ]; then
            . ${consolepi_dir}src/consolepi-addconsole.sh
            udev_main
        else
            logit "ERROR consolepi-addconsole.sh not available in src directory" "WARNING"
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
    echo -e "* \033[1;32mOpenVPN:$*\033[m                                                                                                              *"
    echo "*   if you are using the Automatic VPN feature you should Configure the ConsolePi.ovpn and ovpn_credentials files in    *"
    echo "*   /etc/openvpn/client.  Refer to the example ovpn file as there are a couple of lines specific to ConsolePi           *"
    echo "*   functionality (bottom of the example file).                                                                         *"
    echo "*     You should \"sudo chmod 600 <filename>\" both of the files for added security                                       *"
    echo "*                                                                                                                       *"
    echo -e "* \033[1;32mser2net Usage:$*\033[m                                                                                                        *"
    echo "*   Serial Ports are available starting with telnet port 8001 to 8005 incrementing with each adapter plugged in.        *"
    echo "*   if you configured predictable ports for specific serial adapters those start with 7001 - (no max) label the         *"
    echo "*   adapters appropriately.                                                                                             *"
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
    echo "*   The bulk is sent to syslog. the tags 'puship', 'puship-ovpn', 'autohotspotN' and 'dhcpcd' are of key interest.      *"
    echo "*   - openvpn logs are sent to /var/log/ConsolePi/ovpn.log you can tail this log to troubleshoot any issues with ovpn   *"
    echo "*   - pushbullet responses (json responses to curl cmd) are sent to /var/log/ConsolePi/push_response.log                *"
    echo "*   - An install log can be found in ${consolepi_dir}installer/install.log                                               *"
    echo "*                                                                                                                       *"
    echo -e "* \033[1;32mConsolePi Commands:$*\033[m                                                                                                   *"
    echo "*   - consolepi-upgrade: upgrade consolepi. - using install script direct from repo | ser2net upgrade bypassed for now  *"
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
    upgrade_prep
    ! $bypass_verify && verify
    while ! $input; do
        collect "fix"
        verify
    done
    update_config
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
    ! $upgrade && misc_stuff
    get_known_ssids
    get_serial_udev
    custom_post_install_script
    # move_log
    post_install_msg
}
