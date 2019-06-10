# **ConsolePi - Manual Installation**

*INCOMPLETE INSTRUCTIONS FOR NOW This is a WIP*

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

Update... This change has been made, see AutoHotspotN script in src directory of repo.