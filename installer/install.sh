#!/usr/bin/env bash

# ------------------------------------------------------------------------------------------------------------------------------------------------- #
# --                                                 ConsolePi Installation Script Stage 1                                                       -- #
# --  Wade Wells - Mar, 2019                                                                                                                     -- #
# --    report any issues/bugs on github or fork-fix and submit a PR                                                                             -- #
# --                                                                                                                                             -- #
# --  This script aims to automate the installation of ConsolePi.                                                                                -- #
# --  For manual setup instructions and more detail visit https://github.com/Pack3tL0ss/ConsolePi                                                -- #
# --                                                                                                                                             -- #
# --------------------------------------------------------------------------------------------------------------------------------------------------#

branch="Clustering"

get_common() {
    wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/${branch}/installer/common.sh -O /tmp/common.sh
        . /tmp/common.sh
    [ -f /tmp/common.sh ] && rm /tmp/common.sh
    header 1>/dev/null
    [[ $? -gt 0 ]] && echo "FATAL ERROR: Unable to import common.sh Exiting" && exit 1
}

remove_first_boot() {
    #IF first boot was enabled by image creator script - remove it
    sudo sed -i "s#consolepi-install##g" /home/pi/.bashrc
    count=$(grep -c consolepi-install /home/pi/.bashrc)
    [[ $count > 0 ]] && logit "Remove exec on first-boot" "Failed to remove first-boot verify /etc/rc.local" "WARNING"
}

do_apt_update () {
    header
    process="Update/Upgrade ConsolePi (apt)"
    logit "Update Sources"
    # Only update if initial install (no install.log) or if last update was not today
    if [[ ! -f "${consolepi_dir}installer/install.log" ]] || [[ ! $(ls -l --full-time /var/cache/apt/pkgcache.bin | cut -d' ' -f6) == $(echo $(date +"%Y-%m-%d")) ]]; then
        sudo apt-get update 1>/dev/null 2>> $log_file && logit "Update Successful" || logit "FAILED to Update" "ERROR"
    else
        logit "Skipping Source Update - Already Updated today"
    fi
    
    logit "Upgrading ConsolePi via apt. This may take a while"
    sudo apt-get -y upgrade 1>/dev/null 2>> $log_file && logit "Upgrade Successful" || logit "FAILED to Upgrade" "ERROR"
    
    logit "Performing dist-upgrade"
    sudo apt-get -y dist-upgrade 1>/dev/null 2>> $log_file && logit "dist-upgrade Successful" || logit "FAILED dist-upgrade" "WARNING"

    logit "Tidying up (autoremove)"
    apt-get -y autoremove 1>/dev/null 2>> $log_file && logit "Everything is tidy now" || logit "apt-get autoremove FAILED" "WARNING"
        
    logit "Installing git via apt"
    apt-get -y install git 1>/dev/null 2>> $log_file && logit "git install Successful" || logit "git install FAILED to install" "ERROR"
    logit "Process Complete"
}

# Process Changes that are required prior to git pull when doing upgrade
pre_git_prep() {
    if $upgrade; then
        process="ConsolePi-Upgrade-Prep (refactor bluemenu.sh)"
        if [[ -f /etc/ConsolePi/src/bluemenu.sh ]]; then 
            rm /etc/ConsolePi/src/bluemenu.sh &&
                logit "Removed old menu script will be replaced during pull" ||
                    logit "ERROR Found old menu script but unable to remove (/etc/ConsolePi/src/bluemenu.sh)" "WARNING"
            # Remove old symlink if it exists
            if [[ -L /usr/local/bin/consolepi-menu ]]; then
                unlink /usr/local/bin/consolepi-menu &&
                    logit "Removed old consolepi-menu symlink will replace during upgade" ||
                        logit "ERROR Unable to remove old consolepi-menu symlink verify it should link to file in src dir" "WARNING"
            fi
        fi
    fi
}

