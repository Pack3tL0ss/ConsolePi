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
mydir=`pwd`
touch /tmp/install.log
logline="----------------------------------------------------------------------------------------------------------------"

# -- External Sources --
ser2net_source="https://sourceforge.net/projects/ser2net/files/latest/download"
consolepi_source="https://github.com/Pack3tL0ss/ConsolePi.git"


# -- Build Config File and Directory Structure - Read defaults from config
get_config() {
    bypass_verify=false
    if [[ ! -f "${default_config}" ]] && [[ ! -f "/home/pi/ConsolePi.conf" ]]; then
        # This indicates it's the first time the script has ran
        # [ ! -d "$consolepi_dir" ] && mkdir /etc/ConsolePi
        echo "push=true                            # PushBullet Notifications: true - enable, false - disable" > "${default_config}"
        echo "push_all=true                            # PushBullet send notifications to all devices: true - yes, false - send only to device with iden specified by push_iden" >> "${default_config}"
        echo "push_api_key=\"PutYourPBAPIKeyHereChangeMe:\"            # PushBullet API key" >> "${default_config}"
        echo "push_iden=\"putyourPBidenHere\"                    # iden of device to send PushBullet notification to if not push_all" >> "${default_config}"
        echo "ovpn_enable=true                        # if enabled will establish VPN connection" >> "${default_config}"
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
            bypass_verify=true		# bypass verify function
			input=false				# so collect function will run (while loop in main)
        else
            header
            echo "Please edit config in ${default_config} using editor (i.e. nano) and re-run install script"
            echo "i.e. \"sudo nano ${default_config}\""
            echo
            exit 0
        fi
    fi
	[[ ! -f "${default_config}" ]] && [[ -f "/home/pi/ConsolePi.conf" ]] && sudo cp "/home/pi/ConsolePi.conf" "$default_config"
	. "$default_config" && 
	    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Configuration loaded from pi home dir" | tee -a /tmp/install.log
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
    # if ! $first_run; then
        echo "Enter Y to Continue N to make changes"
        echo
        printf "Are Values Correct? (Y/N): "
        read input
        ([ ${input,,} == 'y' ] || [ ${input,,} == 'yes' ]) && input=true || input=false
    # else
        # first_run=false
        # echo "Press Any Key to Edit Defaults"
        # read
        # input=fase
    # fi
}

set_hostname() {
	header
	valid_response=false
	hostn=$(cat /etc/hostname)

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
		
		echo "$(date +"%b %d %T") ConsolePi Installer[INFO] New hostname set $newhost" | tee -a /tmp/install.log
	fi
}

set_timezone() {
	header
	valid_response=false
	cur_tz=$(date +"%Z")

	while ! $valid_response; do
		read -p "Current TimeZone $cur_tz. Do you want to configure the timezone (y/n)?: " response
		response=${response,,}    # tolower
		( [[ "$response" =~ ^(yes|y)$ ]] || [[ "$response" =~ ^(no|n)$ ]] ) && valid_response=true || valid_response=false
	done
	if [[ "$response" =~ ^(yes|y)$ ]]; then
		sudo dpkg-reconfigure tzdata 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] TimeZone Successfully Changed ($(date +"%Z"))" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to Change TimeZone" |& tee -a /tmp/install.log && exit 1) 
	fi
}

updatepi () {
	header
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Updating Raspberry Pi via apt" | tee -a /tmp/install.log
    sudo apt-get update 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Update Completed Successfully" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to Update" |& tee -a /tmp/install.log && exit 1) 
    [[ $? > 0 ]] && exit $?
	
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Upgrading Raspberry Pi via apt. This may take a while" | tee -a /tmp/install.log
    sudo apt-get -y upgrade 1>/dev/null 2>> /tmp/install.log &&  
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Upgrade Completed Successfully" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to Upgrade" |& tee -a /tmp/install.log && exit 1)
    [[ $? > 0 ]] && exit $?
	
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Performing dist-upgrade" | tee -a /tmp/install.log
    sudo apt-get -y dist-upgrade 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] dist-upgrade Completed Successfully" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] dist-upgrade Failed" |& tee -a /tmp/install.log && exit 1 )
    [[ $? > 0 ]] && exit $?

    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Tidying up (autoremove)" | tee -a /tmp/install.log
    apt-get -y autoremove 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Tidying up (autoremove) Complete" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[WARNING] apt-get autoremove failed" |& tee -a /tmp/install.log && exit 1)
        # [[ $? > 0 ]] && echo $logline >> /tmp/install.log 
		
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Installing git via apt" | tee -a /tmp/install.log
    apt-get -y install git 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] git Install Complete" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] git Install failed" |& tee -a /tmp/install.log && exit 1)
    [[ $? > 0 ]] && exit $?
}

