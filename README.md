# ConsolePi

Automated Raspberry Pi Serial Console Server, with PushBullet Notification of IP changes, Automatic VPN termination...

------
# Contents
 - [What Does it Do](#what-does-it-do)
 - [Installation](#installation)
 - [Tested Hardware](#tested-hardware)
 - [Credits](#credits)
------

## What Does it Do

Acts as a serial Console Server, allowing you to remotely connect to ConsolePi via Telnet to gain Console Access to devices connected to ConsolePi via USB to serial adapters (i.e. Switches, Routers, etc.)

**AutoHotSpot**

Script runs at boot (can be made to check on interval via Cron if desired).  Looks for pre-defined SSIDs, if those SSIDs are not available then it automatically goes into hotspot mode and broadcasts its own SSID.

When ConsolePi enters hotspot mode, it first determines if the wired port is up and has an IP.  If the wired port is *not* connected, then the hotspot distributes DHCP, but does not provide a "Default Gateway" to clients.  This allows a user to dual connect (using a 2nd NIC on Laptop) without having to remove a route to a gateway that can't get anywhere.

If ConsolePi determines there is a wired connection when the hotspot is enabled it acts as an AP routing (NAT) traffic from clients connected to the hotspot to the wired interface.

**Automatic OpenVPN Tunnel**

When ConsolePi receives an IP via DHCP on any interface it will first verify it's not on the users home network.  If not it will automatically establish a connection to an OpenVPN server based on configuration. 

 **Automatic PushBullet Notification:**  

*(Requires a PushBullet Account, API key, and the app for mobile devices.)*

When ConsolePi receives a dynamic IP address.  A message is sent to your phone via PushBullet API with the IP so you can connect remotely.

![Push Bullet Notification image](readme_content/ConsolePiPB1.png)

When the Automatic VPN function successfully terminates the configured tunnel, the Tunnel IP is sent via PushBullet API

![Push Bullet Notification image](readme_content/ConsolePiPB2.png)

Each Time a Notification is triggered all interface IPs are sent in the message along with the ConsolePi's default gateway

## Installation
*This script is a work in progress likely to result in errors at the moment*

**Automatic Installation**

This assumes you have raspian installed.

Once Configured and connected to the network run this command for completely automated install

```
wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/install.sh -O /tmp/ConsolePi && sudo bash /tmp/ConsolePi && rm -f /tmp/ConsolePi
```
**Semi-Automatic Install**

Alternatively you can clone this repository, then run the install script.  The only real benefit here would be pre-configuring some of the parameters in the config file:

```
cd /etc
sudo git clone https://github.com/Pack3tL0ss/ConsolePi.git
```

Optionally Pre-Configure parameters, it will result in less time on data-collection/user-input during the install.

```
sudo nano /etc/ConsolePi.conf
```

Configure parameters to your liking then

ctrl + o  --> to save

ctrl + x  --> to exit

Then run the installer

```cd /etc/ConsolePi
cd /etc/ConsolePi/installer
sudo chmod +x *   #only required for now until I figure out how to set it on git
sudo ./install.sh
```

**Manual Installation**

*INCOMPLETE INSTRUCTIONS FOR NOW*

<u>ser2net</u>: The installer above builds from source so you would have the newest version of ser2net available.  

You can install from source which is: https://sourceforge.net/projects/ser2net/files/latest/download

however unless you need features in the newer release the simpler method is to just install from apt.  (otherwise I'm too lazy to explain it all here, if you want the most current use the installer)

```
sudo apt-get install ser2net
```

edit /etc/ser2net.conf

The file should look something like this (below all the comments):

```
BANNER:banner:\r\nConsolePi port \p device \d [\s] (Debian GNU/Linux)\r\n\r\n

TRACEFILE:usb0:/var/log/consolePi/ser2net/usb0:\p-\M-\D-\Y_\H:\i:\s.\U
TRACEFILE:usb1:/var/log/consolePi/ser2net/usb1:\p-\M-\D-\Y_\H:\i:\s.\U
TRACEFILE:usb2:/var/log/consolePi/ser2net/usb2:\p-\M-\D-\Y_\H:\i:\s.\U
TRACEFILE:usb3:/var/log/consolePi/ser2net/usb3:\p-\M-\D-\Y_\H:\i:\s.\U
TRACEFILE:usb4:/var/log/consolePi/ser2net/usb4:\p-\M-\D-\Y_\H:\i:\s.\U

# Known Devices - tied to udev rules symlinks
7001:telnet:0:/dev/sissyblue1:9600 8DATABITS NONE 1STOPBIT banner
7002:telnet:0:/dev/sissyblue2:9600 8DATABITS NONE 1STOPBIT banner
7003:telnet:0:/dev/white_blue:9600 8DATABITS NONE 1STOPBIT banner
7004:telnet:0:/dev/arubaorg1:9600 8DATABITS NONE 1STOPBIT banner
7005:telnet:0:/dev/old:9600 8DATABITS NONE 1STOPBIT banner      

# unknown devices (known devices will also use these ports first come first serve in order)
8001:telnet:0:/dev/ttyUSB0:9600 8DATABITS NONE 1STOPBIT banner        
8002:telnet:0:/dev/ttyUSB1:9600 8DATABITS NONE 1STOPBIT banner        
8003:telnet:0:/dev/ttyUSB2:9600 8DATABITS NONE 1STOPBIT banner        
8004:telnet:0:/dev/ttyUSB3:9600 8DATABITS NONE 1STOPBIT banner
8005:telnet:0:/dev/ttyUSB4:9600 8DATABITS NONE 1STOPBIT banner
```

Optionally setup udev rules for Predictable Ports.  This way when you plug in a specific serial adapter you always know what port will be assigned to it (label them):

The Easiest Way to do this manually is to tail the syslog, then plug in the serial adapters 1 at a time taking note of some information as it comes in (log the session)

```
tail -f /var/log/messages | grep usb
```

The syslog will look like this

May  2 10:23:42 consolepi kernel: [145144.257115] usb 1-1.2: new full-speed USB device number 9 using dwc_otg
May  2 10:23:42 consolepi kernel: [145144.410521] usb 1-1.2: New USB device found, **idVendor=0403**, **idProduct=6001**
May  2 10:23:42 consolepi kernel: [145144.410535] usb 1-1.2: New USB device strings: Mfr=1, Product=2, SerialNumber=3
May  2 10:23:42 consolepi kernel: [145144.410543] usb 1-1.2: Product: US232R
May  2 10:23:42 consolepi kernel: [145144.410552] usb 1-1.2: Manufacturer: FTDI
May  2 10:23:42 consolepi kernel: [145144.410560] usb 1-1.2: **SerialNumber: FTD991J5**
May  2 10:23:42 consolepi kernel: [145144.414490] ftdi_sio 1-1.2:1.0: FTDI USB Serial Device converter detected
May  2 10:23:42 consolepi kernel: [145144.414641] usb 1-1.2: Detected FT232RL
May  2 10:23:42 consolepi kernel: [145144.415477] usb 1-1.2: FTDI USB Serial Device converter now attached to ttyUSB0
May  2 10:23:42 consolepi mtp-probe: checking bus 1, device 9: "/sys/devices/platform/soc/3f980000.usb/usb1/1-1/1-1.2"
May  2 10:23:42 consolepi mtp-probe: bus: 1, device: 9 was not an MTP device

You can also use `lsusb` to get the details.  The udev.sh script provided with ConsolePi and ran as part of the installation automates this process.

Once You've gathered the details.  Create the udev rules file

`sudo nano /etc/udev/rules.d/10-consolePi.rules`

with content similar to this:

```
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="FTD991J5", SYMLINK+="white_blue"
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="AL991JO9", SYMLINK+="sissyblue1"
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="AL01JY6T", SYMLINK+="sissyblue2"
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6015", ATTRS{serial}=="DO009KB9", SYMLINK+="arubaorg1"
SUBSYSTEM=="tty", ATTRS{idVendor}=="050d", ATTRS{idProduct}=="0109", ATTRS{serial}=="051447", SYMLINK+="old"
```

idVendor, idProduct and serial comes from what we collected as the serial adapters were plugged in.

It is the "SYMLINK" value that ties these rules to the port definition in ser2net.conf.  These rules create an alias for the specific device which is what we use to map the port.

If you only have 1 serial adapter, or only plan to use 1 at a time, none of this is necessary.  

<u>AutoHotSpotN</u>

With this script ConsolePi will first look for configured SSIDs to connect to, if none are available it will fall-back to hotspot mode.  This way you can take your ConsolePi anywhere and connect to it via WiFi.

Custom modifications for this project give the script an extra function, which is it looks to see if the wired interface is up when it enables the hotspot.  If it is it enables dhcp (dnsmasq) to distribute a default-gateway to clients (ConsolePis WLAN/hotspot interface).  If the wired interface is not up it does not distribute a default-gateway.  This allows you to connect with a dual-nic system without having your routes messed up by the addition of a route with no access.

To Configure AutoHotSpotN manually follow the instructions here:

 <http://www.raspberryconnect.com/network/item/330-raspberry-pi-auto-wifi-hotspot-switch-internet>

Then modify the file as follows:

Toward the top below the block of comments add

`[[ -f "/etc/ConsolePi/ConsolePi.conf" ]] && . "/etc/ConsolePi/ConsolePi.conf" || wlan_ip=10.99.99.1`

This checks to make sure ConsolePi.conf is there then reads it in.  That will give the script the wlan_ip variable used elsewhere in the config.  If it's not it falls back to 10.99.99.1 which is only useful if the other files match.

Modify the CreateAdHocNetwork function to look as follows:

```
createAdHocNetwork()
{
    echo "Creating Hotspot"
    ip link set dev "$wifidev" down
    ip a add ${wlan_ip}/24 brd + dev "$wifidev"
    ip link set dev "$wifidev" up
    debug=`ip addr show dev wlan0 | grep 'inet '| cut -d: -f2 |cut -d/ -f1| awk '{ print $2}'`
    logger -t autohotspot $wifidev is up with ip: $debug
    dhcpcd -k "$wifidev" >/dev/null 2>&1
    iptables -t nat -A POSTROUTING -o "$ethdev" -j MASQUERADE
    iptables -A FORWARD -i "$ethdev" -o "$wifidev" -m state --state RELATED,ESTABLISHED -j ACCEPT
    iptables -A FORWARD -i "$wifidev" -o "$ethdev" -j ACCEPT
    ChkWiredState
    systemctl start dnsmasq
    systemctl start hostapd
    echo 1 > /proc/sys/net/ipv4/ip_forward
}
```

insert the following function after the closing } for the ChkWifiUp function

```
ChkWiredState()
{
	eth0_ip=`ip addr show dev eth0 | grep 'inet '| cut -d: -f2 |cut -d/ -f1| awk '{ print $2}'`
	eth0_state=`ip addr show dev eth0 | head -1 | sed -n -e 's/^.*state //p' | cut -d ' ' -f1 |awk '{ print $1 }'`
	if [ ${eth0_state} == "UP" ] && [ ${#eth0_ip} -gt 6 ]; then    
	   eth0_up=true
	else
	   eth0_up=false     
	fi 

	# sudo cp /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
	if [ $eth0_up = false ]; then
		cp /etc/ConsolePi/dnsmasq.conf.noGW /etc/dnsmasq.conf
		logger -t autohotspot Bringing up hotspot with no gateway due to no eth0 connection
		echo Bringing up hotspot with no gateway due to no eth0 connection
	else
		cp /etc/ConsolePi/dnsmasq.conf.withGW /etc/dnsmasq.conf
		logger -t autohotspot Bringing up hotspot with gateway as eth0 is up with IP $eth0_ip
		echo Bringing up hotspot with gateway as eth0 is up with IP $eth0_ip
	fi
}
```

future: Change from swapping files to using SED to comment/uncomment gateway line in /etc/dnsmasq.conf  <-- this is a note to self.  Disregard if it makes no sense.







## Tested Hardware

ConsolePi has been tested on the following:
- RaspberryPi 3 Model B+
  - Tested with RaspberryPi Power supply, PoE Hat, and booster-pack (battery), all worked fine *other than the known over-current errors on the original PoE Hat - still wored on my PoE switch*
- RaspberryPi zero w
  - With both single port micro-usb otg USB adapter and multi-port otg usb-hub
  *I did notice with some serial adapters the RaspberryPi zero w Would reboot when it was plugged in, this is with a RaspberryPi power-supply.  They work fine, it just caused it to reboot when initially plugged-in*

## CREDITS

ConsolePi at it's core utilizes a number of other projects so Some Credit

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

   *RaspAP was tested initially when I set everything up, but is not currently built into the ConsolePi Project.  Some of the changes RaspAP makes possible via the web-interface would likely be in conflict with some of the automated scripts*
