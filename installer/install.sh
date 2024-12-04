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
        if [ "${HOSTNAME,,}" != "consolepi-dev" ]; then
            local _iam=${SUDO_USER:-$(who -m | awk '{ print $1 }')}
            sudo -u $_iam sftp $dev_user@consolepi-dev:/etc/ConsolePi/installer/common.sh /tmp/common.sh >/dev/null ||
            echo "ERROR: -dev sftp get failed"
        else
            [ -f /etc/ConsolePi/installer/common.sh ] && cp /etc/ConsolePi/installer/common.sh /tmp ||
            echo "ERROR: This is the dev ConsolePi, script called with -dev flag, but common.sh not found in installer dir"
        fi
    fi
    . /tmp/common.sh
    [ "$?" -gt 0 ] && echo "FATAL ERROR: Unable to import common.sh Exiting" && exit 1

    # overwrite the default source directory to local repo when running local tests
    $local_dev && consolepi_source="$dev_user@consolepi-dev:/etc/ConsolePi"
    [ -f /tmp/common.sh ] && rm /tmp/common.sh
    header 2>/dev/null || ( echo "FATAL ERROR: common.sh functions not available after import" && exit 1 )
}

remove_first_boot() {
    # SD-Card created using Image Creator Script launches installer automatically - remove first-boot launch
    process="Remove exec on first-boot"
    if grep -q consolepi-install $home_dir/.profile; then
        sudo sed -i "s#consolepi-install.*##g" $home_dir/.profile
        grep -q consolepi-install $home_dir/.profile &&
            logit "Failed to remove first-boot verify $home_dir/.profile" "WARNING"
    fi
}

