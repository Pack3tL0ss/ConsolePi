#!/usr/bin/env bash

ver="1.0"
# ------------------------------------------------------------------------------------------------------------------------------------------------- #
# --                                                 ConsolePi Installation Script                                                               -- #
# --  Wade Wells - Dec, 2018  v1.0                                                                                                               -- #
# --    eMail Wade with any bugs or suggestions, if you don't know Wade's eMail, then don't eMail Wade :)                                        -- #
# --                                                                                                                                             -- #
# --  This script aims to automate the installation of ConsolePi.                                                                                -- #
# --  For manual setup instructions and more detail visit https://github.com/Pack3tL0ss/ConsolePi                                                -- #
# --                                                                                                                                             -- #
# --  ** This was a mistake... should have done this in Python, Never do anything beyond simple in bash, but I was a couple 100 lines in when    -- #
# --  I had that epiphany so bash it is... for now                                                                                               -- #
# --------------------------------------------------------------------------------------------------------------------------------------------------#

# -- Installation Defaults --
consolepi_dir="/etc/ConsolePi"
src_dir="${consolepi_dir}/src"
orig_dir="${consolepi_dir}/originals"
default_config="/etc/ConsolePi/ConsolePi.conf"
wpa_supplicant_file="/etc/wpa_supplicant/wpa_supplicant.conf"
tmp_log="/tmp/consolepi_install.log"
iam=$(who am i | awk '{print $1}')
[[ $( ps -o comm -p $PPID | tail -1 ) == "sshd" ]] && ssh=true || ssh=false
touch $tmp_log
logline="----------------------------------------------------------------------------------------------------------------"

# -- External Sources --
ser2net_source="https://sourceforge.net/projects/ser2net/files/latest/download"
consolepi_source="https://github.com/Pack3tL0ss/ConsolePi.git"

# -- Build Config File and Directory Structure - Read defaults from config
get_config() {
    process="get config"
    bypass_verify=false
    logit "${process}" "Starting get/build Configuration"
    if [[ ! -f "${default_config}" ]] && [[ ! -f "/home/${iam}/ConsolePi.conf" ]]; then
        logit "${process}" "No Existing Config found - building default"
        # This indicates it's the first time the script has ran
        # [ ! -d "$consolepi_dir" ] && mkdir /etc/ConsolePi
        echo "push=true                                    # PushBullet Notifications: true - enable, false - disable" > "${default_config}"
        echo "push_all=true                                # PushBullet send notifications to all devices: true - yes, false - send only to device with iden specified by push_iden" >> "${default_config}"
        echo "push_api_key=\"PutYourPBAPIKeyHereChangeMe:\"    # PushBullet API key" >> "${default_config}"
        echo "push_iden=\"putyourPBidenHere\"                    # iden of device to send PushBullet notification to if not push_all" >> "${default_config}"
        echo "ovpn_enable=true                             # if enabled will establish VPN connection" >> "${default_config}"
        echo "vpn_check_ip=\"10.0.150.1\"                    # used to check VPN (internal) connectivity should be ip only reachable via VPN" >> "${default_config}"
        echo "net_check_ip=\"8.8.8.8\"                        # used to check internet connectivity" >> "${default_config}"
        echo "local_domain=\"arubalab.net\"                    # used to bypass VPN. evals domain sent via dhcp option if matches this var will not establish vpn" >> "${default_config}"
        echo "wlan_ip=\"10.3.0.1\"                        # IP of consolePi when in hotspot mode" >> "${default_config}"
        echo "wlan_ssid=\"ConsolePi\"                        # SSID used in hotspot mode" >> "${default_config}"
        echo "wlan_psk=\"ChangeMe!!\"                        # psk used for hotspot SSID" >> "${default_config}"
        echo "wlan_country=\"US\"                        # regulatory domain for hotspot SSID" >> "${default_config}"
        header
        echo "Configuration File Created with default values. Enter Y to continue in Interactive Mode"
        echo "which will prompt you for each value. Enter N to exit the script, so you can modify the"
        echo "defaults directly then re-run the script."
        echo
        prompt="Continue in Interactive mode? (Y/N)"
        user_input true "${prompt}"
        continue=$result
        if $continue ; then
            bypass_verify=true        # bypass verify function
            input=false                # so collect function will run (while loop in main)
        else
            header
            echo "Please edit config in ${default_config} using editor (i.e. nano) and re-run install script"
            echo "i.e. \"sudo nano ${default_config}\""
            echo
            move_log
            exit 0
        fi
    elif [[ -f "/home/${iam}/ConsolePi.conf" ]]; then
        logit "${process}" "using config found in ${iam} home directory"
        sudo cp "/home/${iam}/ConsolePi.conf" "$default_config" ||
            logit "${process}" "Error Copying Config found in user home directory" "WARNING"
    elif [[ -f "${default_config}" ]]; then
        logit "${process}" "Using existing Config found in ${consolepi_dir}"
    fi
    . "$default_config" || 
        logit "${process}" "Error Loading Configuration defaults"
    hotspot_dhcp_range
}

