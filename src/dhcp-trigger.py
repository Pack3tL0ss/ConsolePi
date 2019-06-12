#!/etc/ConsolePi/venv/bin/python3

from consolepi.common import check_reachable
import sys
import os
from consolepi.common import ConsolePi_Log

log = ConsolePi_Log().set_log()

ip = sys.argv[3]
try:
    vendor = os.environ['DNSMASQ_VENDOR_CLASS']
except KeyError:
    vendor = None

ssh = check_reachable(ip, 22)
telnet = check_reachable(ip, 23)

log('{} {} {} {}'.format(ip, vendor, ssh, telnet))