#!/usr/bin/env bash

# ------------------------------------------------------------------------------------------------------------------------------------------------- #
# --                                                 ConsolePi Installation Script                                                               -- #
# --  Wade Wells - Dec, 2018  v1.0                                                                                                               -- #
# --    eMail Wade with any bugs or suggestions, if you don't know Wade's eMail, then don't eMail Wade :)                                        -- #
# --                                                                                                                                             -- #
# --  This script aims to automate the installation of ConsolePi.																				 -- #
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
mydir=`pwd`

# -- External Sources --
ser2net_source="https://sourceforge.net/projects/ser2net/files/latest/download"
consolepi_source="https://github.com/Pack3tL0ss/ConsolePi.git"


# -- Build Config File and Directory Structure - Read defaults from config
get_config() {
	if [ ! -f "${default_config}" ]; then
		# This indicates it's the first time the script has ran
		# [ ! -d "$consolepi_dir" ] && mkdir /etc/ConsolePi
		echo "push=true							# PushBullet Notifications: true - enable, false - disable" > "${default_config}"
		echo "push_all=true							# PushBullet send notifications to all devices: true - yes, false - send only to device with iden specified by push_iden" >> "${default_config}"
		echo "push_api_key=\"PutYourPBAPIKeyHereChangeMe:\"			# PushBullet API key" >> "${default_config}"
		echo "push_iden=\"putyourPBidenHere\"					# iden of device to send PushBullet notification to if not push_all" >> "${default_config}"
		echo "ovpn_enable=true						# if enabled will establish VPN connection" >> "${default_config}"
		echo "push_all=true							# true - push to all devices, false - push only to push_iden" >> "${default_config}"
		echo "vpn_check_ip=\"10.0.150.1\"					# used to check VPN (internal) connectivity should be ip only reachable via VPN" >> "${default_config}"
		echo "net_check_ip=\"8.8.8.8\"						# used to check internet connectivity" >> "${default_config}"
		echo "local_domain=\"arubalab.net\"					# used to bypass VPN. evals domain sent via dhcp option if matches this var will not establish vpn" >> "${default_config}"
		echo "wlan_ip=\"10.3.0.1\"						# IP of consolePi when in hotspot mode" >> "${default_config}"
		echo "wlan_ssid=\"ConsolePi\"						# SSID used in hotspot mode" >> "${default_config}"
		echo "wlan_psk=\"ChangeMe!!\"						# psk used for hotspot SSID" >> "${default_config}"
		echo "wlan_country=\"US\"						# regulatory domain for hotspot SSID" >> "${default_config}"
		header
		echo "Configuration File Created with default values. Enter Y to continue in Interactive Mode"
		echo "which will prompt you for each value. Enter N to exit the script, so you can modify the"
		echo "defaults directly then re-run the script."
		echo
		prompt="Continue in Interactive mode? (Y/N)"
		user_input true "${prompt}"
		continue=$result
		if ! $continue; then 
			header
			echo "Please edit config in ${default_config} using editor (i.e. nano) and re-run install script"
			echo "i.e. \"sudo nano ${default_config}\""
			echo
			exit 0
		fi
	fi
	. "$default_config"
	hotspot_dhcp_range
}

