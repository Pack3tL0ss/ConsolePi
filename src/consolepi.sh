#!\usr\bin\env bash
#
# - ConsolePi profile script
#   Displays header and help text
#   Updates path to include convenience commands directory

if [ -f /etc/ConsolePi/installer/common.sh ]; then
    . /etc/ConsolePi/installer/common.sh
    header x
    echo
    echo -e "Use ${_green}consolepi-menu${_norm} to launch menu"
    echo -e "or ${_green}consolepi-help${_norm} for a list of other commands (extracted from README)"
    echo
fi

export PATH="$PATH:/etc/ConsolePi/src/consolepi-commands"