update_config() {
    echo "push=${push}                                # PushBullet Notifications: true - enable, false - disable" > "${default_config}"
    echo "push_all=${push_all}                        # PushBullet send notifications to all devices: true - yes, false - send only to device with iden specified by push_iden" >> "${default_config}"
    echo "push_api_key=\"${push_api_key}\"            # PushBullet API key" >> "${default_config}"
    echo "push_iden=\"${push_iden}\"                  # iden of device to send PushBullet notification to if not push_all" >> "${default_config}"
    echo "ovpn_enable=${ovpn_enable}                  # if enabled will establish VPN connection" >> "${default_config}"
    echo "vpn_check_ip=\"${vpn_check_ip}\"            # used to check VPN (internal) connectivity should be ip only reachable via VPN" >> "${default_config}"
    echo "net_check_ip=\"${net_check_ip}\"            # used to check internet connectivity" >> "${default_config}"
    echo "local_domain=\"${local_domain}\"            # used to bypass VPN. evals domain sent via dhcp option if matches this var will not establish vpn" >> "${default_config}"
    echo "wlan_ip=\"${wlan_ip}\"                      # IP of consolePi when in hotspot mode" >> "${default_config}"
    echo "wlan_ssid=\"${wlan_ssid}\"                  # SSID used in hotspot mode" >> "${default_config}"
    echo "wlan_psk=\"${wlan_psk}\"                    # psk used for hotspot SSID" >> "${default_config}"
    echo "wlan_country=\"${wlan_country}\"            # regulatory domain for hotspot SSID" >> "${default_config}"
}

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

update_banner() {
    process="update motd"
    logit "${process}" "Update motd with Custom ConsolePi Banner"
    # Update ConsolePi Banner to display ConsolePi ascii logo at login           
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
}

hotspot_dhcp_range() {
    baseip=`echo $wlan_ip | cut -d. -f1-3`   # get first 3 octets of wlan_ip
    wlan_dhcp_start=$baseip".101"
    wlan_dhcp_end=$baseip".150"
}
    