do_apt_update() {
    process="Update/Upgrade ConsolePi (apt)"
    if $doapt; then
        logit "Update Sources"
        # Only update if initial install (no install.log) or if last update was not today
        if ! $upgrade || [[ ! $(ls -l --full-time /var/cache/apt/pkgcache.bin 2>/dev/null | cut -d' ' -f6) == $(echo $(date +"%Y-%m-%d")) ]]; then
            res=$(apt update 2> >(grep -v "^$\|^WARNING: apt does not.*CLI.*$" >>"$log_file")) && logit "Update Successful" || logit "FAILED to Update" "ERROR"
            [[ "$res" =~ "--upgradable" ]] && mapfile -t _upgd < <(apt list --upgradable 2>/dev/null | grep -v "^Listing.*$")
        else
            logit "Skipping Source Update - Already Updated today"
            mapfile -t _upgd < <(apt list --upgradable 2>/dev/null | grep -v "^Listing.*$")
        fi

        if [[ "${#_upgd[@]}" > 0 ]]; then
            logit "${_cyan}Your system has "${#_upgd[@]}" Packages that can be Upgraded${_norm}"
            logit "${_cyan}ConsolePi *only* ensures packages it requires are current${_norm}"
        fi

    else
        logit "apt updates skipped based on --no-apt flag" "WARNING"
    fi
    unset process
}

do_apt_deps() {
    process="Install Reqd Pkgs"
    if $doapt; then
        logit "$process - Starting"

        which git >/dev/null || process_cmds -e --apt-install git

        # prefer users .config dir over .gitconfig in users home
        if [ ! -f $home_dir/.gitconfig ] && [ ! -d $home_dir/.config/git ]; then
            logit "Creating user git config at $home_dir/.config/git/config"
            sudo -u $iam mkdir -p $home_dir/.config/git 2>>$log_file
            sudo -u $iam touch $home_dir/.config/git/config
        fi
        if [ ! -f /root/.gitconfig ] && [ ! -d /root/.config/git ]; then
            logit "Creating root git config at /root/.config/git/config"
            mkdir -p /root/.config/git 2>>$log_file
            touch /root/.config/git/config
        fi


        # -- Ensure python3-pip is installed --
        [[ ! $(dpkg -l python3-pip 2>/dev/null| tail -1 |cut -d" " -f1) == "ii" ]] &&
            process_cmds -e --apt-install "python3-pip"

        # if consolepi venv dir exists we assume virtualenv is installed
        if [ ! -d ${consolepi_dir}venv ]; then
            # -- Ensure python3 virtualenv is installed --
            venv_ver=$(python3 -m pip show virtualenv 2>/dev/null | grep -i version | cut -d' ' -f2)
            if [ -z "$venv_ver" ]; then
                process_cmds -e --apt-install "python3-virtualenv"
            fi
        fi

        # 02-05-2020 raspbian buster could not pip install requirements would error with no libffi
        # 09-03-2020 Confirmed this is necessary, and need to vrfy on upgrades
        if ! dpkg -l libffi-dev >/dev/null 2>&1 ; then
            process_cmds --apt-install "libffi-dev"
        fi

        # 02-13-2020 raspbian buster could not pip install cryptography resolved by apt installing libssl-dev
        # TODO check if this is required
        if ! dpkg -l libssl-dev >/dev/null 2>&1 ; then
            process_cmds --apt-install "libssl-dev"
        fi

        # Install picocom
        if [[ $(picocom --help 2>/dev/null | head -1) ]]; then
            logit "$(picocom --help 2>/dev/null | head -1) is already installed"
        else
            process_cmds -apt-install picocom
        fi

        logit "$process - Complete"
    else
        logit "apt deps skipped based on --no-apt flag" "WARNING"
    fi
}

do_user_dir_import(){
    [[ $1 == root ]] && local user_home=root || local user_home="home/$1"
    # -- Copy Prep pre-staged files if they exist (stage-dir/home/<username>) for newly created user.
    found_path=$(get_staged_file_path "$user_home" "-d")
    if [ -n "$found_path" ]; then
        logit "Found staged files for $1, copying to users home"
        cp -r "$found_path/." "/$user_home/" &&
            chown -R $(grep "^$1:" /etc/passwd | cut -d: -f3-4) "/$user_home/" &&
            ( logit "Success - copy staged files for user $1" && return 0 ) ||
            ( logit "An error occurred when attempting cp pre-staged files for user $1" "WARNING"
              return 1
            )
    fi
}

do_autolaunch() {
    if echo -e '\n# Auto-Launch consolepi-menu on login\nconsolepi-menu' >> /home/consolepi/.profile; then
        logit "consolepi user configured to auto-launch menu on login"
        return 0
    else
        logit "Failed to cofnigure auto-launch menu on login for consolepi user"
        return 1
    fi
}

do_users(){
    if ! $upgrade; then
        # -- // ONLY PERFORMED ON FRESH INSTALLS \\ --

        # when using the image creator consolepi is the default user
        process="Create consolepi user/group"
        cp /etc/adduser.conf /tmp/adduser.conf
        extra_groups="consolepi adm dialout cdrom sudo audio video plugdev games users input netdev spi i2c gpio"
        echo "EXTRA_GROUPS=\"${extra_groups#"consolepi "}\"" >> /tmp/adduser.conf
        echo 'ADD_EXTRA_GROUPS=1' >> /tmp/adduser.conf

        if ! getent group consolepi >/dev/null; then
            # -- non interactive --
            if [ -n "${consolepi_pass}" ]; then
                echo -e "${consolepi_pass}\n${consolepi_pass}\n" | adduser --conf /tmp/adduser.conf --gecos ",,,," consolepi >/dev/null 2>> $log_file &&
                    logit "consolepi user created silently with config/cmd-line argument" || logit "Error silently creating consolepi user" "ERROR"
                unset consolepi_pass
            else  # -- interactive --
                echo -e "\nAdding 'consolepi' user.  Please provide credentials for 'consolepi' user..."
                ask_pass  # provides _pass in global context
                echo -e "${_pass}\n${_pass}\n" | adduser --conf /tmp/adduser.conf --gecos ",,,," consolepi >/dev/null 2>> $log_file &&
                    (
                        logit "consolepi user created."
                        do_user_dir_import consolepi || logit -L "User dir import for consolepi user returned error"
                    ) || logit "Error creating consolepi user" "ERROR"
                unset _pass
            fi
            echo
        fi

        # -- consolepi user auto-launch menu (The grep verification is for re-testing scenarios to prevent duplicate lines)
        if ! grep -q "^consolepi-menu" /home/consolepi/.profile; then
            if [ -n "${auto_launch}" ]; then
                $auto_launch && do_autolaunch
            else
                if ! $silent; then
                    user_input true "Make consolepi user auto-launch menu on login"
                    $result && do_autolaunch
                else
                    logit "consolepi user auto-launch menu bypassed -silent install lacking --auto-launch flag"
                fi
            fi
        fi


        # Create additional Users (with appropriate rights for ConsolePi)
        process="Add Users"
        if ! $silent && ! $no_users; then
            # strip users from extra_groups as user will have that group automatically
            extra_groups=$( echo $extra_groups | sed 's/\(.*\) users\(.*\)/\1\2/' )
            sed -i "s/^EXTRA_GROUPS=.*/EXTRA_GROUPS=\"$extra_groups\"/" /tmp/adduser.conf
            _res=true; while $_res; do
                echo
                user_input false "Would you like to create additional users"
                _res=$result
                if $result; then
                    user_input "" "Username for new user"
                    # We silently allow user to pass args to adduser
                    local user=$result
                    result=($result)
                    local args=()
                    i=0; while [ $i -lt "${#result[@]}" ]; do
                        case "${result[i]}" in
                            -*)
                                args+=(${result[@]:i:$((i+2))})
                                ((i+=2))
                            ;;
                            *)
                                user="${result[i]}"
                                ((i+=1))
                            ;;
                        esac
                    done
                    if adduser --conf /tmp/adduser.conf --gecos ",,,," ${args[@]} ${user} 1>/dev/null; then
                        logit "Successfully added new user $user"

                        # Now double check the users group thing (not sure if this is new since bookworm)
                        if ! getent group users | grep -q $user; then
                            usermod -a -G users "$user" ; rc=$?
                            logit -L -t "DEVNOTE" "Had to add users group to user $user. returned $rc"
                        fi

                        # -- Copy Prep pre-staged files if they exist (stage-dir/home/<username>) for newly created user.
                        do_user_dir_import $user || logit -L "User dir import for $user user returned error"

                    else
                        logit "Error adding new user $user" "WARNING"
                    fi
                else
                    header
                fi
            done
        fi

        # if pi user exists ensure it has correct group memberships for ConsolePi
        process="Verify pi user groups (Legacy Support)"
        if getent passwd pi >/dev/null; then
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

    else  # --- UPGRADE VERIFICATIONS ---
        # verify group membership -- upgrade only -- checks

        # This is for backward compatability.  Previous versions did not have a consolepi user, just the group
        process="create consolepi user"
        if ! getent group consolepi >/dev/null; then
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
            if ! getent passwd $user >/dev/null; then
                [ $user != pi ] && logit "$user does not exist. Skipping"
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
    fi

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
        unset process
    fi

    # -- // OPERATIONS PERFORMED ON BOTH INSTALLS AND UPGRADES \\ --

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

    # -- Verify cloud cache is owned by consolepi group
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

    # -- verify Group owndership and permissions of /etc/ConsolePi and .git dir
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
                [ "$rc" -gt 0 ] && logit "Error Returned while setting perms for $d" "WARNING" ||
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
        if git clone "${consolepi_source}" 1>/dev/null 2>> $log_file; then
            logit "ConsolePi clone Success"
        else
            logit "Failed to Clone ConsolePi" "ERROR"
            echo "command \"git clone ${consolepi_source}\" failed!!" >> $log_file
        fi
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
    # TODO should be able to ensure empty dir exists via .gitignore - DONE this can be removed once verified
    [[ ! -d $bak_dir ]] && sudo mkdir $bak_dir
    unset process
}

