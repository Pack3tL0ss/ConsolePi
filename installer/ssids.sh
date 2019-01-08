#!/usr/bin/env bash

# -- init some vars --
known_ssid_init() {
    continue=true
    bypass_prompt=false
    psk_valid=false
    wpa_temp_file="/tmp/wpa_temp"
    wpa_supplicant_file="/etc/wpa_supplicant/wpa_supplicant.conf"
    header_txt="----------------->>Enter Known SSIDs - ConsolePi will attempt connect to these if available prior to switching to HotSpot mode<<-----------------\n"
    ( [[ -f "/etc/ConsolePi/ConsolePi.conf" ]] && . "/etc/ConsolePi/ConsolePi.conf" && country_txt="country=${wlan_country}" ) 
}

# defining header and user-input again here so the script can be ran directly until I re-factor so this is less lame
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

init_wpa_temp_file() {
    ( [[ -f "${wpa_supplicant_file}" ]] && cat "${wpa_supplicant_file}" > "${wpa_temp_file}" && cp "${wpa_supplicant_file}" "/etc/ConsolePi/originals" ) \
      || echo -e "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\n${country_txt}\n" > "${wpa_temp_file}"
	# Set wifi country
    [[ ! -z ${country_txt} ]] && wpa_cli -i wlan0 set country "${country_txt}" 1>/dev/null
}

known_ssid_main() {
    init_wpa_temp_file
    while $continue; do
        # -- Known ssid --
        prompt="Input SSID" && header && echo -e $header_txt
        user_input NUL "${prompt}"
        ssid=$result
        # -- Check if ssid input already defined --
        if [ -f "${wpa_temp_file}" ]; then
            temp_match=`cat "${wpa_temp_file}" |grep -c "${ssid}"`
            if [[ $temp_match > 0 ]]; then
                init_wpa_temp_file
                temp=" ${ssid} already added during this session, over-writing all previous entries. Start over\n Don't screw up this time!"
                bypass_prompt=true
            fi
        fi
        match=`cat "${wpa_supplicant_file}" |grep -c "${ssid}"`
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
        if $bypass_prompt ; then
            echo "Press any key to continue" && read
            accept=true		# prompt to see if they want to continue adding - yields $continue
            bypass_prompt=false  # reset bypass_prompt
			psk_valid=false      # reset psk_valid
        else
            prompt="Enter Y to accept as entered or N to reject and re-enter"
            user_input true "${prompt}"
			accept=$result
        fi
        if $accept; then
            [[ $match == 0 ]] && echo -e "$temp" >> $wpa_temp_file
            prompt="Do You have additional SSIDs to define? (Y/N)"
            user_input false "${prompt}"
            continue=$result
        else
            continue=true
            psk_valid=false
            match=0
        fi
    done
}

#echo $0
if [[ ! $0 == *"ConsolePi" ]] && [[ $0 == *"installer/ssids.sh"* ]] ; then
    known_ssid_init
    known_ssid_main
    mv "$wpa_supplicant_file" "/etc/ConsolePi/originals"
    mv "$wpa_temp_file" "$wpa_supplicant_file"
fi
