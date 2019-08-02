#!/usr/bin/env bash

# -- init some vars --
known_ssid_init() {
    continue=true
    bypass_prompt=false
    psk_valid=false
    wpa_temp_file="/tmp/wpa_temp"
    wpa_supplicant_file="/etc/wpa_supplicant/wpa_supplicant.conf"
    header_txt="----------------->>Enter Known SSIDs - ConsolePi will attempt connect to these if available prior to switching to HotSpot mode<<-----------------\n"
    ( [[ -f "/etc/ConsolePi/ConsolePi.conf" ]] && . "/etc/ConsolePi/ConsolePi.conf" && country_txt="country=${wlan_country,,}" ) 
}

init_wpa_temp_file() {
    ( [[ -f "${wpa_supplicant_file}" ]] && cat "${wpa_supplicant_file}" > "${wpa_temp_file}" && cp "${wpa_supplicant_file}" "${bak_dir}" ) ||
        echo -e "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\n${country_txt}\n" > "${wpa_temp_file}"
    # Set wifi country
    # [[ ! -z ${country_txt} ]] && wpa_cli -i wlan0 set country "${country_txt}" 1>/dev/null
    # Make Sure Wifi country is set in wpa_temp_file which will eventually be wpa_supplicant.conf
    if [[ ! -z ${country_txt} ]] && [[ ! $(sudo grep "country=" "${wpa_temp_file}") ]]; then
        line=$(sudo grep -n "network" "${wpa_temp_file}" | head -1 | cut -d: -f1)
        [[ -z $line ]] && echo "${country_txt}" >> "$wpa_temp_file" || sed -i "${line}s/^/${country_txt}\n/" "$wpa_temp_file"
    fi
}

known_ssid_main() {
    init_wpa_temp_file
    while $continue; do
        # -- Known ssid --
        prompt="Input SSID" && header && echo -e $header_txt
        default=
        user_input NUL "${prompt}"
        ssid=$result
        # -- Check if ssid input already defined --
        if [ -f "${wpa_temp_file}" ]; then
            temp_match=`cat "${wpa_temp_file}" | grep "ssid=" | grep -c "${ssid}"`
            if [[ $temp_match > 0 ]]; then
                init_wpa_temp_file
                temp=" ${ssid} already added during this session, over-writing all previous entries. Start over\n Don't screw up this time!"
                bypass_prompt=true
            fi
        fi
        match=`cat "${wpa_supplicant_file}" | grep "ssid=" | grep -c "${ssid}"`
        if [[ $match > 0 ]]; then
            temp=" ${ssid} is already defined, please edit ${wpa_supplicant_file}\n manually or remove the ssid and run ssid.sh"
            bypass_prompt=true
        fi
        ((match=$match+$temp_match))
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
                        temp=$(echo -e "$temp" | sed -e 's/\t/    /g')
                        psk_valid=true
                    fi
                else
                    # -- open network --
                    psk_valid=true
                    temp=`echo -e "network={\n    ssid=\"${ssid}\"\n    key_mgmt=NONE\n}"`
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
                temp+=`echo -e "\n    priority=${priority}\n}"`
            fi
        fi
        header && echo -e $header_txt
        echo "-------------------------------------------------------------->> SSID Details <<-----------------------------------------------------------------"
        echo -e "$temp"
        echo "-------------------------------------------------------------------------------------------------------------------------------------------------"
        echo
        if $bypass_prompt ; then
            echo "Press any key to continue" && read
            accept=true        # prompt to see if they want to continue adding - yields $continue
            bypass_prompt=false  # reset bypass_prompt
            psk_valid=false      # reset psk_valid
        else
            prompt="Enter Y to accept as entered or N to reject and re-enter"
            user_input true "${prompt}"
            accept=$result
        fi

        if $accept; then
            [[ $match == 0 ]] && echo -e "$temp" >> $wpa_temp_file
            prompt="Do You have additional SSIDs to define"
            user_input false "${prompt}"
            continue=$result
            psk_valid=false      # reset psk_valid
        else
            continue=true
            psk_valid=false
            match=0
        fi
    done
}

#__main__
if [[ ! $0 == *"ConsolePi" ]] && [[ $0 == *"src/consolepi-addssids.sh"* ]] ; then
    [ -f /etc/ConsolePi/installer/common.sh ] && . /etc/ConsolePi/installer/common.sh
    known_ssid_init
    header
    if [ -f $wpa_supplicant_file ] && [[ $(cat $wpa_supplicant_file|grep -c network=) > 0 ]] ; then
        echo
        echo "----------------------------------------------------------------------------------------------"
        echo "wpa_supplicant.conf already exists with the following configuration"
        echo "----------------------------------------------------------------------------------------------"
        cat $wpa_supplicant_file
        echo "----------------------------------------------------------------------------------------------"
        echo -e "\nConsolePi will attempt to connect to configured SSIDs prior to going into HotSpot mode.\n"
        prompt="Do You want to configure additional SSIDs"
        user_input true "${prompt}"
        continue=$result
    else
        continue=true
    fi
    if $continue; then
        known_ssid_main
        mv "$wpa_supplicant_file" "${bak_dir}"
        mv "$wpa_temp_file" "$wpa_supplicant_file"
    fi
fi
