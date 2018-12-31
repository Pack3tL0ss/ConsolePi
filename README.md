# ConsolePi

Automated Raspberry Pi Serial Console Server, with PushBullet Notification of IP changes, Automatic VPN termination...

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

When the Automatic VPN function successfully terminates the configured tunnel, the Tunnel IP is sent via PushBullet API

Each Time a Notification is triggered all interface IPs are sent in the message along with the ConsolePi's default gatewway

 

##  Components

*Some of the components utilize other projects see Credits section for source details.*

- ser2net
- AutoHotSpotN
- udev rules (predictable port numbers based on the usb to serial adapter used)
- dnsmasq configuration which is dynamically changed based on wired port reachability (pass gateway to clients or not based on wired port status)
- dhcpcd: configure dhcp client with fallback to static if transitioning to hotspot mode
- ConsolePi script (triggered via dhcp-run-hooks). Runs anytime an IP is assigned to an interface.  Controls dhcp server configuration, PushBullet Notification, OpenVPN Connection, etc.
- init script to reset on boot: Resets some temporary files used to compare IPs to determine if a notification should be sent.  The temp files prevent PushBullet from re-sending a notification if DHCP re-spins, but it's the same IP.  The reset script resets these values on boot.
- OpenVPN Configuration:  Most of the ovpn config would be dependent on how you've configured the OpenVPN server... There are some additional lines appended to trigger Notification on successful VPN connection.
- Configure OpenVPN to log to /var/log/ConsolePi directory and configure log rotation
- Installation Script:  Grabs everything from this repository, and from external source.  Accepts Configuration File with defaults (which can be edited prior to run if desired).  Prompts user for values interactively, installs necessary components and places files etc. in necessary locations.  
  - installation script also creates a udev rule creator.  It prompts the user to plug in serial adapters 1 at a time, creates udev rules for each.  This allows you to label the adapter.  i.e. adapter 1 is always going to be reachable on telnet port 7001 etc.





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