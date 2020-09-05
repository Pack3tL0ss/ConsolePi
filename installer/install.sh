#!/usr/bin/env bash

# ------------------------------------------------------------------------------------------------------------------------------------------------- #
# --                                                 ConsolePi Installation Script Stage 1                                                       -- #
# --  Wade Wells (Pack3tL0ss)                                                                                                                    -- #
# --    report any issues/bugs on github or fork-fix and submit a PR                                                                             -- #
# --                                                                                                                                             -- #
# --  This script automates the installation of ConsolePi.                                                                                       -- #
# --  For more detail visit https://github.com/Pack3tL0ss/ConsolePi                                                                              -- #
# --                                                                                                                                             -- #
# --  This is the main installer file it imports and calls the other 2 files after prepping /etc/ConsolePi                                       -- #
# --    All files source common functions from common.sh pulled directly from git repo                                                           -- #
# --    Sequence: install.sh (prep, common imports, git) --> config.sh (get configuration/user input) --> update.sh (perform install/updates)    -- #
# --------------------------------------------------------------------------------------------------------------------------------------------------#

get_common() {
    if ! $local_dev ; then
        if [[ "$0" =~ install.sh ]] ; then
            this_path=$(dirname $(realpath "$0" ))
            [[ -f ${this_path}/common.sh ]] && cp ${this_path}/common.sh /tmp ||
            (
            echo "WARNING: This appeared to be an install from a pkg release, but common.sh not found in $this_path.  Attempting to fetch from GitHub Repo." ;
            wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/${branch}/installer/common.sh -O /tmp/common.sh || echo "WARNING Failed to fetch common.sh from repo"
            )
        else
            # install via TL;DR install line on GitHub
            wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/${branch}/installer/common.sh -O /tmp/common.sh
        fi
    else
        if [ ! ${HOSTNAME,,} == "consolepi-dev" ]; then
            local iam=${SUDO_USER:-$(who -m | awk '{ print $1 }')}
            sudo -u $iam sftp pi@consolepi-dev:/etc/ConsolePi/installer/common.sh /tmp/common.sh >/dev/null ||
            echo "ERROR: -dev sftp get failed"
        else
            [[ -f /etc/ConsolePi/installer/common.sh ]] && cp /etc/ConsolePi/installer/common.sh /tmp ||
            echo "ERROR: This is the dev ConsolePi, script called with -dev flag, but common.sh not found in installer dir"
        fi
    fi
    . /tmp/common.sh
    [[ $? -gt 0 ]] && echo "FATAL ERROR: Unable to import common.sh Exiting" && exit 1

    # overwrite the default source directory to local repo when running local tests
    $local_dev && consolepi_source='pi@consolepi-dev:/etc/ConsolePi'
    [ -f /tmp/common.sh ] && rm /tmp/common.sh
    header 2>/dev/null || ( echo "FATAL ERROR: common.sh functions not available after import" && exit 1 )

    # the following captures the date string for the start of this run used to parse file for WARNINGS
    # after the install
    # process="Script Starting"; logit -start "Install/Ugrade Scipt Starting"; unset process
}

remove_first_boot() {
    # SD-Card created using Image Creator Script launches installer automatically - remove first-boot launch
    process="Remove exec on first-boot"
    sudo sed -i "s#consolepi-install.*##g" /home/pi/.bashrc
    grep -q consolepi-install /home/pi/.bashrc &&
        logit "Failed to remove first-boot verify /etc/rc.local" "WARNING"
}