gitConsolePi () {
    cd "/etc"
    if [ ! -d $consolepi_dir ]; then 
	    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Clean Install git clone ConsolePi" | tee -a /tmp/install.log
        git clone "${consolepi_source}" 1>/dev/null 2>> /tmp/install.log &&
            (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] ConsolePi clone Successful" | tee -a /tmp/install.log ) ||
            (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] ConsolePi clone failed" |& tee -a /tmp/install.log && exit 1 )
        [[ $? > 0 ]] && exit $?
    else
        cd $consolepi_dir
		echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Directory exists Updating ConsolePi via git" | tee -a /tmp/install.log
        git pull "${consolepi_source}" | tee -a /tmp/install.log
    fi
    echo "$(date +"%b %d %T") [INFO] Clone/Update ConsolePi Package - Complete" | tee -a /tmp/install.log
}

install_ser2net () {
	# To Do add check to see if already installed / update
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Installing ser2net from source" | tee -a /tmp/install.log
    cd /usr/local/bin

    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Retrieve and extract package" | tee -a /tmp/install.log
    wget -q "${ser2net_source}" -O ./ser2net.tar.gz 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] ser2net retrieved" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to download ser2net from source" |& tee -a /tmp/install.log && exit 1 )
    [[ $? > 0 ]] && exit $?

    tar -zxvf ser2net.tar.gz 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] ser2net extracted" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to extract ser2net from source" |& tee -a /tmp/install.log && exit 1 )
    [[ $? > 0 ]] && exit $?
	rm -f /usr/local/bin/ser2net.tar.gz || (echo "$(date +"%b %d %T") ConsolePi Installer[WARNING] Failed to remove tar.gz" | tee -a /tmp/install.log)
    cd ser2net*/

	echo "$(date +"%b %d %T") ConsolePi Installer[INFO] ./configure ser2net" | tee -a /tmp/install.log
    ./configure 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] ser2net ./configure Success" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] ser2net ./configure Failed" |& tee -a /tmp/install.log && exit 1 )
    [[ $? > 0 ]] && exit $?

    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] ser2net make, make install, make clean" | tee -a /tmp/install.log    
    make 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] ser2net make Success" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] ser2net make Failed" |& tee -a /tmp/install.log && exit 1 )
    [[ $? > 0 ]] && exit $?

    make install 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] ser2net make install Success" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] ser2net make install Failed" |& tee -a /tmp/install.log && exit 1 )
    [[ $? > 0 ]] && exit $?

    make clean 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] ser2net make clean Success" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[WARNING] ser2net make clean Failed" |& tee -a /tmp/install.log && exit 1 )
    # [[ $? > 0 ]] && exit $?
	
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Building init & ConsolePi Config for ser2net" | tee -a /tmp/install.log
    cp /etc/ConsolePi/src/ser2net.conf /etc/ || 
	    (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] ser2net Failed to copy config file from ConsolePi src" |& tee -a /tmp/install.log && exit 1 )
    [[ $? > 0 ]] && exit $?
    cp /etc/ConsolePi/src/ser2net.init /etc/init.d/ser2net || 
	    (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] ser2net Failed to copy init file from ConsolePi src" |& tee -a /tmp/install.log && exit 1 )
    [[ $? > 0 ]] && exit $?
    chmod +x /etc/init.d/ser2net || 
	    (echo "$(date +"%b %d %T") ConsolePi Installer[WARNING] ser2net Failed to make init executable" |& tee -a /tmp/install.log && exit 1 )
    # [[ $? > 0 ]] && exit $?
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] ser2net Enable init" | tee -a /tmp/install.log
    /lib/systemd/systemd-sysv-install enable ser2net 1>/dev/null 2>> /tmp/install.log && 
		(echo "$(date +"%b %d %T") ConsolePi Installer[INFO] ser2net init file enabled" | tee -a /tmp/install.log )
	    (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] ser2net failed to enable init file (start on boot)" |& tee -a /tmp/install.log && exit 1 )
		
    systemctl daemon-reload || 
	    (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] systemctl failed to reload daemons" |& tee -a /tmp/install.log && exit 1 )
		
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] ser2net installation complete" | tee -a /tmp/install.log  
}

