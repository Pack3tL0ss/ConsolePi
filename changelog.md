# CHANGELOG

## Oct 2024 (v2024-3.4 installer v83)
  - :pushpin: pin cryptography they've pushed a release with failed build (43.0.3 failes build on piwheels)
  - :bookmark: Installer v83
    - ✨ add flag for installer to skip bluetooth setup
    - ✨ show model info for non rpi if possible
  - :speech_balloon: Simplify `consolepi-status` output.
  - :memo: Documentation updates/improvements


## Oct 2024 (v2024-3.3 installer v82)
  - :bug: ensure /run/dnsmasq dir exists, needed for hotspot dhcp
  - :ambulance: Fix ipv4 method for hotspot in template / enable network sharing.
    - 🐛 2 listed above resolves WiFi Networking issues #210
  - :wrench: Set hotspot IPv6 method based on no_ipv6 option.
  - :memo: Update GPIO UART setup with paths from Bookworm
  - :speech_balloon: adjust text alignment in Predicable console ports message
  - :memo: :tada: prep docs for readthedocs
  - :memo: :bug: add emoji support for sphinx
  - :memo: :art: Add more ConsolePi's in action
  - :speech_balloon:  Add more color to output
  - :bug: add --no-cache-dir to pip install-U commands, to prevent cache with outdated hash.  Resolves Error HASH not match from the requirements file #195
  - :bug: fix additional user prompt displaying during silent install
  - :pushpin: restrict aiohttp dep to 3.10.9- 3.10.10 currently does not have wheel for armv6l (pi zero).
    - Updates in 3.10.10 don't impact us, takes too long to build and often fails on pi zero.
  - :recycle: use existence of noipv6 sysctl file to determine v6_method for hotspot
  - - consistent with others, and don't think no_ipv6 is available during upgrade.
  - :memo: update README, update path for ttyAMA config within example to reflect bookworm path.
  - :sparkles: `consolepi-image`: Add ser2net.yaml as stage file when mass import from existing ConsolePi
  - :sparkles: installer: set ipv6 method in NM templates based on "disable ipv6" option during install.
  - :construction: Testing ConsolePi as a pypi package
  - :bookmark: make version static in pyproject.toml
  - :arrow_up: Add deps to pyproject.toml


## Feb 2024 (v2024-3.0 installer v80)
✨ Large update!!

*The release of Raspberry Pi OS 12 (bookworm) included a change to use NetworkManager to manage the network.
That broke all network based automations (PushBullet notifications of IP change, cloud sync after IP change, Automatic VPN, Auto fallback to hotspot, and ZTP (fallback to static wired w/ DHCP))*

Here is a summary of what's in this release:
  - ✨ Restore all network based automations.
  - ✨ Various improvements in network automation/dispatcher script.
  - ✨ Dynamically determine interface names throughout.  (primarily of benefit for non rpi systems)
  - ✨ Various installer improvements.
  - 🐛 Fix optional utilities part of installer / `consolepi-extras` .  Specifically speed-test (already merged) and ansible/ansible collections.
  - ✨ Change method of installing ansible, new method provides more recent version of ansible.
  - ➖ Strip requirements.txt to only direct dependencies
  - ✨ handle deletion of ser2net.conf file after consolepi daemons have started (typically in favor of ser2net.yaml)
  - ✨ Add proc_ids to identify rpi 5
  - ✨ Improve logic that determines if speed-test should be hidden in utilities/`consolepi-extras` menu.
    > speedtest is hidden for platforms it doesn't make sense on, i.e. everything prior to rpi4 as the eth NIC would be the limitting factor in any speedtest
  - ✨ Improve `consolepi-btconnect` Now shows "not found error" when device isn't found and has `--list` and `--help` command line options.
  - 🧑‍💻 Add `--no-user` option to `consolepi-installer` primarily to speed repeated testing during development.
  - ✨ Add --branch option to installer (to install from a branch other than master)
  - ✨ Various improvements to `consolepi-image`
  - ✨ Deprecate/remove ConsolePi_cleanup sysv script, and deploy consolepi-cleanup systemd (consistency)
  - ✨ Updated `consolepi-autohotspt` to work with NetworkManager (now works with both legacy or bookworm+ installed systems).

## Jan 2024 (v2024-1.0)
  - Change how python3-virtualenv is installed (pip --> apt) per PEP 668.

