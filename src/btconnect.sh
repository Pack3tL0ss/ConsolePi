#!/usr/bin/env bash

[ -f /etc/ConsolePi/installer/common.sh ] && source /etc/ConsolePi/installer/common.sh || (
    echo "Error: Failed to import common functions" ; exit 1
)

_help() {
    local pad=$(printf "%0.1s" " "{1..40})
    printf " %s%*.*s%s.\n" "$1" 0 $((40-${#1})) "$pad" "$2"
}

show_usage() {
    ## !! common is not imported here can't use common funcs
    _green='\e[32;1m' # bold green
    _cyan='\e[96m'
    _norm='\e[0m'
    echo -e "\n${_green}USAGE:${_norm} consolepi-btconnect [OPTIONS] [DEVICE]\n"
    echo -e "${_cyan}Available Options${_norm}"
    _help "-h|--help" "Display this help text"
    _help "-l|--list" "List all discovered bluetooth devices.  Do not connect"
    echo -e "\nProvide the bt device to connect to or ${_cyan}--list${_norm} to list all discovered devices"
    echo -e "${_cyan}consolepi-btconnect <BT dev name or MAC>${_norm} -or- ${_cyan}consolepi-btconnect --list${_norm}"
    echo
}

process_args() {
    list_all=false
    while (( "$#" )); do
        # echo "$1" # -- DEBUG --
        case "$1" in
            -l|-*list|list)
                list_all=true
                shift
                ;;
            -h|-*help)
                show_usage $2
                exit 0
                ;;
            -*|--*) # unsupported flags
                echo "Error: Unsupported flag passed to process_args $1" >&2
                exit 1
                ;;
            *)
                device_in=$1
                shift
                ;;
        esac
    done
}

get_bt_mac(){
    # check if user provided BT MAC or a name
    [ $(echo ${device_in} | tr -cd : | wc -c) -eq 5 ] && local is_mac=true || local is_mac=false

    # If the provided name look up the MAC in the bluetoothctl device list
    if ! $is_mac; then
        device=$(echo devices | sudo bluetoothctl | grep -i "^Device.*${device_in}$" | awk '{printf $2}')
    else
        device="$device_in"
    fi

    [ -n "$device" ] && return 0 || return 1
}

connect(){
    # Connect to device and launch picocom
    sudo sdptool add --channel=1 SP
    echo -e ${_cyan}initiating connection...${_norm}
    sudo -b rfcomm connect /dev/rfcomm0 ${device} >/tmp/btclient 2>&1 ;

    printf "waiting for connection" # && sleep 5
    out=$(cat /tmp/btclient)

    i=0;while [ -z "$out" ]; do
        ((i+=1))
        sleep 1
        out=$(cat /tmp/btclient)
        printf '.'
        [ $i -ge 20 ] && echo -e "\ntimeout" && break
    done
    echo

    if [[ ! "$out" =~ "t connect" ]]; then
        su $iam -c "picocom /dev/rfcomm0 -b 115200 2>/dev/null"
    else
        echo $out
    fi

    rm -f /tmp/btclient
}

main(){
    process_args "$@"
    if $list_all; then
        echo devices | sudo bluetoothctl | grep Device --color=never
    elif [ -n "$device_in" ]; then
        if get_bt_mac; then
            echo "Connecting to BT device @ $device"
            connect
        else
            echo -e "$device_in not found\n"
            echo "Found Devices:"
            echo devices | sudo bluetoothctl | grep Device --color=never
            exit 1
        fi
    else
        show_usage
        exit 1
    fi
}

# __main__
main "$@"