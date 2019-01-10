# ConsolePi

Automated Raspberry Pi Serial Console Server, with PushBullet Notification of IP changes, Automatic VPN termination...

*TL;DR:*

Single Command Install Script. Run from a RaspberryPi running raspbian (that has internet access):
`sudo wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/install.sh -O /tmp/ConsolePi && sudo bash /tmp/ConsolePi && sudo rm -f /tmp/ConsolePi`

------
# Contents
 - [What Does it Do](#what-does-it-do)
 - [Installation](#installation)
 - [Tested Hardware](#tested-hardware)
 - [Credits](#credits)
------

## What Does it Do

Acts as a serial Console Server, allowing you to remotely connect to ConsolePi via Telnet to gain Console Access to devices connected to ConsolePi via USB to serial adapters (i.e. Switches, Routers, Access Points... anything with a serial port)

**AutoHotSpot**

Script runs at boot (can be made to check on interval via Cron if desired).  Looks for pre-defined SSIDs, if those SSIDs are not available then it automatically goes into hotspot mode and broadcasts its own SSID.  In HotSpot mode user traffic is NAT'd to the wired interface if the wired interface is up.

When ConsolePi enters hotspot mode, it first determines if the wired port is up and has an IP.  If the wired port is *not* connected, then the hotspot distributes DHCP, but does not provide a "Default Gateway" to clients.  This allows a user to dual connect without having to remove a route to a gateway that can't get anywhere.  I commonly use a second USB NIC to connect to ConsolePi, while remaining connected to the internet via a different SSID on my primary NIC.

If ConsolePi determines there is a wired connection when the hotspot is enabled it forwards (NATs) traffic from clients connected to the hotspot to the wired interface.

**Automatic OpenVPN Tunnel**

When an interface recieves an IP address ConsolePi will Automatically connect to an OpenVPN server under the following conditions:
- It's configured to use the OpenVPN feature, and the ConsolePi.ovpn file exists (an example is provided during install)
- ConsolePi is not on the users home network (determined by the 'domain' handed out by DHCP)
- The internet is reachable.  (Checked by pinging a configurable common internet reachable destination)

 **Automatic PushBullet Notification:**  

*(Requires a PushBullet Account, API key, and the app for mobile devices.)*

When ConsolePi receives a dynamic IP address.  A message is sent to your phone via PushBullet API with the IP so you know can connect.

![Push Bullet Notification image](readme_content/ConsolePiPB1.png)

When the Automatic VPN function successfully terminates the configured tunnel, the Tunnel IP is sent via PushBullet API

![Push Bullet Notification image](readme_content/ConsolePiPB2.png)

Each Time a Notification is triggered all interface IPs are sent in the message along with the ConsolePi's default gateway

## Installation

If you have a Linux system available you can use the Automated FlashCard imaging script (#3) below to burn the image to a micro-sd, enable SSH, and pre-configure a WLAN as well as PreConfigure ConsolePi settings.  This is the most automated way to install ConsolePi, and was used numerous times during testing.

**The Following Applies to All Automated Installation methods**

ConsolePi will optionally use pre-configured settings for the following if they are placed in the logged in users home-dir when the installer starts (i.e. /home/pi).  This is optional, the installer will prompt for the information if not pre-configured.

- ConsolePi.conf: This is the main configuration file where all ConsolePi.conf configurable settings are defined.  If provided in the users home dir the installer will ask for verification then create the working config /etc/ConsolePi/ConsolePi.conf

- ConsolePi.ovpn: If using the automatic OpenVPN feature this file is placed in the appropriate directory during the install. *Note: there are a few lines specific to ConsolePi functionality that should be at the end of the file, I haven't automated the check/add for those lines so make sure they are there.  Refer to the example file in the ConsolePi/src dir*

- ovpn_credentials: Credentials file for OpenVPN.  Will be placed in the appropriate OpenVPN dir during the install.  This is a simple text file with the openvpn username on the first line and the password on the second line.

*The script will chmod 600 everything in the /etc/openvpn/client directory for security so the files will only be accessible via sudo (root).*

**1. Automatic Installation**

Install raspbian on a raspberryPi and connect it to the network.

The install script below is designed to be essentially turn-key.  It will prompt to change hostname, set timezone, and update the pi users password if you're logged in as pi.

```
sudo wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/install.sh -O /tmp/ConsolePi && sudo bash /tmp/ConsolePi && sudo rm -f /tmp/ConsolePi
```

**2. Semi-Automatic Install**

Alternatively you can clone this repository, then run the install script.  The only real benefit here would be pre-configuring some of the parameters in the config file:

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

**3. Automated Flash Card Imaging with AutoInstall on boot**

*This is a script I used during testing to expedite the process Use at your own risk it does flash a drive so it could do harm*
Using a Linux System (Most distros should work ... tested on Raspbian and Mint) enter the following command:
`curl -JLO https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/ConsolePi_image_creator.sh  && sudo chmod +x ConsolePi_image_creator.sh`

That will download the image creator and make it executable.
Then I would suggest `head -40 ConsolePi_image_creator.sh`, Which will print the top of the file where everything is explained in more detail.  

**ConsolePi_image_creator brief summary:**
- automatically pull the most recent raspbian-lite image if one doesn't exist in the script-dir (whatever dir you run it from)
- Make an attempt to determine the correct drive to be flashed, allow user to verify/confirm (given option to display fdisk -l output)
- Flash image to micro-sd card
- PreConfigure ConsolePi with parameters normally entered during the initial install.  So you bypass data entry and just get a verification screen.
- PreConfigure a WLAN for the ConsolePi to connect to & enable SSH.  Useful for headless installation, you just need to determine what IP address ConsolePi gets from DHCP.
- Use real ovpn installation.  The installer puts an example in, but as the config is specific to your ovpn server, the installer doesn't put a working config in.
- create a quick command 'consolepi-install' to simplify the long command string to pull the installer from this repo and launch.
- The ConsolePi installer will start on first login, as long as the RaspberryPi has internet access.

Once Complete you place the newley blessed micro-sd in your raspberryPi and boot.  Login then `consolepi-install`

**4. Manual Installation**

Manual installation instructions are incomplete at the moment

For the brave or curious... Instructions on how to manually install can be found [here](readme_content/ConsolePi - Manual Installation.md).

## Tested Hardware

ConsolePi has been tested on the following:
- RaspberryPi 3 Model B+
  - Tested with RaspberryPi Power supply, PoE Hat, and booster-pack (battery), all worked fine *other than the known over-current errors on the original PoE Hat - still wored on my PoE switch*
- RaspberryPi zero w
  - With both single port micro-usb otg USB adapter and multi-port otg usb-hub
  *I did notice with some serial adapters the RaspberryPi zero w Would reboot when it was plugged in, this is with a RaspberryPi power-supply.  They work fine, it just caused it to reboot when initially plugged-in*

## CREDITS

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

   *The ser2net available from apt works and has been tested, the installation script pulls the far more current version from source and compiles/installs it and builds the config*

3. -- Not Currently Packaged -- **RaspAp** ([billz](https://github.com/billz))

   A simple, responsive web interface to control wifi and hostapd on the Raspberry Pi

   https://github.com/billz/raspap-webgui

   *RaspAP was tested initially with my first ConsolePi, but is not currently built into the ConsolePi Project.  Some of the changes RaspAP makes possible via the web-interface would likely be in conflict with some of the automated scripts.  It's possible but not high priority that it be integrated (as an option) into ConsolePi.*

