#!/bin/bash

# ConsolePi dhcpcd.exit-hook
# System File @ /etc/dhcpcd.exit-hook symlinks to this file (makes updates via repo easier)
#   File is triggered by dhcpcd anytime an interface has dhcp activity (i.e. gets a new lease)
#   It triggers (based on settings in ConsolePi.conf):
#     - PushBullet Notifications
#     - Updates details to Cloud
#     - Establishes OpenVPN connection

# Locally Defined Variables
## debug=false # Now in config                                                        # For debugging only - additional logs sent to syslog
push_response_log="/var/log/ConsolePi/push_response.log"            # full path to send PushBullet API responses
ovpn_log="/var/log/ConsolePi/ovpn.log"                              # full path to send openvpn logs
ovpn_config="/etc/openvpn/client/ConsolePi.ovpn"	            # full path to openvpn configuration
ovpn_creds="/etc/openvpn/client/ovpn_credentials"                   # full path to openvpn creds file with username password
ovpn_options="--persist-remote-ip --ping 15"                        # openvpn command line options 

# Get Configuration from config file default if config file doesn't exist
if [[ -f "/etc/ConsolePi/ConsolePi.conf" ]]; then
    . "/etc/ConsolePi/ConsolePi.conf"
    # Disable OpenVPN if ovpn config is not found
    $ovpn_enable && [[ ! -f "${ovpn_config}" ]] && ovpn_enable=false && logger -t puship-ovpn ERROR: OpenVPN is enabled but ConsolePi.ovpn not found - disabling
else
	push=false                                                          # PushBullet Notifications: true - enable, false - disable
	ovpn_enable=false                                                   # if enabled will establish VPN connection
	push_api_key="BestToPutYourPBAPIKeyInTheConfigFileNotHere"		    # PushBullet API key
	push_iden="PBidenShouldBeDefinedinConfig"                           # iden of device to send PushBullet notification to if not push_all
	push_all=true                                                       # true - push to all devices, false - push only to push_iden
	vpn_check_ip="10.0.150.1"                                           # used to check VPN (internal) connectivity should be ip only reachable via VPN
	net_check_ip="8.8.8.8"                                              # used to check internet connectivity
	local_domain="arubalab.net"                                         # used to bypass VPN. evals domain sent via dhcp option if matches this var will not establish vpn
        cloud=false                  # enable ConsolePi clustering / cloud config sync
        debug=false                   # turns on additional logging data
fi


## when called after ovpn connect - assign script parameters to variables ##
[ ! -z $1 ] && arg1="$1"
[ ! -z $2 ] && interface="$2"
[ ! -z $5 ] && new_ip_address="$5"
[ -z $reason ] && reason="OVPN_CONNECTED"

## set variables if script called from shell for testing ##
## Usage for test scriptname test [<domain>]  domain is optional used to specify local_domain to test local connection (otherwise script will determine remote and attempt ovpn if enabled) 
#if [ -z $1 ] && [ $0 != "/lib/dhcpcd/dhcpcd-run-hooks" ]; then
if [[ $1 == "test" ]]; then
  logger -t puship-DEBUG Setting random test Variables script ran from shell
  rand1=`shuf -i 3-254 -n 1`
  rand2=`shuf -i 3-254 -n 1`
  reason=BOUND
  interface=eth0
  new_ip_address="10.1.$rand1.$rand2"
  [ ! -z $2 ] && new_domain="$2" || new_domain_name=""
fi

# >> Debug Messages <<
if $debug; then
  logger -t puship-DEBUG $interface - $reason
fi


# >> Send Messages to PushBullet <<
Push() {
    echo -e "\n---- $(date) ----" >> "$push_response_log"
    if $push_all || [ -z $push_iden ]; then
        # Push to all devices
        curl -u "$push_api_key" https://api.pushbullet.com/v2/pushes -d type=note -d title="$pushTitle" -d body="$pushMsg" >> "$push_response_log" 2>&1
    else
        # Push only to device specified by push_iden
        curl -u "$push_api_key" https://api.pushbullet.com/v2/pushes -d device_iden="$push_iden" -d type=note -d title="$pushTitle" -d body="$pushMsg" >> "$push_response_log" 2>&1
    fi

    [ "$reason" != "OVPN_CONNECTED" ] && logger -t puship $logMsg || logger -t puship-ovpn Sent Push Notification OVPN $interface IP $new_ip_address
}

# >> Store Newly assigned IPs to tmp files <<
StashNewIP() {
    logger -t puship \[StashNewIP\] $interface IP change detected from ${last_ip:-undefined} to $new_ip_address
    echo $new_ip_address > /tmp/$interface      # Place newip in tmp file for safe keeping new bind after carrier lost results in nul $old_ip_address being passed from dhcpcd so stashing it
    echo $(date +'%s') >> /tmp/$interface       # TimeStamp not currently used but can be to put a cap on push frequency if something started causing a lot of them
}

# >> This Function is depricated and no longer called - will be removed <<
OldGetCurrentIP() {
    $debug && logger -t puship-DEBUG Enter GetCurrentIP Function
    eth0_ip=`ip addr show dev eth0 2>/dev/null | grep 'inet '| cut -d: -f2 |cut -d/ -f1| awk '{ print $2}'`
    wlan0_ip=`ip addr show dev wlan0 | grep 'inet '| cut -d: -f2 |cut -d/ -f1| awk '{ print $2}'`
    tun0_ip=`ip addr show dev tun0 2>/dev/null | grep 'inet '| cut -d: -f2 |cut -d/ -f1| awk '{ print $2}'`
            xgw=`netstat -rn |grep '^0.0.0.0\s*'$xgw_part|cut -d: -f2| awk '{print $2}'`
}