user_input() {
    case $1 in
        true|false)
            bool=true
        ;;
        *)
            bool=false
        ;;
    esac

    [ ! -z "$1" ] && default="$1" 
    [ ! -z "$2" ] && prompt="$2"

    if [ ! -z $default ]; then
        if $bool; then
            $default && prompt+=" [Y]: " || prompt+=" [N]: "
        else
            prompt+=" [${default}]: "
        fi
    else
        prompt+=" $prompt: "
    fi
    
    printf "%s" "${prompt}"
    read input
    if $bool; then
        if [ ${#input} -gt 0 ] && ([ ${input,,} == 'y' ] || [ ${input,,} == 'yes' ] || [ ${input,,} == 'true' ]); then 
            result=true
        elif [ ${#input} -gt 0 ] && ([ ${input,,} == 'n' ] || [ ${input,,} == 'no' ] || [ ${input,,} == 'false' ]); then 
            result=false
        elif ! [ -z $default ]; then
            result=$default
        else 
            result=false
        fi
    else
        if [ ${#input} -gt 0 ]; then
            result=$input
        elif [ ${#default} -gt 0 ]; then
            result=$default
        else
            result="Invalid"
        fi
    fi
}

collect() {
    # if [ -f /etc/consolePi/config ] && [ ${#1} -eq 0 ]; then
        # . /etc/consolePi/config
    # else
    # PushBullet
    header
    prompt="Configure ConsolePi to send notifications via PushBullet? (Y/N)"
    user_input $push "${prompt}"
    push=$result
    if $push; then
        header
        # -- PushBullet API Key --
        prompt="PushBullet API key"
        user_input $push_api_key "${prompt}"
        push_api_key=$result
        
        # -- Push to All Devices --
        header
        echo "Do you want to send PushBullet Messages to all PushBullet devices?"
        echo "Answer 'N'(no) to send to just 1 device "
        echo
        prompt="Send PushBullet Messages to all devices? (Y/N)"
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
    prompt="Enable Auto-Connect OpenVPN? (Y/N)"
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
    # fi
}

verify() {
    header
    # $first_run && header_txt=">>DEFAULT VALUES CHANGE THESE<<" || header_txt="--->>PLEASE VERIFY VALUES<<----"
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
    echo
    echo "----------------------------------------------------------------------------------------------------------------"
    echo
    echo "Enter Y to Continue N to make changes"
    echo
    prompt="Are Values Correct?"
    input=$(user_input_bool)
    # ([ ${input,,} == 'y' ] || [ ${input,,} == 'yes' ]) && input=true || input=false
}

move_log() {
    [[ -f "${consolepi_dir}/installer/install.log.3" ]] && sudo mv "${consolepi_dir}/installer/install.log.3" "${consolepi_dir}/installer/install.log.4"
    [[ -f "${consolepi_dir}/installer/install.log.2" ]] && sudo mv "${consolepi_dir}/installer/install.log.2" "${consolepi_dir}/installer/install.log.3"
    [[ -f "${consolepi_dir}/installer/install.log.1" ]] && sudo mv "${consolepi_dir}/installer/install.log.1" "${consolepi_dir}/installer/install.log.2"
    [[ -f "${consolepi_dir}/installer/install.log" ]] && sudo mv "${consolepi_dir}/installer/install.log" "${consolepi_dir}/installer/install.log.1"
    mv $tmp_log "${consolepi_dir}/installer/install.log" || echo -e "\n!!!!\nFailed to move install.log from ${tmp_log}\n!!!!"
}

logit() {
    # Logging Function: logit <process|string> <message|string> [<status|string>]
    process=$1                                      # 1st argument is process
    message=$2                                      # 2nd argument is message
    fatal=false                                        # fatal is determined by status default to false.  true if status = ERROR
    if [[ -z "${3}" ]]; then                        # 3rd argument is status default to INFO
        status="INFO"
    else
        status=$3
        [[ "${status}" == "ERROR" ]] && fatal=true
    fi
    
    # Log to stdout and log-file
    echo "$(date +"%b %d %T") ${process} [${status}] ${message}" | tee -a $tmp_log
    # if status was ERROR which means FATAL then log and exit script
    if $fatal ; then
        move_log
        echo "$(date +'%b %d %T') ${process} [${status}] Last Error is fatal, script exiting Please review log in /etc/ConsolePi/installer" && exit 1
    fi
}

user_input_bool() {
    valid_response=false
    while ! $valid_response; do
        read -p "${prompt}? (y/n): " response
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

chg_password() {
    # count=$(who | grep -c '^pi\s') 
    if [[ $iam == "pi" ]]; then 
        header
        echo "You are logged in as pi, the default user."
        prompt="Do You want to change the password for user pi"
        response=$(user_input_bool)
        if $response; then
            match=false
            while ! $match; do
                read -s -p "Enter new password for user pi: " pass && echo
                read -s -p "Re-Enter new password for user pi: " pass2 && echo
                [[ "${pass}" == "${pass2}" ]] && match=true || match=false
                ! $match && echo -e "ERROR: Passwords Do Not Match\n"
            done
            process="pi user password change"
            echo "pi:${pass}" | sudo chpasswd 2>> $tmp_log && logit "${process}" "Success" || 
              ( logit "${process}" "Failed to Change Password for pi user" "WARNING" &&
              echo -e "\n!!! There was an issue changing password.  Installation will continue, but continue to use existing password and update manually !!!" )
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
            #Display existing hostname
            read -p "Current hostname $hostn. Do you want to configure a new hostname (y/n)?: " response
            response=${response,,}    # tolower
            ( [[ "$response" =~ ^(yes|y)$ ]] || [[ "$response" =~ ^(no|n)$ ]] ) && valid_response=true || valid_response=false
        done
        if [[ "$response" =~ ^(yes|y)$ ]]; then
            #Ask for new hostname $newhost
            read -p "Enter new hostname: " newhost

            #change hostname in /etc/hosts & /etc/hostname
            sudo sed -i "s/$hostn/$newhost/g" /etc/hosts
            sudo sed -i "s/$hostn\.$(grep -o "$hostn\.[0-9A-Za-z].*" /etc/hosts | cut -d. -f2-)/$newhost.$local_domain/g" /etc/hosts
            sudo sed -i "s/$hostn/$newhost/g" /etc/hostname
            
            logit "${process}" "New hostname set $newhost" | tee -a $tmp_log
        fi
    else
        logit "${process}" "Hostname ${hostn} is not default, assuming it is desired hostname"
    fi
}

set_timezone() {
    cur_tz=$(date +"%Z")
    process="Configure ConsolePi TimeZone"
    if [[ $cur_tz == "GMT" ]]; then
        header

        prompt="Current TimeZone $cur_tz. Do you want to configure the timezone"
		set_tz=$(user_input_bool)

        if $set_tz; then
            echo "Launching, standby..." && sudo dpkg-reconfigure tzdata 2>> $tmp_log && header && logit "${process}" "Set new TimeZone to $(date +"%Z") Success" ||
                logit "${process}" "FAILED to set new TimeZone" "WARNING"
        fi
    else
        logit "${process}" "TimeZone cur_tz not default (GMT) assuming set as desired."
    fi
}

updatepi () {
    header
    process="Update/Upgrade ConsolePi (apt)"
    logit "${process}" "Update Sources"
    if [[ ! $(ls -l --full-time /var/cache/apt/pkgcache.bin | cut -d' ' -f6) == $(echo $(date +"%Y-%m-%d")) ]]; then
        sudo apt-get update 1>/dev/null 2>> $tmp_log && logit "${process}" "Update Successful" || logit "${process}" "FAILED to Update" "ERROR"
    else
        logit "${process}" "Skipping Source Update - Already Updated today"
    fi
    
    logit "${process}" "Upgrading ConsolePi via apt. This may take a while"
    sudo apt-get -y upgrade 1>/dev/null 2>> $tmp_log && logit "${process}" "Upgrade Successful" || logit "${process}" "FAILED to Upgrade" "ERROR"
    
    logit "${process}" "Performing dist-upgrade"
    sudo apt-get -y dist-upgrade 1>/dev/null 2>> $tmp_log && logit "${process}" "dist-upgrade Successful" || logit "${process}" "FAILED dist-upgrade" "WARNING"

    logit "${process}" "Tidying up (autoremove)"
    apt-get -y autoremove 1>/dev/null 2>> $tmp_log && logit "${process}" "Everything is tidy now" || logit "${process}" "apt-get autoremove FAILED" "WARNING"
        
    logit "${process}" "Installing git dependency via apt"
    apt-get -y install git 1>/dev/null 2>> $tmp_log && logit "${process}" "git install Successful" || logit "${process}" "git install FAILED to install" "ERROR"
    logit "${process}" "Process Complete"
}

gitConsolePi () {
    process="git Clone/Update ConsolePi"
    cd "/etc"
    if [ ! -d $consolepi_dir ]; then 
        logit "${process}" "Clean Install git clone ConsolePi"
        git clone "${consolepi_source}" 1>/dev/null 2>> $tmp_log && logit "${process}" "ConsolePi clone Success" || logit "${process}" "Failed to Clone ConsolePi" "ERROR"
    else
        cd $consolepi_dir
        logit "${process}" "Directory exists Updating ConsolePi via git"
        git pull "${consolepi_source}" 1>/dev/null 2>> $tmp_log && 
            logit "${process}" "ConsolePi update/pull Success" || logit "${process}" "Failed to update/pull ConsolePi" "WARNING"
    fi
}

install_ser2net () {
    # To Do add check to see if already installed / update
    process="Install ser2net"
    ser2net_ver=$(ser2net -v 2>> /dev/null | cut -d' ' -f3 && installed=true || installed=false)
    if [[ -z $ser2net_ver ]] ; then
        logit "${process}" "Installing ser2net from source"
        cd /usr/local/bin

        logit "${process}" "Retrieve and extract package"
        wget -q "${ser2net_source}" -O ./ser2net.tar.gz 1>/dev/null 2>> $tmp_log && 
            logit "${process}" "Successfully pulled ser2net from source" || logit "${process}" "Failed to pull ser2net from source" "ERROR"

        tar -zxvf ser2net.tar.gz 1>/dev/null 2>> $tmp_log &&
            logit "${process}" "ser2net extracted" ||
            logit "${process}" "Failed to extract ser2net from source" "ERROR"

        rm -f /usr/local/bin/ser2net.tar.gz || logit "${process}" "Failed to remove tar.gz" "WARNING"
        cd ser2net*/

        logit "${process}" "./configure ser2net"
        ./configure 1>/dev/null 2>> $tmp_log &&
            logit "${process}" "./configure ser2net Success" ||
            logit "${process}" "ser2net ./configure Failed" "ERROR"

        logit "${process}" "ser2net make, make install, make clean"
        make 1>/dev/null 2>> $tmp_log &&
            logit "${process}" "ser2net make Success" ||
            logit "${process}" "ser2net make Failed" "ERROR"

        make install 1>/dev/null 2>> $tmp_log &&
            logit "${process}" "ser2net make install Success" ||
            logit "${process}" "ser2net make install Failed" "ERROR"

        make clean 1>/dev/null 2>> $tmp_log &&
            logit "${process}" "ser2net make clean Success" ||
            logit "${process}" "ser2net make clean Failed" "WARNING"
        
        logit "${process}" "Building init & ConsolePi Config for ser2net"
        cp /etc/ConsolePi/src/ser2net.conf /etc/ 2>> $tmp_log || 
            logit "${process}" "ser2net Failed to copy config file from ConsolePi src" "ERROR"
        
        cp /etc/ConsolePi/src/ser2net.init /etc/init.d/ser2net 2>> $tmp_log || 
            logit "${process}" "ser2net Failed to copy init file from ConsolePi src" "ERROR"
            
        chmod +x /etc/init.d/ser2net 2>> $tmp_log || 
            logit "${process}" "ser2net Failed to make init executable" "WARNING"
        
        logit "${process}" "ser2net Enable init"
        /lib/systemd/systemd-sysv-install enable ser2net 1>/dev/null 2>> $tmp_log && 
            logit "${process}" "ser2net init file enabled" ||
            logit "${process}" "ser2net failed to enable init file (start on boot)" "WARNING"
            
        systemctl daemon-reload || 
            logit "${process}" "systemctl failed to reload daemons" "WARNING"
    else
        logit "${process}" "Ser2Net ${ser2net_ver} already installed. No Action Taken re ser2net"
        logit "${process}" "Ser2Net Upgrade is a Potential future function of this script"
    fi
        
    logit "${process}" "${process} Complete"
}

dhcp_run_hook() {
    process="Configure dhcp.exit-hook"
    error=0
    # ToDo add error checking, Verify logic the first if seems wrong
    logit "${process}" "Point dhcp.exit-hook to ConsolePi script"
    [[ -f /etc/dhcpcd.exit-hook ]] && exists=true || exists=false                      # find out if exit-hook file already exists
    if $exists; then
        is_there=`cat /etc/dhcpcd.exit-hook |grep -c /etc/ConsolePi/ConsolePi.sh`      # find out if it's already pointing to ConsolePi script
        lines=$(wc -l < "/etc/dhcpcd.exit-hook")                                       # find out if there are other lines in addition to ConsolePi in script
        if [[ $is_there > 0 ]] && [[ $lines > 1 ]]; then                                 # This scenario we just create a new script
            [[ ! -d "/etc/ConsolePi/originals" ]] && mkdir /etc/ConsolePi/originals 
            mv /etc/dhcpcd.exit-hook /etc/ConsolePi/originals/dhcpcd.exit-hook && 
              logit "${process}" "existing exit-hook backed up to originals folder" || logit "${process}" "Failed backup existing exit-hook file" "WARNING"
            echo "/etc/ConsolePi/ConsolePi.sh \"\$@\"" > "/etc/dhcpcd.exit-hook" || logit "${process}" "Failed to create exit-hook script" "ERROR"
        elif [[ $is_there == 0 ]]; then                                                # exit-hook exist but ConsolePi line does not append to file
            echo "/etc/ConsolePi/ConsolePi.sh \"\$@\"" >> "/etc/dhcpcd.exit-hook" || logit "${process}" "Failed to append ConsolePi pointer to exit-hook script" "ERROR"
        else
            logit "${process}" "exit-hook already configured [${is_there} ${lines}]"  #exit-hook exists and line is already there
        fi
    else
        echo "/etc/ConsolePi/ConsolePi.sh \"\$@\"" > "/etc/dhcpcd.exit-hook" || logit "${process}" "Failed to create exit-hook script" "ERROR"
    fi
    
    chmod +x /etc/dhcpcd.exit-hook 2>> $tmp_log || logit "${process}" "Failed to make dhcpcd.exit-hook executable" "WARNING"
    logit "${process}" "Install ConsolePi script Success"
}

ConsolePi_cleanup() {
    # ConsolePi_cleanup is an init script that runs on startup / shutdown.  On startup it removes tmp files used by ConsolePi script to determine if the ip
    # address of an interface has changed (PB notifications only occur if there is a change). So notifications are always sent on reboot
    # It also does a graceful shutdown of any openvpn sessions on shutdown.  This prevents an errant PB notification as the interfaces may bounce during shutdown
    # causing a reset of the openvpn session and an extraneous PB notification
    process="Deploy ConsolePi cleanup init Script"
    logit "${process}" "copy and enable ConsolePi_cleanup init script"
    cp "/etc/ConsolePi/src/ConsolePi_cleanup" "/etc/init.d" 1>/dev/null 2>> $tmp_log || 
        logit "${process}" "Error Copying ConsolePi_cleanup init script." "WARNING"
    chmod +x /etc/init.d/ConsolePi_cleanup 1>/dev/null 2>> $tmp_log || 
        logit "${process}" "Failed to make ConsolePi_cleanup init script executable." "WARNING"
    sudo /lib/systemd/systemd-sysv-install enable ConsolePi_cleanup 1>/dev/null 2>> $tmp_log || 
        logit "${process}" "Failed to enable ConsolePi_cleanup init script." "WARNING"
        
    logit "${process}" "copy and enable ConsolePi_cleanup init script - Complete"
}

install_ovpn() {
    process="OpenVPN"
    logit "${process}" "Install OpenVPN"
    if [[ ! $(dpkg -l openvpn | tail -1 |cut -d" " -f1) == "ii" ]]; then
        sudo apt-get -y install openvpn 1>/dev/null 2>> $tmp_log && logit "${process}" "OpenVPN installed Successfully" || logit "${process}" "FAILED to install OpenVPN" "WARNING"
        if ! $ovpn_enable; then
            logit "${process}" "You've chosen not to use the OpenVPN function.  Disabling OpenVPN. Package will remain installed. '/lib/systemd/systemd-sysv-install enable openvpn' to enable"
            /lib/systemd/systemd-sysv-install disable openvpn 1>/dev/null 2>> $tmp_log && logit "${process}" "Failed to disable OpenVPN" || logit "${process}" "FAILED to disable OpenVPN" "WARNING"
        else
            /lib/systemd/systemd-sysv-install enable openvpn 1>/dev/null 2>> $tmp_log && logit "${process}" "Failed to enable OpenVPN" || logit "${process}" "FAILED to enable OpenVPN" "WARNING"
        fi
    else
        logit "${process}" "OpenVPN Already present"
    fi
    
    if [[ ! -f "/home/${iam}/ConsolePi.ovpn" ]]; then 
        [[ ! -f "/etc/openvpn/client/ConsolePi.ovpn.example" ]] && cp "${src_dir}/ConsolePi.ovpn.example" "/etc/openvpn/client" ||
            logit "${process}" "Retaining existing ConsolePi.ovpn.example file. See src dir for original example file."
    else
        cp "/home/${iam}/ConsolePi.ovpn" "/etc/openvpn" &&
            logit "${process}" "Found ConsolePi.ovpn in /home/${iam}.  Copying the config you've provided." &&
            logit "${process}" "**Ensure the ovpn file has the ConsolePi specific lines at the end of the file... see example in \etc\ConsolePi\src" "WARNING" &&
            logit "${process}" "For security, once verified you should delete or chmod the ovpn config in your home dir, it's been copied to /openvpn/clients dir" "WARNING" ||
            logit "${process}" "Error occurred moving your ovpn config" "WARNING"
    fi
    
    if [[ ! -f "/home/${iam}/ovpn_credentials" ]]; then 
        [[ ! -f "/etc/openvpn/client/ovpn_credentials" ]] && cp "${src_dir}/ovpn_credentials" "/etc/openvpn/client" ||
            logit "${process}" "Retaining existing ovpn_credentials file. See src dir for original example file."
    else
        cp "/home/${iam}/ovpn_credentials" "/etc/ovpn_credentials" &&
            logit "${process}" "Found ovpn_credentials in /home/${iam}. Moving your provided file to openvpn/client dir."  &&
            logit "${process}" "For security, once verified you should delete or chmod the ovpn_credentials in your home dir, it's been copied to /openvpn/clients dir" "WARNING" ||
            logit "${process}" "Error occurred moving your ovpn_credentials file" "WARNING"
    fi
            
    sudo chmod 600 /etc/openvpn/client/* 1>/dev/null 2>> $tmp_log || 
        logit "${process}" "Failed chmod 600 openvpn client files" "WARNING"
}

ovpn_graceful_shutdown() {
    process="OpenVPN Graceful Shutdown on Reboot"
    logit "${process}" "Deploy ovpn_graceful_shutdown to reboot.target.wants"
    this_file="/etc/systemd/system/reboot.target.wants/ovpn-graceful-shutdown"
    echo -e "[Unit]\nDescription=Gracefully terminates any ovpn sessions on shutdown/reboot\nDefaultDependencies=no\nBefore=networking.service\n\n" > "${this_file}" 
    echo -e "[Service]\nType=oneshot\nExecStart=/bin/sh -c 'pkill -SIGTERM -e -F /var/run/ovpn.pid '\n\n" >> "${this_file}"
    echo -e "[Install]\nWantedBy=reboot.target halt.target poweroff.target" >> "${this_file}"
    lines=$(wc -l < "${this_file}") || lines=0
    [[ $lines == 0 ]] && 
        logit "${process}" "Failed to create ovpn_graceful_shutdown in reboot.target.wants dir" "WARNING"
    chmod +x "${this_file}" 1>/dev/null 2>> $tmp_log || logit "${process}" "Failed to chmod File" "WARNING"
    logit "${process}" "deploy ovpn_graceful_shutdown to reboot.target.wants Complete"
}

ovpn_logging() {
    process="OpenVPN and PushBullet Logging"
    logit "${process}" "Configure Logging in /var/log/ConsolePi - Other ConsolePi functions log to syslog"
    if [[ ! -d "/var/log/ConsolePi" ]]; then
        sudo mkdir /var/log/ConsolePi 1>/dev/null 2>> $tmp_log || logit "${process}" "Failed to create Log Directory"
    fi
    touch /var/log/ConsolePi/ovpn.log || logit "${process}" "Failed to create OpenVPN log file" "WARNING"
    touch /var/log/ConsolePi/push_response.log || logit "${process}" "Failed to create PushBullet log file" "WARNING"
    echo "/var/log/ConsolePi/ovpn.log" > "/etc/logrotate.d/ConsolePi"
    echo "/var/log/ConsolePi/push_response.log" >> "/etc/logrotate.d/ConsolePi"
    echo "{" >> "/etc/logrotate.d/ConsolePi"
    echo "        rotate 4" >> "/etc/logrotate.d/ConsolePi"
    echo "        weekly" >> "/etc/logrotate.d/ConsolePi"
    echo "        missingok" >> "/etc/logrotate.d/ConsolePi"
    echo "        notifempty" >> "/etc/logrotate.d/ConsolePi"
    echo "        compress" >> "/etc/logrotate.d/ConsolePi"
    echo "        delaycompress" >> "/etc/logrotate.d/ConsolePi"
    echo "}" >> "/etc/logrotate.d/ConsolePi"
    lines=$(wc -l < "/etc/logrotate.d/ConsolePi")
    [[ $lines == 10 ]] && logit "${process}" "${process} Completed Successfully" || logit "${process}" "${process} ERROR Verify '/etc/logrotate.d/ConsolePi'" "WARNING"
}

install_autohotspotn () {
    process="AutoHotSpotN"
    logit "${process}" "Install AutoHotSpotN"
    [[ -f "${src_dir}/autohotspotN" ]] && cp "${src_dir}/autohotspotN" /usr/bin 1>/dev/null 2>> $tmp_log
    [[ $? == 0 ]] && logit "${process}" "Create autohotspotN script Success" || logit "${process}" "Failed to create autohotspotN script" "WARNING"
        
    chmod +x /usr/bin/autohotspotN 1>/dev/null 2>> $tmp_log ||
        logit "${process}" "Failed to chmod autohotspotN script" "WARNING"
        
    logit "${process}" "Installing hostapd via apt."
    apt-get -y install hostapd 1>/dev/null 2>> $tmp_log &&
        logit "${process}" "hostapd install Success" ||
        logit "${process}" "hostapd install Failed" "WARNING"
    
    logit "${process}" "Installing dnsmasq via apt."
    apt-get -y install dnsmasq 1>/dev/null 2>> $tmp_log &&
        logit "${process}" "dnsmasq install Success" ||
        logit "${process}" "dnsmasq install Failed" "WARNING"
    
    logit "${process}" "disabling hostapd and dnsmasq autostart (handled by AutoHotSpotN)."
    sudo /lib/systemd/systemd-sysv-install disable hostapd 1>/dev/null 2>> $tmp_log && res=$?
    sudo /lib/systemd/systemd-sysv-install disable dnsmasq 1>/dev/null 2>> $tmp_log && ((res=$?+$res))
    [[ $res == 0 ]] && logit "${process}" "hostapd and dnsmasq autostart disabled Successfully" ||
        logit "${process}" "An error occurred disabling hostapd and/or dnsmasq autostart" "WARNING"

    logit "${process}" "Create/Configure hostapd.conf"
    [[ -f "/etc/hostapd/hostapd.conf" ]] && mv "/etc/hostapd/hostapd.conf" "${orig_dir}" && logit "${process}" "existing hostapd.conf found, backed up to originals folder"
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
    mv /tmp/hostapd.conf /etc/hostapd/hostapd.conf 1>/dev/null 2>> $tmp_log &&
        logit "${process}" "hostapd.conf Successfully configured." ||
        logit "${process}" "hostapdapd.conf Failed to create config" "WARNING"
    
    logit "${process}" "Making changes to /etc/hostapd/hostapd.conf"
    [[ -f "/etc/default/hostapd" ]] && mv "/etc/default/hostapd" "${orig_dir}" 
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
        logit "${process}" "Changes to /etc/hostapd/hostapd.conf made successfully" ||
        logit "${process}" "Error making Changes to /etc/hostapd/hostapd.conf" "WARNING"
    
    logit "${process}" "Verifying interface file."
    int_line=`cat /etc/network/interfaces |grep -v '^$\|^\s*\#'`
    if [[ ! "${int_line}" == "source-directory /etc/network/interfaces.d" ]]; then
        echo "# interfaces(5) file used by ifup(8) and ifdown(8)" >> "/tmp/interfaces"
        echo "# Please note that this file is written to be used with dhcpcd" >> "/tmp/interfaces"
        echo "# For static IP, consult /etc/dhcpcd.conf and 'man dhcpcd.conf'" >> "/tmp/interfaces"
        echo "# Include files from /etc/network/interfaces.d:" >> "/tmp/interfaces"
        echo "source-directory /etc/network/interfaces.d" >> "/tmp/interfaces"
        mv /etc/network/interfaces "${orig_dir}" 1>/dev/null 2>> $tmp_log ||
            logit "${process}" "Failed to backup original interfaces file" "WARNING"
        mv "/tmp/interfaces" "/etc/network" 1>/dev/null 2>> $tmp_log ||
            logit "${process}" "Failed to move interfaces file" "WARNING"
    fi

    logit "${process}" "Creating Startup script."
    echo "[Unit]" > "/tmp/autohotspot.service"
    echo "Description=Automatically generates an internet Hotspot when a valid ssid is not in range" >> "/tmp/autohotspot.service"
    echo "After=multi-user.target" >> "/tmp/autohotspot.service"
    echo "[Service]" >> "/tmp/autohotspot.service"
    echo "Type=oneshot" >> "/tmp/autohotspot.service"
    echo "RemainAfterExit=yes" >> "/tmp/autohotspot.service"
    echo "ExecStart=/usr/bin/autohotspotN" >> "/tmp/autohotspot.service"
    echo "[Install]" >> "/tmp/autohotspot.service"
    echo "WantedBy=multi-user.target" >> "/tmp/autohotspot.service"
    mv "/tmp/autohotspot.service" "/etc/systemd/system/" 1>/dev/null 2>> $tmp_log ||
            logit "${process}" "Failed to create autohotspot.service init" "WARNING"
    logit "${process}" "Enabling Startup script."
    systemctl enable autohotspot.service 1>/dev/null 2>> $tmp_log &&
        logit "${process}" "Successfully enabled autohotspot.service" ||
        logit "${process}" "Failed to enable autohotspot.service" "WARNING"
    
    logit "${process}" "Verify iw is installed on system."
    if [[ ! $(dpkg -l iw | tail -1 |cut -d" " -f1) == "ii" ]]; then
        logit "${process}" "iw not found, Installing iw via apt."
        apt-get -y install iw 1>/dev/null 2>> $tmp_log && logit "${process}" "iw installed Successfully" || logit "${process}" "FAILED to install iw" "WARNING"
    else
        echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] iw already on system."
    fi
    
    logit "${process}" "Enable IP-forwarding (/etc/sysctl.conf)"
    sed -i '/^#net\.ipv4\.ip_forward=1/s/^#//g' /etc/sysctl.conf
    
    logit "${process}" "${process} Complete"
}

gen_dnsmasq_conf () {
    process="Configure dnsmasq"
    logit "${process}" "Generating Files for dnsmasq."
    echo "# dnsmasq configuration created by ConsolePi installer" > /tmp/dnsmasq.conf
    echo "# modifications can be made but the 'dhcp-option-wlan0,3' line needs to exist" >> /tmp/dnsmasq.conf
    echo "# for the default-gateway on/off based on eth0 status function to work" >> /tmp/dnsmasq.conf
    common_text="interface=wlan0\nbogus-priv\ndomain-needed\ndhcp-range=${wlan_dhcp_start},${wlan_dhcp_end},255.255.255.0,12h\ndhcp-option=wlan0,3\n"
    echo -e "$common_text" >> /tmp/dnsmasq.conf
    [[ -f "/etc/dnsmasq.conf" ]] && mv "/etc/dnsmasq.conf" "${orig_dir}" && logit "${process}" "Existing dnsmasq.conf backed up to originals folder"
    mv "/tmp/dnsmasq.conf" "/etc/dnsmasq.conf" 1>/dev/null 2>> $tmp_log ||
            logit "${process}" "Failed to Deploy ConsolePi dnsmasq.conf configuration" "WARNING"
}

dhcpcd_conf () {
    process="dhcpcd.conf"
    logit "${process}" "configure dhcp client and static fallback"
    [[ -f /etc/dhcpcd.conf ]] && mv /etc/dhcpcd.conf /etc/ConsolePi/originals
    cp /etc/ConsolePi/src/dhcpcd.conf /etc/dhcpcd.conf 1>/dev/null 2>> $tmp_log
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
        echo "interface eth0" >> "/etc/dhcpcd.conf"
        echo "# fallback static_eth0" >> "/etc/dhcpcd.conf"
        echo "" >> "/etc/dhcpcd.conf"
        echo "#For AutoHotkeyN" >> "/etc/dhcpcd.conf"
        echo "nohook wpa_supplicant" >> "/etc/dhcpcd.conf"
        logit "${process}" "Process Completed Successfully"
    else
        logit "${process}" "Error Code (${res}) returned when attempting to mv dhcpcd.conf from ConsolePi src"
        logit "${process}" "Verify dhcpcd.conf and configure manually after install completes"
    fi
}

get_known_ssids() {
    process="Get Known SSIDs"
    logit "${process}" "${process} Started"
    header
    if [ -f $wpa_supplicant_file ] && [[ $(cat $wpa_supplicant_file|grep -c network=) > 0 ]] ; then
        echo
        echo "----------------------------------------------------------------------------------------------"
        echo "wpa_supplicant.conf already exists with the following configuration"
        echo "----------------------------------------------------------------------------------------------"
        cat $wpa_supplicant_file
        echo "----------------------------------------------------------------------------------------------"
        echo -e "\nConsolePi will attempt to connect to configured SSIDs prior to going into HotSpot mode.\n"
        prompt="Do You want to configure additional SSIDs (Y/N)"
        user_input false "${prompt}"
        continue=$result
    else
        continue=true
    fi
    if $continue; then
        if [ -f $consolepi_dir/installer/ssids.sh ]; then
            . $consolepi_dir/installer/ssids.sh
            known_ssid_init
            known_ssid_main
            mv "$wpa_supplicant_file" "/etc/ConsolePi/originals" 1>/dev/null 2>> $tmp_log ||
                logit "${process}" "Failed to backup existing file to originals dir" "WARNING"
            mv "$wpa_temp_file" "$wpa_supplicant_file" 1>/dev/null 2>> $tmp_log ||
                logit "${process}" "Failed to move collected ssids to wpa_supplicant.conf Verify Manually" "WARNING"
        else
            logit "${process}" "SSID collection script not found in ConsolePi install dir" "WARNING"
        fi
    fi
    logit "${process}" "${process} Complete"
}

get_serial_udev() {
    process="Predictable Console Ports"
    logit "${process}" "${process} Starting."
    header
    echo
    echo -e "--------------------------------------------- \033[1;32mPredictable Console ports$*\033[m ---------------------------------------------"
    echo "-                                                                                                                   -"
    echo "- Predictable Console ports allow you to configure ConsolePi so that each time you plug-in a specific adapter it    -"
    echo "- will always be reachable on a predictable telnet port.                                                            -"
    echo "-                                                                                                                   -"
    echo "- This is handy if you ever plan to have multiple adapters, or if you are using a multi-port pig-tail adapter.      -"
    echo "-                                                                                                                   -"
    echo "---------------------------------------------------------------------------------------------------------------------"
    echo
    echo "You need to have the serial adapters you want to map to specific telnet ports available"
    prompt="Would you like to configure predictable serial ports now (Y/N)"
    user_input true "${prompt}"
    if $result ; then
        if [ -f $consolepi_dir/installer/udev.sh ]; then
            . $consolepi_dir/installer/udev.sh
            udev_main
        else
            logit "${process}" "ERROR udev.sh not available in installer directory" "WARNING"
        fi
    fi
    logit "${process}" "${process} Complete"
}

post_install_msg() {
    echo
    echo "*********************************************** Installation Complete ***************************************************"
    echo "*                                                                                                                       *"
    echo -e "* \033[1;32mNext Steps:$*\033[m                                                                                                           *"
    echo -e "*   \033[1;32mOpenVPN:$*\033[m if you are using the Automatic VPN feature you should Configure the ConsolePi.ovpn and ovpn_credentials    *"
    echo "*     files in /etc/openvpn/client.  Refer to the example ovpn file as there are a couple of lines specific to          *"
    echo "*     ConsolePi functionality (bottom of the example file)                                                              *"
    echo "*     You chould \"sudo chmod 600 <filename>\"both of the files for added security                                        *"
    echo "*                                                                                                                       *"
    echo -e "* \033[1;32mser2net Usage:$*\033[m                                                                                                        *"
    echo "*   Serial Ports are available starting with telnet port 8001 to 8005 incrementing with each adapter plugged in.        *"
    echo "*   if you configured predictable ports for specific serial adapters those start with 7001 to 7005 - label the          *"
    echo "*   adapters appropriately.                                                                                             *"
    echo "*                                                                                                                       *"
    echo "*   The Console Server has a control port on telnet 7000 type \"help\" for a list of commands available                   *"
    echo "*                                                                                                                       *"
    echo "*   An install log can be found in ${consolepi_dir}/installer/install.log                                               *"
    echo "*                                                                                                                       *"
    echo "**ConsolePi Installation Script v${ver}*************************************************************************************"
    echo -e "\n\n"
    #Press a key to reboot
    read -s -n 1 -p "Press any key to reboot"
    sudo reboot
}

main() {
    script_iam=`whoami`
    if [ "${script_iam}" = "root" ]; then 
        updatepi
        gitConsolePi
        get_config
        ! $bypass_verify && verify
        while ! $input; do
            collect "fix"
            verify
        done
        update_config
        if [[ ! -f "{consolepi_dir}/installer/install.log}" ]]; then 
            chg_password
            set_hostname
            set_timezone
        fi
        install_ser2net
        dhcp_run_hook
        ConsolePi_cleanup
        install_ovpn
        ovpn_graceful_shutdown
        ovpn_logging
        install_autohotspotn
        gen_dnsmasq_conf
        dhcpcd_conf
        update_banner
        get_known_ssids
        get_serial_udev
        move_log
        post_install_msg
    else
      echo 'Script should be ran as root. exiting.'
    fi
}

main