# ConsolePi

Acts as a serial Console Server, allowing you to remotely connect to ConsolePi via Telnet/SSH/bluetooth to gain Console Access to devices connected to local **or remote** ConsolePis via USB to serial adapters (i.e. Switches, Routers, Access Points... anything with a serial port).

***TL;DR:***
Single Command Install Script. Run from an internet connected RaspberryPi running RaspiOS (ideally a fresh image).  *See [Known Issues](#known-issues) regarding changes in Raspberry Pi OS 12(bookworm).*

```bash
wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/install.sh -O /tmp/ConsolePi && sudo bash /tmp/ConsolePi && sudo rm -f /tmp/ConsolePi
```

![consolepi animated Demo](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/main-demo.gif)


>*Making multiple ConsolePis?  Want to re-image, but pull-over all of your existing configs?  Check out the [image creator](#3-consolepi-image-creator)!!!*

------
<!-- prettier-ignore-start -->
# Contents
- [Known Issues](#known-issues)
- [What's New](#whats-new)
- [Planned Enhancements](#planned-enhancements)
- [Features](#features)
  - [Serial Console Server](#serial-console-server)
    - [Guidance on LAME USB to RS232 adapters](#guidance-on-lame-usb-to-rs232-adapters)
  - [AutoHotSpot](#autoHotSpot)
  - [Automatic VPN](#automatic-vpn)
  - [Automatic PushBullet Notifications](#automatic-pushbullet-notification)
  - [Automatic Wired DHCP Fallback](#automatic-wired-dhcp-fallback)
  - [Clustering / Cloud Sync](#consolepi-cluster--cloud-sync)
    - [Supported Cluster Methods](#supported-cluster-sync-methods)
      - [Google Drive](#google-drive)
      - [mDNS / API](#mdns--api)
      - [Manual](#local-cloud-cache)
  - [Power Outlet Control](#power-control)
  - [Manual Host Entries](#manual-host-entries)
  - [ZTP Orchestration](#ztp-orchestration)
  - [ConsolePi Restful API](#consolepi-api)
  - [ConsolePi Extras](#consolepi-extras)
- [Installation](#installation)
  - [Automated Installation](#1-automated-installation)
    - [Silent Install](#silent-install)
  - [Semi-Automatic Install](#2-semi-automatic-install)
  - [ConsolePi Image Creator](#3-consolepi-image-creator)
  - [Alternative Hardware Installs](#alternative-hardware-installs)
- [ConsolePi Usage](#consolepi-usage)
  - [Configuration](#configuration)
    - [menu sorting and connection settings](#consolepi-menu-sorting-and-connection-settings)
    - [Manual Host Entries](#configuring-manual-host-entries)
    - [Local UART support (GPIO)](#local-uart-support)
    - [Power Control Setup](readme_content/power.md#power-control-setup)
      - [GPIO Connected Relays](readme_content/power.md##gpio-connected-relays)
      - [espHome flashed WiFi Smart Outlets](readme_content/power.md##esphome-flashed-wifi-smart-outlets)
      - [Tasmota flashed WiFi Smart Outlets](readme_content/power.md##tasmota-flashed-wifi-smart-outlets)
      - [DLI Web/Ethernet Power Switch](readme_content/power.md##dli-webethernet-power-switch)
    - [ZTP Orchestration](readme_content/ztp.md)
    - [OVERRIDES](#overrides)
  - [Console Server](#console-server)
    - [TELNET](#telnet)
    - [SSH / BlueTooth (`consolepi-menu`)](#ssh--bluetooth)
  - [Convenience Commands](#convenience-commands)
- [Upgrading ConsolePi](#upgrading-consolepi)
- [Tested Hardware/Software](#tested-hardware--software)
- [ConsolePi @ Work! (Image Gallery)](#consolepi-@-work)
- [Credits](#credits)
<!-- prettier-ignore-end -->
------


# Known Issues

- :bangbang: *Not an issue, but a breaking change in ser2net if you've upgraded.*  Bullseye updates the ser2net available from the package repo from 3.x to 4.x this is a significant change.  Functionality wise it's a very good thing, ser2net 4.x brings a lot more flexibility and connectivity options, but it means if you already have aliases that were configured (via `consolepi-addconsole` or the rename(`rn`) option in `consolepi-menu`) against the ser2net v3 config `/etc/ser2net.conf`... Those are no longer what ser2net uses for the TELNET connections.

  Good news though.  As of v2023-6.0 the various options mentioned above for adding/updating/renaming adapter aliases now work with the v4 config (`/etc/ser2net.yaml`).  Not only that, but there is now a migration command `consolepi-convert` which will migrate an existing ser2net v3 config to v4.

  if the v3 file still exists, the menu and rename options will continue to use it (it will warn you on menu launch if the v3 config is still in place with ser2netv4 installed).  If you run `consolepi-convert` it will migrate the config, and if ser2net v4 is installed it will stash the old v3 config in the bak dir.

- ser2net v4 config parsing errors: I have seen on multiple occasions ser2net throw parsing errors after bootup.  `systemctl restart ser2net` has resolved it, so it's not an actual file format issue.  Investigating why this occasionally happens.
  The errors look something like this:
  ```shell
    ---------------- // STATUS OF ser2net.service \\ ---------------
  ● ser2net.service - Serial port to network proxy
      Loaded: loaded (/lib/systemd/system/ser2net.service; enabled; vendor preset: enabled)
      Active: active (running) since Tue 2023-07-11 14:34:27 CDT; 1 weeks 0 days ago
        Docs: man:ser2net(8)
    Main PID: 407 (ser2net)
        Tasks: 1 (limit: 2057)
          CPU: 131ms
      CGroup: /system.slice/ser2net.service
              └─407 /usr/sbin/ser2net -n -c /etc/ser2net.yaml -P /run/ser2net.pid

  Jul 11 14:34:28 ConsolePi3 ser2net[407]: Invalid port name/number: Invalid data to parameter on line 361 column 0
  Jul 11 14:34:28 ConsolePi3 ser2net[407]: Invalid port name/number: Invalid data to parameter on line 369 column 0
  Jul 11 14:34:28 ConsolePi3 ser2net[407]: Invalid port name/number: Invalid data to parameter on line 377 column 0
  Jul 11 14:34:28 ConsolePi3 ser2net[407]: Invalid port name/number: Invalid data to parameter on line 385 column 0
  Jul 11 14:34:28 ConsolePi3 ser2net[407]: Invalid port name/number: Invalid data to parameter on line 393 column 0
  Jul 11 14:34:28 ConsolePi3 ser2net[407]: Invalid port name/number: Invalid data to parameter on line 401 column 0
  Jul 11 14:34:28 ConsolePi3 ser2net[407]: Invalid port name/number: Invalid data to parameter on line 409 column 0
  Jul 11 14:34:28 ConsolePi3 ser2net[407]: Invalid port name/number: Invalid data to parameter on line 420 column 0
  Jul 11 14:34:28 ConsolePi3 ser2net[407]: Invalid port name/number: Invalid data to parameter on line 431 column 0
  Jul 11 14:34:28 ConsolePi3 ser2net[407]: Invalid port name/number: Invalid data to parameter on line 442 column 0
  ```
  Again simply restarting the service seems to resolve the issue.  I suspect it may be a race-condition on bootup with the initialization of udev.

# What's New

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

Prior Changes can be found in the - [ChangeLog](changelog.md)

# Planned enhancements
  - Complete automation of feature to provide ssh direct to adapter discussed in [issue #119](https://github.com/Pack3tL0ss/ConsolePi/issues/119)
  - Non RPI & wsl (menu accessing all remotes) support for the installer.  Should work now, but needs further testing.
  - Ability to pick a non sequential port when using `rn` in menu or `consolepi-addconsole`
  - *Most excited about* launch menu in byobu session (tmux).  With any connections in a new tab.
  - Eventually... formatting tweaks, and TUI.  Also consolepi-commands turn into `consolepi command [options]` with auto complete and help text for all (transition to typer CLI).

# Features
## **Feature Summary Image**
![consolepi-menu image](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/ConsolePi_features.jpg)

## Serial Console Server
**This is the core feature of ConsolePi.**
  - Connect USB to serial adapters to ConsolePi (or use the onboard UART(s)), then access the devices on those adapters via the ConsolePi.
  - Supports TELNET directly to the adapter.  Use `consolepi-addconsole` or the rename(`rn`) option in `consolepi-menu` to create predictable alias for a USB to serial adapter (vs the default /dev/ttyUSB0...) and assign the TELNET port associated with it.
  - Connect to ConsolePi via SSH or BlueTooth and select the adapter from `consolepi-menu`.  The menu will show connection options for any locally connected adapters, as well as connections to any remote ConsolePis discovered via Cluster/sync.  The menu has a lot of other features beyond connecting to local adapters, as shown in the image above.
  <!-- - ssh directly to an adapter by connecting via ssh to port 2222 and providing the adapter name i.e. `ssh -t consolepi4 -p 2202 r1-8360-TOP` -->
- When connecting to the ConsolePi via bluetooth, default behavior is to auto-login and launch a limited function menu.  Given this user is automatically logged in, the user has limited rights, hence the limited function menu (allows access to locally attached adapters).
- The `consolepi` user can also be configured to auto-launch the menu on login (option during install), this user doesn't auto-login, so it's created with typical rights and launches the full menu.
> To disable auto-login via Bluetooth, modify /etc/systemd/system/rfcomm.service and remove `-a blue` from the end of the `ExecStart` line.  Then issue the following to create an empty file telling `consolepi-upgrade` not to update the file on upgrade: `touch /etc/ConsolePi/overrides/rfcomm.service`.


### Guidance on LAME USB to RS232 adapters

There are some lame adapters that don't burn a serial # to the chip, this makes assigning a unique name/TELNET port more challenging.  Refer to the [adapters](adapters.md) page for more guidance.

>Spoiler alert, Adapters based on an FTDI chipset FTW!


## AutoHotSpot

This is handled by NetworkManager, but the installer deploys the appropriate config (if you've chosen to enable the feature).  On boot NetworkManager will first look for any configured SSIDs (you need to build those profiles), if it can't find or is unable to connect it will fallback to hotspot.  Any profiles you setup should have an autoconnect-priority=N where N is anything > 0.  Consolpi will also configure DHCP for hotspot clients such that if the ConsolePi has no network reachability (it is isolated) it will not distribute a gateway to hotspot clients.  This is specifically done so you can connect to a ConsolePi that is not network connected (to access connected serial ports) from a PC via a second NIC.  This way it won't compete with your existing default-route (which would black-hole all your traffic).

> If a domain is provided to the wired port via DHCP, and the hotspot is enabled ConsolePi will distribute that same domain via DHCP to clients.

> On systems initially installed prior to Raspberry Pi OS 12 (bookworm) (Uses dhcpcd vs NetworkManager), autohotspot is managed by the `autohotspot` service which runs a script on boot, but functionality is the same.

## Automatic VPN

When an interface receives an IP address ConsolePi will Automatically connect to a VPN server under the following conditions:
- It's configured to use the Auto VPN feature (ConsolePi.yaml)
- A NetworkManager connection profile has been created with `type=vpn`
- ConsolePi is not on the users home network (determined by the 'domain' handed out by DHCP)
- The internet is reachable.

> You need to configure the NetworkManager connection profile for your VPN.  It is best to manually test it using `nmcli con up <connection id>` to verify the configuration.  You may need to include the `--ask` option when you manually test it so NetworkManager will store any secrets involved.  Refer to NetworkManager documentation for more detail.

## Automatic PushBullet Notification

*(Requires a PushBullet Account, API key, and the app / browser extension.)*

When ConsolePi receives a dynamic IP address.  A message is sent via PushBullet API with the IP so you know how to reach ConsolePi.

![Push Bullet Notification image](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/ConsolePiPB1.png)

An additional message is sent once a tunnel is established if the Automatic VPN feature is enabled.

![Push Bullet Notification image](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/ConsolePiPB2.png)

Each Time a Notification is triggered **all** interface IPs are sent in the message along with the ConsolePi's default gateway(s).

## Automatic Wired DHCP Fallback

**Use with caution**

The Wired DHCP Fallback function configures the wired interface of ConsolePi to fallback to static when it fails to get an address as a client via DHCP.  It will then enable a DHCP Server on the wired interface (with the ConsolePi as the gateway for the clients).

This is useful when configuring factory-default devices, or on an isolated staging network.  *Caution should be taken on production networks*.

This function also:
- Configures traffic from the wired interface to NAT out of the WLAN interface if the WLAN has an internet connection. (The reverse of Auto-HotSpot)
- Optionally, with `ovpn_share: true` set in the optional `OVERRIDES:` section of ConsolePi.yaml wired devices will share access to the OpenVPN tunnel if established (via Auto-OpenVPN).
  > NAT & ovpn_share override with the new NetworkManager based automations has not been tested.  iptables is not installed with Raspberry Pi OS 12 (bookworm)

> The [ZTP Orchestration](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/ztp.md) feature will enable wired fallback to static/DHCP Server when you run `consolepi-ztp`.  `consolepi-ztp -end` restores everything to pre-ZTP state.  You do not need to enable it if ZTP is your only need for it `consolepi-ztp` will handle that.

## ConsolePi Cluster / Cloud Sync

The Cluster feature allows you to have multiple ConsolePis connected to the network, or to each other (i.e. first ConsolePi in hotspot mode, the others connected as clients to that hotspot).  A connection to any one of the ConsolePis in the Cluster will provide options to connect to any local serial adapters, as well as those connected to the other ConsolePis in the cluster (via the `consolepi-menu` command).


![consolepi-menu image](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/consolepi-use-diagram.jpg)

**Another look at the menu**

![consolepi-menu image](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/menu.png)

> In this example only 1 adapter is connected locally (menu item 1), Items 2 - 26 are adapters discovered on other ConsolePis on the network. Items 27 - 50 are [Manual Host Entries](configuring-manual-host-entries).


### Supported Cluster Sync Methods:

#### Google Drive:
   > Read The [Google Drive Setup](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/gdrive.md) for instructions on setting up Google Drive and authorizing ConsolePi to leverage the API.
 - Google Drive/Google Sheets is currently the only external method supported.  Given this gets the job done, it unlikely more external methods will be added.

 - The ConsolePi will automatically exchange information with `ConsolePi.csv` in your gdrive under the following scenarios (*all assume the function is enabled in the config*):
  1. When the ConsolePi receives an IP address, and can reach the google API endpoints.

  2. When consolepi-menu is launched and the `'r'` (refresh) option is selected.

  3. When a USB to Serial adapter is added or removed.  (This happens on a 30 second delay, so if multiple add/removes are made in a 30 second window, only 1 update to the cloud will occur, that update will include everything that happened within the 30 second window)

      > Note: The plan is to disable this update scenario in a future release, as we only need address information for the remote, not a full snapshot of the data.  The remote is queried via API to ensure reachability and get the current list of adapters available, so we no longer need that data stored in the cloud.

  >The Gdrive function uses the hostname as a unique identifier.  If all of your ConsolePis have the same hostname only one of them will be synchronized.  **Make Hostnames unique for each ConsolePi**
  >
  >In all of the above a local cloud cache which includes data for any remote ConsolePis pulled from ConsolePi.csv is updated for the sake of persistence and speed.  The local cloud cache is what is referenced when the menu is initially launched

#### mDNS / API
* ConsolePis advertise themselves on the local network via mDNS (bonjour, avahi, ...)

* 3 daemons run on ConsolePi one that advertises details via mdns and updates anytime a change in available USB-serial adapters is detected, a browser service which browses for remote ConsolePis registered on the network, and the API described below.  The browser service updates the local cloud cache anytime a new ConsolePi is detected.

  > The API described [here](#api) comes into play when enough adapters are plugged in, such that the data payload would be over what's allowed via mDNS.  In the event this occurs... well here is an example:  *ConsolePi-A* has a has enough USB to Serial adapters plugged in to be over the data limit allowed via mDNS, the consolepi-mdnsreg service will detect this and fall-back to advertising *ConsolePi-A* without the adapter data.  *ConsolePi-B*, and *ConsolePi-C* are on the network and discover *ConsolePi-A*.  B and Cs consolepi-mdnsbrowse service will detect that the adapter data was stripped and request the adapter data from A via the API.
  >
  >When `consolepi-menu` is launched any remotes in the cache are queried via the API to ensure an up to date listing of available adapters.  If for some reason it doesn't respond to the API a secondary check is done to verify it is listening on the SSH port.  If it fails both it will be listed as unreachable and will not appear in the menu.  If it fails API, but is listening on the SSH port it won't be in the adapter menu (as we didn't get any adapter data), but will show up in the `rs` (remote shell) menu.

#### Local Cloud Cache
  - local cloud cache:  For both of the above methods, a local file `/etc/ConsolePi/cloud.json` is updated with details for remote ConsolePis.  This cache file can be modified or created manually.  If the file exists, the remote ConsolePis contained within are checked for reachability and added to the menu on launch.

 - The rename option in `consolepi-menu` or the `consolepi-addconsole` command supports assignment of custom aliases used to predictably identify the serial adapters with friendly names (udev rules).  If configured these names are used in `consolepi-menu`, the default device name is used if not (i.e. ttyUSB0), but that's less predictable.

 - `consolepi-menu` does not attempt to connect to the cloud on launch, it retrieves remote data from the local cache file only, verifies the devices are reachable, and if so adds them to the menu.  To trigger a cloud update use the `r` refresh option.
  >Note: that ConsolePi will automatically update the local cache file when it gets an IP address, or adapters are added/removed, so the refresh should only be necessary if other ConsolePis have come online since the the menu was launched.  Additionally ConsolePis will automatically discover each other via mdns if on the same network, this will automatically update the local-cache if a new remote ConsolePi is discovered.

 - Read The [Google Drive Setup](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/gdrive.md) for instructions on setting up Google Drive and authorizing ConsolePi to leverage the API.

   #### If you are configuring multiple ConsolePis to use this cluster, you should consider using the [ConsolePi Image Creator](#3.-consolepi-image-creator).  Once You've installed the first ConsolePi, leverage the `consolepi-image` command to pre-stage the micro-sd cards for the other ConsolePis you will be creating.  This script is handy, if duplicating the install across multiple ConsolePis.  It can pre-stage the entire configuration and cut out some install time.

## **Power Control**

The Power Control Function allows you to control power to external outlets.  ConsolePi supports:
  - [digital Loggers](https://www.digital-loggers.com/index.html) Ethernet Power Switch/Web Power Switch (including older models lacking rest API).
  - External relays controlled by ConsolePi GPIO ( Like this one [Digital-Loggers IoT Relay](https://dlidirect.com/products/iot-power-relay) ).
  - [espHome](https://esphome.io) flashed WiFi smart outlets (i.e. SonOff S31).  These are low cost outlets based on ESP8266/ESP32 microcontrollers.
  - [Tasmota](https://blakadder.github.io/templates/) flashed WiFi smart [outlets](https://blakadder.github.io/templates/) These are also esp8266 based outlets similar to espHome.

      > espHome/Tasmota were chosen because it allows for local control without reliance on a cloud service.  So your 'kit' can include a small relatively portable smart outlet which can be programmed to connect to the ConsolePi hotspot.  Then ConsolePi can control that outlet even if an internet connection is not available.
- If the function is enabled and outlets are defined, an option in `consolepi-menu` will be presented allowing access to a sub-menu where those outlets can be controlled (toggle power on/off, cycle).
- Outlets can be linked to Console Adapter(s) (best if the adapter is pre-defined using `consolepi-addconsole` or `rn` option in the menu) or manually defined host connections.  If there is a link defined between the outlet and the adapter/host, anytime you initiate a connection to the adapter/host via `consolepi-menu` ConsolePi will ensure the outlet is powered on.  Otherwise if the link is defined you can connect to a device and power it on, simply by initiating the connection from the menu **Only applies when connecting via `consolepi-menu`**.

    > The power sub-menu **currently** only appears in the menu on the ConsolePi where the outlets are defined (Menu does not display outlets defined on remote ConsolePis).  The auto-power-on when connecting to an adapter linked to an outlet works for both local and remote connections (establishing a connection to an adapter on a remote ConsolePi (clustering / cloud-sync function) via another ConsolePis menu)

### The Power Control Menu
*Defined Outlets will show up in the Power Menu*

![consolepi-menu image](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master//readme_content/powermenu.png)


### Additional Controls for Digital Loggers
*You may have an 8 port digital-loggers web power switch, with only some of those ports linked to devices.  Any Outlets linked to devices will show up in the Power Menu, **All** of the Ports for the DLI (regardless of linkage) will show up in the dli menu*

![consolepi-menu image](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master//readme_content/dlimenu.png)

### Outlet Linkages

Example Outlet Linkage.  In this case the switch "rw-6200T-sw" has 2 ports linked.  Both are on a dli web power switch.  One of the ports is for this switch, the other is for the up-stream switch that serves this rack.  When connecting to the switch, ConsolePi will ensure the linked outlets are powered ON.  *ConsolePi does **not** power-off the outlets when you disconnect.*
```shell

------------------------------------------------------------------------------------
  Ensuring r2-6200T-sw Linked Outlets (labpower2:[1, 4]) are Powered ON
------------------------------------------------------------------------------------

Connecting To r2-6200T-sw...
picocom v3.1
...
```
Refer to [Power Control Setup](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/power.md) for details on how to setup Power Control.

## Manual Host Entries
The Manual Host Entries Feature allows you to manually define other SSH or TELNET endpoints that you want to appear in the menu.  These entries will appear in the `rs` (remote shell) menu by default, but can also show-up in the main menu if `show_in_main: true`.  Manual host entries support outlet bindings (Auto Power On when connecting through the menu).

Refer to [Manual Host Entries](#configuring-manual-host-entries) in the Configuration section foe details on how to configure.

## ZTP Orchestration

ConsolePi supports Zero Touch Provisioning(ZTP) of devices via wired ethernet/DHCP.  The feature uses DHCP to trigger ZTP, and supports config file generation using jinja2 templates.  For more details see [`ConsolePi ZTP Orchestration`](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/ztp.md).

## ConsolePi API

ConsolePi includes an API with the following available methods
> All Are GET methods the default port is 5000, which can be overridden in the config via the `api_port` key in the optional `OVERRIDES` stanza. See [ConsolePi.yaml.example](ConsolePi.yaml.example).

/api/v1.0/
* adapters: returns list of local adapters
* remotes: returns the local cloud cache
* interfaces: returns interface / IP details
* details: full json representing all local details for the ConsolePi

The swagger interface is @ `/api/docs` or `/api/redoc`.  You can browse/try the less common API methods there.

The API is used by ConsolePi to verify reachability and ensure adapter data is current on menu-load.

> The API is currently unsecured, it uses http, and Auth is not implemented *yet*.  It currently only supports GET requests and doesn't provide any sensitive (credential) data.

## ConsolePi Extras
Toward the end of the install, and via `consolepi-extras` anytime after the install, you are provided with options to automate the deployment (and removal for most) of some additional tools.  This is a selection of tools not required for ConsolePi, but often desired, or useful for the kind of folks that would be using ConsolePi.

![`consolepi-extras`](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/consolepi-extras.png)

>Note: speed test (locally hosted browser based speed-test (server)), is only presented as an option for Pi4/CM4+.  Devices prior had a slow ethernet port, so it wouldn't make sense to use them as a speed-test server.

# Installation

If you have a Linux system available you can use [ConsolePi image creator](#3.-consolepi-image-creator)  to burn the image to a micro-sd, enable SSH, mass-import configurations (if ran from a ConsolePi, optional), and PreConfigure ConsolePi settings (optional).  This script is especially useful for doing headless installations.

**The Following Applies to All Automated Installation methods**
> Note Previous versions of ConsolePi supported import from either the users home-dir (i.e. `/home/wade`) or from a `consolepi-stage` subdir in the users home-dir (i.e. `/home/wade/ConsolePi-stage`).  The import logic directly from the home-dir has not been removed, but going forward any new imports will only be tested using the `consolePi-stage` directory for simplicity.

ConsolePi will **optionally** use pre-configured settings for the following if they are placed in the a `consolepi-stage` subdir in the users home folder (i.e. `/home/wade/consolepi-stage`).  This is optional, the installer will prompt for the information if not pre-configured.  It will prompt you to verify either way.  *Imports only occur during initial install not upgrades.*

staged-file import also supports host specific folders within `consolepi-stage`.  The installer will first check if there is a folder that matches the CosnolePis hostname (you can set via the --hostname flag when you run the installer, if it's still the default.).  So if i'm installing on a system already set with the hostname `ConsolePi5` or i've launched the installer with the `--hostname ConsolePi5` option.  Any imports described below found in `consolepi-stage/ConsolePi5` will take precedence over anything found in the root of `consolepi-stage`

**Examples below use `consolepi-stage/...` for brevity but `consolepi-stage/HOSTNAME/...` is valid for all examples**

- ConsolePi.yaml: This is the main configuration file where all configurable settings are defined.  If provided in the `consolepi-stage` dir the installer will ask for verification then create the working config `/etc/ConsolePi/ConsolePi.yaml`

- 10-ConsolePi.rules: udev rules file used to automatically map specific adapters to user defined aliases, which map to specific TELNET ports.  This file is created automatically during the install if you don't skip the *predictable serial port/names* workflow toward the end.  It's also available after the install via the `rn` (rename) option in the menu, or via the `consolepi-addconsole` command.  This is **highly recommended** in most use cases, and is explained further [here](#telnet).

- ser2net.yaml|ser2net.conf: ser2net configuration will be cp to /etc if found in the stage-dir.

- NetworkManager profiles (should be in `consolepi-stage/NetworkManager/system-connections` or in a host specific folder as described above).  Any profiles found will be cp to /etc/NetworkManager/system-connections and ownership permission requirements will be corrected if necessary.

- certificates (EAP-TLS SSIDs) should be pre-staged in `consolepi-stage/cert`, the installer will scan the pre-staged connection profiles, and pre-stage them in the directory defined within the profile.  It will also verify/adjust the permissions on the private key file.

- authorized_keys/known_hosts: If either of these ssh related files are found they will be placed in both the /home/consolepi/.ssh and /root/.ssh directories (ownership is adjusted appropriately).

- Users home directories.  You can pre-stage random files by placing them in `consolepi-stage/home` or in the case or the root user `consolepi-stage/root`.  The installer will import and set ownership for the default consolepi user, root, any users created during the install, and the current user (if happens to be something different).
> When re-imaging a ConsolePi, it's useful to import the users `.ssh` directory so thier ssh keys stay consistent with the previous image.

- rpi-poe-overlay.dts: This is a custom overlay file for the official Rpi PoE hat.  If the dts is found in the stage dir, a dtbo (overlay binary) is created from it and placed in /boot/overlays.  A custom overlay for the PoE hat can be used to adjust what temp triggers the fan, and how fast the fan will run at each temp threshold.
> Refer to google for more info, be aware some apt upgrades update the overlays overwriting your customization.  I use a separate script I run occasionally which creates a dtbo then compares it to the one in /boot/overlays, and updates if necessary (to revert back to my custom settings)

- autohotspot-dhcp(directory): If you have a autohotspot-dhcp directory inside the `consolepi-stage` dir, it's contents are copied to /etc/ConsolePi/dnsmasq.d/autohotspot.  This is useful if you have additional configs you want to use for autohotspot, dhcp-reservations, etc.  The main config for the autohotspot feature `autohotspot` is still managed by ConsolePi.

- wired-dhcp(directory): If you have a wired-dhcp directory inside the `consolepi-stage` dir, it's contents are copied to /etc/ConsolePi/dnsmasq.d/wired-dhcp.  This is useful if you have additional configs you want to use for wired-dhcp, dhcp-reservations, etc.  The main config for the wired-dhcp feature `wired-dhcp` is still managed by ConsolePi.

- ztp(directory): if a `ztp` directory is found in the `consolepi-stage` dir, it's contents are copied to /etc/ConsolePi/ztp.  This is where your template/variable files, and custom_parsers are configured.

- consolepi-post.sh: Custom post install script.  This custom script is triggered after all install steps are complete.  It runs just before the post-install message is displayed.  Use it to do anything the installer does not cover that you normally setup on your systems.  For Example my consolepi-post.sh script does the following:
  - generates certificates for cockpit if it's installed on the system
  - verifies cloud credentials were imported during the install, and if I forgot to pre-stage them it sftps them from another ConsolePi on the network.
  - Installs python3-cryptography used by one of my other scripts that generates EAP-TLS certificates.
  - Pulls various common .bash_aliases and other *stuff* from my NAS.
  - modify /etc/nanorc to my liking

  This is just an optional mechanism to automatically prep whatever it is you normally prep on your systems after the install completes.  The custom Post install script is only executed on initial install, not on upgrade (unless you supply the `-p|--post` flag to `consolepi-upgrade`).

  > Some functions/variables available to the script (will be in the environment) that you could leverage:
  > - $iam (variable) is the user (script is ran as root hence the sudo -u examples above to run a command as the user that launched the installer)
  > - $logit (function) logit "message to log" ["log-level" defaults to "INFO"] *log-lvl "ERROR" results in script aborting if it hits, so don't set the log-lvl to ERROR*

**To enable the Clustering / Cloud-Sync function see the description [above](#consolepi-cluster--cloud-sync) and the prerequisite [Google Drive Setup](readme_content/gdrive.md)  instructions.**

## **1. Automated Installation**

Install RaspberryPi OS on a raspberryPi and connect it to the network.

Use the command string below to kick-off the automated installer.  The install script is designed to be essentially turn-key.  It will prompt to change hostname, set timezone, and set the consolepi users password.  Be sure to checkout the [image creator script](#3-consolepi-image-creator) if doing a headless install, creating multiple ConsolePis, or want to re-image an existing ConsolePi.

```
wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/install.sh -O /tmp/ConsolePi && sudo bash /tmp/ConsolePi && sudo rm -f /tmp/ConsolePi
```

>Command String Breakdown:
>
>`wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/install.sh -O /tmp/ConsolePi` --> Pull current install script from GitHub and place in /tmp/ConsolePi
>
> `sudo bash /tmp/ConsolePi` --> Execute ConsolePi install script with sudo privs
>
> `sudo rm -f /tmp/ConsolePi` --> Remove the install script (script execution is complete at this point)
>
> The `&&` between each command just means the command will execute given there was not an error returned from the previous command.

### Silent Install
A Silent install (Installation runs without prompts) is possible cmd line arguments provided to the installer or a config file, where the path to the config is provided to the installer via the `-C </path/to/config/file.conf>` argument.  A pre configured ConsolePi.yaml should also exist in the `consolepi-stage` dir described above.

Refer to [/etc/ConsolePi/installer/install.conf.example](installer/install.conf.example) for an example config.  This command string will download it to your home dir as install.conf and open it in nano for editing.
```
wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/install.conf.example -O ~/install.conf && nano ~/install.conf
```

> The output below shows `consolepi-upgrade` as the command to launch, the command will be `consolepi-install` on an image created using the [image creator script](#3-consolepi-image-creator).  If neither is the case you would call the installer directly (with sudo) and pass in the args (The [TL;DR](#consolepi) string at the top of this README can be modified to pass in the arguments)

```
wade@ConsolePi-dev:~$ consolepi-upgrade --help

USAGE: consolepi-upgrade [OPTIONS]

Available Options
 -h|--help                               Display this help text.
 -s|--silent                             Perform silent install no prompts, all variables reqd must be provided via pre-staged configs.
 -C | --config <path/to/config>          Specify config file to import for install variables (see /etc/ConsolePi/installer/install.conf.example).
    Copy the example file to your home dir and make edits to use.
 -6|--no-ipv6                            Disable IPv6 (Only applies to initial install).
 -R|--reboot                             reboot automatically after silent install (Only applies to silent install).
 -w|--wlan_country <2 char country code> wlan regulatory domain (Default: US).
 --locale <2 char country code>          Update locale and keyboard layout. i.e. '--locale us' will result in locale being updated to en_US.UTF-8.
 --us                                    Alternative to the 2 above, implies us for wlan country, locale, and keyboard..
 -H|--hostname <hostname>                If set will bypass prompt for hostname and set based on this value (during initial install).
 --tz <tz>                               Configure TimeZone i.e. America/Chicago.
 -L|--auto-launch                        Automatically launch consolepi-menu for consolepi user.  Defaults to False..
 -p|--passwd '<password>'                Use single quotes: The password to configure for consolepi user during install..
    Any manually added users should be members of 'dialout' and 'consolepi' groups for ConsolePi to function properly

The Following optional arguments are more for dev, but can be useful in some other scenarios
 -P|--post                               ~/consolepi-stage/consolepi-post.sh if found is executed after initial install.  Use this to run after upgrade..
 --no-apt                                Skip the apt update/upgrade portion of the Upgrade.  Should not be used on initial installs..
 --no-pip                                Skip pip install -r requirements.txt.  Should not be used on initial installs..

Examples:
  This example specifies a config file with -C (telling it to get some info from the specified config) as well as the silent install option (no prompts)
        > consolepi-upgrade -C /home/consolepi/consolepi-stage/installer.conf --silent

  Alternatively the necessary arguments can be passed in via cmd line arguments
  NOTE: Showing minimum required options for a silent install.  ConsolePi.yaml has to exist
        wlan_country will default to US, No changes will be made re timezone, ipv6 & hostname
        > consolepi-upgrade -silent -p 'c0nS0lePi!'
```

## **2. Semi-Automatic Install**

Alternatively you can clone this repository to /etc manually, then run the install script.  The only real benefit here is it would allow you to `cp ConsolePi.yaml.example ConsolePi.yaml` and make edits to your liking.  If ConsolePi.yaml exists when the installer runs you'll skip a number of user input steps and go straight to verification of the provided settings.

> You still get the option when using the [Automated Installation](#1-automated-installation) to stop the install after a default ConsolePi.yaml is created, allowing you to edit then re-run bypassing input prompts.

```
cd /etc
sudo git clone https://github.com/Pack3tL0ss/ConsolePi.git

- or -

cd /tmp
git clone https://github.com/Pack3tL0ss/ConsolePi.git
sudo mv /tmp/ConsolePi /etc
```

Optionally Pre-Configure parameters, it will result in less time on data-collection/user-input during the install.  Just grab the ConsolePi.yaml.example file from the repo, edit it with your settings, and rename/place in  `~/consolepi-stage/ConsolePi.yaml`

```bash
# example assuming logged in as pi
cd ~
mkdir consolepi-stage
sudo cp ConsolePi.yaml.example ~/consolepi-stage/ConsolePi.yaml
sudo nano ConsolePi.yaml
```
> This example copies the configuration to the stage directory to highlight that function (importing settings from the stage directory), you could also place the configured `ConsolePi.yaml` file in `/etc/ConsolePi`.
>
> *NOTE:* pre-staging only occurs on the initial install, not when using `consolepi-upgrade`.

Configure parameters to your liking then
- `ctrl + o`  --> to save
- `ctrl + x`  --> to exit
- Then run the installer

```bash
sudo /etc/ConsolePi/installer/install.sh
```

## **3. ConsolePi Image Creator**

> !!WARNING!! This script writes RaspberryPi OS to a connected micro-sd card.  This will overwrite everything on that card.  If something doesn't look right STOP.  With that said I've used it 100s of times by now, so image away.

From an Existing ConsolePi:
- Insert the micro-sd card you want to image (USB to micro-sd card adapter)
- Launch Script with `consolepi-image`.
> The script defaults to using RaspiOS-lite.  This can be changed via cmd line argument (see below)

**OR**

Using a Linux System (Most distros should work only requirement is a bash shell ... tested on RaspiOS and Mint) enter the following command:
- `curl -JLO https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/consolepi-image-creator.sh  && sudo chmod +x consolepi-image-creator.sh`
- That will download the image creator and make it executable.
- The image creator supports both command line arguments and a configuration file (where the same settings configurable as cmd line arguments can be configured in file... handy for re-use).
- `curl -JLO https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/consolepi-image-creator.conf` To get the optional conf file for the image creator.  The config file will be automatically imported if it's in cwd (current working directory).

### ConsolePi_image_creator brief summary:

> *The "Stage dir" referenced below is a sub directory found in cwd (your current working directory).  The script looks for the Stage dir which needs to be named 'consolepi-stage' and moves the entire directory to the pi users home directory on the media being imaged.  When the installer runs (on the new ConsolePi) it will automatically import config items from that staging directory.*

The Pre-staging described below is optional, this script can be used without any pre-staging files, it will simply burn a RaspiOS image to the micro-sd, enable SSH, and set the installer to run automatically on boot (unless you set auto_install to false via cmd line arg or config).

```bash
USAGE: consolepi-image [OPTIONS]

Available Options
 -h|--help                               Display this help text.
 -C <location of config file>            Look @ Specified config file loc to get command line values vs. the default consolepi-image-creator.conf (in cwd).
 --ssid <ssid>                           Configure SSID on image (configure wpa_supplicant.conf).
 --psk '<psk>'                           Use single quotes: psk for SSID (must be provided if ssid is provided).
 --wlan-country <2 char country code>    wlan regulatory domain (Default: US).
 --priority <priority>                   wlan priority if specifying psk SSID via --ssid and --psk flags (Default 0).
 --img-type <lite|desktop|full>          Type of RaspiOS image to write to media (Default: lite).
 --img-only                              Only install RaspiOS, no pre-staging will be done other than enabling SSH (Default: false).
 --[no-]auto-install                     image will not be configured to auto launch the installer on first login (Default true).
 --[no-]import                           whether or not to import files from this system to the image, if this is a ConsolePi.  Prompted if not set..
 --[no-]edit                             Skips prompt asking if you want to edit (nano) the imported ConsolePi.yaml..
 -H|--hostname                           pre-configure hostname on image..
 -I|--image                              Use specified image (full path or file in cwd).
 -p|--passwd <consolepi password>        The password to set for the consolepi user..
 --cmd-line '<cmd_line arguments>'       *Use single quotes* cmd line arguments passed on to 'consolepi-install' cmd/script on image.

The consolepi-image-creator will also look for consolepi-image-creator.conf in the current working directory for the above settings

Examples:
  This example overrides the default RaspiOS image type (lite) in favor of the desktop image and configures a psk SSID (use single quotes if special characters exist)
        sudo ./consolepi-image-creator.sh --img-type desktop --ssid MySSID --psk 'ConsolePi!!!'
  This example passes the -C option to the installer (telling it to get some info from the specified config) as well as the silent install option (no prompts)
        sudo ./consolepi-image-creator.sh --cmd-line='-C /home/consolepi/consolepi-stage/installer.conf --silent'
```
```bash
# ----------------------------------- // DEFAULTS \\ -----------------------------------
# ssid: No Default ~ psk ssid not configured if ssid and psk is not provided
# psk: No Default
# wlan_country: "us"
# priority: 0
# img_type: "lite"
# img_only: false
# auto_install: true
# mass_import: Not Set (Will Prompt User)
#    mass_import=true will bypass the prompt and do the import
#    mass_import=false will bypass the prompt and will not perform the import
# edit: Not Set (Will Prompt User)
#    edit=true will bypass the prompt and open the staged ConsolePi.yaml for editing
#    edit=false will bypass, the prompt ConsolePi.yaml will remain as imported
# hotspot_hostname: Not Set (Will Prompt User)
#    edit=true will pre-configure the hostname on the image to match the HotSpot SSID
#    edit=false will bypass prompt and leave hostname as default (raspberrypi)
# --------------------------------------------------------------------------------------
```
**What the script does**
  - automatically pull the most recent RaspiOS image (lite by default) if one is not found in the script-dir (whatever dir you run it from)
    - It will check to see if a more current image is available and prompt for image selection even if an image exists in the script dir.
  - Make an attempt to determine the correct drive to be flashed, and display details ... User to verify/confirm before writing.
  > As a fail-safe the script will exit if it finds more than 1 USB storage device on the system.
  - Flash image to micro-sd card
  - pre-configure default consolepi user via userconf *(RaspiOS no longer boots with a default `pi` user)*
  - Enable SSH (to facilitate headless install)
  > ***if img_only=true the script stops here***

  - The entire stage dir (consolepi-stage) is moved to the /home/consolepi dir on the micro-sd if found in the script dir.  This can be used to pre-stage a number of config files the installer will detect and use, along with anything else you'd like on the ConsolePi image.

    >The installer and image-creator will first look in `consolepi-stage/HOSTNAME` for imports specific to that ConsolePi, then fallback to the root of `consolepi-stage` if no folder matching the hostname exists.  For the image-creator the HOSTNAME would need to be specified via `-H|--hostname` flag.

  - You can pre-configure WLAN by placing NetworkManager connection profiles inside `NetworkManager/system-connections/` directory (within consolepi-stage).   Any pre-staged profiles will be copied to the `/etc/NetworkManager/system-connections` dir on the micro-sd card.  Ownership and permissions, will then be set.  This method supports the typical methods (i.e. PSK) along with EAP-TLS with certificates.  Just place the cert files referenced in the provided connection profile in a `cert` folder inside the stage dir.  *( Only works for a single EAP-TLS SSID or rather a single set of certs )*, the image creator will then move the certs to the micro-sd to the path specified in the provided connection profile.

  - create a quick command `consolepi-install` to simplify the command string to pull the installer from this repo and launch.  If cmd_line= argument is provided to consolepi-image-creator.sh those arguments are passed on to the auto-install.
  - The ConsolePi installer will start on first login, as long as the RaspberryPi has internet access.  This can be disabled with `--auto_install=false`.

    > If you set `--auto_install=false`, `--cmd_line=...` is ignored.  You would specify arguments for the installer manually.
  - If the `consolepi-image` is ran from a ConsolePi, the script will detect that it's a ConsolePi and offer to pre-stage it's existing settings.  If a file has already been pre-staged (via consolepi-stage dir) it will skip it.  It will give you the chance to edit ConsolePi.yaml if pre-staged *(unless you pass in `--no-edit`)*, so you can deploy multiple ConsolePis and edit the specifics for each as you stage them.
  - Entire home directory imports:  If you place /root and/or /home/consolepi inside the consolepi-stage directory.  Those contents/sub-dirs will be imported to the respective users directory on the image.
    - You can even pre-stage a users home directory for a user that doesn't exist.  When the installer runs, you are given the option to create new users.  Once created if a folder is found in consolepi-stage for that user (i.e. `~/consolepi-stage/home/larry`), the contents will be copied from the `consolepi-stage` dir to `/home/larry`.

  The install script (not this image-creator, the installer that actually installs ConsolePi) will look for and if found import a number of items from the consolepi-stage directory.  Gdrive credentials, ovpn settings, ssh keys, udev rules, ser2net config...

**This capture highlights what the script does and what it pulls via mass import if ran from an existing ConsolePi**

> If ran from a ConsolePi there is a convenience command `consolepi-image`.  It can also be run from other Linux based systems by cloning this repo and running it directly with elevated privileges i.e. `sudo installer/consolepi-image-creator.sh`

```bash
wade@ConsolePi8:~$ consolepi-image -C consolepi-stage/ConsolePi8/consolepi-image-creator.conf
   ______                       __     ____  _
  / ____/___  ____  _________  / /__  / __ \(_)
 / /   / __ \/ __ \/ ___/ __ \/ / _ \/ /_/ / /
/ /___/ /_/ / / / (__  ) /_/ / /  __/ ____/ /
\____/\____/_/ /_/____/\____/_/\___/_/   /_/
  https://github.com/Pack3tL0ss/ConsolePi


2629828608 bytes (2.6 GB, 2.4 GiB) copied, 81 s, 32.4 MB/s2634022912 bytes (2.6 GB, 2.5 GiB) copied, 81.2102 s, 32.4 MB/s

628+0 records in
628+0 records out
2634022912 bytes (2.6 GB, 2.5 GiB) copied, 84.2852 s, 31.3 MB/s


Image written to flash - no Errors


 ~ mounting boot partition...............................................OK
 ~ enable ssh on image...................................................OK
 ~ staging consolepi user for userconf...................................OK
 ~ unmount boot partition................................................OK
 ~ mounting system partition to pre-configure consolePi image............OK
 ~ create consolepi home dir on image....................................OK
 ~ copy skel files to consolepi home dir.................................OK
 ~ chmod skel files staged in consolepi home.............................OK
 ~ set ownership of consolepi home dir...................................OK
 ~ configure auto launch installer on first login........................OK
     Configured with the following args -6 --us --tz America/Chicago --auto-launch
 ~ consolepi-stage dir found Pre-Staging all files.......................OK
 ~ No staged /home/consolepi files found.................................skip
 ~ No staged /root files found...........................................skip
 ~ stage NetworkManager profile Aruba-PSK................................OK
 ~ stage NetworkManager profile bt-pan...................................OK
 ~ stage NetworkManager profile dhcp.....................................OK
 ~ stage NetworkManager profile HPE_Aruba................................OK
 ~ HPE_Aruba is EAP-TLS SSID looking for certs...........................OK
 ~ Set staged private key (ConsolePi8.key) permissions (600).............OK
 ~ stage NetworkManager profile wadelab-ovpn-split.......................OK
 ~ stage NetworkManager profile zipline..................................OK
 ~ chown/chmod pre-staged profiles.......................................OK

   -- Performing Imports from This ConsolePi --
 ~ /etc/ConsolePi/ConsolePi.yaml.........................................Skipped - Already Staged
 ~ /etc/udev/rules.d/10-ConsolePi.rules..................................Skipped - Already Staged
 ~ /etc/ser2net.conf.....................................................Skipped - File Not Found
 ~ /etc/ser2net.yaml.....................................................Imported
 ~ /home/wade/.ssh/authorized_keys.......................................Skipped - Already Staged
 ~ /home/wade/.ssh/known_hosts...........................................Skipped - Already Staged
 ~ /home/wade/.ssh/id_rsa................................................Skipped - Already Staged
 ~ /home/wade/.ssh/id_rsa.pub............................................Skipped - Already Staged
 ~ /etc/ConsolePi/cloud/gdrive/.credentials/credentials.json.............Skipped - Already Staged
 ~ /etc/ConsolePi/cloud/gdrive/.credentials/token.pickle.................Skipped - Already Staged
 ~ /etc/openvpn/client/ConsolePi.ovpn....................................Skipped - File Not Found
 ~ /etc/openvpn/client/ovpn_credentials..................................Skipped - File Not Found
 ~ /etc/ssh/*............................................................Imported
 ~ configure hostname ConsolePi8 on image................................OK

ConsolePi image ready
```

Once Complete you place the newly blessed micro-sd in your raspberryPi and boot.  The installer will automatically start unless you've disabled it.  In which case the `consolepi-install` will launch the installer *(unless img_only=true, if so consolepi-install command is not created)*.

## Alternative Hardware Installs

For my use case I manually installed these, but depending on the system/use-case you could use the installer in the same method described above. *results may vary :)*

> Testing and extending the installer to natively detect and support installation on non RaspberryPi devices is planned for a future release.  It currently has not been tested.

The Use Cases
  1. ConsolePi running on a Linux Mint laptop
      - desire was to be able to load the menu, see the remotes, and use a locally connected adapter if I wanted, but to only sync one way (discover remote ConsolePis, but don't advertise to them).  This is because the laptop is used ad-hoc and if I'm using it I'm on it, not remote.
      - Install Process was simply (this is from memory so might be off a bit):
      ```bash
      sudo apt install python3-pip virtualenv git
      cd /tmp
      git clone https://github.com/Pack3tL0ss/ConsolePi.git
      cd ConsolePi  # Should now be in /tmp/ConsolePi
      python3 -m virtualenv venv
      sudo mv /tmp/ConsolePi /etc
      sudo cp /etc/ConsolePi/src/consolepi.sh /etc/profile.d && . /etc/profile.d/consolepi.sh # <-- adds consolepi-commands to PATH
      consolepi-sync -pip # <-- updates perms installs (pip) requirements
      cp /etc/ConsolePi/ConsolePi.yaml.example /etc/ConsolePi/ConsolePi.yaml
      consolepi-config # <-- edit as required ~ `cloud_pull_only: true` option in the OVERRIDES: section for this use case.
      sudo cp /etc/ConsolePi/src/systemd/consolepi-mdnsbrowse.service /etc/systemd/system
      sudo systemctl enable consolepi-mdnsbrowse
      sudo systemctl start consolepi-mdnsbrowse
      consolepi-menu # <-- See Note Below Regarding initial cloud AuthZ if using Gdrive Sync
      ```
      >test the menu (note if cloud sync enabled you still need to put the creds in the dir).
      Select option `r` (refresh) if cloud enabled and creds in place.
        If you've completed [Google Drive Setup](readme_content/gdrive.md), and need to authorize ConsolePi for the first time launch the menu with the `cloud` argument (`consolepi-menu cloud`) (then select the `r` (refresh) option).  This is only required to create the credential files for the first time, you can use `consolepi-menu` without arguments to launch after the creds have been created.

        *I think that's it.  So the above will allow use of the menu on the LapTop, will detect any local adapters if any are plugged in, will discover and allow connection to any remotes, manually defined hosts, power outlets, etc, but will not advertise itself to any other ConsolePis.*

        > If you did want the system to advertise itself on the network, so other ConsolePis could discover it:  Repeat the commands above related to `consolepi-mdnsbrowse.service` but swap in `consolepi-mdnsreg.service`.

  2. ConsolePi running on wsl-ubuntu (Windows Subsystem for Linux)
      - Use Case... I always have a wsl terminal open, so I use the `consolepi-menu` in wsl, which displays all the discovered remote consolepis.
      - No local-adapters wsl would be remote only.
      - Install process: Same as above with the exception of leave out the consolpi-mdnsbrowse bit (no systemd on wsl).
      - It works as expected, with the minor caveat that it's only source to get remote details is via cloud-sync.  Adapter data is still refreshed on menu-load by querying the remote directly.  You also can not create the cloud credentials files (do the initial Authorization) in wsl.  That needs to be done on another system and copied over.

  > For Alternative installs.  Use `consolepi-sync` to update ConsolePi rather than `consolepi-upgrade`.  *or* just `git pull` from the `/etc/ConsolePi` directory.  `consolepi-upgrade` is the installer (which will detect ConsolePi is already installed and run as upgrade), has not been tested on non RaspberryPi installs yet.

# ConsolePi Usage

## Configuration

The Configuration file is validated and created during the install.  Settings can be modified post-install via the configuration file `/etc/ConsolePi.yaml` (Some Changes will require consolepi-upgrade to be ran to take effect). See ConsolePi.yaml.example for an example of the available options.

### consolepi-menu sorting and connection settings
When you assign a friendly alias to an adapter for predictability via the `rn` (rename) option in `consolepi-menu` or via `consolepi-addconsole` an alias (udev rule) is created for that adapter and ser2net.conf is updated with a pointer to that alias using the next available TELNET port in the 7xxx range which includes the desired serial settings.  The `consolepi-menu` parses the ser2net.conf to retrieve the serial settings for each device, but it also uses this file to determine the order the adapters appear in the menu.  The menu is sorted by TELNET port#.  So if you want re-arrange the order devices show up you just need to re-arrange the port #s mapped in `/etc/ser2net.conf` for the devices.  Just ensure each device is mapped to a unique port (no duplicate ports).
> You can use the `tp` option in `consolepi-menu` to display the TELNET ports mapped to each device.  Re-arranging them still needs to be done manually by editing `/etc/ser2net.conf`

### Configuring Manual Host Entries
The Manual Host Entries Feature allows you to manually define other SSH or TELNET endpoints that you want to appear in the menu.  These entries will appear in the `rs` remote shell menu by default, but can also show-up in the main menu if `show_in_main: true`.  Manual host entries support [power outlet bindings](readme_content/power.md#power-control-setup) as well. To configure this feature simply populate the optional `HOSTS:` section of `ConsolePi.yaml`. Using the following structure:

```yaml
HOSTS:
  mm1(serial):
    address: 10.0.30.60:7001
    method: telnet  # This field is now optional defaults to ssh if not specified.
    show_in_main: true
    group: WLAN
  mc1(ssh):
    address: 10.0.30.24
    method: ssh
    username: wade
    show_in_main: true
    key: wade_arubaos_pub.key
    group: WLAN
  LabDigi1:
    address: labdigi.kabrew.com
    method: ssh
    username: wade
  omv:
    address: omv.kabrew.com
    method: ssh
    username: root
    group: WADELAB-HOSTS
```
**The Above Example highlights different options**
- The address field can be a IP or FQDN and a custom port can be included by appending `:<port>` to the end of the address if no port is defined the standard port for the protocol specified via the `method` key is used (22 for ssh 23 for TELNET).
- mm1 shows the address with an optional non-std port defined.  Connection would be made via TELNET on port 7001
- mm1 will use `wade_arubaos_pub.key` as the ssh private key/identity rather than the default identity file (typically `~/.ssh/id_rsa`)
  > The `key` specified can be in a number of places.
  > 1. The script always looks in `~/.ssh` first
  > 2. full path and relative (to cwd) path are also valid in the config (i.e. `key: /home/wade/mykeys/wade_arubaos_pub.key`)
  > 3. Lastly if you create the dir `/etc/ConsolePi/.ssh` and place the key there.  It will be copied to the users .ssh dir (`~/.ssh`) on menu launch and permissions/ownership will be updated appropriately for the logged in user.
  >
  > Option 3 has the benefit of providing a single global identity file for the host regardless of what user you are logged in as on the ConsolePi.  If the file in `/etc/ConsolePi/.ssh` is updated, the menu will detect the change, and copy the new file.
- mm1 and mc1 will show up in the main menu both grouped under the WLAN sub-head
- LagDigi1 does not define a group or set show_in_main (both are optional).  It will show up in the rshell menu in group "user-defined".
- omv will show up in the rshell menu under group "WADELAB-HOSTS"
- outlet bindings with these devices are supported by adding the device name in linked_devs for an outlet defined in the [POWER: section](readme_content/power.md#power-control-setup) of `ConsolePi.yaml`.

    > Ensure names are unique across both hosts defined here and the adapters defined via the menu or `consolepi-addconsole`.  If there is a conflict the serial adapter wins.

### Local UART Support

ConsolePi supports use of the onboard UARTs for external connections.  The Pi4 actually has 6 UARTs onboard (5 useable).  The additional UARTs would need to be enabled.  The examples below should get you there if you want to make use of the extra UARTs, obviously you can search the internet or refer to the Pi4 [data-sheet](https://www.raspberrypi.org/documentation/hardware/raspberrypi/bcm2711/rpi_DATA_2711_1p0.pdf) for info beyond that.

>Note: The RaspberryPis onboard UARTs are TTL level.  This is useful for connecting to other devices with TTL level UARTs (i.e. Another Rpi, Arduino, or Aruba APs that used the flat 4 pin connector (The grey Aruba Adapter used to connect to these APs `AP-SER` has a TTL to RS232 level shifter built into the cable)).  To use these to connect to RS232 ports typically found on Network Hardware and other equipment you need a ttl<-->RS232 level shifter i.e. (max232 family).

  **To Enable Support for GPIO UARTs (ttyAMA):**

  #### Update 10-ConsolePi.rules if necessary

  If `/etc/udev/rules.d/10-ConsolePi.rules` already exists on the system, and was created prior to v2020-4.5 (Sept 2020).  You will likely need to update the file to support the additional GPIO UARTs on the Pi4.  The GPIO UARTs were initially configured to use it's own separate rules file (11-ConsolePi-ttyama.rules).  With v2020-4.5 it was added to the common rules file `10-CosnolePi.rules`.  The format/template used to build `10-ConsolePi.rules` had to be updated to support the GPIO UARTs (ttyAMA devices).

  You can verify by checking `/etc/udev/rules.d/10-ConsolePi.rules` for `KERNEL=="ttyAMA[1-4]*", GOTO="TTYAMA-DEVS"` near the top of the file (line 2).

  If `/etc/udev/rules.d/10-ConsolePi.rules` does not exist, nothing needs to be done.  If it does and the verification above indicates it needs to be updated you can either delete it (which will remove any current aliases, you'll be starting over, but the file will take on the new format). -- or -- if you want to avoid the need to rename the serial devices you've already set aliases for, you can...
  ```bash
  sudo mv /etc/udev/rules.d/10-ConsolePi.rules ~/ # move the file out of the rules dir (to your home dir)
  sudo cp /etc/ConsolePi/src/10-ConsolePi.rules /etc/udev/rules.d  # copy the new file template to the rules dir
  cat ~/10-ConsolePi.rules  # cat the old file contents.
  # Select and copy only the lines with aliases that were previously configured
  sudo nano /etc/udev/rules.d/10-ConsolePi.rules  # open the new rules file for editing
  # paste in the lines with aliases from the previous rules file, in the same section they existed previously
  # Be sure not to remove any of the existing comments/lines
  # repeat cat, copy, edit, paste as needed if content existed in multiple sections.
  consolepi-resetudev  # trigger/reload udev to update devs based on new file content.
  consolepi-showaliases  # This utility verifies All aliases set in the rules file also exist in ser2net and vice versa.
  ```

  #### Configure `/boot/firmware/config.txt`  *(On older pre-bookworm images this file is @ `/boot/config.txt`)*
  ```bash
  # related snippet from /boot/firmware/config.txt

  #Enable Default UART (used to access this ConsolePi not externally)
  enable_uart=1

  # Enable Additional UARTs
  # dtoverlay=uart0,<param>=<val>
  # Params: txd0_pin                GPIO pin for TXD0 (14, 32 or 36 - default 14)
  #         rxd0_pin                GPIO pin for RXD0 (15, 33 or 37 - default 15)
  #         pin_func                Alternative pin function - 4(Alt0) for 14&15,
  #                                 7(Alt3) for 32&33, 6(Alt2) for 36&37

  # Enable uart 2 on GPIOs 0,1
  dtoverlay=uart2

  # Enable uart 3 on GPIOs 4,5
  dtoverlay=uart3

  # Enable uart 4 on GPIOs 8,9
  dtoverlay=uart4

  # Enable uart 5 on GPIOs 12,13
  dtoverlay=uart5
  ```
  #### Configure `/boot/firmware/cmdline.txt`  *(On older pre-bookworm images this file is @ `/boot/cmdline.txt`)*
  ```bash
# /boot/firmware/cmdline.txt

# The default UART is enabled for "inbound" access to this Pi, this first line can be left as is.
console=serial0,115200 console=tty1 root=PARTUUID=6fddac24-02 rootfstype=ext4 fsck.repair=yes rootwait
# Add the remaining UARTS configured for external access, Note that uart3 is not actually being used due to pin access
console=ttyAMA1,115200
console=ttyAMA2,115200
console=ttyAMA3,115200
console=ttyAMA4,115200
  ```

#### Configure ConsolePi.yaml

ConsolePi.yaml needs to include a TTYAMA: key (where `TTYAMA` is not indented, it should be at the same level as `CONFIG` or the optional `OVERRIDES`, `HOSTS`, and `POWER` keys)

Given the example above with 3 uarts enabled (technically 4 but the default UART is used for "inbound" access)

```yaml
TTYAMA: [ttyAMA1, ttyAMA2, ttyAMA3]
```
The onboard UARTs will then showup in the consolepi-menu as ttyAMA#, you can then use the rename option to assign a friendly name and configure custom serial settings (i.e. change the baud used by the menu, the rename option will also add the device to ser2net using the next available TELNET port in the 7xxx range)

### Power Control Setup
Refer to [Power Control Setup](readme_content/power.md#power-control-setup)

### ZTP Orchestration
Refer to [ZTP Orchestration](readme_content/ztp.md)

### **OVERRIDES:**

**Optional Overrides to prevent `consolepi-upgrade` from updating ConsolePi related system files**

To Upgrade ConsolePi it's recommended to use the `consolepi-upgrade` command.  This runs the install/upgrade script which on upgrade will verify some of the system configuration related to ConsolePi functionality.  If you've made customizations to any of the system files ConsolePi initially configures, the upgrade script will backup the file (to /etc/ConsolePi/bak) and replace it.  This may be undesired if you've made customizations, to prevent this from occurring simply create an empty file (doesn't technically have to be empty) with the same name as the file you want to prevent being modified by ConsolePi in '/etc/ConsolePi/overrides' (i.e. `touch /etc/ConsolePi/overrides/dhcpcd.conf`)

> `consolepi-upgrade` is the preferred method, but you can run `consolepi-sync` described in [Convenience Commands](#convenience-commands) or alternatively simply do a git pull from within /etc/ConsolePi to Upgrade.  However there is some risk, as references to system paths/symlinks etc. may have changed, and `consolepi-sync` doesn't automate any of the system changes that may be part of the upgrade.

**List of files ConsolePi will verify and potentially update**
- /etc/dhcpcd.conf
- /etc/network/interfaces *verified, but no changes from the system default are typically necessary*
- /etc/default/hostapd
- /etc/hostapd/hostapd.conf
- /etc/profile.d/consolepi.sh  *This file adds the consolepi-commands directory to PATH, but also prints the ConsolePi ascii banner on login, to get rid of the banner, or create a custom banner you could modify the file and place an empty consolepi.sh in overrides dir, you do need the PATH update for any of the `consolepi-...` commands to work.*
- /etc/hosts  *Hostname is added mapped to hotspot IP, needed for proper resolution if client were to connect to the hotspot and try to access by hostname*

**Service Files**

Overriding Service files not only turns off validation of the contents of the systemd unit file, but also the state of the service (enabled/disabled)

- hostapd.service *If AutoHotSpot is enabled, Script will configure based on config and ensure the service is disabled as startup is handled by AutoHotSpot*
- bluetooth.service
- rfcomm.service *You can override rfcomm.service if running ConsolePi on older hardware lacking bluetooth (it'll fail given no hardware is present)*

 *On ConsolePis Built prior to v2020.2 (merged in April 2020) the following may also apply (AutoHotSpot now uses it's own dnsmasq service separate from the default dnsmasq service)*
- dnsmasq.service *Script will modify for hotspot and ensure the service is disabled as startup is handled by AutoHotSpot*


**Optional override Variables in ConsolePi.yaml**

ConsolePi.yaml also supports a few customizations via the optional `OVERRIDES` section.  Examples of most of them should be in your configuration after the install (with the default values, so they are not overriding anything just in place as a reference).

A summary of available overrides:
- **skip_utils:** Instruct the upgrade script to skip the optional utilities step (this step can be done outside the installer via `consolepi-extras`).
- **default_baud:** This rarely comes into play.  It only applies to a device that is detected, but has no entry in ser2net.conf  Given ser2net.conf is pre-populated with 20 devices for ttyUSB# and ttyACM# both, it's unlikely default_baud would ever apply to a device.  (default_dbits, default_parity, default_flow, default_sbits - are all available as overrides as well)
- **cloud_pull_only:** Primary use case is for Non-rPi where you want to launch the menu and access adapters on remotes (i.e. a laptop).  This only applies if cloud-sync is enabled.  Will result in pulling data from the cloud, but not updating the cloud with the laptops details (so the laptop would never show up in the menu if accessed from one of the other ConsolePis)
- **compact_mode:**  This feature is still a bit of a test use, and will only apply if you have multiple remotes (multiple ConsolePis that discover each other via mdns or cloud sync).  Remotes are typically broken into groupings by remote ConsolePi, `compact_mode: true` will result in all remote adapters appearing in the same group.
- **remote_timeout:**  If remotes have been discovered ConsolePi fetches current adapter details from that remote when the menu is launched to ensure adapter data is current and verify the remote is reachable.  The default timeout is 3 seconds, if the request takes longer it's considered unreachable and doesn't show up in the menu.  This is normally a good balance.  If it's too high verification and menu_load is delayed when remotes are not reachable, however I have seen cases where 3 seconds may be too low.  Typically on very old Raspberry Pis with a lot of adapters connected (i.e. had the issue on original Pi B with ~ 20 adapters).
- **dli_timeout:**  (Power outlet control) Applies to dli web power switches (digital-loggers).  If the dli does not respond in `dli_timeout` seconds it is considered failed, and is excluded from the menu.  Use this to override the default which is 7.
- **smartoutlet_timeout:**  (Power outlet control) Same as dli_timeout, but for esphome/tasmota outlets, default is 3.
- **cycle_time:**  (Power outlet control) When cycling power on outlets (turning off then back on), this setting will override the default wait period between off and on.  Default is 3 (seconds).
- **ovpn_share:**  Set this to true to allow traffic from hotspot users to egress the tunnel (along with the wired interface).  Default is false.
- **skip_utils:**  The utilities/extras installer allows you to select optional components external to ConsolePi, but often handy for the type of users that would utilize it.  This option skips that section when doing `consolepi-update` (or `consolepi-install` if you stage a populated `ConsolePi.yaml`).  It just removes that step if you know you are never going to add any of them.  The utilities/extras installer can also be ran outside the installer via `consolepi-extras`.
- **disable_ztp:**  When a ZTP configuration exists (`ZTP:` section of `ConsolePi.yaml`), and wired_dhcp is enabled, then ZTP is enabled.  Setting this to false, will override that / disable ztp (wired_dhcp is still left enabled, be careful)
- **ztp_lease_time:**  Used to override the default lease time (2 min `2m`) the wired_dhcp process uses for ZTP.
- **hide_legend:**  Set to true to hide the legend by default in the menu, can still toggle it back on with `TL`.
- **api_port:**  Used to override the default API port (5000), It's how other ConsolePis gather information from this ConsolePi when multiple ConsolePis exist on the network or learn about each other via Gdrive sync.

## Console Server

### TELNET

*Don't overlook `consolepi-menu` which supports remote ConsolePi discovery and provides a single launch point into any local and remote connections discovered*

- Serial/Console adapters that show up as ttyUSB# devices when plugged in are reachable starting with telnet port 8001 +1 for each subsequent adapter plugged in (8002, 8003...). If you use multiple adapters then it may be a crap shoot which will be assigned to each telnet port (or which root dev (ttyUSB#) they appear as).  Hence the next step.

- Serial/Console adapters that show up as ttyACM# devices start at 9001 +1 for each subsequent device.
> Most USB to serial adapters present as ttyUSB, some embedded adapters; i.e. network devices with built in USB consoles typically show up as ttyACM#

- The install script automates the mapping of specific adapters to specific ports (provided you don't skip the step).  The defined predictable adapters start with 7001 +1 for each adapter you define.  The reasoning behind this is so you can label the adapters and always know what port you would reach them on.  This can also be accomplished after the install via the `consolepi-addconsole` command or via rename (`rn`) option in `consolepi-menu`.

> **!!** It is recommended to use `consolepi-addconsole` or the `rn` option in the menu to provide a consistent alias for each adapter/device.  If more than one adapter is plugged in, they are assigned the root device names (ttyUSB#/ttyACM#) in the order they are detected by the kernel.  The can occasionally change after reboot / or if an adapter is disconnected.  Setting the aliases is the only way to ensure predictability.

  >Note: Some cheap a@# serial console adapters don't define serial #s, which is one of the attributes used to uniquely identify the adapter.  The rename function/`consolepi-addconsole` command now support these adapters, but with caveats explained by the script when such a case is detected.

Note: the 8000/9000 range is always valid even if you are using an adapter specifically mapped to a port in the 7000 range.  So if you plug in an adapter (ttyUSB) pre-mapped to port 7005, and it's the only adapter plugged in, it would also be available on port 8001

- Port monitoring/and control is available on TELNET port 7000.  This allows you to change the baud rate of the port on the fly without changing the config permanently.  The installer configures all ports to 9600 8N1.
- Serial Port configuration options can be modified after the install in /etc/ser2net.conf or via the rename option in the menu (just specify the same name, you are offered the option to change serial settings after specifying the new name)


### SSH / BlueTooth

The ```consolepi-menu``` command can be used to display a menu providing options for any locally connected USB to Serial adapters.  In addition to any remotely connected USB to serial adapters connected to other remote ConsolePis discovered (either via mdns or the Cloud Sync function).  When connecting to ConsolePi via bluetooth this menu launches automatically.
> Note that when using bluetooth the menu is limited to local adapters and remotes found in the local-cache file.  Connect via SSH for full remote functionality in the menu.
>
>Serial Adapter connection options (baud, flow-control, data-bits, parity) are extracted from ser2net.conf by consolepi-menu.  If there is an issue getting the data it falls back to the default of 9600 8N1 which can be changed in the menu (option c)


## **Convenience Commands:**

There are a few convenience commands created for ConsolePi during the automated install

- `consolepi-menu`: Launches ConsolePi Menu, which will have menu items described in the list below.

    - Connection options for locally attached serial adapters
    - Connection options for serial adapters connected to remote ConsolePis (discovered via mdns or cloud-sync as described [here](#consolepi-cluster--cloud-sync))
    - Connection options for any [manually defined hosts](#configuring-manual-host-entries)
    - sub-menu to automate distribution of ssh keys to remote ConsolePis.
      > *Distributing SSH keys allows you to securely connect to the remote adapter seamlessly without the need to enter a password.*
    - Remote Shell sub-menu, providing options to ssh directly to the shell of any discovered remote ConsolePis.
    - Power Control sub-menu if power relays have been defined (as described [here](#power-control))
    - Refresh option: Refresh will detect any new serial adapters directly attached, as well as connect to Gdrive to sync.
      - If Cloud-Sync is enabled ConsolePi only reaches out to the cloud when the refresh option is used, *NOT* during initial menu-load.
    - Rename option: rename/define predictable names for a local or remote adapter

      >Some menu items only appear if the feature is enabled.

  > `consolepi-menu` also accepts a single argument `sh`.  Which will launch the original consolepi-menu created in bash.  It's been crippled so it only displays local connections, it loads faster because it's local only, and doesn't need to import any modules.  This is currently the default menu that launches when connecting via bluetooth.  If running on an older Raspberry Pi (certainly the original Pi you may notice a difference in load time vs the full menu)

- `consolepi-upgrade`:  Upgrades ConsolePi:  **Preferred method to properly update ConsolePi**.  In general this verifies that all configurations system services etc related to ConsolePi functionality are configured as expected.  This means if you've customized any of the related system files the upgrade might revert them.  It will back up the original if that occurs, but to facilitate customizations for anything you don't want the upgrade script to validate simply place a file by the same name in the overrides directory (just touch an empty file with the same name i.e. `touch /etc/ConsolePi/overrides/dhcpcd.conf`) will tell the upgrade script *not* to validate dhcpcd.conf.

    > Reducing potential areas of conflict with other functions you might want running is an ongoing task, and will continue to improve as I find mechanisms to reliably do so.  Leverage the overrides dir & worst case the original will be in the bak dir if an overwrite occurs you didn't anticipate.  *Obviously if the systems primary use is dedicated to ConsolePi, none of this should be an issue.*

- `consolepi-sync`:  Alternative Upgrade: Primarily created to speed testing of remote ConsolePis during development, but can be used to Upgrade.  However note that no system changes will occur, so any systemd unit file updates, configuration file updates, symlink changes, etc. won't occur, which could break functionality.  It essentially just does a git pull, but has a number of options on top of that.  `consolepi-sync --help` to see the available options.

- `consolepi-config`: Launch ConsolePi Configuration file for editing in nano with tabs=2 spaces.

- `consolepi-image`: Launch [ConsolePi Image Creator](#3-consolepi-image-creator).

- `consolepi-ztp`: See [ZTP Orchestration](readme_content/ztp.md).

- `consolepi-details`: Displays full details of all data ConsolePi collects/generates.  With multiple available arguments.
  - `consolepi-details` : Displays all collected data
  - `consolepi-details local` : Same as above but without data for remote ConsolePis
  - `consolepi-details [<remote consolepi hostname>]` : Displays data for the specified remote ConsolePi only (from the local cloud cache)
  - `consolepi-details adapters` : Displays all data collected for discovered adapters connected directly to ConsolePi (USB to Serial Adapters)
  - `consolepi-details interfaces` : Displays interface data
  - `consolepi-details outlets` : Displays power outlet data
  - `consolepi-details remotes` : Displays data for remote ConsolePis from the local cloud cache
  - `consolepi-details remotes del [<remote consolepi hostname>]` : remove a remote from local cloud cache
  > `consolepi-menu` will automatically remove any remote from the local cache if it has been found unreachable 3x.  Reachability is verified on menu load and during refresh.
  >
  > This command currently does not support --help, that will come with the planned migration from these `consolepi-...` commands to a true cli app.

- `consolepi-logs`: By default follows tail on both the consolepi main log file, and portions of syslog related to ConsolePi.
  - `consolepi-logs -f` Follow tail on the primary consolepi log file only.
  - `consolepi-logs -30` | `consolepi-logs 30`: Display last 30 lines from primary consolepi log file.
  - `consolepi-logs -all` | `consolepi-logs all`: Display contents of the consolepi log file.
  - `consolepi-logs -install [-f|-##|-all]` Same as above but with the install log.  *The hyphen in the optional flags are optional, `f` and `-f` will yield the same results.*
- `consolepi-addssids`: Automates the creation of additional SSIDs which ConsolePi will attempt to connect to on boot.  Supports psk and open SSIDs.
- `consolepi-addconsole`: Automates the process of detecting USB to serial adapters so friendly names can be defined for them (used in `consolepi-menu`) and mapping them to specific TELNET ports.  It does this by collecting the data required to create a udev rule.  It then creates the udev rule starting with the next available port (if rules already exist).
- `consolepi-showaliases`: This is a validation utility/command, It will display all configured aliases (configured via `consolepi-addconsole` or the `rn` option in the menu).  This utility will show if there are any orphaned aliases.

  > An orphaned alias is an alias that only exists in 1 of the 2 files involved (`/etc/udev/rules.d/10-ConsolePi.rules` and `/etc/ser2net.conf`)
- `consolepi-autohotspot`: This script re-runs the autohotspot script which runs at boot (or periodically via cron although the installer currently doesn't configure that).  If the wlan adapter is already connected to an SSID it doesn't do anything.  If it's acting as a hotspot or not connected, it will scan for known SSIDs and attempt to connect, then fallback to a hotspot if it's unable to find/connect to a known SSID.
- `consolepi-testhotspot`: Toggles (Disables/Enables) the SSIDs ConsolePi is configured to connect to as a client before falling back to hotspot mode.  This is done to aid in testing hotspot mode.  After toggling the SSIDs run consolepi-autohotspot to trigger a change in state.  (specifically it prepends 'DISABLED_' to all configured SSIDs)
- `consolepi-pbtest`: Used to test PushBullet this commands simulates an IP address change by calling the script responsible for sending the PB messages and passing in a random IP to force a notification.
- `consolepi-leases`: Simply prints the active leases issued to any clients connected to the [HotSpot](#autoHotSpot) or via [Wired DHCP Fallback](#automatic-wired-dhcp-fallback).
- `consolepi-browse`: Runs the mdns browser script which runs as a daemon in the background by default.  When ran via this command it will display any ConsolePis discovered on the network along with a summary of the data being advertised by that remote ConsolePi.  Primarily good for testing mdns.
- `consolepi-killvpn`: gracefully terminates the OpenVPN tunnel if established.
- `consolepi-bton`: Make ConsolePi Discoverable via BlueTooth (Default Behavior on boot)
- `consolepi-btoff`: Stop advertising via BlueTooth.  Previously paired devices will still be able to Pair.
- `consolepi-extras`: Launches optional [utilities installer](#consolepi-extras)
- `consolepi-version`: Displays ConsolePi version (which is in the format YYYY-MajorRel.MinorRel)
- `consolepi-wlanreset`: Disables hotspot if enabled, disconnects from AP if connected as a station.  Then starts wpa_supplicant.  Otherwise attempts to reset WLAN adapter to initial bootup state, autohotspot will not run (use `consolepi-autohotspot` after reset to force autohotspot logic to run).
- `consolepi-wlanscan`: Scan and display SSIDs visible to this ConsolePi, does not impact existing connection.
- `consolepi-convert`: A utility that parses ser2net v3 config (`/etc/ser2net.conf`) and creates a ConsolePi compatible ser2net v4 config (`/etc/ser2net.yaml`).  Buster brings with it an upgrade from ser2netv3 to v4.  This script will migrate any existing adapter deffinitions (configured via `consolepi-addconsole` or the `rn` option in the menu) to v4 and create / update the v4 config.
- `consolepi-help`: Shows this output

## Upgrading ConsolePi

Use `consolepi-upgrade` to upgrade ConsolePi.  Simply doing a git pull *may* occasionally work, but there are a lot of system files, symlinks, etc. outside of the ConsolePi folder that are occasionally updated, those changes are made via the upgrade script.

> ConsolePi ensures packages related to ConsolePi are configured per your configuration.  If you've made customizations the existing config will be backed up to the bak directory, and the config will be updated.  Use the [OVERRIDES](#overrides) function to override this behavior for files you don't want updated.

# Tested Hardware / Software

## Raspberry Pi

ConsolePi requires Python version >= 3.6, which means it now requires Buster.  If running an older version of ConsolePi the last supported version is taggeed stretch-final, but reccomend creating a Buster Image to get the latest features.

ConsolePi Should work on all variants of the RaspberryPi and will work on other Linux systems including wsl (Windows Subsystem for Linux).

​	*If you find a variant of the Rpi that does not work, create an "issue" to let me know.  If I have one I'll test when I have time to do so*
- RaspberryPi 4 Model B
    - Tested with RaspberryPi Power supply, PoE Hat, and booster-pack (battery)
    - Tested all variations of connection types
- RaspberryPi Compute Module 4
    - Tested with official Raspberry Pi CM4 io board.
- RaspberryPi 3 Model B+
  - Tested with RaspberryPi Power supply, PoE Hat, and booster-pack (battery)
  - Tested all variations of connection types
- Raspberry Pi 2 Model B (running Buster)
    - Tested via wired port, and with external USB-WiFi adapter.  Have not tested any BlueTooth Dongles
- Raspberry Pi Model B (running Buster)
    - Tested via wired port, and with external USB-WiFi adapter.  Have not tested any BlueTooth Dongles
    - Pretty slow to load the Google Drive Libraries, slower menu-load, slower for about everything, but works.  `consolepi-menu sh` which loads the faster local-only shell menu loads faster given it has no libraries to pull in, but these are best relegated to seldomly used remotes if used at all.
- RaspberryPi zero w
  - With both single port micro-usb otg USB adapter and multi-port otg usb-hub.
  - Tested with wired port via otg USB adapter, built-in wlan. BlueTooth... Use this with battery pack on a regular basis.
- RaspberryPi zero w 2

> ConsolePi will also work on other Linux systems as described in [Alternative Hardware Installs](#alternative-hardware-installs).

# ConsolePi @ Work!

*Have some good pics of ConsolePi in action?  Let me know.*

  ![ConsolePi in action](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/consolepi-cm.png)
  ![ConsolePi in action](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/consolepi-cm-r2-extension.png)
  ![ConsolePi in action](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/garagepi.png)
  ![ConsolePi in action](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/ConsolePi0.jpg)
  ![ConsolePi in action](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/ConsolePi.jpg)
  ![ConsolePi in action](https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/readme_content/consolepi_cy.jpg)

# CREDITS

ConsolePi utilizes a couple of other projects so Some Credit

1. **ser2net** ([cminyard](http://sourceforge.net/users/cminyard))

   This project provides a proxy that allows telnet/tcp connections to be made to serial ports on a machine.

      [sourceforge](https://sourceforge.net/projects/ser2net/)

      [github](https://github.com/cminyard/ser2net)


2. **Others**
   Available via optional Utilities Installer `consolepi-extras` or during `consolepi-upgrade`
    - SpeedTest: HTML 5 speed Test https://github.com/librespeed/speedtest
    - Cockpit: https://cockpit-project.org (utilities installer installs without network-manager component to avoid conflict with ConsolePi functionality)
