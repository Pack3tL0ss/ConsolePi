#!/usr/bin/env bash

# ------------------------------------------------------------------------------------------------------------------------------------------------- #
# --                                                 ConsolePi Installation Script Stage 1                                                       -- #
# --  Wade Wells (Pack3tL0ss)                                                                                                                    -- #
# --    report any issues/bugs on github or fork-fix and submit a PR                                                                             -- #
# --                                                                                                                                             -- #
# --  This script aims to automate the installation of ConsolePi.                                                                                -- #
# --  For more detail visit https://github.com/Pack3tL0ss/ConsolePi                                                                              -- #
# --                                                                                                                                             -- #
# --  This is the main installer file it imports and calls the other 2 files after prepping /etc/ConsolePi                                       -- #
# --    All files source common functions from common.sh pulled directly for git repo                                                            -- #
# --    Sequence: install.sh (prep, common imports) --> config.sh (get configuration/user input) --> update.sh (perform install/updates)         -- #
# --------------------------------------------------------------------------------------------------------------------------------------------------#

# if [ ! -z $1 ] && [ "$1" = 'local-dev' ] ; then
#     branch=dev
#     local_dev=true
# else
#     branch=$(pushd /etc/ConsolePi >/dev/null 2>&1 && git rev-parse --abbrev-ref HEAD && popd >/dev/null || echo "master")
#     local_dev=false
# fi

# get_common() {
#     if ! $local_dev ; then
#         wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/${branch}/installer/common.sh -O /tmp/common.sh
#     else
#         sudo -u pi sftp pi@consolepi-dev:/etc/ConsolePi/installer/common.sh /tmp/common.sh
#     fi
#     . /tmp/common.sh
#     [[ $? -gt 0 ]] && echo "FATAL ERROR: Unable to import common.sh Exiting" && exit 1
#     # overwrite the default source directory to local repo when running local tests
#     $local_dev && consolepi_source='pi@consolepi-dev:/etc/ConsolePi'
#     [ -f /tmp/common.sh ] && rm /tmp/common.sh
#     header 2>/dev/null || ( echo "FATAL ERROR: common.sh functions not available after import" && exit 1 )
# }

# Testing improved get_common that should work with install scenarios where they pull then run this script directly or from a zipped release
get_common() {
    if ! $local_dev ; then
        if [[ "$0" =~ install.sh ]] ; then
            this_path=$(dirname $(realpath consolepi/install.sh ))
            [[ -f ${this_path}/common.sh ]] && cp ${this_path}/common.sh /tmp ||
            (
            echo "This appeared to be an install from a pkg release, but common.sh not found in $this_path.  Attempting to fetch from GitHub Repo." "WARNING" ;
            wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/${branch}/installer/common.sh -O /tmp/common.sh || echo Failed to fetch common.sh from repo "WARNING"
            )
        else
            # install via TL;DR install line on GitHub
            wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/${branch}/installer/common.sh -O /tmp/common.sh
        fi
    else
        sudo -u pi sftp pi@consolepi-dev:/etc/ConsolePi/installer/common.sh /tmp/common.sh
    fi
    . /tmp/common.sh 2>>$log_file
    [[ $? -gt 0 ]] && echo "FATAL ERROR: Unable to import common.sh Exiting" && exit 1
    # overwrite the default source directory to local repo when running local tests
    $local_dev && consolepi_source='pi@consolepi-dev:/etc/ConsolePi'
    [ -f /tmp/common.sh ] && rm /tmp/common.sh
    header 2>/dev/null || ( echo "FATAL ERROR: common.sh functions not available after import" && exit 1 )
}

remove_first_boot() {
    # SD-Card created using Image Creator Script launches installer automatically - remove first-boot launch
    process="Remove exec on first-boot"
    sudo sed -i "s#consolepi-install##g" /home/pi/.bashrc
    grep -q consolepi-install /home/pi/.bashrc &&
        logit "Failed to remove first-boot verify /etc/rc.local" "WARNING"
}

do_apt_update() {
    process="Update/Upgrade ConsolePi (apt)"
    if $doapt; then
        logit "Update Sources"
        # Only update if initial install (no install.log) or if last update was not today
        if ! $upgrade || [[ ! $(ls -l --full-time /var/cache/apt/pkgcache.bin 2>/dev/null | cut -d' ' -f6) == $(echo $(date +"%Y-%m-%d")) ]]; then
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

        logit "Install/update git (apt)"
        apt-get -y install git 1>/dev/null 2>> $log_file && logit "git install/upgraded Successful" || logit "git install/upgrade FAILED to install" "ERROR"
        logit "Process Complete"
    else
        logit "apt updates skipped based on -noapt argument" "WARNING"
    fi
    unset process
}

