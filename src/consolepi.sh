#!\usr\bin\env bash
#
# - ConsolePi profile script
#   Displays header and help text
#   Updates path to include convenience commands directory

tty_cols=$(stty -a 2>/dev/null| grep -o "columns [0-9]*" | awk '{print $2}')

# Terminal coloring
_norm='\e[0m'
_bold='\033[1;32m'
_blink='\e[5m'
_red='\e[31m'
_blue='\e[34m'
_lred='\e[91m'
_yellow='\e[33;1m'
_green='\e[32m'
_cyan='\e[96m' # technically light cyan

# header reqs 144 cols to display properly
header() {
    [ -z $1 ] && clear # pass anything as an argument to prevent screen clear
    if [ ! -z $tty_cols ] && [ $tty_cols -gt 144 ] && [ -z "$BYOBU_TTY" ]; then
        echo "                                                                                                                                                ";
        echo "                                                                                                                                                ";
        echo -e "${_cyan}        CCCCCCCCCCCCC                                                                     lllllll                   ${_lred}PPPPPPPPPPPPPPPPP     iiii  ";
        echo -e "${_cyan}     CCC::::::::::::C                                                                     l:::::l                   ${_lred}P::::::::::::::::P   i::::i ";
        echo -e "${_cyan}   CC:::::::::::::::C                                                                     l:::::l                   ${_lred}P::::::PPPPPP:::::P   iiii  ";
        echo -e "${_cyan}  C:::::CCCCCCCC::::C                                                                     l:::::l                   ${_lred}PP:::::P     P:::::P        ";
        echo -e "${_cyan} C:::::C       CCCCCC   ooooooooooo   nnnn  nnnnnnnn        ssssssssss      ooooooooooo    l::::l     eeeeeeeeeeee    ${_lred}P::::P     P:::::Piiiiiii ";
        echo -e "${_cyan}C:::::C               oo:::::::::::oo n:::nn::::::::nn    ss::::::::::s   oo:::::::::::oo  l::::l   ee::::::::::::ee  ${_lred}P::::P     P:::::Pi:::::i ";
        echo -e "${_cyan}C:::::C              o:::::::::::::::on::::::::::::::nn ss:::::::::::::s o:::::::::::::::o l::::l  e::::::eeeee:::::ee${_lred}P::::PPPPPP:::::P  i::::i ";
        echo -e "${_cyan}C:::::C              o:::::ooooo:::::onn:::::::::::::::ns::::::ssss:::::so:::::ooooo:::::o l::::l e::::::e     e:::::e${_lred}P:::::::::::::PP   i::::i ";
        echo -e "${_cyan}C:::::C              o::::o     o::::o  n:::::nnnn:::::n s:::::s  ssssss o::::o     o::::o l::::l e:::::::eeeee::::::e${_lred}P::::PPPPPPPPP     i::::i ";
        echo -e "${_cyan}C:::::C              o::::o     o::::o  n::::n    n::::n   s::::::s      o::::o     o::::o l::::l e:::::::::::::::::e ${_lred}P::::P             i::::i ";
        echo -e "${_cyan}C:::::C              o::::o     o::::o  n::::n    n::::n      s::::::s   o::::o     o::::o l::::l e::::::eeeeeeeeeee  ${_lred}P::::P             i::::i ";
        echo -e "${_cyan} C:::::C       CCCCCCo::::o     o::::o  n::::n    n::::nssssss   s:::::s o::::o     o::::o l::::l e:::::::e           ${_lred}P::::P             i::::i ";
        echo -e "${_cyan}  C:::::CCCCCCCC::::Co:::::ooooo:::::o  n::::n    n::::ns:::::ssss::::::so:::::ooooo:::::ol::::::le::::::::e        ${_lred}PP::::::PP          i::::::i";
        echo -e "${_cyan}   CC:::::::::::::::Co:::::::::::::::o  n::::n    n::::ns::::::::::::::s o:::::::::::::::ol::::::l e::::::::eeeeeeee${_lred}P::::::::P          i::::::i";
        echo -e "${_cyan}     CCC::::::::::::C oo:::::::::::oo   n::::n    n::::n s:::::::::::ss   oo:::::::::::oo l::::::l  ee:::::::::::::e${_lred}P::::::::P          i::::::i";
        echo -e "${_cyan}        CCCCCCCCCCCCC   ooooooooooo     nnnnnn    nnnnnn  sssssssssss       ooooooooooo   llllllll    eeeeeeeeeeeeee${_lred}PPPPPPPPPP          iiiiiiii";
        echo -e "${_blue}                                                     https://github.com/Pack3tL0ss/ConsolePi${_norm}";
        echo "                                                                                                                                                ";
    else
        echo -e "${_cyan}   ______                       __    ${_lred} ____  _ "
        echo -e "${_cyan}  / ____/___  ____  _________  / /__  ${_lred}/ __ \(_)"
        echo -e "${_cyan} / /   / __ \/ __ \/ ___/ __ \/ / _ \\\\${_lred}/ /_/ / / "
        echo -e "${_cyan}/ /___/ /_/ / / / (__  ) /_/ / /  __${_lred}/ ____/ /  "
        echo -e "${_cyan}\____/\____/_/ /_/____/\____/_/\___${_lred}/_/   /_/   "
        echo -e "${_blue}  https://github.com/Pack3tL0ss/ConsolePi${_norm}"
        echo -e ""
    fi
}

header x
echo
echo -e "Use ${_green}consolepi-menu${_norm} to launch menu"
echo -e "or ${_green}consolepi-help${_norm} for a list of other commands (extracted from README)"
echo

[[ "$PATH" =~ "consolepi-commands" ]] || export PATH="$PATH:/etc/ConsolePi/src/consolepi-commands"