dhcp_run_hook() {
	# ToDo add error checking
	# this_error=0
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Install ConsolePi (point dhcp.exit-hook to ConsolePi script)" | tee -a /tmp/install.log  
    [[ -f /etc/dhcpcd.exit-hook ]] && exists=true || exists=false
    if $exists; then
        is_there=`cat /etc/dhcpcd.exit-hook |grep -c /etc/ConsolePi/ConsolePi.sh`
        lines=$(wc -l < "/etc/dhcpcd.exit-hook")
        if [[ $is_there > 0 ]] && [[ $lines > 1 ]]; then
            [[ ! -d "/etc/ConsolePi/originals" ]] && mkdir /etc/ConsolePi/originals
            mv /etc/dhcpcd.exit-hook /etc/ConsolePi/originals/dhcpcd.exit-hook
            echo "/etc/ConsolePi/ConsolePi.sh \"\$@\"" > "/etc/dhcpcd.exit-hook" 
        elif [[ $is_there == 0 ]]; then
            echo "/etc/ConsolePi/ConsolePi.sh \"\$@\"" >> "/etc/dhcpcd.exit-hook"
        else
            echo "No Change Necessary ${is_there} ${lines} exit-hook already configured."
        fi
    else
        echo "/etc/ConsolePi/ConsolePi.sh \"\$@\"" > "/etc/dhcpcd.exit-hook"
    fi
    chmod +x /etc/dhcpcd.exit-hook
	chmod +x /etc/ConsolePi/ConsolePi.sh	# Once I get git to retain +x should not need this
	echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Install ConsolePi script Success" | tee -a /tmp/install.log 
}

