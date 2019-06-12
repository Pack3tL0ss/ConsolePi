#!/etc/ConsolePi/venv/bin/python3

from consolepi.common import check_reachable
# from consolepi.common import get_config
import sys
import os
from consolepi.common import ConsolePi_Log

match = ['2530', '3810']

log = ConsolePi_Log().set_log()

ip = sys.argv[3]
try:
    vendor = os.environ['DNSMASQ_VENDOR_CLASS']
except KeyError:
    vendor = None

ssh = check_reachable(ip, 22)
telnet = check_reachable(ip, 23)

log.info('{} {} {} {}'.format(ip, vendor, ssh, telnet))

for _ in match:
    if _ in vendor:
        if ssh:
            log.info('{} is reachable via ssh @ {}'.format(_, ip))
        elif telnet:
            log.info('{} is reachable via telnet @ {}'.format(_, ip))