#!/etc/ConsolePi/venv/bin/python3

""" 
    -- dev testing file currently --
    This file currently only logs
    Eventually it will replace the function in consolepi-menu which looks at the leases file
    and if a lease was handed out to a client with the Raspberry Pi MAC OUI it attempts to 
    ssh to that device to echange adapter info (both pis will update)

    This file will have a few advantages, 
    - rather than keying off of MAC OUI it keys off the custom vendor class id ConsolePi 
      has been modified to send.  
    - Updates will be passed back and forth via the new API.  This is a bit more flexible than doing it via ssh
      currently the api is http and no auth is in place, but its only gets and no sensitive
      info so not an issue for testing.  
    - Updates occur as the lease comes in vs. looking at the leases file upon refresh in the menu
      This reduces the operations the menu would need to perform to help keep it lean/fast
"""

from consolepi.common import check_reachable
import sys
import os
import json
from consolepi.common import ConsolePi_Log
from consolepi.common import get_local

# -- Some Testing Stuff --
# with open('/home/pi/dhcp-test.out', 'a') as new_file:
#     new_file.write(str(sys.argv[1:]) + '\n' + str(os.environ) + '\n')

# -- Some Testing Stuff - eventually move to ztp.conf or oobm.conf file --
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

log.info('DHCP Client Connected ({}): iface: {}, mac: {}, ip: {}, vendor: {}'.format(add_del, iface, mac, ip, vendor))

if vendor is not None and 'ConsolePi' in vendor:
    log.info('ConsolePi Discovered via DHCP')
    # TODO get/post info from/to ConsolePi that just connected via API
    # Update local cloud cache
# oobm Discovery & ZTP trigger
elif vendor is not None and iface is not None and iface == 'eth0':
    for _ in match:
        if _ in vendor:
            if check_reachable(ip, 22):
                log.info('{} is reachable via ssh @ {}'.format(_, ip))
            elif check_reachable(ip, 23):
                log.info('{} is reachable via telnet @ {}'.format(_, ip))
    # TODO add connection to reachable ssh/telnet on eth if oobm is enabled in config
    # TODO add option to ztp via jinja2 templates (longer term goal)