ConsolePi_cleanup() {
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] copy and enable ConsolePi_cleanup init script" | tee -a /tmp/install.log 
    cp "/etc/ConsolePi/src/ConsolePi_cleanup" "/etc/init.d" 1>/dev/null 2>> /tmp/install.log || 
	    (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Error Copying ConsolePi_cleanup init script." |& tee -a /tmp/install.log && exit 1 )
    chmod +x /etc/init.d/ConsolePi_cleanup 1>/dev/null 2>> /tmp/install.log || 
	    (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to make ConsolePi_cleanup init script executable." |& tee -a /tmp/install.log && exit 1 )
    sudo systemctl start ConsolePi_cleanup 1>/dev/null 2>> /tmp/install.log || 
	    (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to enable ConsolePi_cleanup init script." |& tee -a /tmp/install.log && exit 1 )
		
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] copy and enable ConsolePi_cleanup init script - Complete" | tee -a /tmp/install.log 
}

install_ovpn() {
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Install OpenVPN" | tee -a /tmp/install.log
    if [[ ! $(dpkg -s openvpn | grep Status | cut -d' ' -f4) == "installed" ]]; then
        sudo apt-get -y install openvpn 1>/dev/null 2>> /tmp/install.log &&
            (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] OpenVPN install Success" | tee -a /tmp/install.log ) ||
            (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] OpenVPN install Failed" |& tee -a /tmp/install.log && exit 1 )
		if ! $ovpn_enable; then
			"    OpenVPN is installed, in case it's wanted later"
			"    The init script is being disabled as you are currently"
			"    choosing not to use it"
			/lib/systemd/systemd-sysv-install disable openvpn
		else
			/lib/systemd/systemd-sysv-install enable openvpn
		fi
	else
	    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] OpenVPN Already present" | tee -a /tmp/install.log
	fi
    [[ ! -f "/etc/openvpn/client/ConsolePi.ovpn.example" ]] && cp "${src_dir}/ConsolePi.ovpn.example" "/etc/openvpn/client" ||
	    (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Retaining existing ConsolePi.ovpn.example file. See src dir for original example file." | tee -a /tmp/install.log )
    [[ ! -f "/etc/openvpn/client/ConsolePi.ovpn.example" ]] && cp "${src_dir}/ovpn_credentials" "/etc/openvpn/client" ||
	    (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Retaining existing ovpn_credentials file. See src dir for original example file." | tee -a /tmp/install.log )
	sudo chmod 600 /etc/openvpn/client/* 1>/dev/null 2>> /tmp/install.log || 
	    (echo "$(date +"%b %d %T") ConsolePi Installer[WARNING] Failed chmod 600 openvpn client files" |& tee -a /tmp/install.log && exit 1 )
}

ovpn_graceful_shutdown() {
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] deploy ovpn_graceful_shutdown to reboot.target.wants" | tee -a /tmp/install.log
    this_file="/etc/systemd/system/reboot.target.wants/ovpn-graceful-shutdown"
    echo -e "[Unit]\nDescription=Gracefully terminates any ovpn sessions on shutdown/reboot\nDefaultDependencies=no\nBefore=networking.service\n\n" > "${this_file}"
    echo -e "[Service]\nType=oneshot\nExecStart=/bin/sh -c 'pkill -SIGTERM -e -F /var/run/ovpn.pid '\n\n" >> "${this_file}"
    echo -e "[Install]\nWantedBy=reboot.target halt.target poweroff.target" >> "${this_file}"
	lines=$(wc -l < "${this_file}") || lines=0
	[[ $lines == 0 ]] && 
	    echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Error deploying ovpn_graceful_shutdown to reboot.target.wants" | tee -a /tmp/install.log
    chmod +x "${this_file}" 1>/dev/null 2>> /tmp/install.log || 
	    (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to chmod File" |& tee -a /tmp/install.log && exit 1 )
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] deploy ovpn_graceful_shutdown to reboot.target.wants Complete" | tee -a /tmp/install.log
}

ovpn_logging() {
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Configure openvpn and PushBullet Logging in /var/log/ConsolePi" | tee -a /tmp/install.log
	echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Other ConsolePi functions log to syslog" | tee -a /tmp/install.log
    if [[ ! -d "/var/log/ConsolePi" ]]; then
        sudo mkdir /var/log/ConsolePi 1>/dev/null 2>> /tmp/install.log || 
	        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to create Log Directory" |& tee -a /tmp/install.log && exit 1 )
	fi
    touch /var/log/ConsolePi/ovpn.log
    touch /var/log/ConsolePi/push_response.log
    echo "/var/log/ConsolePi/ovpn.log" > "/etc/logrotate.d/ConsolePi" 1>/dev/null 2>> /tmp/install.log || 
	    (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to create/write into new logrotate file" |& tee -a /tmp/install.log && exit 1 )
    echo "/var/log/ConsolePi/push_response.log" >> "/etc/logrotate.d/ConsolePi"
    echo "{" >> "/etc/logrotate.d/ConsolePi"
    echo "        rotate 4" >> "/etc/logrotate.d/ConsolePi"
    echo "        weekly" >> "/etc/logrotate.d/ConsolePi"
    echo "        missingok" >> "/etc/logrotate.d/ConsolePi"
    echo "        notifempty" >> "/etc/logrotate.d/ConsolePi"
    echo "        compress" >> "/etc/logrotate.d/ConsolePi"
    echo "        delaycompress" >> "/etc/logrotate.d/ConsolePi"
    echo "}" >> "/etc/logrotate.d/ConsolePi"
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Configure openvpn and PushBullet Logging in /var/log/ConsolePi -- Done" | tee -a /tmp/install.log
}

install_autohotspotn () {
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Install AutoHotSpotN" | tee -a /tmp/install.log
    [[ -f "${src_dir}/autohotspotN" ]] && mv "${src_dir}/autohotspotN" /usr/bin 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] create autohotspotN script Success" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to create autohotspotN script" |& tee -a /tmp/install.log && exit 1 )
		
    chmod +x /usr/bin/autohotspotN 1>/dev/null 2>> /tmp/install.log ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to chmod autohotspotN script" |& tee -a /tmp/install.log && exit 1 )
		
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Installing hostapd via apt." | tee -a /tmp/install.log
    apt-get -y install hostapd 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] hostapd install Success" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] hostapd install Failed" |& tee -a /tmp/install.log && exit 1 )
    # [[ $? > 0 ]] && exit $?
	
    
    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Installing dnsmasq via apt." | tee -a /tmp/install.log
    apt-get -y install dnsmasq 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] dnsmasq install Success" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] dnsmasq install Failed" |& tee -a /tmp/install.log && exit 1 )
    
	echo "$(date +"%b %d %T") ConsolePi Installer[INFO] disabling hostapd and dnsmasq autostart (handled by AutoHotSpotN)." | tee -a /tmp/install.log
    sudo /lib/systemd/systemd-sysv-install disable hostapd 1>/dev/null 2>> /tmp/install.log && res=$?
    sudo /lib/systemd/systemd-sysv-install disable dnsmasq 1>/dev/null 2>> /tmp/install.log && ((res=$?+$res))
	[[ $res == 0 ]] && (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] hostapd and dnsmasq autostart disabled Successfully" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] An error occured disabling hostapd and/or dnsmasq autostart" |& tee -a /tmp/install.log && exit 1 )

    echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Create/Configure hostapd.conf" | tee -a /tmp/install.log
    [[ -f "/etc/hostapd/hostapd.conf" ]] && mv "/etc/hostapd/hostapd.conf" "${orig_dir}"
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
    mv /tmp/hostapd.conf /etc/hostapd/hostapd.conf 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] hostapd.conf Successfully configured." | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] hostapdapd.conf Failed to create config" |& tee -a /tmp/install.log && exit 1 )
    
    echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] Making changes to /etc/hostapd/hostapd.conf" | tee -a /tmp/install.log
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
        echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] Changes to /etc/hostapd/hostapd.conf made successfully" || \
        echo "$(date +"%b %d %T") [10.]autohotspotN [ERROR] Error making Changes to /etc/hostapd/hostapd.conf"
    
    echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] Verifying interface file." | tee -a /tmp/install.log
    int_line=`cat /etc/network/interfaces |grep -v '^$\|^\s*\#'`
    if [[ ! "${int_line}" == "source-directory /etc/network/interfaces.d" ]]; then
        echo "# interfaces(5) file used by ifup(8) and ifdown(8)" >> "/tmp/interfaces"
        echo "# Please note that this file is written to be used with dhcpcd" >> "/tmp/interfaces"
        echo "# For static IP, consult /etc/dhcpcd.conf and 'man dhcpcd.conf'" >> "/tmp/interfaces"
        echo "# Include files from /etc/network/interfaces.d:" >> "/tmp/interfaces"
        echo "source-directory /etc/network/interfaces.d" >> "/tmp/interfaces"
        mv /etc/network/interfaces "${orig_dir}"
        cp "/tmp/interfaces" "/etc/network"
    fi

    echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] Creating Startup script." | tee -a /tmp/install.log
    echo "[Unit]" > "/tmp/autohotspot.service"
    echo "Description=Automatically generates an internet Hotspot when a valid ssid is not in range" >> "/tmp/autohotspot.service"
    echo "After=multi-user.target" >> "/tmp/autohotspot.service"
    echo "[Service]" >> "/tmp/autohotspot.service"
    echo "Type=oneshot" >> "/tmp/autohotspot.service"
    echo "RemainAfterExit=yes" >> "/tmp/autohotspot.service"
    echo "ExecStart=/usr/bin/autohotspotN" >> "/tmp/autohotspot.service"
    echo "[Install]" >> "/tmp/autohotspot.service"
    echo "WantedBy=multi-user.target" >> "/tmp/autohotspot.service"
    mv "/tmp/autohotspot.service" "/etc/systemd/system/" 
    echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] Enabling Startup script."
    systemctl enable autohotspot.service 1>/dev/null 2>> /tmp/install.log &&
        (echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Successfully enabled autohotspot.service" | tee -a /tmp/install.log ) ||
        (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to enable autohotspot.service" |& tee -a /tmp/install.log && exit 1 )
    
    echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] Verify iw is installed on system."
    if [[ ! $(dpkg -s iw | grep Status | cut -d' ' -f4) == "installed" ]]; then
        echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] iw not found, Installing iw via apt."
        apt-get install iw
    else
        echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] iw already on system."
    fi
    
    echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] Enable IP-forwarding (/etc/sysctl.conf)"
    sed -i '/^#net\.ipv4\.ip_forward=1/s/^#//g' /etc/sysctl.conf
}

gen_dnsmasq_conf () {
    printf "\n12)--Generating Files for dnsmasq."
    echo "# No Default Gateway provided with DHCP (consolePi Does this when no link on eth0)" > /etc/ConsolePi/dnsmasq.conf.noGW && printf "."
    echo "# Default Gateway *is* provided with DHCP (consolePi Does this when eth0 is up)" > /etc/ConsolePi/dnsmasq.conf.withGW && printf "."
    common_text="interface=wlan0\nbogus-priv\ndomain-needed\ndhcp-range=${wlan_dhcp_start},${wlan_dhcp_end},255.255.255.0,12h"
    echo -e "$common_text" >> /etc/ConsolePi/dnsmasq.conf.noGW && printf "."
    echo -e "$common_text" >> /etc/ConsolePi/dnsmasq.conf.withGW && printf "."
    echo "dhcp-option=wlan0,3" >> /etc/ConsolePi/dnsmasq.conf.noGW && printf "Done\n"
    [[ -f "/etc/dnsmasq.conf" ]] && mv "/etc/dnsmasq.conf" "${orig_dir}"
    cp "${consolepi_dir}/dnsmasq.conf.noGW" "/etc/dnsmasq.conf"
}

dhcpcd_conf () {
        printf "\n13)----------- configure dhcp client and static fallback --------------\n"
        [[ -f /etc/dhcpcd.conf ]] && mv /etc/dhcpcd.conf /etc/ConsolePi/originals
        mv /etc/ConsolePi/src/dhcpcd.conf /etc/dhcpcd.conf
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
            echo "$(date +"%b %d %T") [13.]dhcp client and static fallback - dhcpcd.conf [INFO] Process Completed Successfully"
        else
            echo "$(date +"%b %d %T") [13.]dhcp client and static fallback - dhcpcd.conf [ERROR] Error Code (${res}}) returned when attempting to mv dhcpcd.conf from ConsolePi src"
            echo "$(date +"%b %d %T") [13.]dhcp client and static fallback - dhcpcd.conf [ERROR] To Remediate Please verify dhcpcd.conf and configure manually after install completes"
        fi
}

get_known_ssids() {
    echo "$(date +"%b %d %T") [14.]Collect Known SSIDs [INFO] Process Started" | tee -a /tmp/install.log
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
            mv "$wpa_supplicant_file" "/etc/ConsolePi/originals" 1>/dev/null 2>> /tmp/install.log ||
	            (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to backup existing file to originals dir" |& tee -a /tmp/install.log && exit 1 )
            mv "$wpa_temp_file" "$wpa_supplicant_file" 1>/dev/null 2>> /tmp/install.log ||
	            (echo "$(date +"%b %d %T") ConsolePi Installer[ERROR] Failed to move collected ssids to wpa_supplicant.conf Verify Manually" |& tee -a /tmp/install.log && exit 1 )
        else
            echo "$(date +"%b %d %T") [14.]Collect Known SSIDs [ERROR] ssid collection script not found in ConsolePi install dir" |& tee -a /tmp/install.log
        fi
    fi
}

get_serial_udev() {
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
            echo "ERROR udev.sh not available in installer directory"
        fi
    fi
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
	iam=`whoami`
	if [ "${iam}" = "root" ]; then 
		updatepi
		gitConsolePi
		get_config
		! $bypass_verify && verify
		while ! $input; do
			collect "fix"
			verify
		done
		set_hostname
		set_timezone
		update_config
		install_ser2net
		dhcp_run_hook
		ConsolePi_cleanup
		install_ovpn
		ovpn_graceful_shutdown
		ovpn_logging
		install_autohotspotn
		gen_dnsmasq_conf
		dhcpcd_conf
		get_known_ssids
		get_serial_udev
		post_install_msg
		# cd "${mydir}"
		[[ -f /etc/ConsolePi/installer/install.log ]] && sudo mv /etc/ConsolePi/installer/install.log /etc/ConsolePi/installer/install.log.bak
		mv /tmp/install.log /etc/ConsolePi/installer/install.log
	else
	  echo 'Script should be ran as root. exiting.'
	fi
}

main