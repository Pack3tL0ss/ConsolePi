#!/usr/bin/env bash

# ------------------------------------------------------------------------------------------------------------------------------------------------- #
# --                                                 ConsolePi Installation Script                                                               -- #
# --  Wade Wells - Dec, 2018  v1.0                                                                                                               -- #
# --    eMail Wade with any bugs or suggestions, if you don't know Wade's eMail, then don't eMail Wade :)                                        -- #
# --                                                                                                                                             -- #
# --  This script aims to automate the installation of ConsolePi.  For manual setup instructions and more detail seee <github link>              -- #
# --                                                                                                                                             -- #
# --  This was a mistake... should have done this in Python, Never do anything beyond simple in bash, but I was a couple 100 lines in when       -- #
# --  I had that epiphany so bash it is... for now  																						     -- #
# --------------------------------------------------------------------------------------------------------------------------------------------------#

# -- Installation Defaults --
consolepi_dir="/etc/ConsolePi"
default_config="/etc/default/ConsolePi.conf"
ser2net_source="https://sourceforge.net/projects/ser2net/files/latest/download"
consolepi_source="https://github.com/Pack3tL0ss/ConsolePi.git"
mydir=`pwd`

# -- Build Config File and Directory Structure - Read defaults from config
get_defaults() {
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
			echo "Please edit config in ${default_config} using editor (i.e. nano) and re-run script"
			echo "i.e. \"sudo nano ${default_config}\""
			echo
			exit 0
		fi
	fi
	. "$default_config"
	hotspot_dhcp_range
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
	echo "Starting Install"
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
	echo "3)------ fetching ConsolePi Package --------"
	cd "/etc"
	git clone "${consolepi_source}"
	echo "--Complete"
}

install_ser2net () {
	echo
	echo "4)------- installing ser2net from source -------"
	cd /usr/local/bin
	echo
	echo "4A)----------retrieving source package----------"
	wget "${ser2net_source}" -O ./ser2net.tar.gz
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

gen_dnsmasq_conf () {
	printf "\n5)--Generating Files for dnsmasq."
	echo "# No Default Gateway provided with DHCP (consolePi Does this when no link on eth0)" > /etc/ConsolePi/dnsmasq.conf.noGW && printf "."
	echo "# Default Gateway *is* provided with DHCP (consolePi Does this when eth0 is up)" > /etc/ConsolePi/dnsmasq.conf.withGW && printf "."
	common_text="interface=wlan0\nbogus-priv\ndomain-needed\ndhcp-range=${wlan_dhcp_start},${wlan_dhcp_end},255.255.255.0,12h"
	echo -e "$common_text" >> /etc/ConsolePi/dnsmasq.conf.noGW && printf "."
	echo -e "$common_text" >> /etc/ConsolePi/dnsmasq.conf.withGW && printf "."
	echo "dhcp-option=wlan0,3" >> /etc/ConsolePi/dnsmasq.conf.noGW && printf "Done\n"
}

dhcp_run_hook() {
	printf "\n6)---- update/create dhcp.exit-hook ----------\n"
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
	cp /etc/ConsolePi/src/ConsolePi.ovpn.example /etc/openvpn/client
	cp /etc/ConsolePi/src/ovpn_credentials /etc/openvpn/client
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

dhcpcd_conf () {
        printf "\n9)----------- configure dhcp client and static fallback --------------\n"
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
			else
			echo "$(date) [9.]dhcp client and static fallback - dhcpcd.conf [ERROR] Error Code (${res}}) returned when attempting to mv dhcpcd.conf from ConsolePi src"
			echo "$(date) [9.]dhcp client and static fallback - dhcpcd.conf [ERROR] To Remediate Please verify dhcpcd.conf and configure manually after install completes"
        fi
}

main() {
iam=`whoami`
if [ "${iam}" = "root" ]; then 
	get_defaults
	verify
	while ! $input; do
		collect "fix"
		verify
	done
	updatepi
	gitConsolePi
	install_ser2net
	gen_dnsmasq_conf
	dhcp_run_hook
	ConsolePi_cleanup
	install_ovpn
	ovpn_graceful_shutdown
	ovpn_logging
	cd "${mydir}"
else
  echo 'Script should be ran as root. exiting.'
fi

}

main