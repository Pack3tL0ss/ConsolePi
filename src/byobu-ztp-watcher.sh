#!/usr/bin/env bash

check_reqs(){
    if ! ( which byobu >/dev/null && which tcpdump >/dev/null ); then
        [ -f /etc/ConsolePi/installer/common.sh ] && . /etc/ConsolePi/installer/common.sh || (
            echo "Unable to load common functions."
            echo "You need byobu and tcpdump to run the ZTP Watcher 'sudo apt install byobu tcpdump"
            exit
            )
        prompt="byobu and tcpdump are required for ZTP watcher, OK to install"
        res=$(user_input_bool)
        if $res; then
            echo "Installing byobu and tcpdump..."
            sudo apt install byobu tcpdump -y >/dev/null 2>$log_file || (
                echo "Something went wrong review $log_file for error"
                exit 1
            )
        else
            echo "exiting..." && exit 0
        fi
    fi
}

get_interfaces  # from common provies wired_iface and wlan_iface

check_reqs
# set up tmux
# tmux start-server

# create a new detached session for dnsmasq
byobu new-session -d -s consolepi-ztp -n consolepi-ztp "consolepi-logs -f"

# Select pane 1, consolepi-logs -f
# byobu selectp -t 1
# Split pane 2 vertiacally by 25%
byobu splitw -v -p 75

# select pane 2, tcpdump
# byobu selectp -t 2
byobu send-keys "sudo tcpdump -vnes0 -i $wired_iface port 67 or port 68 or tftp" C-m

# Select pane 1
byobu selectp -t 0

byobu attach-session -t consolepi-ztp