## July 2023 (v2023-6.1)
  - ✨ `consolepi-menu` will now show remote ConsolePis that fail API but are reachable via SSH (in remote shell menu)
  - ✨ Enhance consolepi-status now has `-R` (reload consolepi services) and `-B` (brief) options
  - ✨ consolepi-showaliases now works with ser2net v3 or v4
  > Will use ser2net v4 config (if found) only if ser2net v3 config doesn't exist.


## July 2023 (v2023-6.0)
  - :sparkles: Add full support for ser2netv4 add/change/rename via rename(`rn`) option in the menu, and the `consolepi-addconsole`.
  - :sparkles: Add `consolepi-convert` command, which will parse an existing ser2netv3 config (`/etc/ser2net.conf`) and create/update a ser2netv4 config (`/etc/ser2net.yaml`)
  - :zap: Convert remote ConsolePi updates to async (they were already using threading)
  - :zap: Convert remote ConsolePi updates to async (they were already using threading)
  - :loud_sound: Update Spinner with the name of the remote as reachability is being check for remote ConsolePis.  Make failures persistent (spinner shows what failed and continues one line down.)
  - The various consolepi-services that run as daemons (for remote discovery) now display a descriptive process name (i.e. when running `top` and the like) vs generically `python3`
  - :construction: (Requires manual setup for now see issue [#119](https://github.com/Pack3tL0ss/ConsolePi/issues/119))  Add ability to ssh directly to an adapter specifying adapter by name
    - i.e. `ssh -t <consolepi address> -p 2202 <device name>`
    - real example `ssh -t consolepi4 -p 2202 r1-8360-TOP` will connect to the defined udev alias `/dev/r1-8360-TOP` connected to remote ConsolePi ConsolePi4 (you could use ip vs hostname)
    > The examples uses a predictable device name (`r1-8360-TOP`) vs. the default /dev/ttyUSB# Use consolepi-addconsole or the rename(`rn`) option in `consolepi-menu` to discover and apply predictable names to connected serial adapters.
    - This feature retains power-control, so if `r1-8360-TOP` has an outlet linked to it, connecting to the device will automatically verify the outlet is on, and turn it on if not.  See [Power Control Setup](readme_content/power.md#power-control-setup) for more details.
    - This is a work in progress.  The sshd config still needs to be automated but can be manually created.  Just place the following in a new file /etc/ssh/sshd_config.d/consolepi.conf and restart ssh `systemctl restart ssh`
    ```shell
    Port 22
    Port 2202
    AddressFamily any
    ListenAddress 0.0.0.0

    Match LocalPort 2202
        ForceCommand /etc/ConsolePi/src/remote_launcher.py $SSH_ORIGINAL_COMMAND
    ```
    - In future release additional flags will be passed on to picocom i.e. `ssh -t <consolepi address> -p 2202 <device name> [any flags picocom supports]`
    - :bangbang: The `-t` option is crucial, otherwise there is no tty which causes strange behavior in the terminal (tab completion via the connected device among other things break).  Will research if there is a way to attach it on the server side.

## June 2023 (v2023-5.0)
  - ser2netv4 Parsing.  Rename is not refactored yet, but parsing the baud rate from defined adapters now works with ser2netv3 and ser2netv4.
    - Rename still functional if still using ser2netv3
    - If ser2netv4 is installed but the ser2netv3 config file still exists (`/etc/ser2net.conf`).  ConsolePi will continue to use the v3 config for parsing.  This is to allow time for manual conversion to the v4 format (`/etc/ser2net.yaml`)
  - Fix issue introduced in v2022-4.x (which should have been v2023-xx.yy).  Issue relates to handling optional requirement for RPi.GPIO module.
## Sep 2022 (v2022-3.0)  **Breaking Change for silent installs**
  - Changed cmd-line flags for `consolepi-image` and `consolepi-install`/`consolepi-upgrade`.  Use `--help` with those commands to see the changes.
    - This is a breaking change for silent install.  If using an install.conf file refer to the new example as some varirables have changed.
  - Re-worked `consolepi-image` script ([consolepi-image-creator.sh](installer/consolepi-image-creator.sh)) to configure consolepi as the default user on the image.
    - This is necessary for headless installs, as there is no default pi user anymore.
  - Updated installation script... worked-around some dependencies that required rust build environment.
  - Various other improvements to both of the above mentioned scripts.
## Nov 2021 (v2021-1.5)
  - Fix: RPI.GPIO set to use 0.7.1a4+ to accommodate known issue with python3.9 (bullseye default)
  - Fix: bluetooth.service template updated for bullseye (dynamically handles both bullseye where exec path changed and prev rel)
  - Enhancement: New OVERRIDE `api_port` actually merged previously is now documented in ConsolePi.yaml.example
  - Enhancement: New OVERRIDE `hide_legend` will hide the legend by default in the menu (`consolepi-menu`).  `TL` in the menu will restore it.
  - Documentation: `ConsolePi.yaml.example` Now has all of the supported OVERRIDES listed with the default value and description.
## Feb 2021 (v2021-1.2)
  - Fix: new menu and options from previous commit broke baud rate change during rename.
  - Fix: A remote with no local adapters would fail to launch rename (to rename an adapter on a remote another remote ConsolePi)
  *Next commit will add support for custom port for the API on a per ConsolePi basis.*
## Feb 2021 (v2021-1.1)
  - Fix: dhcpcd.exit-hook had an issue that impacted shared vpn on wired, a previously undocumented feature.
  - Fix: menu item mapping, when a refresh resulted in an additional adapter being added.
  - Enhancement: Expose previously hidden 'tl' and 'tp' menu items.
  - Enhancement: Display current tty size when connecting to a serial or TELNET device.
    >Handy when connecting to a device that needs the terminal adjusted to use the full display size.
## Jan 2021 (v2021-1.0) **DHCP based Automation Enhancements**
  - Fix an issue that was overlooked, where AutoHotSpot is *not* selected and wired-dhcp is.
  - Improve the way PushBullet Notifications are constructed/sent.
  - Add Additional Test flags to `consolepi-pbtest`
  - ovpn_share: true|false option in OVERRIDES of config = share VPN connection with wired devices when utilizing wired-dhcp (wired fallback to DHCP, where the uplink is the wlan.  ConsolePi will configure wired traffic to NAT out wlan, this option will do the same for OpenVPN tunnel if there is one established.).  This was added to test the functionality, it will eventually end up as a config option.

> There were a lot of other minor tweaks throughout during this time frame.  Review commit log for details.
## Sept 2020 (v2020-4.5)
- Bypass ssh private key import logic for daemons
- mv ttyAMA rules to common rules file (initially deployed to it's own rules file)
- Additional rename error prevention (don't add new alias to ser2net if already mapped)

## Sept 2020 (v2020-4.4)
- Added support for host specific ssh private key for [Manual Host Entries](#configuring-manual-host-entries).
- Added gpiofan and associated systemd unit file for Variable Speed fan control
  - I'll document the optional scripts in the near future.
- minor typo fixes, linter clean-up, etc
- more error prevention in rename (no rename to alias that's aready in use, no rename to alias that starts with sys root_dev prefix)

## Sept 2020 (v2020-4.3) Installer Version 53 Sept 2020 Lots of Installer Tweaks
- This effort was primarily around the Installer and the Image Creator.
- Installer: Tested, re-tested, made enhancements/improvements, added more imports
- Place home/pi home/your-user /root etc. in consolepi-stage dir and run image-creator...
  - Image Creator will import home/pi into home/pi on the image, entire directory structure.  Same for /root.
  - Once the installer runs on the image it will also import /home/pi (redundant, but useful if you don't use the image-creator)
  - Installer also prompts to see if you want to create new users, once created if in the consolepi-stage dir it's structure will be imported
> So you can import .ssh keys / known_hosts and any other files/dirs you want in the users home.

## Sept 2020 (v2020-4.2) Sept 2020 Bug Fix
- Fixes issue introduced with changes made in v2020-2.4 (technically it was a merge after v2020-2.4)
- That release introduced a change where a consolepi user is created vs. just a consolepi group. You were to be given the option to auto-launch menu for that user.
  - Neither prompt was shown, but the user was created, and auto-launch enabled.  The bug resulted in no user input being requested.
  - Additionally AutoHotSpot was added as a configurable option, but the prompt didn't display.  All of these worked via cmd-line option/silent install.
  > If you did a fresh install w/ any version from v2020-2.4 - v2020-4.2 you are likely impacted.  Just use `sudo passwd consolepi` to set the password as desired.

## Sept 2020 (v2020-4.1) Sept 2020 Bug Fix
- Fixes a bug that would result in all the optional sections from the example config being populated in the resulting default config.  If You've done a recent install this is why there were some hosts in the menu that you didn't configure.

> If you've installed in the last few months, you can clean out the results of the bug by checking your ConsolePi.yaml and deleting everything below the CONFIG: section (OVERRIDES, POWER, HOSTS... essentially anything past the 'debug:' line)

## Oct 2020 (v2020-5.0) *MAJOR Update!* Posted Jan 2021
  - **Paging Support in Menu:**
    The previous Menu supported some formatting (would build columns to utilize space more efficiently).  It lacked support for Paging when the menu content was too much for a single screen given the terminal size.  The old menu would just overrun, causing word-wrap.
    **The New Menu Library** now supports paging.  Pages will dynamically adapt to terminal size, even if you re-size after launching the menu.  Default menu-options at bottom of menu now take less space (split into to columns)
    ***I don't want to talk about the asinine amount of time I spent working out the logic for this… and there is more to come.***
> The lag in posting this update was an attempt to re-write the re-write, or make it more elegant.  In the end I decided I should get the repo current, and create a new branch for further enhancing the menu.

  > If you have suggestions on different ways to accomplish this, how to organize the menu-formatting module [menu.py](src/pypkg/consolepi/menu.py), etc.  let me know.  I'm absolutely more than happy to leverage an existing module, but I was unable to find one with the flexibility I wanted (custom item numbering/prefixes, etc)
  -  A couple of other menu options (some already existed, but were hidden options):
      - sp: Show Ports (main-menu & rename-menu: currently still hidden in main-menu).  Switches from the default of displaying the connection settings (baud...) to showing the configured TELNET port for the device.
      - rl (RL): (main-menu).  This is a hidden option, if you don't use cloud-sync r and `rl` are equivalent.  For those that do use cloud-sync, `rl` refreshes detected adapters, and does a refresh from locally cached data.  It doesn't sync with the cloud, just re-checks reachability for all cached remotes.

## Sept 2020 (v2020-4.0) Sept 2020 *Major Update*
- Major Feature add is ZTP-Orchestration and wired DHCP (fallback if no address recieved from any DHCP servers)
  - ConsolePi supports Zero Touch Provisioning(ZTP) of devices via wired ethernet/DHCP.  The feature uses DHCP to trigger ZTP, and supports config file generation using jinja2 templates.  For more details see [`ConsolePi ZTP Orchestration`](reademe_content/ztp.md).
- Fix bug with legacy digital loggers power controllers, failures would occur after the session expired, session is now being renewed when necessary.  This did not impact newer dli power controllers that support REST API.
- Removed `apt upgrade` from `consolepi-upgrade`.  ConsolePi will only install/verify/upgrade packages related to it's operation.  Up to the user beyond that.

## June 2020 v2020.2.4+ (current master ~ not pkgd into a release) significant installer improvements
  - Support silent install facilitating automated deployment via Ansible
  - installer creates consolepi user and offers to make it auto-launch menu on login (prev ver created a consolepi group)
    - This is only for new installs Upgrades are not impacted.
  - consolepi-image-creator supports mass import if ran from a ConsolePi

## May 2020 v2020.2.3 minor release
  - Fix consolepi-details in some scnearios relaating to existence of outlets in config.
  - Fix configuration parsing of yaml for bools, and related nooff setting for outlets
  - Minor Formatting improvements to consolepi-showaliases

## May 2020 v2020.2.2 minor release
  - The feature was fixed for many use-cases in v2020.2.1, but I discovered issues in some scenarios when a hub was used.  That logic was improved so mapping "lame" adapters to a specific port should now work consistently regardless of the use of hub(s).

## APR 2020.2.1 minor release
- Most Significant Change is addition of support for espHome flashed outlets
- Added Support for local UARTs.  The Pi4 actually has 6 UARTs (5 are useable), ConsolePi now supports those onboard UARTS (they will show in the menu).  See the [Local UART support (GPIO)](#local-uart-support) section for details.
- Fixed minor issue with keyboard update to US when regulatory domain for hotspot for WLAN is set to US, issue was if user opted to not enable AutoHotSpot (a new option in last release), reg domain wasn't used but was defaulted to US.
- Fixed Show/Hide Linked devices toggle in Power Menu for dli and espHome.  Now correctly displays just what is linked to that specific port (was showing all linked to any port on that dli/espHome device).  Also fixed display of locally defined hosts (TELNET/SSH hosts defined in ConsolePi.yaml), so they appear if linked as well.
- Enhanced the Show/Hide Linked devices toggle to show any adapters defined, vs. previously only showing if the adapter was actually connected. If your terminal client is configured to honor ASCII coloring linked adapters that are disconnected will appear in red (Only applies to adapters, connevtivity is not verified for TELNET/SSH hosts configured in ConsolePi.yaml).
- Fixed issue with rename function for adapters that don't present a serial #

## APR 2020 *Biggest Update since original Posting*
- This update was primarily an exercise in code organization (more work needs to be done here, learning on the fly a bit), breaking things up, but a lot of features were added in the process
- Configuration File format/file changed from ConsolePi.conf to ConsolePi.yaml all configuration including optional outlets and manually defined hosts should be configured in ConsolePi.yaml
    - During the upgrade ConsolePi.conf settings are converted for you.  power.json and hosts.json if they exist are not converted, those settings *should* still work, but very little testing is done with the old file formats so user is warned during upgrade and should change to the new format
- The rename function for adding / changing adapter names (udev rules and connection settings) overhauled, and now works for remote adapters.
- hosts function has additional features, you can group hosts, and determine what menu they will display in:  show_in_main: true and they will show in the main menu along with available adapters discovered locally and/or on remotes otherwise they will show in the rshell menu.
- Outlet auto-pwr-on shows more detail about linked outlets when auto-pwr-on is invoked for a remote
- Auto-Pwr-on works for manually defined hosts.  If it fails the initial connection it will check-wait-repeat to see if the host has booted if the initial state of the outlet was OFF, then attempt to re-connect automatically.
- The power menu has a toggle option to show/hide associated linked devices/hosts (only connected linked devices show up, but any defined host linkage will show)
- AutoHotSpot now runs it's own instance of dnsmasq and does not get it's config from dnsmasq.conf or /etc/dnsmasq.d - allows custom dnsmasq setup for other interfaces without conflict
- The I broke shit fallback:  consolepi-menu will provide a prompt to launch into the simplified backup menu if the menu crashes.  I catch most exceptions, but occasionally a scenario comes up I failed to accomodate, if that happens so you're not dead in the water re the menu it will offer to launch the backup... The backup is fast and simple, and has essentially no dependencies, but it only supports local adapters (not remotes, hosts, outlets, etc)
- The local shell option is no longer.  The menu now directly supports valid shell commands, so if you want to ping a device without exiting and re-launching you can just type `ping 10.0.30.51` from the menu prompt and it will work.
- Added support for more OVERRIDE options in ConsolePi.yaml.  These options change the default behavior of ConsolePi i.e. 'cloud_pull_only: true'.  Will retrieve from cloud but won't update the cloud with it's information... That one is useful for the feature below:
- ConsolePi can now be deployed to non RaspberryPis with minimal effort, including Windows Subsystem for Linux (because why not).  See more detailed explanation and install options below.
- There is more stuff but I can't recall all of it... the [picture](#feature-summary-image) below hightlights the bulk of the feature set.

## JAN 2020 *MONSTER Update*
- Additional improvements to in menu rename function / `consolepi-addconsole`
    - Added support for adapters that don't have a serial #, this was added prior, but would actually crash the menu (oops), I finally found a crappy adapter that lacks a serial # to test with as a result that function should now work.  It will be a compromise, essentially it will either need to be the only adapter of that kind (modelid/vendorid) or always be plugged into the same USB port.
    - Added a connect option in the rename menu (So you can connect to the adapter directly from that menu... useful if you need to verify what's what.)
- `consolepi-extras` or the Optional utilities menu presented during the install/upgrade further enhanced
    - This installs/uninstalls optional packages useful for many ConsolePi users.
        - ansible: Changed to use a different ppa to source the package, vs the default raspbian repo
        - Aruba ansible modules: Added option to install modules for networking products from Aruba Networks.
        - SpeedTest: Added An HTML 5 speed Test https://github.com/librespeed/speedtest. This option will only be available on Pi 4 models (makes little sense on anything older)
        - cockpit: Provides a Dashboard to monitor the ConsolePi, as well as a web based tty.
          > Making network configuration changes via Cockpit may conflict with the AutoHotSpot function
- dhcp server process (dnsmasq) for autohotspot is now a unique process just for wlan0, this allows you to have a separate process for the wired port without impacting the hotspot.  wired-dhcp will be a configurable option in a future build, an example systemd file for a separate dnsmasq process bound to the wired port is in /etc/ConsolePi/src/systemd
- ConsolePi_image_creator script which is used to prep an SD card for a headless ConsolePi install re-worked / improved, had to back down some ciphers no longer allowed by curl to match the raspberrypi.org cert (the script will pull the latest image if not found in the script dir).
- API changed to fastAPI for those that are on Raspbian Buster (Python 3.6+ is required), for systems running with python 3.5 or prior the current API remains.  FastAPI adds a swagger interface to ConsolePi.  The API will continue to be improved in future releases.
- Changed remote connectivity verification to use the API rather than attempting a socket connection on the SSH port.  This ensures both connectivity and that the adapter data presented in the menu for the remote is current.
- Added support for manually configured hosts (additional TELNET or ssh hosts you want to show up in the menu).  These are configured in hosts.json and support outlet linkage in the same way serial adapters do.  Just be sure the all names are unique.  This works, but needs some minor tweaks, when ssh to some devices the banner text is actually sent via stderr which is hidden until you exit the way it's setup currently.
- The **major** part of the work in this build was to make menu-load more async.  Verification of remote connectivity is now done asynchronously each remote is verified in parallel, then the menu loads once they are all finished.  The same for power control if tasmota or dli outlets need to be queried for outlet state, this is done in the background, the menu will load and allow those threads to run in the background.  If you go to the power menu prior to them being complete, you'll get a spinner while they finish.  All of this results in a much faster menu-load.  Auto Power On when connecting to devices/hosts with linked outlets also occurs in the background on launch.
- Plenty of other various tweaks.

## DEC 2019 *Major Update*
- refactored the menu formatter.  When multiple ConsolePis are clustered it will populate the colums in a more intuitive way
    > This is still evolving, but an improvement.
- Completely Replaced consolepi-addconsole function with more capable option which is also available in the menu
    - Accomodates a couple of problematic adapters.  Multi-Port pig-tail with a single serial # and adapters that lack a serial #
        however the latter is not tested yet, and it's a compromise, that essentially maps the USB port (any serail adapter plugged into the port would
        use the assigned alias)
- FIX TTY SIZING!! Prior to this update, if the device you connect to resized the terminal smaller than your native tty size you were stuck with that after disconnecting until you resized manually using stty or a similar mechanism.  That is no longer necessary, on exit of any serial session the display is automatically resized based on the terminals available rows/cols.
- Optional Utilities Selector presented during consolepi-install / consolepi-upgrade
    - This installs/uninstalls optional packages useful for many ConsolePi users.
    The packages currently included:
        - tftpd: (with ability to read/write), this actually was there prior, but moved to this new menu
        - lldpd: this is useful as another mechansim to get the IP of the ConsolePi by querying the switch you've plugged it into.
        - ansible: Useful if you want to tinker with Ansible.  Not configured yet, the script just installs it.

## NOV 2019
- New rename function directly from menu.  Rename adapters already defined by `consolepi-addconsole` (or manually) or adapters that have never been defined.

## Sept 2019 *Major Update*
-  Menu will now allow user to purge host key from known hosts and retry connection when connecting to a remote ConsolePi who's SSH key has changed.
-  Menu Auto-sizing with multiple cols based on terminal size.  Currently will place multiple remotes in different Cols if warranted (still 1 col if enough space vertically).
- Added Support for Digital Loggers Web Power Switches (both the newer ones with API and older models).  Separate menu for DLI outlets, the existing power menu remains for linked outlets (The existing power menu will evolve, still considering best options for how to display defined but not linked, different types, etc.)
- Incorporated spinners from [Halo](https://github.com/manrajgrover/halo) during load and update operations.
- Any information or error messages now display in an information pane that populates the bottom of the menu if any errors are encountered
- Changed URI for a couple of API methods (so all match the key field in the dict they reference)
- lots of other little tweaks

## AUG 2019 *Major Update*
- remote connections are now established through proxy script, which will prompt/kill a previous hung session.
    - Bonus, the proxy script also adds support for auto-power-on for devices linked to outlets on the remote system (having them appear in a power sub-menu will come later once I build out the API further)
-  Added override function for most system files involved... So Custom system files won't be backed up and replaced during `consolepi-upgrade`
-  Added option to install and configure a tftp server.
- ConsolePi remote discovery via mdns, or sync to Google Drive
- Power Outlet Control, via relay attached to GPIO or network connected tasmota flashed wifi smart-outlet.  Power on automatically when attempting to connect to console session (via `consolepi-menu`), or toggle via power sub-menu (`consolepi-menu`)
- consolepi-menu adapter connection parameters (baud, flow, parity, data-bits) are now extracted from the associated definition in ser2net.conf if one exists, if it doesn't defaults are used (which can be changed via menu option c)
- Added new option 's' to menu which allows you to connect to the shell on any reachable remote ConsolePis
- Added new quick commands and an option to delete a remote ConsolePi from the local cloud cache via ```consolepi-remotes```