# Process Changes that are required prior to git pull when doing upgrade
pre_git_prep() {
    if $upgrade; then

        # remove old bluemenu.sh script replaced with consolepi-menu.py
        process="ConsolePi-Upgrade-Prep (refactor bluemenu.sh)"
        if [[ -f /etc/ConsolePi/src/bluemenu.sh ]]; then
            rm /etc/ConsolePi/src/bluemenu.sh &&
                logit "Removed old menu script will be replaced during pull" ||
                    logit "ERROR Found old menu script but unable to remove (/etc/ConsolePi/src/bluemenu.sh)" "WARNING"
        fi
        # Remove old symlink if it exists
        process="ConsolePi-Upgrade-Prep (remove symlink consolepi-menu)"
        if [[ -L /usr/local/bin/consolepi-menu ]]; then
            unlink /usr/local/bin/consolepi-menu &&
                logit "Removed old consolepi-menu symlink will replace during upgade" ||
                    logit "ERROR Unable to remove old consolepi-menu symlink verify it should link to file in src dir" "WARNING"
        fi
        # Remove old launch file if it exists
        process="ConsolePi-Upgrade-Prep (remove consolepi-menu quick-launch file)"
        if [[ -f /usr/local/bin/consolepi-menu ]]; then
            rm /usr/local/bin/consolepi-menu &&
                logit "Removed old consolepi-menu quick-launch file will replace during upgade" ||
                    logit "ERROR Unable to remove old consolepi-menu quick-launch file" "WARNING"
        fi
    else
        # 02-05-2020 raspbian buster could not pip install requirements would error with no libffi
        process="ConsolePi-Upgrade-Prep (install libffi-dev)"
        if ! dpkg -l libffi-dev >/dev/null 2>&1 ; then
            apt install -y libffi-dev >/dev/null 2>>${log_file} &&
                logit "Success Installing development files for libffi" ||
                    logit "ERROR apt install libffi-dev retrurned an error" "WARNING"
        fi
    fi

    # 02-13-2020 raspbian buster could not pip install cryptography resolved by apt installing libssl-dev
    process="ConsolePi-Upgrade-Prep (install libssl-dev)"
    if ! dpkg -l libssl-dev >/dev/null 2>&1 ; then
        apt install -y libssl-dev >/dev/null 2>>${log_file} &&
            logit "Success Installing development files for libssl" ||
                logit "ERROR apt install libssl-dev retrurned an error" "WARNING"
    fi

    process="ConsolePi-Upgrade-Prep (create consolepi group)"
    for user in pi; do  # placeholder for additional non-pi users
        if [[ ! $(groups $user) == *"consolepi"* ]]; then
            if ! $(grep -q consolepi /etc/group); then
                sudo groupadd consolepi &&
                logit "Added consolepi group" ||
                logit "Error adding consolepi group" "WARNING"
            else
                logit "consolepi group already exists"
            fi
            sudo usermod -a -G consolepi $user &&
                logit "Added ${user} user to consolepi group" ||
                    logit "Error adding ${user} user to consolepi group" "WARNING"
        else
            logit "all good ${user} user already belongs to consolepi group"
        fi
    done
    unset process

    if [ -f $cloud_cache ]; then
        process="ConsolePi-Upgrade-Prep (check cache owned by consolepi group)"
        group=$(stat -c '%G' $cloud_cache)
        if [ ! $group == "consolepi" ]; then
            sudo chgrp consolepi $cloud_cache 2>> $log_file &&
                logit "Successfully Changed cloud cache group" ||
                logit "Failed to Change cloud cache group" "WARNING"
        else
            logit "Cloud Cache ownership already OK"
        fi
        unset process
    fi

    if [ -d $consolepi_dir ]; then
        process="ConsolePi-Upgrade-Prep (verify permissions)"

        check_list=("$consolepi_dir" "${consolepi_dir}.git")
        [[ -f ${consolepi_dir}.static.yaml ]] && check_list+=("${consolepi_dir}.static.yaml")

        for d in "${check_list[@]}"; do
            [ $(stat -c '%G' $d) == "consolepi" ] && grpok=true || grpok=false
            stat -c %A $d |grep -q "^....rw....$" && modok=true || modok=false
            if ! $grpok || ! $modok; then
                sudo chgrp -R consolepi ${d} 2>> $log_file ; local rc=$?
                sudo chmod g+w -R ${d} 2>> $log_file ; ((rc+=$?))
                [[ $rc > 0 ]] && logit "Error Returned while setting perms for $d" "WARNING" ||
                    logit "Success ~ Update Permissions for $d"
            else
                logit "Permissions for $d already OK"
            fi
        done
        unset process
    fi
}