GetCurrentIP() {
    sys_interface_list=`ls /sys/class/net | grep -v lo`
    # declare -A interfaces # declared outside of function for portability       
    for interface in ${sys_interface_list[@]}; do
        this_ip=`ip addr show dev $interface | grep 'inet '| cut -d: -f2 |cut -d/ -f1| awk '{ print $2}'`
        [ ${#this_ip} -gt 0 ] && interfaces[$interface]=$this_ip                
    done
    xgw=`netstat -rn |grep '^0.0.0.0\s*'$xgw_part|cut -d: -f2| awk '{print $2}'`
}

# >> Check Connectivity to net or VPN <<
Ping_Check() {
    $debug && logger -t puship-DEBUG Enter Ping_Check Function
    ping -c 1 $1 &> /dev/null && ping_ok=true || ping_ok=false
}

# >> Establish VPN Connection <<
Connect_VPN() {
    $debug && logger -t puship-DEBUG Enter Connect_VPN Function
    openvpn --config ${ovpn_config} --auth-user-pass ${ovpn_creds} --log-append ${ovpn_log} ${ovpn_options} --writepid /var/run/ovpn.pid --daemon
    logger -t puship-ovpn Starting OpenVPN client connection.
}

# >> Check if VPN process is running and get PID <<
Check_VPN_Running() {
    $debug && logger -t puship-DEBUG Enter Check_VPN_Running Function
    PID=`ps -elf | grep "openvpn" | grep -v grep | awk '{print $4}'`
    [ "" !=  "$PID" ] && vpn_run=true || vpn_run=false
}

# >> Check if VPN needs to be established <<
Check_VPN() {
    $debug && logger -t puship-DEBUG Enter Check_VPN Function "${local_domain}"
    GetCurrentIP
    if [ -z ${interfaces[tun0]} ]; then
      Ping_Check "$net_check_ip"
      if $ping_ok; then
        [ "${new_domain_name}" = "${local_domain}" ] && remote=false || remote=true
        $remote && Connect_VPN || logger -t puship-ovpn Not starting VPN - device connected to home lab
      else
          logger -t puship-ovpn OpenVPN start Bypassed due to failed network connectivity check.
      fi
    else
      Ping_Check "$vpn_check_ip"
      if $ping_ok; then
        logger -t puship-ovpn OpenVPN start initiated but vpn is up \(${interfaces[tun0]}\).  Doing nothing
      else
        Check_VPN_Runing
        $vpn_run && pkill -SIGTERM -F /var/run/ovpn.pid
        $vpn_run && logger -t puship-ovpn VPN process is running with IP ${interfaces[tun0]} but VPN rechablity failed.  Restarting
        Connect_VPN
      fi
    fi      
}


BuildMsg() {
    $debug && logger -t puship-DEBUG Enter BuildMsg Function
    GetCurrentIP
    if [ "$1" = "bound" ]; then
        pushTitle="$HOSTNAME $new_ip_address"
        pushMsg="ConsolePi IP Update"
    else
        pushTitle="$HOSTNAME VPN Established: ${new_ip_address}"
        pushMsg="ConsolePi VPN Connection success on ${interface}"
    fi
    logMsg="PushBullet Notification Sent. "

    for i in "${!interfaces[@]}"; do
        pushMsg="$pushMsg %0A $i: ${interfaces[$i]}"
        logMsg="$logMsg | $i: ${interfaces[$i]}"
    done
    pushMsg="$pushMsg %0A GW: $xgw"
    logMsg="$logMsg | GW: $xgw"
}   

# >> Check if IP new_ip_address is same as previously pushed IP <<#
Check_is_new_ip() {
    $debug && logger -t puship-DEBUG Enter check_is_new_ip Function Old: "${old_ip_address}" new: "${new_ip_address}"

    if [ -f /tmp/$interface ]; then                                                                     # Pull last IP from file if file exists
        last_ip=`head -1 /tmp/$interface`
        [ "$last_ip" = "$new_ip_address" ] && is_new_ip=false || is_new_ip=true
    fi

    # [ "$old_ip_address" = "$new_ip_address" ] && is_new_ip=false || is_new_ip=true
    $is_new_ip && StashNewIP
}

update_cloud() {
    /etc/ConsolePi/cloud/${cloud_svc}/cloud.py && 
        logger -t puship-${cloud_svc} Updated cloud Config ||
        logger -t puship-${cloud_svc} Error returned while Updating cloud Config
}

run() {
    $debug && logger -t puship-DEBUG Enter run Function
    Check_is_new_ip
    if $is_new_ip; then
        BuildMsg "bound" 
        $push && Push         
        $ovpn_enable && Check_VPN
    else
        logger -t puship $interface IP is same as prior \($new_ip_address\) No Need for Push Notification.
    fi
}

# __main__
[ "${new_domain_name}" = "${local_domain}" ] && remote=false || remote=true
$debug && [[ -z $local_domain ]] && local_domain="null_local_domain"
$debug && [[ -z $new_domain_name ]] && new_domain_name="null_cur_domain"
$debug && logger -t puship Arguments: $0 $1 $interface $3 $4 $new_ip_address $6 $7 $reason "${local_domain}" "${new_domain_name}" $remote
declare -A interfaces       

case "$reason" in
  OVPN_CONNECTED)
     StashNewIP
     BuildMsg "OVPN"
     $push && Push
     $cloud && update_cloud
     exit 0
     ;;
  BOUND|REBIND)
     run
     $cloud && update_cloud
     ;;
  STATIC)
    [ $interface = "eth0" ] && run || exit 0
    ;;
  *)
     exit 0
     ;;
esac
