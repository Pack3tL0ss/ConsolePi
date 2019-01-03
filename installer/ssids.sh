#!/usr/bin/env bash

# -- init some vars --
known_ssid_init() {
	continue=true
	# error=false
	psk_valid=false
	wpa_temp_file="/tmp/wpa_temp"
	wpa_supplicant_file="/etc/wpa_supplicant/wpa_supplicant.conf"
	header_txt="----------------->>Enter Known SSIDs - ConsolePi will attempt connect to these if available prior to switching to HotSpot mode<<-----------------\n"
	( [[ -f "/etc/ConsolePi/ConsolePi.conf" ]] && . "/etc/ConsolePi/ConsolePi.conf" && country_txt="country=${wlan_country}" ) || country_txt="#"
}

init_wpa_temp_file() {
	( [[ -f "${wpa_supplicant_file}" ]] && cat "${wpa_supplicant_file}" > "${wpa_temp_file}" && cp "${wpa_supplicant_file}" "/etc/ConsolePi/originals" ) \
	  || echo -e "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\n${country_txt}\n" > "${wpa_temp_file}"
	echo "# ssids added by ConsolePi install script (it's OK to edit manually)" >> "$wpa_temp_file"
}

known_ssid_main() {
	init_wpa_temp_file
	while $continue; do
		# -- Known ssid --
		prompt="Input SSID" && header && echo -e $header_txt
		user_input NUL "${prompt}"
		ssid=$result
		# -- Check if ssid input already defined --
		match=`cat "${wpa_supplicant_file}" |grep -c "${ssid}"`
		if [[ $match > 0 ]]; then
			temp=" ${ssid} is already defined, please edit ${wpa_supplicant_file}\n manually or remove the ssid and run ssid.sh"
			# error=true
		fi
		if [ -f "${wpa_temp_file}" ]; then
			temp_match=`cat "${wpa_temp_file}" |grep -c "${ssid}"`
			if [[ $temp_match > 0 ]]; then
				init_wpa_temp_file
				echo " ${ssid} already added during this session, over-writing all previous entries."
			fi
		fi
		echo $match $temp_match
		if [[ $match == 0 ]]; then
			# -- psk or open network --
			prompt="Input psk for ${ssid} or press enter to configure ${ssid} as an open network" && header && echo -e $header_txt
			# -- psk input loop (collect and validate)--
			while ! $psk_valid; do
				user_input open "${prompt}"
				psk="$result"
				[ $psk == "open" ] && open=true || open=false
				# -- Build ssid stanza for wpa_supplicant.conf --
				if ! $open; then
					temp=`wpa_passphrase $ssid "${psk}"`
					if [[ $temp == *"Passphrase must be"* ]]; then
						psk_valid=false
						prompt="ERROR: Passphrase must be 8..63 characters. Enter valid Passphrase for ${ssid}" && header && echo -e $header_txt
					else
						psk_valid=true
					fi
				else
					psk_valid=true
					temp=`echo -e "network={\n        ssid="${ssid}"\n        key_mgmt=NONE\n}"`
				fi
			done
			
			prompt="Priority for ${ssid}" && header && echo -e $header_txt
			echo "Set Priority for this SSID (higher priority = more likely to connect vs lower priority SSIDs if both are discovered)"
			echo "or hit enter to accept default priority."
			echo
			user_input 0 "${prompt}"
			priority=$result
			

			
			# -- append priority if not default to ssid definition --
			if [[ $priority > 0 ]]; then
				temp=`echo "$temp" | cut -d"}" -f1`
				temp+=`echo -e "\n        priority=${priority}\n}"`
			fi
		fi
		header && echo -e $header_txt
		echo "-------------------------------------------------------------->> SSID Details <<-----------------------------------------------------------------"
		echo -e "$temp"
		echo "-------------------------------------------------------------------------------------------------------------------------------------------------"
		echo
		# if $error ; then
		prompt="Enter Y to accept as entered or N to reject and re-enter"
		user_input true "${prompt}"
		# else
			# result=true
		# fi
		if $result; then
			[[ $match == 0 ]] && echo -e "$temp" >> $wpa_temp_file
			prompt="Do You have additional SSIDs to define? (Y/N)"
			user_input false "${prompt}"
			continue=$result
		else
			continue=true
			psk_valid=false
		fi
	done
}

if [[ $0 == "/etc/ConsolePi/installer/ssid.sh" ]] ; then
	known_ssid_init
	known_ssid_main
	mv "$wpa_supplicant_file" "/etc/ConsolePi/originals"
	mv "$wpa_temp_file" "$wpa_supplicant_file"
fi
# cat "${wpa_temp_file}"