# DELME -- This should be safe to remove now
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
    venv_py3ver=""
    export DEB_PYTHON_INSTALL_LAYOUT='deb'  # see https://askubuntu.com/questions/1406304/virtualenv-installs-envs-into-local-bin-instead-of-bin

    # -- Check that release upgrade or manual python upgrade hasnt made the venv python ver differ from system --
    if [ -d ${consolepi_dir}venv ] && [ -x "${consolepi_dir}venv/bin/python3" ]; then
        venv_py3ver=$(basename ${consolepi_dir}venv/bin/python3.* | grep -v '*' | cut -d. -f2)
        if [ "$venv_py3ver" != "$py3ver" ]; then
            mv ${consolepi_dir}venv $bak_dir && logit "The Python version on the system has been upgraded moving existing venv to bak dir." &&
                logit "A New venv will be created. (it is OK to delete anything in bak)"
        fi
    fi

    if [ ! -d ${consolepi_dir}venv ]; then
        # -- Create ConsolePi venv --
        logit "Creating ConsolePi virtualenv"
        sudo python3 -m virtualenv ${consolepi_dir}venv 1>/dev/null 2>> $log_file &&
            logit "Success - Creating ConsolePi virtualenv" ||
            logit "Error - Creating ConsolePi virtualenv" "ERROR"
    else
        logit "${consolepi_dir}venv directory already exists"
    fi

    # dopip can be toggled off via --no-pip flag (used for repeated testing of install scripts)
    if $dopip; then
        logit "Upgrade pip"
        sudo ${consolepi_dir}venv/bin/python3 -m pip install --upgrade pip 1>/dev/null 2>> $log_file &&
            logit "Success - pip upgrade" ||
            logit "WARNING - pip upgrade returned error" "WARNING"

        logit "pip install/upgrade ConsolePi requirements - This can take some time."
        echo -e "\n-- Output of \"pip install --no-cache-dir --prefer-binary --upgrade -r ${consolepi_dir}installer/requirements.txt\" --\n"
        # -- RPi.GPIO is done separately as it's a distutils package installed by apt, but pypi may be newer.  this is in a venv, should do no harm
        # It will also install on non rpi Linux systems (via pip).  So does no harm to install it.
        # Will not install in python global context via apt on other systems: sudo apt install python3-rpi.gpio ; as it's only in the rpi repo
        # Some platforms (i.e. Jetson Nano) use different library to operate GPIO, would need wrapper that could determine platform and which to use.  Just means GPIO based power would not be supported on those systems.

        # if we do --upgrade below ERROR: Cannot uninstall 'RPi.GPIO'. It is a distutils installed project and thus we cannot accurately determine which files belong to it which would lead to only a partial uninstall.
        # if we include RPi.GPIO in the requirements file then pip install --upgrade -r requirements.txt ... it will result in the same error.
        #  SO we simply do pip install RPi.GPIO to ensure it's installed in the venv, log a WARNING which allows script to continue if there is a failure.  RPi.GPIO would be upgraded only when venv is re-created. (or manually)
        # TODO test removing from venv and installing in global context via "sudo apt install python3-rpi.gpio"
        if [ "$is_pi" = true ]; then  # removed --ignore-installed from below need to verify what's needed here
            sudo ${consolepi_dir}venv/bin/python3 -m pip install --no-cache-dir RPi.GPIO 2> >(grep -v "WARNING: Retrying " | tee -a $log_file >&2) ||
                logit "pip install/upgrade RPi.GPIO (separately) returned an error." "WARNING"
        fi
        # -- Update venv packages based on requirements file --
        sudo ${consolepi_dir}venv/bin/python3 -m pip install --no-cache-dir --prefer-binary --upgrade -r ${consolepi_dir}installer/requirements.txt 2> >(grep -v "WARNING: Retrying " | tee -a $log_file >&2) &&
            ( echo; logit "Success - pip install/upgrade ConsolePi requirements" ) ||
            logit "Error - pip install/upgrade ConsolePi requirements" "ERROR"
    else
        logit "pip upgrade / requirements upgrade skipped based on --no-pip flag" "WARNING"
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

    # DELME Should be safe to remove at this point
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
    . "${consolepi_dir}installer/config.sh" 2>>$log_file || logit "Error Occurred importing config.sh" "Error"
    process="import update.sh"
    . "${consolepi_dir}installer/update.sh" 2>>$log_file || logit "Error Occurred importing update.sh" "Error"
    unset process
}