update_config() {
	echo "push=${push}							# PushBullet Notifications: true - enable, false - disable" > "${default_config}"
	echo "push_all=${push_all}							# PushBullet send notifications to all devices: true - yes, false - send only to device with iden specified by push_iden" >> "${default_config}"
	echo "push_api_key=\"${push_api_key}\"			# PushBullet API key" >> "${default_config}"
	echo "push_iden=\"${push_iden}\"					# iden of device to send PushBullet notification to if not push_all" >> "${default_config}"
	echo "ovpn_enable=${ovpn_enable}						# if enabled will establish VPN connection" >> "${default_config}"
	echo "vpn_check_ip=\"${vpn_check_ip}\"					# used to check VPN (internal) connectivity should be ip only reachable via VPN" >> "${default_config}"
	echo "net_check_ip=\"${net_check_ip}\"						# used to check internet connectivity" >> "${default_config}"
	echo "local_domain=\"${local_domain}\"					# used to bypass VPN. evals domain sent via dhcp option if matches this var will not establish vpn" >> "${default_config}"
	echo "wlan_ip=\"${wlan_ip}\"						# IP of consolePi when in hotspot mode" >> "${default_config}"
	echo "wlan_ssid=\"${wlan_ssid}\"						# SSID used in hotspot mode" >> "${default_config}"
	echo "wlan_psk=\"${wlan_psk}\"						# psk used for hotspot SSID" >> "${default_config}"
	echo "wlan_country=\"${wlan_country}\"						# regulatory domain for hotspot SSID" >> "${default_config}"
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
		echo "What is your local lab domain?"
		echo "This Domain should be provided by your lab DHCP server"
		echo "It is used to determine if you are connected locally (No VPN will be established)"
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
	echo " Send Notifications via PushBullet?:				$push"
	if $push; then
		echo " PushBullet API Key:                 				${push_api_key}"
		echo " Send Push Notification to all devices?:             		$push_all"
		! $push_all && echo " iden of device to receive PushBullet Notifications: 		$push_iden"
	fi

	echo " Enable Automatic VPN?:                              		$ovpn_enable"
	if $ovpn_enable; then
		echo " IP used to verify VPN is connected:                 		$vpn_check_ip"
		echo " IP used to verify Internet connectivity:            		$net_check_ip"
		echo " Local Lab Domain:                                   		$local_domain"
	fi

	echo " ConsolePi Hot Spot IP:						$wlan_ip"
	echo "  *hotspot DHCP Range:						${wlan_dhcp_start} to ${wlan_dhcp_end}"
	echo " ConsolePi Hot Spot SSID:			            	$wlan_ssid"
	echo " ConsolePi Hot Spot psk:			            	$wlan_psk"
	echo " ConsolePi Hot Spot regulatory domain:	        		$wlan_country"
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

updatepi () {
	header
	echo "$(date +"%b %d %T") ConsolePi Installer[INFO] Starting Updating Raspberry Pi and getting source files"
	echo "1)---- updating RaspberryPi (aptitude) -----"
	apt-get update && apt-get -y upgrade
	echo
	sudo apt-get -y dist-upgrade
	sudo apt-get -y autoremove
	echo
	echo "2)---------- installing git ----------------"
	sudo apt-get -y install git
	echo "Raspberry Pi Update Complete"
}

gitConsolePi () {
	echo
	echo "$(date +"%b %d %T") [INFO] Clone/Update ConsolePi Package"
	cd "/etc"
	if [ ! -d $consolepi_dir ]; then 
		git clone "${consolepi_source}"
	else
		cd $consolepi_dir
		git pull "${consolepi_source}"
	fi
	echo "$(date +"%b %d %T") [INFO] Clone/Update ConsolePi Package - Complete"
}

install_ser2net () {
	echo
	echo "4)------- installing ser2net from source -------"
	cd /usr/local/bin
	echo
	echo "4A)----------retrieving source package----------"
	wget -q "${ser2net_source}" -O ./ser2net.tar.gz
	echo "wget finished return value ${?}"
	echo
	echo "4B)----------extracting source package----------"
	tar -zxf ser2net.tar.gz
	echo "--extraction Complete"
	echo
	echo "4C)---------------- ./configure ----------------"
	cd ser2net*/
	./configure
	echo "configure finished return value ${?}"
	echo
	echo "4D)------------------- make --------------------"	
	echo "make finished return value ${?}"
	echo
	echo "4E)--------------- make install ----------------"
	make install
	echo "make install finished return value ${?}"
	echo
	echo "4F)--------------- make clean ------------------"
	make clean
	echo "ser2net installation now complete. "
	rm -f /usr/local/bin/ser2net.tar.gz
	echo
	echo "4G)---Generating Configuration and init file----"
	cp /etc/ConsolePi/src/ser2net.conf /etc/
	cp /etc/ConsolePi/src/ser2net.init /etc/init.d/ser2net
	chmod +x /etc/init.d/ser2net
	echo
	echo "4H)--------- enable ser2net init --------------"
	/lib/systemd/systemd-sysv-install enable ser2net
	systemctl daemon-reload
	echo "ser2net install complete with default ConsolePi Configuration"
}

dhcp_run_hook() {
	printf "\n5)---- update/create dhcp.exit-hook ----------\n"
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
	chmod +x /etc/ConsolePi/ConsolePi.sh
}

ConsolePi_cleanup() {
	printf "\n6)---- enable Cleanup init script ----------\n"
	cp "/etc/ConsolePi/src/ConsolePi_cleanup" "/etc/init.d"
	chmod +x /etc/init.d/ConsolePi_cleanup
	/lib/systemd/systemd-sysv-install enable ConsolePi_cleanup
	echo "--Done"
}

install_ovpn() {
	printf "\n7)----------- install openvpn --------------\n"
	sudo apt-get -y install openvpn
	if ! $ovpn_enable; then
		"    OpenVPN is installed, in case it's wanted later"
		"    The init script is being disabled as you are currently"
		"    choosing not to use it"
		/lib/systemd/systemd-sysv-install disable openvpn
	else
		/lib/systemd/systemd-sysv-install enable openvpn
	fi
	cp "${src_dir}/ConsolePi.ovpn.example" "/etc/openvpn/client"
	cp "${src_dir}/ovpn_credentials" "/etc/openvpn/client"
}

ovpn_graceful_shutdown() {
	printf "\n8)---- ovpn graceful shutdown on reboot -----\n"
	this_file="/etc/systemd/system/reboot.target.wants/ovpn-graceful-shutdown"
	echo "[Unit]" > "${this_file}"
	echo "Description=Gracefully terminates any ovpn sessions on shutdown/reboot" >> "${this_file}"
	echo "DefaultDependencies=no" >> "${this_file}"
	echo "Before=networking.service" >> "${this_file}"
	echo "" >> "${this_file}"
	echo "[Service]" >> "${this_file}"
	echo "Type=oneshot" >> "${this_file}"
	echo "ExecStart=/bin/sh -c 'pkill -SIGTERM -e -F /var/run/ovpn.pid '" >> "${this_file}"
	echo "" >> "${this_file}"
	echo "[Install]" >> "${this_file}"
	echo "WantedBy=reboot.target halt.target poweroff.target" >> "${this_file}"
	chmod +x "${this_file}"
	echo "--Done"
}

ovpn_logging() {
	printf "\n9)----------- openvpn logging --------------\n"
	[[ ! -d "/var/log/ConsolePi" ]] && mkdir /var/log/ConsolePi
	touch /var/log/ConsolePi/ovpn.log
	touch /var/log/ConsolePi/push_response.log
	echo "/var/log/ConsolePi/ovpn.log" > "/etc/logrotate.d/ConsolePi"
	echo "/var/log/ConsolePi/push_response.log" >> "/etc/logrotate.d/ConsolePi"
	echo "{" >> "/etc/logrotate.d/ConsolePi"
	echo "		rotate 4" >> "/etc/logrotate.d/ConsolePi"
	echo "		weekly" >> "/etc/logrotate.d/ConsolePi"
	echo "		missingok" >> "/etc/logrotate.d/ConsolePi"
	echo "		notifempty" >> "/etc/logrotate.d/ConsolePi"
	echo "		compress" >> "/etc/logrotate.d/ConsolePi"
	echo "		delaycompress" >> "/etc/logrotate.d/ConsolePi"
	echo "}" >> "/etc/logrotate.d/ConsolePi"
	echo "--Done"
}

install_autohotspotn () {
	printf "\n10)----------- Install AutoHotSpotN --------------\n"
	[[ -f "${src_dir}/autohotspotN" ]] && mv "${src_dir}/autohotspotN" /usr/bin
	chmod +x /usr/bin/autohotspotN
	echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] Installing hostapd via apt."
	apt-get -y install hostapd && res=$?
	[[ $res == 0 ]] && echo "$(date +"%b %d %T") [10.]autohotspotN - hostapd [INFO] Install Complete with no error." || "$(date +"%b %d %T") [10.]autohotspotN - hostapd [ERROR] Installation Error."
	echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] Installing dnsmasq via apt."
	apt-get -y install dnsmasq && res=$?
	[[ $res == 0 ]] && echo "$(date +"%b %d %T") [10.]autohotspotN - dnsmasq [INFO] Install Complete with no error." || "$(date +"%b %d %T") [10.]autohotspotN - dnsmasq [ERROR] Installation Error."
	systemctl disable hostapd
	systemctl disable dnsmasq

	echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] Configuring hostapd.conf"
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
	mv /tmp/hostapd.conf /etc/hostapd/hostapd.conf
	
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
	mv /tmp/hostapd /etc/default
	
	echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] Verifying interface file."
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

	echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] Creating Startup script."
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
	systemctl enable autohotspot.service
	
	echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] Verify iw is installed on system."
	if [[ ! $(dpkg -s iw | grep Status | cut -d' ' -f4) == "installed" ]]; then
		echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] iw not found, Installing iw via apt."
		apt-get install iw
	else
		echo "$(date +"%b %d %T") [10.]autohotspotN [INFO] iw already on system."
	fi
	
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
	mv "${consolepi_dir}/dnsmasq.conf.withGW" "/etc/dnsmasq.conf"
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
	echo "$(date +"%b %d %T") [14.]Collect Known SSIDs [INFO] Process Started"
	if [ -f $wpa_supplicant_file ] && [[ $(cat $wpa_supplicant_file|grep -c network=) > 0 ]] ; then
		echo "wpa_supplicant.conf already exists with the following configuration"
		cat $wpa_supplicant_file
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
			mv "$wpa_supplicant_file" "/etc/ConsolePi/originals"
			mv "$wpa_temp_file" "$wpa_supplicant_file"
		else
			echo "$(date +"%b %d %T") [14.]Collect Known SSIDs [ERROR] ssid collection script not found in ConsolePi install dir"
		fi
	fi
}

get_serial_udev() {
	echo
	echo "-------------- Predictable Console Ports -------------------"
	echo " Predictable Console ports allow you to configure ConsolePi "
	echo " So that each time you plug-in a specific adapter it will   "
	echo " always be reachable on a predictable port.                 "
	echo " This is handy if you ever plan to have multiple adapters   "
	echo " in use.                                                    "
	echo "------------------------------------------------------------"
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

main() {
iam=`whoami`
if [ "${iam}" = "root" ]; then 
	updatepi
	gitConsolePi
	get_config
	verify
	while ! $input; do
		collect "fix"
		verify
	done
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
	cd "${mydir}"
else
  echo 'Script should be ran as root. exiting.'
fi

}

main