git_ConsolePi() {
    process="git Clone/Update ConsolePi"

    # -- exit if python3 ver < 3.6
    [ ! -z $py3ver ] && [ $py3ver -lt 6 ] && (
        echo "ConsolePi Requires Python3 ver >= 3.6, aborting install."
        echo "Reccomend using ConsolePi_image_creator to create a fresh image on a new sd-card" &&
        exit 1
    )

    cd "/etc"
    if [ ! -d $consolepi_dir ]; then
        logit "Clean Install git clone ConsolePi"
        git clone "${consolepi_source}" 1>/dev/null 2>> $log_file && logit "ConsolePi clone Success" || logit "Failed to Clone ConsolePi" "ERROR"
    else
        cd $consolepi_dir
        logit "Directory exists Updating ConsolePi via git"
        git pull 1>/dev/null 2>> $log_file &&
            logit "ConsolePi update/pull Success" || logit "Failed to update/pull ConsolePi" "ERROR"
    fi
    [[ ! -d $bak_dir ]] && sudo mkdir $bak_dir
    # -- change group ownership to consolepi --
    sudo chgrp -R consolepi /etc/ConsolePi || logit "Failed to chgrp for ConsolePi dir to consolepi group" "WARNING"
    unset process
}

post_git() {
    process="relocate overrides"
    if [ -d ${src_dir}override ]; then
        files=($(ls ${src_dir}override | grep -v README 2>/dev/null))
        if [[ ${#files[@]} > 0 ]]; then
            cp ${src_dir}override/* $override_dir && error=false &&
                logit "overrides directory has re-located to $override_dir contents of old override dir moved" ||
                    ( error=true ; logit "Failure moving existing overrides to relocated ($override_dir)" )
            mv ${src_dir}override $bak_dir && logit "existing override dir moved to bak" ||
                logit "Failure moving existing override dir to bak dir" "WARNING"
        else
            rm -r ${src_dir}override || logit "Failure to rm old override dir" "WARNING"
        fi
    fi
}

do_pyvenv() {
    process="Prepare/Check Python venv"
    logit "$process - Starting"

    # -- Check that git pull didn't bork venv ~ I don't think I handled the removal of venv from git properly seems to break things if it was already installed --
    if [ -d ${consolepi_dir}venv ] && [ ! -x ${consolepi_dir}venv/bin/python3 ]; then
        sudo mv ${consolepi_dir}venv $bak_dir && logit "existing venv found, moved to bak, new venv will be created (it is OK to delete anything in bak)"
    fi

    # -- Ensure python3-pip is installed --
    if [[ ! $(dpkg -l python3-pip 2>/dev/null| tail -1 |cut -d" " -f1) == "ii" ]]; then
        sudo apt-get install -y python3-pip 1>/dev/null 2>> $log_file &&
            logit "Success - Install python3-pip" ||
            logit "Error - installing Python3-pip" "ERROR"
    fi

    if [ ! -d ${consolepi_dir}venv ]; then
        # -- Ensure python3 virtualenv is installed --
        venv_ver=$(sudo python3 -m pip list --format columns | grep virtualenv | awk '{print $2}')
        if [ -z $venv_ver ]; then
            logit "python virtualenv not installed... installing"
            sudo python3 -m pip install virtualenv 1>/dev/null 2>> $log_file &&
                logit "Success - Install virtualenv" ||
                logit "Error - installing virtualenv" "ERROR"
        else
            logit "python virtualenv v${venv_ver} installed"
        fi

        # -- Create ConsolePi venv --
        logit "Creating ConsolePi virtualenv"
        sudo python3 -m virtualenv ${consolepi_dir}venv 1>/dev/null 2>> $log_file &&
            logit "Success - Creating ConsolePi virtualenv" ||
            logit "Error - Creating ConsolePi virtualenv" "ERROR"
    else
        logit "${consolepi_dir}venv directory already exists"
    fi

    if $dopip; then
        if $upgrade; then
            # -- *Upgrade Only* update pip to current --
            logit "Upgrade pip"
            sudo ${consolepi_dir}venv/bin/python3 -m pip install --upgrade pip 1>/dev/null 2>> $log_file &&
                logit "Success - pip upgrade" ||
                logit "WARNING - pip upgrade returned error" "WARNING"
        fi

        # -- *Always* update venv packages based on requirements file --
        [ ! -z $py3ver ] && [ $py3ver -lt 6 ] && req_file="requirements-legacy.txt" || req_file="requirements.txt"
        logit "pip install/upgrade ConsolePi requirements - This can take some time."
        echo "-- Output of \"pip install --upgrade -r ${consolepi_dir}installer/${req_file}\" --"
        sudo ${consolepi_dir}venv/bin/python3 -m pip install --upgrade -r ${consolepi_dir}installer/${req_file} 2> >(tee -a $log_file >&2) &&
            logit "Success - pip install/upgrade ConsolePi requirements" ||
            logit "Error - pip install/upgrade ConsolePi requirements" "ERROR"
    else
        logit "pip upgrade / requirements upgrade skipped based on -nopip argument" "WARNING"
    fi

    # -- temporary until I have consolepi module on pypi --
    # !! No Longer Required, using sys.path.insert in the scripts until loaded on pypi
    # python_ver=$(ls -l /etc/ConsolePi/venv/lib | grep python3 |  awk '{print $9}')
    # pkg_dir=${consolepi_dir}venv/lib/${python_ver}/site-packages/consolepi
    # if [[ ! -L $pkg_dir ]] ; then
    #     logit "link consolepi python module in venv site-packages"
    #     # sudo cp -R ${src_dir}PyConsolePi/. ${consolepi_dir}venv/lib/${python_ver}/site-packages/consolepi 2>> $log_file &&
    #     [[ -d $pkg_dir ]] && rm -r $pkg_dir >/dev/null 2>> $log_file
    #     ln -s ${src_dir}PyConsolePi/ ${consolepi_dir}venv/lib/${python_ver}/site-packages/consolepi 2>> $log_file &&
    #     # sudo cp -r ${src_dir}PyConsolePi ${consolepi_dir}venv/lib/python3*/site-packages 2>> $log_file &&
    #         logit "Success - link consolepi python module into venv site-packages" ||
    #         logit "Error - link consolepi python module into venv site-packages" "ERROR"
    # fi


    unset process
}

# Configure ConsolePi logging directory and logrotate
do_logging() {
    process="Configure Logging"
    logit "Configure Logging in /var/log/ConsolePi"

    # Create /var/log/ConsolePi dir if it doesn't exist
    if [[ ! -d "/var/log/ConsolePi" ]]; then
        sudo mkdir /var/log/ConsolePi 1>/dev/null 2>> $log_file || logit "Failed to create Log Directory"
    fi

    # Create Log Files
    touch /var/log/ConsolePi/ovpn.log || logit "Failed to create OpenVPN log file" "WARNING"
    touch /var/log/ConsolePi/push_response.log || logit "Failed to create PushBullet log file" "WARNING"
    touch /var/log/ConsolePi/cloud.log || logit "Failed to create consolepi log file" "WARNING"
    touch /var/log/ConsolePi/install.log || logit "Failed to create install log file" "WARNING"
    touch /var/log/ConsolePi/consolepi.log || logit "Failed to create install log file" "WARNING"

    # Update permissions
    sudo chgrp -R consolepi /var/log/ConsolePi || logit "Failed to update group for log file" "WARNING"
    # if [ ! $(stat -c "%a" /var/log/ConsolePi/cloud.log) == 664 ]; then
    if [ ! $(stat -c "%a" /var/log/ConsolePi/consolepi.log) == 664 ]; then
        sudo chmod g+w /var/log/ConsolePi/* &&
            logit "Logging Permissions Updated (group writable)" ||
            logit "Failed to make log files group writable" "WARNING"
    fi

    # move installer log from temp to it's final location
    if ! $upgrade; then
        log_file=$final_log
        cat $tmp_log >> $log_file
        rm $tmp_log
    else
        if [ -f $tmp_log ]; then
            echo "ERROR: tmp log found when it should not have existed" | tee -a $final_log
            echo "-------------------------------- contents of leftover tmp log --------------------------------" >> $final_log
            cat $tmp_log >> $final_log
            echo "------------------------------ end contents of leftover tmp log ------------------------------" >> $final_log
            rm $tmp_log
        fi
    fi

    file_diff_update "${src_dir}ConsolePi.logrotate" "/etc/logrotate.d/ConsolePi"
    unset process
}

# Early versions of ConsolePi placed consolepi-commands in /usr/local/bin natively in the users path.
# ConsolePi now adds a script in profile.d to display the login banner and update path to include the
# consolepi-commands dir.  This function ensures the old stuff in /usr/local/bin are removed
do_remove_old_consolepi_commands() {
    process="Remove old consolepi-commands from /usr/local/bin"
    if [ $(ls -l /usr/local/bin/consolepi* 2>/dev/null | wc -l) -ne 0 ]; then
        sudo cp /usr/local/bin/consolepi-* $bak_dir 2>>$log_file || logit "Failed to Backup potentially custom consolepi-commands in /usr/local/bin" "WARNING"
        sudo rm /usr/local/bin/consolepi-* > /dev/null 2>&1
        sudo unlink /usr/local/bin/consolepi-* > /dev/null 2>&1
        [ $(ls -l /usr/local/bin/consolepi* 2>/dev/null | wc -l) -eq 0 ] &&
            logit "Success - Removing convenience command links created by older version" ||
            logit "Failure - Verify old consolepi-command scripts/symlinks were removed from /usr/local/bin after the install" "WARNING"
    fi
    unset process
}

# Update ConsolePi Banner to display ConsolePi ascii logo at login
update_banner() {
    process="update motd & profile"
    # remove old banner from /etc/motd - remove entire thing nothing useful
    if [ -f /etc/motd ]; then
        grep -q "PPPPPPPPPPPPPPPPP" /etc/motd && motd_exists=true || motd_exists=false
        if $motd_exists; then
            mv /etc/motd /bak && sudo touch /etc/motd &&
                logit "Clear old motd - Success" ||
                logit "Failed to Clear old motd" "WARNING"
        fi
    fi

    # remove old path update from /etc/profile
    if grep -q consolepi-commands /etc/profile ; then
        sed -i '/export.*PATH.*consolepi-commands/d'  /etc/profile &&
            logit "Success - move path update to script in profile.d" ||
            logit "Error - error code returned while updating profile script"
    fi

    # create new consolepi.sh profile script with banner and path
    file_diff_update ${src_dir}consolepi.sh /etc/profile.d/consolepi.sh
    unset process
}

get_config() {
    local process="import config.sh"
    if [[ -f /etc/ConsolePi/installer/config.sh ]]; then
        . /etc/ConsolePi/installer/config.sh ||
            logit "Error Occured importing config.sh" "Error"
    fi
}

get_update() {
    local process="import update.sh"
    if [ -f "${consolepi_dir}installer/update.sh" ]; then
        . "${consolepi_dir}installer/update.sh" ||
            logit "Error Occured importing update.sh" "Error"
    fi
}

main() {
    script_iam=`whoami`
    if [ "${script_iam}" = "root" ]; then
        get_common                          # get and import common functions script
        get_pi_info                         # (common.sh func) Collect some version info for logging
        remove_first_boot                   # if autolaunch install is configured remove
        do_apt_update ||          # apt-get update the pi
        pre_git_prep                        # process upgrade tasks required prior to git pull
        git_ConsolePi                       # git clone or git pull ConsolePi
        $upgrade && post_git                # post git changes
        do_pyvenv                           # build upgrade python3 venv for ConsolePi
        do_logging                          # Configure logging and rotation
        $upgrade && do_remove_old_consolepi_commands    # Remove consolepi-commands from old version of ConsolePi
        update_banner                       # ConsolePi login banner update
        get_config                          # import config.sh functions
        config_main                         # Kick off config.sh functions (Collect Config details from user)
        get_update                          # import update.sh functions
        update_main                         # Kick off update.sh functions
    else
      echo 'Script should be ran as root. exiting.'
    fi
}

process_args() {
    # All currently supported arguments are for dev/testing use
    branch=$(pushd /etc/ConsolePi >/dev/null 2>&1 && git rev-parse --abbrev-ref HEAD && popd >/dev/null || echo "master")
    local_dev=false
    dopip=true
    doapt=true
    while (( "$#" )); do
        case "$1" in
            -dev)
                branch=dev
                local_dev=true
                shift
                ;;
            -nopip)
                dopip=false
                shift
                ;;
            -noapt)
                doapt=false
                shift
                ;;
            -*|--*=) # unsupported flags
                echo "Error: Unsupported flag passed to process_cmds $1" >&2
                exit 1
                ;;
        esac
    done
}

process_args "$@"
main