_help() {
    local pad=$(printf "%0.1s" " "{1..40})
    printf " %s%*.*s%s.\n" "$1" 0 $((40-${#1})) "$pad" "$2"
}

show_usage() {
    ## !! common is not imported here can't use common funcs
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
    _help "-h|--help" "Display this help text"
    _help "-s|--silent" "Perform silent install no prompts, all variables reqd must be provided via pre-staged configs"
    _help "-C | --config <path/to/config>" "Specify config file to import for install variables (see /etc/ConsolePi/installer/install.conf.example)"
    echo "    Copy the example file to your home dir and make edits to use."
    _help "-6|--no-ipv6" "Disable IPv6 (Only applies to initial install)"
    # _help "--bt-pan" "Configure Bluetooth with PAN service (prompted if not provided, defaults to serial if silent and not provided)"
    _help "-R|--reboot" "reboot automatically after silent install (Only applies to silent install)"
    _help "-w|--wlan_country <2 char country code>" "wlan regulatory domain (Default: US)"
    _help "--locale <2 char country code>" "Update locale and keyboard layout. i.e. '--locale us' will result in locale being updated to en_US.UTF-8"
    _help "--us" "Alternative to the 2 above, implies us for wlan country, locale, and keyboard."
    _help "-H|--hostname <hostname>" "If set will bypass prompt for hostname and set based on this value (during initial install)"
    _help "--tz <tz>" "Configure TimeZone i.e. America/Chicago"
    _help "-L|--auto-launch" "Automatically launch consolepi-menu for consolepi user.  Defaults to False."
    _help "-p|--passwd '<password>'" "Use single quotes: The password to configure for consolepi user during install."
    echo -e "    ${_cyan}Any manually added users should be members of 'dialout' and 'consolepi' groups for ConsolePi to function properly${_norm}"
    echo
    echo "The Following optional arguments are more for dev, but can be useful in some other scenarios"
    if [ -n "$1" ] && [ "$1" = "dev" ]; then  # hidden dev flags --help dev to display them.
        _help "-D|--dev" "Install from ConsolePi-dev (will use dev branch unless -b|--branch specifies otherwise)"
        _help "--dev-user <user>" "Override the default user used for sftp/ssh/git to ConsolePi-dev"
        _help "-b|--branch" "Will pull from an alternate branch (default is master or dev when -D|--dev flag is used)"
        _help "--me" "Override the default user used for sftp/ssh/git to ConsolePi-dev, use current user."
        _help "-I|--install" "Run as if it's the initial install"
        _help "--no-users" "Bypass prompt that asks if you want to create additional users (always bypassed w/ --silent)"
    fi
    _help "-P|--post" "~/consolepi-stage/consolepi-post.sh if found is executed after initial install.  Use this to run after upgrade."
    _help "--no-apt" "Skip the apt update/upgrade portion of the Upgrade.  Should not be used on initial installs."
    _help "--no-pip" "Skip pip install -r requirements.txt.  Should not be used on initial installs."
    _help "--no-blue" "Skip bluetooth console and blue user setup."
    echo
    echo -e "${_cyan}Examples:${_norm}"
    echo "  This example specifies a config file with -C (telling it to get some info from the specified config) as well as the silent install option (no prompts)"
    if [[ ! "$_cmd" =~ "upgrade" ]]; then
        echo -e "  ${_cyan}NOTE:${_norm} In order to perform a silent install ConsolePi.yaml needs to be pre-staged/pre-configured in /home/<user>/consolepi-stage directory"
    fi
    echo -e "\t> $_cmd -C /home/consolepi/consolepi-stage/installer.conf --silent"
    echo
    echo "  Alternatively the necessary arguments can be passed in via cmd line arguments"
    echo -e "  ${_cyan}NOTE:${_norm} Showing minimum required options for a silent install.  ConsolePi.yaml has to exist"
    echo -e "        wlan_country will default to US, No changes will be made re timezone, ipv6 & hostname"
    echo -e "\t> $_cmd -silent -p 'c0nS0lePi!'"
    echo
}

missing_param(){
    echo $1 requires an argument. >&2
    show_usage
    exit 1
}

do_safe_dir(){
    # Prevent fatal: detected dubious ownership in repository at '/etc/ConsolePi'
    # common is not loaded yet, hence the need to define the local vars

    # local iam=${SUDO_USER:-$(who -m | awk '{ print $1 }')}
    # local tmp_log="/tmp/consolepi_install.log"
    # local final_log="/var/log/ConsolePi/install.log"
    # [ -f "$final_log" ] && local log_file=$final_log || local log_file=$tmp_log
    if ! git config --global -l 2>/dev/null | grep -q "safe.directory=/etc/ConsolePi"; then
        echo "$(date +"%b %d %T") [$$][INFO][Verify git safe.directory] Adding /etc/ConsolePi as git safe.directory globally" | tee -a $log_file
        git config --global --add safe.directory /etc/ConsolePi 2>>$log_file
    fi
    if ! sudo -u $iam git config --global -l 2>/dev/null | grep -q "safe.directory=/etc/ConsolePi"; then
        echo "$(date +"%b %d %T") [$$][INFO][Verify git safe.directory] Adding /etc/ConsolePi as git safe.directory globally for user $iam" | tee -a $log_file
        sudo -u $iam git config --global --add safe.directory /etc/ConsolePi 2>>$log_file
    fi
}

process_args() {
    branch=$(pushd /etc/ConsolePi >/dev/null 2>&1 && git rev-parse --abbrev-ref HEAD 2>/dev/null && popd >/dev/null || echo "master")
    silent=false
    local_dev=false
    dopip=true
    doapt=true
    do_blue=true
    do_reboot=false
    do_consolepi_post=false
    no_users=false
    dev_user=${SUDO_USER:-$(who -m | awk '{ print $1 }')}
    while (( "$#" )); do
        # echo "$1" # -- DEBUG --
        case "$1" in
            -D|-*dev)
                local_dev=true
                shift
                ;;
            -b|-*branch)
                local _branch="$2"
                shift 2
                ;;
            -*dev-user)
                [ -n "$2" ] && dev_user=$2 || missing_param "$@" # override of static var set in common.sh
                shift 2
                ;;
            -*me)
                dev_user=${SUDO_USER:-$(who -m | awk '{ print $1 }')} # can remove... it's now the default
                shift
                ;;
            -*no-pip)
                dopip=false
                shift
                ;;
            -*no-apt)
                doapt=false
                shift
                ;;
            -*no-blue)
                do_blue=false  # skip bluetooth and blue user
                shift
                ;;
            -*no-users) # Don't ask for additional users during install
                no_users=true
                shift
                ;;
            -s|--silent)  # silent install
                silent=true
                shift
                ;;
            -R|--reboot)  # reboot automatically after silent install
                do_reboot=true
                shift
                ;;
            -I|-*install)  # dev flag run as if initial install
                upgrade=false
                shift
                ;;
            -P|-*post)  # Run post-install script even on upgrade
                do_consolepi_post=true
                shift
                ;;
            # -- silent install options --
            -C|--config)
                if [ -f "$2" ]; then
                   . "$2"
                else
                    echo "Specified Config $2 not found"
                    exit 1
                fi
                shift 2
                ;;
            -6|--no-ipv6) # disable ipv6
                no_ipv6=true
                shift
                ;;
            --bt-pan) # Setup bt to use PAN, default is serial
                btmode=pan
                shift
                ;;
            -H|--hostname)
                [ -n "$2" ] && hostname=$2 || missing_param "$@"
                shift 2
                ;;
            --tz) # timezone, provide in America/Chicago format
                [ -n "$2" ] && tz=$2 || missing_param "$@"
                shift 2
                ;;
            -w|--wlan-country)
                [ -n "$2" ] && wlan_country="${2^^}" || missing_param "$@"
                shift 2
                ;;
            --locale)  # do_locale() in update.sh will run if locale has value
                [ -n "$2" ] && locale=$2 || missing_param "$@"
                shift 2
                ;;
            --us)
                locale=us
                wlan_country=us
                shift
                ;;
            -p|--passwd) # consolepi user's password
                [ -n "$2" ] && consolepi_pass=$2 || missing_param "$@"
                shift 2
                ;;
            -L|--auto-launch)
                auto_launch=true
                shift
                ;;
            # -- \silent install options --
            -h|-*help)
                show_usage $2
                exit 0
                ;;
            *) # -*|--*=) # unsupported flags
                echo "Error: Unsupported flag passed to process_args $1" >&2
                exit 1
                ;;
        esac
    done

    if [ -n "$_branch" ]; then
        branch=$_branch
    elif $local_dev; then
        branch="dev"
    fi

    # -- Set defaults applied when using silent mode if not specified --
    $silent && btmode=${btmode:-serial}
    $silent && auto_launch=${auto_launch:-false}
    $silent && wlan_country=${wlan_country:-US}
}

main() {
    script_iam=`whoami`
    if [ "${script_iam}" = "root" ]; then
        set +H                              # Turn off ! history expansion
        cmd_line="$@"
        # original loc for do_safe_dir
        process_args "$@"
        get_common                          # get and import common functions script
        [ -n "$cmd_line" ] && logit -L -t "ConsolePi Installer" "Called with the following args: $cmd_line"
        get_pi_info                         # (common.sh func) Collect some version info for logging
        remove_first_boot                   # if auto-launch install on first login is configured remove (consolepi-image)
        do_users                            # USER INPUT - create / update users and do staged imports
        do_apt_update                       # apt-get update the rpi
        do_apt_deps                         # install dependencies via apt
        do_safe_dir                         # Ensures /etc/ConsolePi is git safe.directory
        pre_git_prep                        # UPGRADE ONLY: process upgrade tasks required prior to git pull
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

main "$@"
