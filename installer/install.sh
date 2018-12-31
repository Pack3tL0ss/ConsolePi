#!/usr/bin/env bash

# ------------------------------------------------------------------------------------------------------------------------------------------------- #
# --                                                 ConsolePi Installation Script                                                               -- #
# --  Wade Wells - Dec, 2018  v1.0                                                                                                               -- #
# --    eMail Wade with any bugs or suggestions, if you don't know Wade's eMail, then don't eMail Wade :)                                        -- #
# --                                                                                                                                             -- #
# --  This script aims to automate the installation of ConsolePi.  For manual setup instructions and more detail seee <github link>              -- #
# --                                                                                                                                             -- #
# --  This was a mistake... should have done this in Python, Never doing anything beyond simple in bash, but I was a couple 100 lines in when    -- #
# --  I had that epiphany so bash it is.																									     -- #
# --------------------------------------------------------------------------------------------------------------------------------------------------#

# -- Installation Defaults --
consolepi_dir="/etc/ConsolePi"

# -- Build Config File and Directory Structure - Read defaults from config
get_defaults() {
	if [ ! -f "${consolepi_dir}/"config ]; then
		# This indicates it's the first time the script has ran
		[ ! -d "$consolepi_dir" ] && mkdir /etc/ConsolePi
		echo "push=true							# PushBullet Notifications: true - enable, false - disable" > ${consolepi_dir}/config
		echo "push_all=true							# PushBullet send notifications to all devices: true - yes, false - send only to device with iden specified by push_iden" >> ${consolepi_dir}/config
		echo "push_api_key=\"PutYourPBAPIKeyHereChangeMe:\"			# PushBullet API key" >> ${consolepi_dir}/config
		echo "push_iden=\"putyourPBidenHere\"					# iden of device to send PushBullet notification to if not push_all" >> ${consolepi_dir}/config
		echo "ovpn_enable=true						# if enabled will establish VPN connection" >> ${consolepi_dir}/config
		echo "push_all=true							# true - push to all devices, false - push only to push_iden" >> ${consolepi_dir}/config
		echo "vpn_check_ip=\"10.0.150.1\"					# used to check VPN (internal) connectivity should be ip only reachable via VPN" >> ${consolepi_dir}/config
		echo "net_check_ip=\"8.8.8.8\"						# used to check internet connectivity" >> ${consolepi_dir}/config
		echo "local_domain=\"arubalab.net\"					# used to bypass VPN. evals domain sent via dhcp option if matches this var will not establish vpn" >> ${consolepi_dir}/config
		echo "wlan_ip=\"10.3.0.1\"						# IP of consolePi when in hotspot mode" >> ${consolepi_dir}/config
		echo "wlan_ssid=\"ConsolePi\"						# SSID used in hotspot mode" >> ${consolepi_dir}/config
		echo "wlan_psk=\"ChangeMe!!\"						# psk used for hotspot SSID" >> ${consolepi_dir}/config
		header
		echo "Configuration File Created with default values. Enter Y to continue in Interactive Mode"
		echo "which will prompt you for each value. Enter N to exit the script, so you can modify the"
		echo "defaults directly then re-run the script."
		echo
		prompt="Continue in Interactive mode? (Y/N)"
		user_input true "${prompt}"
		continue=$result
		if ! $continue; then 
			echo "Please edit config in ${consolepi_dir}/config using editor (i.e. nano) and re-run script"
			echo "i.e. \"sudo nano ${consolepi_dir}/config\""
			exit 0
		else
			first_run=true
		fi
	fi
	. "$consolepi_dir"/config
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
	$first_run && header_txt=">>DEFAULT VALUES CHANGE THESE<<" || header_txt="--->>PLEASE VERIFY VALUES<<----"
	echo "-----------------------------------------${header_txt}----------------------------------------"
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
	echo "----------------------------------------------------------------------------------------------------------------"
	echo
	if ! $first_run; then
		echo "Enter Y to Continue N to make changes"
		echo
		printf "Are Values Correct? (Y/N): "
		read input
		([ ${input,,} == 'y' ] || [ ${input,,} == 'yes' ]) && input=true || input=false
	else
		first_run=false
		echo "Press Any Key to Edit Defaults"
		read
		input=fase
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
else
  echo 'Script should be ran as root. exiting.'
fi

}

main