gitConsolePi () {
    process="git Clone/Update ConsolePi"
    cd "/etc"
    if [ ! -d $consolepi_dir ]; then 
        logit "Clean Install git clone ConsolePi"
        git clone "${consolepi_source}" 1>/dev/null 2>> $log_file && logit "ConsolePi clone Success" || logit "Failed to Clone ConsolePi" "ERROR"
    else
        cd $consolepi_dir
        logit "Directory exists Updating ConsolePi via git"
        git fetch "${consolepi_source}" 1>/dev/null 2>> $log_file && 
            logit "ConsolePi fetch Success" || logit "Failed to fetch ConsolePi from github" "WARNING"
        git pull "${consolepi_source}" 1>/dev/null 2>> $log_file && 
            logit "ConsolePi update/pull Success" || logit "Failed to update/pull ConsolePi" "WARNING"
    fi
    [[ ! -d $orig_dir ]] && sudo mkdir $orig_dir
}

# Configure ConsolePi logging directory and logrotate
do_logging() {
    process="Configure Logging"
    logit "Configure Logging in /var/log/ConsolePi - Other ConsolePi functions log to syslog"
    
    # Create /var/log/ConsolePi dir if it doesn't exist
    if [[ ! -d "/var/log/ConsolePi" ]]; then
        sudo mkdir /var/log/ConsolePi 1>/dev/null 2>> $log_file || logit "Failed to create Log Directory"
    fi

    # move installer log from temp to it's final location
    if ! $upgrade; then
        cat $tmp_log >> $log_file
        rm $tmp_log
        log_file=$final_log
    else
        [ -f $tmp_log ] && echo "ERROR: tmp log found when it should not have existed" | tee -a $final_log
    fi

    # Create Log Files
    touch /var/log/ConsolePi/ovpn.log || logit "Failed to create OpenVPN log file" "WARNING"
    touch /var/log/ConsolePi/push_response.log || logit "Failed to create PushBullet log file" "WARNING"
    
    # Create logrotate file for logs
    echo "/var/log/ConsolePi/ovpn.log" > "/etc/logrotate.d/ConsolePi"
    echo "/var/log/ConsolePi/push_response.log" >> "/etc/logrotate.d/ConsolePi"
    echo "/var/log/ConsolePi/install.log" >> "/etc/logrotate.d/ConsolePi"
    $cloud && echo "/var/log/ConsolePi/cloud.log" >> "/etc/logrotate.d/ConsolePi"    
    echo "{" >> "/etc/logrotate.d/ConsolePi"
    echo "        rotate 4" >> "/etc/logrotate.d/ConsolePi"
    echo "        weekly" >> "/etc/logrotate.d/ConsolePi"
    echo "        missingok" >> "/etc/logrotate.d/ConsolePi"
    echo "        notifempty" >> "/etc/logrotate.d/ConsolePi"
    echo "        compress" >> "/etc/logrotate.d/ConsolePi"
    echo "        delaycompress" >> "/etc/logrotate.d/ConsolePi"
    echo "}" >> "/etc/logrotate.d/ConsolePi"
    
    # Verify logrotate file was created correctly
    lines=$(wc -l < "/etc/logrotate.d/ConsolePi")
    ( $cloud && [[ $lines == 12 ]] ) || ( ! $cloud && [[ $lines == 11 ]] ) && 
        logit "${process} Completed Successfully" || 
        logit "${process} ERROR Verify '/etc/logrotate.d/ConsolePi'" "WARNING"
}

get_install2() {
    if [ -f "${consolepi_dir}installer/install2.sh" ]; then
        . "${consolepi_dir}installer/install2.sh"
    else
        echo "FATAL ERROR install2.sh not found exiting"
        exit 1
    fi
}

main() {
    script_iam=`whoami`
    if [ "${script_iam}" = "root" ]; then
        get_common              # get and import common functions script
        remove_first_boot       # if autolaunch install is configured remove
        do_apt_update           # apt-get update the pi
        pre_git_prep            # process upgrade tasks required prior to git pull
        gitConsolePi            # git ConsolePi
        do_logging              # Configure logging and rotation
        get_install2            # get and import install2 functions
        install2_main           # Kick off install2 functions
    else
      echo 'Script should be ran as root. exiting.'
    fi
}

main