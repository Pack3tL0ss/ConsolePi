#!/etc/ConsolePi/venv/bin/python3

from consolepi.common import check_reachable
# from consolepi.common import get_config
import sys
import os
import json
from consolepi.common import ConsolePi_Log
from consolepi.common import get_local

with open('/home/pi/dhcp-test.out', 'a') as new_file:
    new_file.write(str(sys.argv[1:]) + '\n' + str(os.environ) + '\n')

match = ['2530', '3810']

log = ConsolePi_Log().set_log()


add_del = sys.argv[1]
mac = sys.argv[2]
ip = sys.argv[3]


try:
    iface = os.environ['DNSMASQ_INTERFACE']
except KeyError:
    iface = None
try:
    vendor = os.environ['DNSMASQ_VENDOR_CLASS']
except KeyError:
    vendor = None

log.info('{},  iface: {}, mac: {}, ip: {}, vendor: {}'.format(add_del, iface, mac, ip, vendor))

# oobm Discovery & ZTP trigger
if iface is not None and iface == 'eth0':
    ssh = check_reachable(ip, 22)
    telnet = check_reachable(ip, 23)

    log.info('{} {} {} {}'.format(ip, vendor, ssh, telnet))

    for _ in match:
        if _ in vendor:
            if ssh:
                log.info('{} is reachable via ssh @ {}'.format(_, ip))
            elif telnet:
                log.info('{} is reachable via telnet @ {}'.format(_, ip))

if vendor is not None and 'ConsolePi' in vendor:
    log.info('ConsolePi Discovered via DHCP')