do_apt_update() {
    process="Update/Upgrade ConsolePi (apt)"
    if $doapt; then
        logit "Update Sources"
        # Only update if initial install (no install.log) or if last update was not today
        if ! $upgrade || [[ ! $(ls -l --full-time /var/cache/apt/pkgcache.bin 2>/dev/null | cut -d' ' -f6) == $(echo $(date +"%Y-%m-%d")) ]]; then
            res=$(apt update 2>>$log_file) && logit "Update Successful" || logit "FAILED to Update" "ERROR"
            [[ "$res" =~ "--upgradable" ]] && mapfile -t _upgd < <(apt list --upgradable 2>/dev/null | grep -v "^Listing.*$")
        else
            logit "Skipping Source Update - Already Updated today"
            mapfile -t _upgd < <(apt list --upgradable 2>/dev/null | grep -v "^Listing.*$")
        fi

        if [[ "${#_upgd[@]}" > 0 ]]; then
            logit "${_cyan}Your system has "${#_upgd[@]}" Packages that can be Upgraded${_norm}"
            logit "${_cyan}ConsolePi now *only* ensures packages it requires are current${_norm}"
        fi

    else
        logit "apt updates skipped based on -noapt argument" "WARNING"
    fi
    unset process
}

do_apt_deps() {
    process="Install Reqd Pkgs"
    which git >/dev/null || process_cmds -e -pf "install git" -apt-install git

    # -- Ensure python3-pip is installed --
    [[ ! $(dpkg -l python3-pip 2>/dev/null| tail -1 |cut -d" " -f1) == "ii" ]] &&
        process_cmds -e -pf "install python3-pip" -apt-install "python3-pip"

    # TODO add picocom, maybe ser2net, ensure process_cmds can accept multiple packages

    logit "$process - Complete"
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

        # verify group membership -- upgrade only -- checks
        process="create consolepi group"
        if ! grep -q consolepi /etc/group; then
            sudo groupadd consolepi &&
            logit "Added consolepi group" ||
            logit "Error adding consolepi group" "WARNING"
        else
            logit "consolepi group already exists"
        fi
        process="Verify Group Membership"
        [[ "$iam" == "pi" ]] && _users=pi || _users=("pi" "$iam")
        _groups=('consolepi' 'dialout')
        for user in "${_users[@]}"; do
            if ! grep -q "^${user}:" /etc/passwd; then
                logit "$user does not exist. Skipping"
                continue
            fi
            for grp in "${_groups[@]}"; do
                if [[ ! $(groups $user) == *"${grp}"* ]]; then
                    sudo usermod -a -G $grp $user &&
                        logit "Added ${user} user to $grp group" ||
                            logit "Error adding ${user} user to $grp group" "WARNING"
                else
                    logit "${user} already belongs to $grp group"
                fi
            done
        done
        unset process

    else  # -- // ONLY PERFORMED ON FRESH INSTALLS \\ --

        process="Create consolepi user/group"
        # add consolepi user
        header
        cp /etc/adduser.conf /tmp/adduser.conf
        extra_groups="adm dialout cdrom sudo audio video plugdev games users input netdev spi i2c gpio"
        extra_groups2="consolepi adm dialout cdrom sudo audio video plugdev games users input netdev spi i2c gpio"
        echo "EXTRA_GROUPS=\"$extra_groups\"" >> /tmp/adduser.conf
        echo 'ADD_EXTRA_GROUPS=1' >> /tmp/adduser.conf

        if ! grep -q "^consolepi:" /etc/group; then
            if [ ! -z "${consolepi_pass}" ]; then
                echo -e "${consolepi_pass}\n${consolepi_pass}\n" | adduser --conf /tmp/adduser.conf --gecos "" consolepi >/dev/null 2>> $log_file &&
                    logit "consolepi user created silently with config/cmd-line argument" || logit "Error silently creating consolepi user" "ERROR"
            else
                echo -e "\nAdding 'consolepi' user.  Please provide credentials for 'consolepi' user..."
                adduser --conf /tmp/adduser.conf --gecos "" consolepi >/dev/null 2>> $log_file ||
                    logit "Error adding consolepi user check $log_file" "ERROR"
            fi
        fi

        if [ ! -z "${auto_launch}" ]; then
            echo -e '\n#Auto-Launch consolepi-menu on login\nconsolepi-menu' >> /home/consolepi/.profile
        else
            if ! $silent; then
                user_input true "Make consolepi user auto-launch menu on login"
                $result && echo -e '\n#Auto-Launch consolepi-menu on login\nconsolepi-menu' >> /home/consolepi/.profile
            else
                logit "consolepi user auto-launch menu bypassed -silent install lacking --auto_launch flag="
            fi
        fi


        # Create additional Users (with appropriate rights for ConsolePi)
        if ! $silent; then
            sed -i "s/^EXTRA_GROUPS=.*/EXTRA_GROUPS=\"$extra_groups2\"/" /tmp/adduser.conf
            _res=true; while $_res; do
                echo
                user_input false "Would you like to create additional users"
                _res=$result
                if $result; then
                    user_input "" "Username for new user"
                    adduser --conf /tmp/adduser.conf --gecos "" ${result} 1>/dev/null &&
                        logit "Successfully added new user $result" ||
                        logit "Error adding new user $result" "WARNING"
                fi
            done
        fi

        # if pi user exists ensure it has correct group memberships for ConsolePi
        if grep -q "^pi:" /etc/passwd; then
            _groups=('consolepi' 'dialout')
            for grp in "${_groups[@]}"; do
                if [[ ! $(groups pi) == *"${grp}"* ]]; then
                    sudo usermod -a -G $grp pi &&
                        logit "Added pi user to $grp group" ||
                            logit "Error adding pi user to $grp group" "WARNING"
                else
                    logit "pi already belongs to $grp group"
                fi
            done
        fi

        rm /tmp/adduser.conf

        # Provide option to remove default pi user
        # process="Remove Default pi User"
        # if [[ $iam == "pi" ]]; then
        #     user_input false "Do You want to remove the default pi user?"
        #     if $result; then
        #         userdel pi 2>> $log_file && logit "pi user removed" || "Error returned when attempting to remove pi user" "WARNING"
        #     fi
        # fi
    fi
    # -- // Operations performed on both installs and upgrades \\ --

    # 02-05-2020 raspbian buster could not pip install requirements would error with no libffi
    # 09-03-2020 Confirmed this is necessary, and need to vrfy on upgrades
    process="Verify libffi-dev"
    if ! dpkg -l libffi-dev >/dev/null 2>&1 ; then
        process_cmds -nostart -apt-install "libffi-dev"
    fi

    # Give consolepi group sudo rights without passwd to stuff in the ConsolePi dir
    if [ ! -f /etc/sudoers.d/010_consolepi ]; then
        process="sudo rights consolepi group"
        echo '%consolepi ALL=(ALL) NOPASSWD: /etc/ConsolePi/src/*, /etc/ConsolePi/src/consolepi-commands/*, /etc/ConsolePi/venv/bin/python3 *' > /etc/sudoers.d/010_consolepi 2>>$log_file &&
        logit "consolepi group given sudo rights for consolepi-commands" ||
        logit "FAILED to give consolepi group sudo rights for ConsolePi functions" "WARNING"
        if [ -f /etc/sudoers.d/010_consolepi ]; then
            chmod 0440 /etc/sudoers.d/010_consolepi 2>>$log_file &&
            logit "Success chmod 0440 consolepi group sudoers.d file" ||
            logit "FAILED chmod 0440 consolepi group sudoers.d file" "WARNING"
        fi
        unset process
    fi

    # 02-13-2020 raspbian buster could not pip install cryptography resolved by apt installing libssl-dev
    # TODO check if this is required
    process="install libssl-dev"
    if ! dpkg -l libssl-dev >/dev/null 2>&1 ; then
        process_cmds -nostart -apt-install "libssl-dev"
    fi

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
                chgrp -R consolepi ${d} 2>> $log_file ; local rc=$?
                chmod g+w -R ${d} 2>> $log_file ; ((rc+=$?))
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
    $upgrade && process="Update ConsolePi (git pull)" || process="Clone ConsolePi (git clone)"

    # -- exit if python3 ver < 3.6
    [ ! -z "$py3ver" ] && [ "$py3ver" -lt 6 ] && (
        echo "ConsolePi Requires Python3 ver >= 3.6, aborting install."
        echo "Reccomend using ConsolePi_image_creator to create a fresh image on a new sd-card while retaining existing for backup." &&
        exit 1
    )

    if [ ! -d $consolepi_dir ]; then
        # -- ConsolePi dir does not exist clone from repo --
        logit "Clean Install git clone ConsolePi"
        pushd $home_dir >/dev/null
        git clone "${consolepi_source}" 1>/dev/null 2>> $log_file && logit "ConsolePi clone Success" || logit "Failed to Clone ConsolePi" "ERROR"
        popd >/dev/null

        # -- change group ownership to consolepi --
        chgrp -R consolepi $home_dir/ConsolePi || logit "Failed to chgrp for ConsolePi dir to consolepi group" "WARNING"
        chmod g+w -R $home_dir/ConsolePi 2>> $log_file || logit "Failed to make ConsolePi dir group wrteable" "WARNING"

        mv $home_dir/ConsolePi /etc || logit "Failed to mv ConsolePi dir to /etc"
    else
        # -- ConsolePi already exists update from repo --
        pushd $consolepi_dir >/dev/null
        logit "Directory exists Updating ConsolePi via git"
        git pull 1>/dev/null 2>> $log_file &&
            logit "ConsolePi update/pull Success" || logit "Failed to update/pull ConsolePi" "ERROR"
        popd >/dev/null
    fi

    # create bak dir if it doesn't exist
    # TODO should be able to ensure empty dir exists via .gitignore
    [[ ! -d $bak_dir ]] && sudo mkdir $bak_dir
    unset process
}

post_git() {
    process="relocate overrides"
    if [ -d ${src_dir}override ]; then
        files=($(ls ${src_dir}override | grep -v README 2>/dev/null))
        if [[ ${#files[@]} > 0 ]]; then
            cp ${src_dir}override/* $override_dir && error=false &&
                logit "overrides directory has re-located to $override_dir contents of old override dir coppied" ||
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
        mv ${consolepi_dir}venv $bak_dir && logit "existing venv found, moved to bak, new venv will be created (it is OK to delete anything in bak)"
    fi

    if [ ! -d ${consolepi_dir}venv ]; then
        # -- Ensure python3 virtualenv is installed --
        venv_ver=$(sudo python3 -m pip list --format columns | grep virtualenv | awk '{print $2}')
        if [ -z "$venv_ver" ]; then
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
        # [ ! -z $py3ver ] && [ $py3ver -lt 6 ] && req_file="requirements-legacy.txt" || req_file="requirements.txt"
        logit "pip install/upgrade ConsolePi requirements - This can take some time."
        echo -e "\n-- Output of \"pip install --upgrade -r ${consolepi_dir}installer/requirements.txt\" --\n"
        sudo ${consolepi_dir}venv/bin/python3 -m pip install --upgrade -r ${consolepi_dir}installer/requirements.txt 2> >(grep -v "WARNING: Retrying " | tee -a $log_file >&2) &&
            ( echo; logit "Success - pip install/upgrade ConsolePi requirements" ) ||
            logit "Error - pip install/upgrade ConsolePi requirements" "ERROR"

        # clean up the retry logs if pip install requirements was successful
        # grep -q "^.*Success.*pip install.*requirements" $log_file && sed -i '/WARNING: Retrying (Retry.*/d' $log_file
    else
        logit "pip upgrade / requirements upgrade skipped based on -nopip argument" "WARNING"
    fi

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
    # touch /var/log/ConsolePi/cloud.log || logit "Failed to create consolepi log file" "WARNING"
    touch /var/log/ConsolePi/install.log || logit "Failed to create install log file" "WARNING"
    touch /var/log/ConsolePi/consolepi.log || logit "Failed to create install log file" "WARNING"

    # Update permissions
    sudo chgrp -R consolepi /var/log/ConsolePi || logit "Failed to update group for log file" "WARNING"
    if [ ! $(stat -c "%a" /var/log/ConsolePi/consolepi.log) == 664 ]; then
        sudo chmod g+w /var/log/ConsolePi/* &&
            logit "Logging Permissions Updated (group writable)" ||
            logit "Failed to make log files group writable" "WARNING"
    fi

    # move installer log from temp to it's final location
    if ! $upgrade; then
        log_file=$final_log
        if [ -f $tmp_log ]; then
            cat $tmp_log >> $log_file 2>&1
            rm $tmp_log
        fi
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

do_imports() {
    process="import config.sh"
    . "${consolepi_dir}installer/config.sh" 2>>$log_file || logit "Error Occured importing config.sh" "Error"
    process="import update.sh"
    . "${consolepi_dir}installer/update.sh" 2>>$log_file || logit "Error Occured importing update.sh" "Error"
    unset process
}

_help() {
    local pad=$(printf "%0.1s" " "{1..40})
    printf " %s%*.*s%s.\n" "$1" 0 $((40-${#1})) "$pad" "$2"
}

show_usage() {
    # common is not imported here can't use common funcs
    _green='\e[32;1m' # bold green
    _cyan='\e[96m'
    _norm='\e[0m'
    if [ -f /etc/ConsolePi/src/consolepi-commands/consolepi-upgrade ]; then
        local _cmd=consolepi-upgrade
    elif [ -f /usr/local/bin/consolepi-install ]; then
        local _cmd=consolepi-install
    else
        local _cmd="sudo $(echo $SUDO_COMMAND | cut -d' ' -f1)"
    fi
    echo -e "\n${_green}USAGE:${_norm} $_cmd [OPTIONS]\n"
    echo -e "${_cyan}Available Options${_norm}"
    _help "--help | -help | help" "Display this help text"
    _help "-silent" "Perform silent install no prompts, all variables reqd must be provided via pre-staged configs"
    _help "-C|-config <path/to/config>" "Specify config file to import for install variables (see /etc/ConsolePi/installer/install.conf.example)"
    echo "    Copy the example file to your home dir and make edits to use"
    _help "-noipv6" "bypass 'Do you want to disable ipv6 during install' prompt.  Disable or not based on this value =true: Disables"
    _help "-btpan" "Configure Bluetooth with PAN service (prompted if not provided, defaults to serial if silent and not provided)"
    _help "-reboot" "reboot automatically after silent install (Only applies to silent install)"
    _help "--wlan_country=<wlan_country>" "wlan regulatory domain (Default: US)"
    _help "--hostname=<hostname>" "If set will bypass prompt for hostname and set based on this value (during initial install)"
    _help "--tz=<i.e. 'America/Chicago'>" "If set will bypass tz prompt on install and configure based on this value"
    _help "--auto_launch='<true|false>'" "Bypass prompt 'Auto Launch menu when consolepi user logs in' - set based on this value"
    _help "--consolepi_pass='<password>'" "Use single quotes: Bypass prompt on install set consolepi user pass to this value"
    _help "--pi_pass=<'password>" "Use single quotes: Bypass prompt on install set pi user pass to this value"
    echo "    pi user can be deleted after initial install if desired, A non silent install will prompt for additional users and set appropriate group perms"
    echo -e "    ${_cyan}Any manually added users should be members of 'dialout' and 'consolepi' groups for ConsolePi to function properly${_norm}"
    echo
    echo "The Following optional arguments are more for dev, but can be useful in some other scenarios"
    _help "-noapt" "Skip the apt update/upgrade portion of the Upgrade.  Should not be used on initial installs."
    _help "-nopip" "Skip pip install -r requirements.txt.  Should not be used on initial installs."
    echo
    echo -e "${_cyan}Examples:${_norm}"
    echo "  This example specifies a config file with -C (telling it to get some info from the specified config) as well as the silent install option (no prompts)"
    if [[ ! "$_cmd" =~ "upgrade" ]]; then
        echo -e "  ${_cyan}NOTE:${_norm} In order to perform a silent install ConsolePi.yaml needs to be pre-staged/pre-configured in /home/<user>/consolepi-stage directory"
    fi
    echo -e "\t> $_cmd -C /home/pi/consolepi-stage/installer.conf -silent"
    echo
    echo "  Alternatively the necessary arguments can be passed in via cmd line arguments"
    echo -e "  ${_cyan}NOTE:${_norm} Showing minimum required options for a silent install.  ConsolePi.yaml has to exist"
    echo -e "        wlan_country will default to US, No changes will be made re timezone, ipv6 & hostname"
    echo -e "\t> $_cmd -silent --consolepi-pass='c0nS0lePi!' --pi-pass='c0nS0lePi!'"
    echo
}

process_args() {
    # All currently supported arguments are for dev/testing use
    branch=$(pushd /etc/ConsolePi >/dev/null 2>&1 && git rev-parse --abbrev-ref HEAD && popd >/dev/null || echo "master")
    silent=false
    local_dev=false
    dopip=true
    doapt=true
    do_reboot=false
    while (( "$#" )); do
        # echo "$1" # -- DEBUG --
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
            -silent)  # silent install
                silent=true
                shift
                ;;
            -reboot)  # reboot automatically after silent install
                do_reboot=true
                shift
                ;;
            -install)  # dev flag run as if initial install
                upgrade=false
                shift
                ;;
            # -- silent install options --
            -C|-config)
                if [ -f "$2" ]; then
                   . "$2"
                   [ ! -z "$noipv6" ] && dis_ipv6=$noipv6
                else
                    echo "Specified Config $2 not found"
                    exit 1
                fi
                shift 2
                ;;
            -noipv6) # disable ipv6
                dis_ipv6=true
                shift
                ;;
            -btpan) # Setup bt to use PAN
                btmode=pan
                shift
                ;;
            --hostname=*)
                hostname=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --tz=*) # timezone
                tz=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --wlan_country=*)
                wlan_country=$(echo "${1^^}"| cut -d= -f2)
                shift
                ;;
            --consolepi_pass=*) # consolepi user's password
                consolepi_pass=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --auto_launch=*)
                auto_launch=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            --pi_pass=*) # pi user's password
                pi_pass=$(echo "$1"| cut -d= -f2)
                shift
                ;;
            # -- \silent install options --
            help|-help|--help)
                show_usage
                exit 0
                ;;
            *) # -*|--*=) # unsupported flags
                echo "Error: Unsupported flag passed to process_args $1" >&2
                exit 1
                ;;
        esac
    done

    # -- Set defaults applied when using silent mode if not specified --
    $silent && btmode=${btmode:-serial}
}

main() {
    script_iam=`whoami`
    if [ "${script_iam}" = "root" ]; then
        set +H                              # Turn off ! history expansion
        process_args "$@"
        get_common                          # get and import common functions script
        get_pi_info                         # (common.sh func) Collect some version info for logging
        remove_first_boot                   # if auto-launch install on first login is configured remove
        do_apt_update                       # apt-get update the pi
        do_apt_deps                         # install dependencies via apt
        pre_git_prep                        # process upgrade tasks required prior to git pull
        git_ConsolePi                       # git clone or git pull ConsolePi
        $upgrade && post_git                # post git changes
        do_pyvenv                           # build upgrade python3 venv for ConsolePi
        do_logging                          # Configure logging and rotation
        update_banner                       # ConsolePi login banner update
        do_imports                          # import config.sh functions and update.sh functions
        config_main                         # Kick off config.sh functions (Collect Config details from user)
        update_main                         # Kick off update.sh functions
    else
      echo 'Script should be ran as root. exiting.'
    fi
}

# process_args "$@"
main "$@"
