# ConsolePi

Acts as a serial Console Server, allowing you to remotely connect to ConsolePi via Telnet/SSH/bluetooth to gain Console Access to devices connected to local **or remote** ConsolePis via USB to serial adapters (i.e. Switches, Routers, Access Points... anything with a serial port).  

*Check out the **NEW** [ConsolePi Clustering Feature](#consolepi-cluster--cloud-config)!!*

***TL;DR:***
Single Command Install Script. Run from a RaspberryPi running raspbian (that has internet access):

```
sudo wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/install.sh -O /tmp/ConsolePi && sudo bash /tmp/ConsolePi && sudo rm -f /tmp/ConsolePi
```
------
# Contents
 - [What's New](#whats-new)
 - [Features](#features)
     - [Serial Console Server](#serial-console-server)
     - [AutoHotSpot](#autoHotSpot)
     - [Automatic VPN](#automatic-openvpn-tunnel)
     - [Automatic PushBullet Notifications](#automatic-pushbullet-notification)
     - [Clustering / Cloud Sync](#consolepi-cluster--cloud-sync)
         - [Supported Cluster Methods](#supported-cluster-sync-methods)
             - [Google Drive](#google-drive)
             - [mDNS / API](#mdns--api)
             - [Manual](#local-cloud-cache)
          - [Important Notes](#important-notes)
      - [API](#api)
      - [Power Control](#power-control)
          - [Power Control Setup](#power-control-setup)
              - [GPIO Connected Relays](#gpio-connected-relays)
              - [WiFi Smart Outlets (tasmota)](#wifi-smart-outlets-tasmota)
              - [DLI Web/Ethernet Power Switch](#dli-webethernet-power-switch)
      - [Manual Host Entries](#manual-host-entries)
      - [ConsolePi Extras](#consolepi-extras)
 - [Installation](#installation)
     - [Automated Installation](#1-automated-installation)
     - [Semi-Automatic Install](#2-semi-automatic-install)
     - [Automated Flash Card Imaging/prep](#3-automated-flash-card-imaging-with-auto-install-on-boot)
 - [ConsolePi Usage](#consolepi-usage)
     - [Configuration](#configuration)
     - [Console Server](#console-server)
         - [TELNET](#telnet)
         - [SSH / BlueTooth (`consolepi-menu`)](#ssh--bluetooth)
      - [Convenience Commands](#convenience-commands)
      - [Upgrading ConsolePi](#upgrading-consolepi)
          - [Custom overrides](#custom-overrides)
 - [Tested Hardware/Software](#tested-hardware--software)
 - [ConsolePi @ Work! (Image Gallery)](#consolepi-@-work)
 - [Credits](#credits)
------

## *!!!Deprecation Warning!!!*
Python 3.6 or greater will soon be required for the menu to work properly.  This simply means if you have a ConsolePi running Raspbian prior to Buster you should build a new one using the Buster image.  The upgrade is fairly painless given you can pre-stage a ton of stuff in a ConsolePi_stage folder and use the ConsolePi_image_creator script to build an image on a new micro-sd card.

# What's New

Prior Changes can be found in the - [ChangeLog](changelog.md)

### JAN 2019 *MONSTER Update*
- Additional improvements to in menu rename function / `consolepi-addconsole`
    - Added support for adapters that don't have a serial #, this was added prior, but would actually crash the menu (oops), I finally found a crappy adapter that lacks a serial # to test with as a result that function should now work.  It will be a compromise, essentially it will either need to be the only adapter of that kind (modelid/vendorid) or always be plugged into the same USB port.
    - Added a connect option in the rename menu (So you can connect to the adapter directly from that menu... useful if you need to verify what's what.)

- `consolepi-extras` or the Optional utilities menu presented during the install/upgrade further enhanced
    - This installs/uninstalls optional packages useful for many ConsolePi users.
        - ansible: Changed to use a different ppa to source the package, vs the default raspbian repo
        - Aruba ansible modules: Added option to install modules for networking products from Aruba Networks.
        - SpeedTest: Added An HTML 5 speed Test https://github.com/librespeed/speedtest. This option will only be available on Pi 4 models (makes little sense on anything older)
        - cockpit: Provides a Dashboard to monitor the ConsolePi, as well as a web based tty.
            > Note Making network configuration changes via Cockpit may conflict with the AutoHotSpot function
- dhcp server process (dnsmasq) for autohotspot is now a unique process just for wlan0, this allows you to have a separate process for the wired port without impacting the hotspot.  wired-dhcp will be a configurable option in a future build, an example systemd file for a separate dnsmasq process bound to the wired port is in /etc/ConsolePi/src/systemd
- ConsolePi_image_creator script which is used to prep an SD card for a headless ConsolePi install re-worked / improved, had to back down some ciphers no longer allowed by curl to match the raspberrypi.org cert (the script will pull the latest image if not found in the script dir).
- API changed to fastAPI for those that are on Raspbian Buster (Python 3.6+ is required), for systems running with python 3.5 or prior the current API remains.  FastAPI adds a swagger interface to ConsolePi.  The API will continue to be improved in future releases.
- Changed remote connectivity verification to use the API rather than attempting a socket connection on the SSH port.  This ensures both connectivity and that the adapter data presented in the menu for the remote is current.
- Added support for manually configured hosts (additional TELNET or ssh hosts you want to show up in the menu).  These are configured in hosts.json and support outlet linkage in the same way serial adapters do.  Just be sure the all names are unique.  This works, but needs some minor tweaks, when ssh to some devices the banner text is actually sent via stderr which is hidden until you exit the way it's setup currently.
- The **major** part of the work in this build was to make menu-load more async.  Verification of remote connectivity is now done asynchronously each remote is verified in parallel, then the menu loads once they are all finished.  The same for power control if tasmota or dli outlets need to be queried for outlet state, this is done in the background, the menu will load and allow those threads to run in the background.  If you go to the power menu prior to them being complete, you'll get a spinner while they finish.  All of this results in a much faster menu-load.  Auto Power On when connecting to devices/hosts with linked outlets also occurs in the background on launch.
- Plenty of other various tweaks.  

# Features

## **Serial Console Server**
This is the core feature of ConsolePi.  Connect USB to serial adapters to ConsolePi, then access the devices on those adapters via the ConsolePi.  Supports TELNET directly to the adapter, or connect to ConsolePi via SSH or BlueTooth and select the adapter from the menu.  A menu is launched automatically when connecting via BlueTooth, use `consolepi-menu` to launch the menu from an SSH connection.  The menu will show connection options for any locally connected adapters, as well as connections to any remote ConsolePis discovered via Cluster/sync.

For guidance on USB to serial adapters check out the sh#t list [here](adapters.md)
> There are some lame adapters that don't burn a serial # to the chip, this makes assigning a unique name/TELNET port more challenging).  The link above is a page where we note what chipsets are solid and which ones are a PITA.

## **AutoHotSpot**

Script runs at boot (can be made to check on interval via Cron if desired).  Looks for pre-defined SSIDs, if those SSIDs are not available then it automatically goes into hotspot mode and broadcasts its own SSID.  In HotSpot mode user traffic is NAT'd to the wired interface if the wired interface is up.

When ConsolePi enters hotspot mode, it first determines if the wired port is up and has an IP.  If the wired port is *not* connected, then the hotspot distributes DHCP, but does not provide a "Default Gateway" to clients.  This allows a user to dual connect without having to remove a route to a gateway that can't get anywhere.  I commonly use a second USB WLAN adapter to connect to ConsolePi, while remaining connected to the internet via a different SSID on my primary adapter.

> If a domain is provided to the wired port via DHCP, and the hotspot is enabled ConsolePi will distribute that same domain via DHCP to clients.

## Automatic OpenVPN Tunnel

When an interface receives an IP address ConsolePi will Automatically connect to an OpenVPN server under the following conditions:
- It's configured to use the OpenVPN feature, and the ConsolePi.ovpn file exists (an example is provided during install)
- ConsolePi is not on the users home network (determined by the 'domain' handed out by DHCP)
- The internet is reachable.  (Checked by pinging a configurable common internet reachable destination)

##  **Automatic PushBullet Notification**

*(Requires a PushBullet Account, API key, and the app / browser extension.)*

When ConsolePi receives a dynamic IP address.  A message is sent via PushBullet API with the IP so you know how to reach ConsolePi.

![Push Bullet Notification image](readme_content/ConsolePiPB1.png)

An additional message is sent once a tunnel is established if the Automatic OpenVPN feature is enabled.

![Push Bullet Notification image](readme_content/ConsolePiPB2.png)

Each Time a Notification is triggered all interface IPs are sent in the message along with the ConsolePi's default gateway(s).

## ConsolePi Cluster / Cloud Sync

The Cluster feature allows you to have multiple ConsolePis connected to the network, or to each other (i.e. first ConsolePi in hotspot mode, the others connected as clients to that hotspot).  A connection to any one of the ConsolePis in the Cluster will provide options to connect to any local serial adapters, as well as those connected to the other ConsolePis in the cluster (via the `consolepi-menu` command).


![consolepi-menu image](readme_content/consolepi-use-diagram.jpg)

**Another look at the menu**

![consolepi-menu image](readme_content/menu.png)


### Supported Cluster Sync Methods:

#### Google Drive:
   > Read The [Google Drive Setup](readme_content/gdrive.md) for instructions on setting up Google Drive and authorizing ConsolePi to leverage the API.
 - Google Drive/Google Sheets is currently the only external method supported.  Given this gets the job done, it unlikely more external methods will be added.

 - The ConsolePi will automatically exchange information with `ConsolePi.csv` in your gdrive under the following scenarios (*all assume the function is enabled in the config*):
  1. When the ConsolePi receives an IP address, and can reach the google API endpoints.

  2. When consolepi-menu is launched and the `'r'` (refresh) option is selected.

  3. When a USB to Serial adapter is added or removed.  (This happens on a 30 second delay, so if multiple add/removes are made in a 30 second window, only 1 update to the cloud will occur, that update will include everything that happened within the 30 second window)

  >In all of the above a local cloud cache which includes data for any remote ConsolePis pulled from ConsolePi.csv is updated for the sake of persistence and speed.  The local cloud cache is what is referenced when the menu is initially launched

#### mDNS / API
* ConsolePis now advertise themselves on the local network via mDNS (bonjour, avahi, ...)

* 2 daemons run on ConsolePi one that registers itself via mdns and updates anytime a change in available USB-serial adapters is detected, and a browser service which browses for remote ConsolePis registered on the network.  The browser service updates the local cloud cache when a new ConsolePi is detected.

> The API described [here](#api) comes into play when enough adapters are plugged in, such that the data payload would be over what's allowed via mDNS.  In the event this occurs... well here is an example:  ConsolePi-A has a has enough USB to Serial adapters plugged in to be over the data limit allowed via mDNS, the mdns-register service will detect this and fall-back to advertising ConsolePi-A without the adapter data.  ConsolePi-B, and ConsolePi-C are on the network and discover ConsolePi-A.  B and Cs browser service will detect that the adapter data was stripped and request the adapter data from A via the API.

#### Local Cloud Cache
  - local cloud cache:  For both of the above methods, a local file `/etc/ConsolePi/cloud.data` is updated with details for remote ConsolePis.  This cache file can be modified or created manually.  If the file exists, the remote ConsolePis contained within are checked for reachability and added to the menu on launch.

#### DHCP based:

This function currently only logs as mDNS has made this unnecessary. It remains as future enhancements (auto detect oobm ports, ztp) will likely use this mechanism.

Triggered by ConsolePi Acting as DHCP server (generally hotspot):
  

###  Important Notes:

 - The Gdrive function uses the hostname as a unique identifier.  If all of your ConsolePis have the same hostname they will each overwrite the data.  The Hostname is also used to identify the device in the menu.

   **Make Hostnames unique for each ConsolePi**

 - The ```consolepi-addconsole``` command now supports assingment of custom names to the aliases used to identify the serial adapters when using the predictable TELNET ports. (udev rules).  If configured these names are used in ```consolepi-menu```, the default device name is used if not (i.e. ttyUSB0), but that's less predictable.

 - The last ConsolePi to connect is the only one that will have menu-items for all the connected ConsolePis on the initial launch of ```consolepi-menu```.  Use the refresh option in ```consolepi-menu``` if connecting to one of the previous ConsolePis so it can fetch the data for ConsolePis that came online after it did.

 - `consolepi-menu` does not attempt to connect to the cloud on launch, it retrieves remote data from the local cache file only, verifies the devices are reachable, and if so adds them to the menu.  To trigger a cloud update use the refresh option.  *Note that ConsolePi will automatically update the local cache file when it gets an IP address, so the refresh should only be necessary if other ConsolePis have come online since the refresh.*

 - Read The [Google Drive Setup](readme_content/gdrive.md) for instructions on setting up Google Drive and authorizing ConsolePi to leverage the API.

   #### If you are configuring multiple ConsolePis to use this cluster, you should consider using the [Flash-Card imaging script](#3.-automated-flash-card-imaging-with-auto-install-on-boot).  Once You've installed the first ConsolePi, leverage the Automated flash-card imaging script to pre-stage the micro-sd cards for the other ConsolePis you will be creating.  This script is handy, if duplicating the install across multiple ConsolePis.  It can pre-stage the entire configuration and cut out some install time.

## ConsolePi API

ConsolePi includes an API with the following available methods (All Are GET methods via http currently).

/api/v1.0/
* adapters: returns list of local adapters
* remotes: returns the local cloud cache
* interfaces: returns interface / IP details
* outlets: returns details for defined outlets (power control function)
* details: full json representing all local details for the ConsolePi   

The API is used by ConsolePi when mdns doesn't have the head-room for all of the data.  When this occurs, the remote will advertise via mdns without it's adapter data, the local ConsolePi will detect the adapter data was stripped out and request it via the API.

> The API is currently unsecured, it uses http, and Auth is not implemented yet.  It currently only supports GET requests and doesn't provide any sensitive (credential) data.

## Power Control

The Power Control Function allows you to control power to external outlets.  ConsolePi supports:
  - [digital Loggers](https://www.digital-loggers.com/index.html) Ethernet Power Switch/Web Power Switch (including older models lacking rest API).
  - External relays controlled by ConsolePi GPIO ( Like this one [Digital-Loggers IoT Relay](https://dlidirect.com/products/iot-power-relay) ).
  - [Tasmota](https://blakadder.github.io/templates/) flashed WiFi smart [outlets](https://blakadder.github.io/templates/) (i.e. SonOff S31).  These are low cost outlets based on ESP8266 microcontrollers.
      > Tasmota was chosen because it allows for local control without reliance on a cloud service.  So your 'kit' can include a small relatively portable smart outlet which can be programmed to connect to the ConsolePi hotspot.  Then ConsolePi can control that outlet even if an internet connection is not available.
- If the function is enabled and outlets are defined, an option in `consolepi-menu` will be presented allowing access to a sub-menu where those outlets can be controlled (toggle power on/off, cycle, rename(rename only implemented for dli power switch outlets currently)).
- Outlets can be linked to Console Adapter(s) (best if the adapter is pre-defined using `consolepi-addconsole`).  If there is a link defined between the outlet and the adapter, anytime you initiate a connection to the adapter via `consolepi-menu` ConsolePi will ensure the outlet is powered on.  Otherwise if the link is defined you can connect to a device and power it on, simply by initiating the connection from the menu (*does not apply when connecting via TELNET*).
    > The power sub-menu **currently** only appears in the menu on the ConsolePi where the outlets are defined (Menu does not display outlets defined on remote ConsolePis).  The auto-power-on when connecting to an adapter linked to an outlet works for both local and remote connections (establishing a connection to an adapter on a remote ConsolePi (clustering / cloud-sync function) via another ConsolePis menu)

### Power Control Setup

After enabling via `consolepi-upgrade` or during initial install; `power.json` needs to be populated, see `power.json.example` for formatting.
The file should look something like this:
```
{
    "vc33_test_env": {
        "type": "tasmota",
        "address": "10.3.0.11",
        "linked": true,
        "linked_devs": ["/dev/Aruba2930F_cloud-lab", "/dev/SDBranchGW1_cloud-lab"]
        },
    "Aruba8325_Top": {
        "type": "GPIO",
        "address": 4,
        "noff": true,
        "linked": true,
        "linked_devs": ["/dev/Orange6_Home_7006"]
        },
    "switching_lab": {
        "type": "GPIO",
        "address": 19,
        "noff": true,
        "linked": false,
        "linked_devs": []
        },
    "labpower1": {
        "type": "dli",
        "address": "labpower1.example.com",
        "username": "apiuser",
        "password": "redacted",
        "linked": true,
        "linked_ports": [5, 6],
        "linked_devs": ["/dev/FT4232H_port1"]
        },
    "labpower2": {
        "type": "dli",
        "address": "labpower2.example.com",
        "username": "apiuser",
        "password": "redacted",
        "linked": true,
        "linked_ports": 8,
        "linked_devs": ["/dev/FT4232H_port2", "/dev/Aruba6300"]
        },
    "dli_with_no_linked_outlets": {
        "type": "dli",
        "address": "10.0.30.71",
        "username": "apiuser",
        "password": "redacted"
        }
}
```
The example above assumes you have udev rules assigning aliases ('Aruba2930F_cloud-lab', 'SDBranchGW1_cloud-lab' ...) to specific adapters (You can use `consolepi-addconsole` to accomplish this with most adapters.).

> You could link the root devices i.e. /dev/ttyUSB0 or /dev/ttyACM0 to an outlet.  This will work if there is no alias configured for the adapter.  The predictable aliases just ensure the outlet is linked to a specific physical adapter, where the root devices essentially links the outlet to whichever adapter was plugged in first.  In either case the function only powers ON the outlet automatically.  It will **not** power OFF a device. The power sub-menu provides full on|off|cycle|rename capabilities for the ports.


The schema or explanation of fields:
```
{
  "unique_name_for_outlet_grp": [required, string] ... this is how the outlet is described in the power sub-menu 
  {
    "type": [required, valid values = "GPIO", "tasmota", "dli"]
    "address": [required, integer(GPIO pin (BCM numbering)) if type is "GPIO" OR string(ip address) if type is "tasmota" or "dli"]
    "noff": [required for type GPIO, bool] ... indicates if outlet is normally off (true) or normally on (false)
    "username": [required for dli, str] username used to access the dli
    "password": [required for dli, str] password used to access the dli
    "linked": *Depricated* If there are linked_devs defined it's linked
    "linked_devs": [required to enable outlet linkage with adapter or host, str or list of str] each str in the list specifies a linked serial adapter (including /dev/ prefix is no longer required, alias will suffice)
    "linked_ports": [required if dli, int or list of ints], The Ports on the dli that are linked to the adapter(s).
  }
}
```
> NOTE: The Power Menu and how outlets are defined will continue to evolve.  The schema will change in the future.  Still thinking through it but thougt is to define the outlets under 1 key, with outlet_names, then define adapter linkages under a separate key (outlet-groups).  Add Group level operations `all on` ... etc.

#### GPIO Connected Relays
- For GPIO controlled relays: The trigger on the relay should be connected to GPIO ports.  Trigger(+) to one of the GPIO pins, Trigger(-) to one of the GPIO ground pins.
- ConsolePi expects the GPIO number not the Board pin # in `power.json`.  For example given the GPIO layout for the Raspberry Pi below.  Board Pin # 7 = GPIO 4.  `power.json` should be populated with 4.
> The Power Control Function supports relays with outlets that are 'normally on' or 'normally off'.  A 'normally off' outlet will not apply power until told to do so by ConsolePi (voltage applied to Trigger).  A 'normally on' outlet works the opposite way, it will have power with no voltage on the trigger, meaning it would be powered even if there is no connection to the ConsolePi.  It only powers off the outlet if ConsolePi applies voltage.  
>
> *A 'normally off' outlet will revert to powered off if ConsolePi is powered-off, disconnected, or rebooted, inversly a 'normally on' outlet will revert to a powered-on state if ConsolePi is powered-off, disconnected, or rebooted.*
>
> ConsolePi Supports both 'normally on' and 'normally off' outlets, this is configured via the required "noff" key in the power.json file (true|false).

![GPIO Pin Layout](readme_content/pin_layout.svg)

#### WiFi Smart Outlets (Tasmota)
- You'll need a WiFi smart outlet running Tasmota.  There are plenty of resources online to help with that.  You should start [here](https://blakadder.github.io/templates/)
- You can control the outlet as long as ConsolePi can reach it (IP).
- When setting the outlet to connect to ConsolePi via hotspot, it's best to configure a DHCP reservation so it is assigned the same IP everytime.  This way the IP in power.json is always valid.

To add a DHCP reservation you'll need to determine the MAC address of the smart-outlet.  If you're not sure what the MAC is, you can run `tail -f /var/log/syslog | grep DHCPACK`.  Then power on the smart-outlet.  Once it connects and gets DHCP you should see a log with the MAC.  Then use <ctrl+c> to break out of `tail -f`.
To Create the reservation add a file in the `/etc/dnsmasq.d/` directory called something like `smartoutlets`
```
sudo nano /etc/dnsmasq.d/smartoutlets
```
Then in nano add something like the following:
```
#Outlet A
dhcp-host=b4:e6:2d:aa:bb:99,outleta,10.3.0.11
```
repeat as needed for multiple outlets.

Then your power.json file should look something like this:
```
{
    "OutletA": {
        "type": "tasmota",
        "address": "10.3.0.11",
        "linked_devs": ["/dev/Aruba2930F_cloud-lab", "SDBranchGW1_cloud-lab"]
        }
}
```

#### DLI Web/Ethernet Power Switch

Just add the definition for the dli in power.json which should look something like this:
```
{
    "labpower1": {
        "type": "dli",
        "address": "labpower1.example.com",
        "username": "apiuser",
        "password": "redacted",
        "linked_ports": [5, 6],
        "linked_devs": "2530IAP"
        },
    "labpower2": {
        "type": "dli",
        "address": "labpower2.example.com",
        "username": "apiuser",
        "password": "redacted",
        "linked_ports": 8,
        "linked_devs": ["/dev/2530IAP", "Aruba6300"]
        },
    "dli_with_no_linked_outlets": {
        "type": "dli",
        "address": "10.0.30.71",
        "username": "apiuser",
        "password": "redacted"
        }
}

```
**The Above Example highlights different options**
- Outlet Group "labpower1" has multiple ports linked to a single adapter.  Both ports would be powered on when connecting to that adapter.
- Outlet Group "labpower2" has a single port linked to multiple adapters.  Connecting to either adapter via the menu will result in the port being powered
- As shown in Outlet Group "labpower2" the /dev/ prefix is now optional.
- The last Outlet Group defines the dli, but has no linkages.  This outlet group won't appear in the power menu invoked by 'p', but dlis have thier own dedicated menu 'd' that displays all ports on the dli.
- Notice `/dev/2530IAP` is linked in 2 different outlet groups, meaning a connection to 2530IAP will power on labpower1 port 5 and 6, as well as, labpower2 port 8.
> More granular port linkage mappings for dli will come when I switch to a single yaml for all configs.

### Manual Host Entries
The Manual Host Entries Feature allows you to manually define other SSH or TELNET endpoints that you want to appear in the menu.  These entries don't currently show up in the main menu on launch, they will appear in the `s` remote shell menu.  Manual host entries do support outlet linkages (Auto Power On when connecting throught he menu) To enable this feature simply create a hosts.json file in /etc/ConsolePi with the following structure:

```
{
    "8320T": {
        "method": "ssh",
        "address": "10.0.30.41",
        "user": "wade"
    },
    "8320B": {
        "method": "ssh",
        "address": "10.0.30.42",
        "user": "wade"
    },
    "5900T": {
        "method": "ssh",
        "address": "172.30.0.7:22",
        "user": "wade"
    },
    "5900T_console": {
        "method": "telnet",
        "address": "labdigi.example.com:7007"
    },
    "LabDigi1": {
        "method": "ssh",
        "user": "wade",
        "address": "labdigi.example.com"
    }
}
```
**The Above Example highlights different options**
- The address field can be a IP or FQDN and a custom port can be included by appending :port to the end of the address
- All but 5900T_console are ssh.
- 5900T and 5900T_console show the address with port defined (optional)
- outlet linkages with these devices are supported by adding the device name in linked_devs for an outlet defined in power.json
    > Ensure names are unique across both hosts defined here and the adapters defined via the menu or `consolepi-addconsole`.  If there is a conflict the serial adapter wins.

# Installation

If you have a Linux system available you can use the [Flash-Card imaging script](#3.-automated-flash-card-imaging-with-auto-install-on-boot)  to burn the image to a micro-sd, enable SSH, pre-configure a WLAN (optional), and PreConfigure ConsolePi settings (optional).  This script is especially useful for doing headless installations.

**The Following Applies to All Automated Installation methods**

ConsolePi will **optionally** use pre-configured settings for the following if they are placed in the logged in users home-dir when the installer starts (i.e. /home/pi) or in a 'ConsolePi_stage' subdir (i.e. /home/pi/ConsolePi_stage).  This is optional, the installer will prompt for the information if not pre-configured.  It will prompt you to verify either way.

- ConsolePi.conf: This is the main configuration file where all ConsolePi.conf configurable settings are defined.  If provided in the users home dir the installer will ask for verification then create the working config /etc/ConsolePi/ConsolePi.conf

- ConsolePi.ovpn: If using the automatic OpenVPN feature this file is placed in the appropriate directory during the install. *Note: there are a few lines specific to ConsolePi functionality that should be at the end of the file, I haven't automated the check/add for those lines so make sure they are there.  Refer to the example file in the /etc/ConsolePi/src dir*

- ovpn_credentials: Credentials file for OpenVPN.  Will be placed in the appropriate OpenVPN dir during the install.  This is a simple text file with the openvpn username on the first line and the password on the second line.

  *The script will chmod 600 everything in the /etc/openvpn/client directory for security so the files will only be accessible via sudo (root).*

- 10-ConsolePi.rules: udev rules file used to automatically map specific adapters to specific telnet ports.  So every time you plug in that specific adapter it will be reachable on the same telnet port even if other adapters are also plugged in.  Pre-Configuring this is only useful if you are doing a rebuild and already have a rules file defined, it allows you to skip the step in the install where the rules are created by plugging adapters in 1 at a time.

- wpa_supplicant.conf:  If found during install this file will be copied to /etc/wpa_supplicant.  The file is parsed to determine if any EAP-TLS SSIDs are configured, and if so the associated certificate files are also copied to the directory specified in the wpa_supplicant.conf file.  

  The script will look for certs in the following directories (using pi as an example will look in user home dir for any user):

  1. /home/pi
  2. /home/pi/cert
  3. /home/pi/ConsolePi_stage/cert

- ConsolePi_init.sh: Custom post install script.  This custom script is triggered after all install steps are complete.  It runs just before the post-install message is displayed.

**To enable the Clustering / Cloud-Sync function see the description [above](#consolepi-cluster-/-cloud-config) and the prerequisite [Google Drive Setup](readme_content/gdrive.md)  instructions.**

## **1. Automated Installation**

Install raspbian on a raspberryPi and connect it to the network.

Use the command string below to kick-off the automated installer.  The install script is designed to be essentially turn-key.  It will prompt to change hostname, set timezone, and update the pi users password if you're logged in as pi.  Be sure to checkout the [image creator script](#3-automated-flash-card-imaging-with-auto-install-on-boot) if doing a headless install, or if you are creating multiple ConsolePis

```
sudo wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/install.sh -O /tmp/ConsolePi && sudo bash /tmp/ConsolePi && sudo rm -f /tmp/ConsolePi
```

## **2. Semi-Automatic Install**

Alternatively you can clone this repository to /etc manually, then run the install script.  The only real benefit here would be pre-configuring some of the parameters in the config file:

```
cd /etc
sudo git clone https://github.com/Pack3tL0ss/ConsolePi.git
```

Optionally Pre-Configure parameters, it will result in less time on data-collection/user-input during the install.  Just grab the ConsolePi.conf.example file from the repo, edit it with your settings, and place it in the home dir (for the logged in user: i.e. /home/pi)

```
# example assuming logged in as pi
cd ~/
sudo mv ConsolePi.conf.example ConsolePi.conf
sudo nano ConsolePi.conf
```

Configure parameters to your liking then
ctrl + o  --> to save
ctrl + x  --> to exit
Then run the installer

```
cd /etc/ConsolePi/installer
sudo ./install.sh
```

## 3. Automated Flash Card Imaging with Auto-Install on boot

**Script has been tested and works with USB to micro-sd adapter and sd to micro-sd adapters.**

*This is a script I used during testing to expedite the process Use at your own risk it does flash a drive so it could do harm!*

*NOTE: USB adapters seemed to have more consistency than sd/micro-sd adapters, the latter would occasionally not mount until after the adapter was removed and re-inserted*

Using a Linux System (Most distros should work ... tested on Raspbian and Mint) enter the following command:
`curl -JLO https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/ConsolePi_image_creator.sh  && sudo chmod +x ConsolePi_image_creator.sh`

That will download the image creator and make it executable.
Then I would suggest `head -48 ConsolePi_image_creator.sh`, Which will print the top of the file where everything is explained in more detail.  

#### **ConsolePi_image_creator brief summary:**

*The "Stage dir" referenced below is a sub directory found in the script dir (the directory you run the script from).  The script looks for the Stage dir which needs to be named 'ConsolePi_stage' and moves the entire directory to the pi users home directory.*

The Pre-staging described below is optional, this script can be used without any pre-staging files, it will simply burn the Raspbian-lite image to the micro-sd and set the installer to run automatically on boot (unless you set auto_install to false in the script.  It's true by default).  

**NOTE: The script will look for and pull down the most current Raspbian "lite" image, that's the more bare-bones Raspbian image with no desktop environment.  If you want to use if for one of the images that includes a desktop, that's possible, but the script would need to be tweaked to support that. **

*A Quick and dirty way to achieve this would be to add ```img_file="<name-of-image>"``` below the comment on line 190 of the script.  Place the image in the same dir as the script.  The script will still check for (and download if not found) the most current lite image, but the new line will effectively override all that and tell it to use the file you've specified*

- automatically pull the most recent raspbian-lite image if one is not found in the script-dir (whatever dir you run it from)
- Make an attempt to determine the correct drive to be flashed, allow user to verify/confirm (given option to display fdisk -l output)
- Flash image to micro-sd card
- PreConfigure ConsolePi with parameters normally entered during the initial install.  So you bypass data entry and just get a verification screen.
- The entire stage dir (ConsolePi_stage) is moved to the micro-sd if found in the script dir.  This can be used to pre-stage a number of config files the installer will detect and use, along with anything else you'd like on the ConsolePi image.
- Pre-Configure a psk or open WLAN via parameters in script, and Enable SSH.  Useful for headless installation, you just need to determine what IP address ConsolePi gets from DHCP.
- You can also pre-configure WLAN by placing a wpa_supplicant.conf file in the script dir (or stage dir).  This method supports EAP-TLS with certificates.  Just place the cert files referenced in the provided wpa_supplicant.conf file in a 'cert' folder inside the stage dir.  ( Only works for a single EAP-TLS SSID or rather a single set of certs ).
- PreStage all OpenVPN related files (ConsolePi.ovpn and ovpn_credentials) by placing them on the ConsolePi image.  The script will detect them if found in script dir or stage dir.  The installer will then detect them and place them in the /etc/openvpn/client directory.  By default the installer places example files in for OpenVPN (as the specifics depend on your server config).
- create a quick command 'consolepi-install' to simplify the long command string to pull the installer from this repo and launch.
- The ConsolePi installer will start on first login, as long as the RaspberryPi has internet access.  This can be disabled by setting auto_install to false in this script.

Once Complete you place the newly blessed micro-sd in your raspberryPi and boot.  The installer will automatically start unless you've disabled it.  In which case the `consolepi-install` will launch the installer.

# ConsolePi Usage

## **Configuration:**

The Configuration file is validated and created during the install.  Settings can be modified post-install via the configuration file `/etc/ConsolePi.conf` (Some Changes will require consolepi-upgrade to be ran to take effect)

## **Console Server:**

### TELNET

*Don't overlook consolepi-menu which supports remote ConsolePi discovery and provides a single launch point into any local and remote connections discovered*

- Serial/Console adapters that show up as ttyUSB# devices when plugged in are reachable starting with telnet port 8001 +1 for each subsequent adapter plugged in (8002, 8003...).  If you are using a multi-port pigtail adapter or have multiple adapters plugged in @ boot, then it's a crap shoot which will be assigned to each telnet port.  Hence the next step.

- Serial/Console adapters that show up as ttyACM# devices start at 9001 +1 for each subsequent device.

> Most USB to serial adapters present as ttyUSB, some emnbeded adapters; i.e. network devices with built in USB console (typically a micro or mini USB) may show up as ttyACM#  

- The install script automates the mapping of specific adapters to specific ports.  The defined predictable adapters start with 7001 +1 for each adapter you define.  The reasoning behind this is so you can label the adapters and always know what port you would reach them on.  Key if you are using a  multi-port pig-tail adapter, or if multiple adapters are plugged in @ boot.  This can also be accomplished after the install via the `consolepi-addconsole` command.

  >Note: Some cheap a@# serial console adapters don't define serial #s, which is one of the attributes used to uniquely identify the adapter.  If the script finds this to be the case it will let you know and create a log with an attribute walk for the adapter; ```/var/log/ConsolePi/consolepi-addudev.error```* 

Note: the 8000/9000 range is always valid even if you are using an adapter specifically mapped to a port in the 7000 range.  So if you plug in an adapter (ttyUSB) pre-mapped to port 7005, and it's the only adapter plugged in, it would also be available on port 8001

- Port monitoring/and control is available on TELNET port 7000.  This allows you to change the baud rate of the port on the fly without changing the config permanently.  The installer configures all ports to 9600 8N1. 
- Serial Port configuration options can be modified after the install in /etc/ser2net.conf


### SSH / BlueTooth

The ```consolepi-menu``` command can be used to display a menu providing options for any locally connected USB to Serial adapters.  In addition to any remotely connected USB to serial adapters connected to other remote ConsolePis discovered (either via mdns or the Cloud Sync function).  When connecting to ConsolePi via bluetooth this menu launches automatically.
> Note that when using bluetooth the menu is limited to local adapters and remotes found in the local-cache file.  Connect via SSH for full remote functionality in the menu.
>
>Serial Adapter connection options (baud, flow-control, data-bits, parity) are extracted from ser2net.conf by consolepi-menu.  If there is an issue getting the data it falls back to the default of 9600 8N1 which can be changed in the menu (option c)


## **Convenience Commands:**

There are a few convenience commands created for ConsolePi during the automated install

- **consolepi-menu**: Launches ConsolePi Console Menu, which will have menu items described in the list below.  This menu is launched automatically when connecting to ConsolePi via BlueTooth, but can also be invoked from any shell session (i.e. SSH)

    - Connection options for locally attached serial adapters
    - Connection options for serial adapters connected to remote ConsolePis (discovered via mdns or cloud-sync as described [here](#consolepi-cluster--cloud-config))
    - sub-menu to automate distribution of ssh keys to remote ConsolePis.
      > *Distributing SSH keys allows you to securely connect to the remote adapter seemlessly without the need to enter a password.*
    - Remote Shell sub-menu, providing options to ssh directly to the shell of one of the remote ConsolePis
    - Power Control sub-menu if power relays have been defined (as described [here](#power-control))
    - Refresh option: If Cloud-Sync is enabled ConsolePi only reaches out to the cloud when the refresh option is used, *NOT* during initial menu-load.  Refresh will detect any new serail adapters directly attahced, as well as connect to Gdrive to sync.
    >Some menu items only appear if the feature is enabled.
    
    

  > ```consolepi-menu``` also accepts a single argument "sh".  Which will launch the original consolepi-menu created in bash.  It's been crippled so it only displays local connections, it loads a bit faster because it's local only, and doens't need to import any modules as the new full-featured Python based menu does.  This is currently the default menu that launches when connecting via bluetooth.  Although if connecting to a RaspberryPi Zero you may find it more favorable based on load time.

- **consolepi-upgrade**:  Upgrades ConsolePi:  **Required method to properly update ConsolePi**.  *Currently bypasses upgrade of ser2net (it's compiled from source).*

- **consolepi-remotes**: Displays the formatted contents of the local cloud cache.  This command accepts an optional case sensitive argument: Hostname of the remote ConsolePi.  If a hostname is provided only data for that host will be displayed (if it exists in the local cache, if it doesn't exist the entire cache is dispayed).  

    > This command can also be used to remove a remote from the local cache by using the argument 'del' followed by the hostname.  i.e. `consolepi-remote del ConsolePi0` will delete ConsolePi0 from the local cache.
    
- **consolepi-details**: Displays full details of all data ConsolePi collects/generates.  With multiple available arguments.
    - ```consolepi-details``` : Displays all collected data
    - ```consolepi-details local``` : Same as above but without data for remote ConsolePis
    - ```consolepi-details [<remote consolepi hostname>]``` : Displays data for the specified remote ConsolePi only (from the local cloud cache)
    - ```consolepi-details adapters``` : Displays all data collected for discovered adapters connected directly to ConsolePi (USB to Serial Adapters)
    - ```consolepi-details interfaces``` : Displays interface data
    - ```consolepi-details outlets``` : Displays power outlet data
    - ```consolepi-details remotes``` : Displays data for remote ConsolePis from the local cloud cache

- **consolepi-addssids**:  Automates the creation of additional SSIDs which ConsolePi will attempt to connect to on boot.  Currently only supports psk and open SSIDs, but may eventually be improved to automate creation of other SSID types.
- **consolepi-addconsole**: Automates the process of detecting USB to serial adapters so friendly names can be defined for them (used in `consolepi-menu`) and mapping them to specific TELNET ports.  It does this by collecting the data required to create a udev rule.  It then creates the udev rule starting with the next available port (if rules already exist).
- **consolepi-autohotspot**: This script re-runs the autohotspot script which runs at boot (or periodically via cron although the installer currently doesn't configure that).  If the wlan adapter is already connected to an SSID it doesn't do anything.  If it's acting as a hotspot or not connected, it will scan for known SSIDs and attempt to connect, then fallback to a hotspot if it's unable to find/connect to a known SSID. 
- **consolepi-testhotspot**: Toggles (Disables/Enables) the SSIDs ConsolePi is configured to connect to as a client before falling back to hotspot mode.  This is done to aid in testing hotspot mode.  After toggling the SSIDs run consolepi-autohotspot to trigger a change in state.
- **consolepi-pbtest**: Used to test PushBullet this commands simulates an IP address change by calling the script responsible for sending the PB messages and passing in a random IP to force a notification.
- **consolepi-browse**: Runs the mdns browser script which runs as a daemon in the background by default.  When ran via this command it will display any ConsolePis discovered on the network along with the data being advertised by that remote ConsolePi.
- **consolepi-killvpn**: gracefully terminates the OpenVPN tunnel if established.

- **consolepi-bton**: Make ConsolePi Discoverable via BlueTooth (Default Behavior on boot)
- **consolepi-btoff**: Stop advertising via BlueTooth.  Previously paired devices will still be able to Pair.

## Upgrading ConsolePi

Use ```consolepi-upgrade``` to upgrade ConsolePi.  Simply doing a git pull *may* occasionally work, but there are a lot of system files, etc. outside of the ConsolePi folder that are occasionally updated, those changes are made via the upgrade script.

### Custom overrides
ConsolePi configures a number of system files elsewhere on the system.  If there is a need to create a custom one-off it's possible to do so simply by creating a file with the same name in /etc/ConsolePi/src/overrides/ directory.  For example:  ConsolePi configures rfcomm.service to enable bluetooth connections.  During upgrade that file is compared to the src template/file, if there are differences the original is backed up to /etc/ConsolePi/bak and the src template/file is used.  If a file with the name rfcomm.service exists in the override directory (this can be an empty file, it just has to exist), the upgrade process will just skip it.  It's then up to the user to manage the contents of the overriden system file.

> Note: The override process should have nearly 100% coverage, but that still needs to be verified.  It's best to backup any customizations to system files involved in ConsolePi functionality.

# Tested Hardware / Software

ConsolePi was built on raspbian Stretch, and has been tested with both Stretch and Buster.

ConsolePi Should work on all variants of the RaspberryPi, but it has been tested on the following: 

​	*If you find a variant of the Rpi that does not work, create an "issue" to let me know.  If I have one I'll test when I have time to do so*
- RaspberryPi 4 Model B
    - Tested with RaspberryPi Power supply, PoE Hat, and booster-pack (battery)
- RaspberryPi 3 Model B+
  - Tested with RaspberryPi Power supply, PoE Hat, and booster-pack (battery)
- RaspberryPi zero w
  - With both single port micro-usb otg USB adapter and multi-port otg usb-hub.  Use this with battery pack on a regular basis.
- Raspberry Pi 2 Model B (running Buster)
    - Tested via wired port, and with external USB-WiFi adapter.  Have not tested any BlueTooth Dongles
- Raspberry Pi Model B (running Buster)
    - Tested via wired port, and with external USB-WiFi adapter.  Have not tested any BlueTooth Dongles

>I did notice with some serial adapters the RaspberryPi zero w Would reboot when the adapter was plugged in, this is with a RaspberryPi power-supply.  They work fine, it just caused it to reboot when initially plugged-in.

# ConsolePi @ Work!

Have some good pics of ConsolePi in action?  Let me know.

  ![ConsolePi in action](readme_content/ConsolePi.jpg)
  ![ConsolePi in action](readme_content/ConsolePi0.jpg)

# CREDITS

ConsolePi utilizes a couple of other projects so Some Credit

1. **AutoHotSpotN** ([roboberry](http://www.raspberryconnect.com/network/itemlist/user/269-graeme))

   Network Wifi & Hotspot with Internet
   A script to switch between a wifi network and an Internet routed Hotspot
   A Raspberry Pi with a network port required for Internet in hotspot mode.
   Works at startup or with a seperate timer or manually without a reboot
   Other setup required find out more at
   http://www.raspberryconnect.com

   *ConsolePi Provides the source script for AutoHotSpotN as there are minor modifications to the script for some ConsolePi functionality*

2. **ser2net** ([cminyard](http://sourceforge.net/users/cminyard))

   This project provides a proxy that allows telnet/tcp connections to be made to serial ports on a machine.

   https://sourceforge.net/projects/ser2net/

   https://github.com/cminyard/ser2net

   *The ser2net available from apt works and has been tested, the installation script pulls the far more current version from sourceforge and compiles/installs it and builds the config*


