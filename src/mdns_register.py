#!/etc/ConsolePi/venv/bin/python3

from consolepi.common import ConsolePi_Log
from consolepi.common import get_local
from consolepi.common import get_if_ips
from consolepi.common import get_config
from zeroconf import ServiceInfo, Zeroconf
from time import sleep
import json
import socket
import pyudev
import threading


DEBUG = get_config('debug')
cpi_log = ConsolePi_Log(debug=DEBUG, do_print=False)
LOG = cpi_log.log
# reference_value = get_local(log)
HOSTNAME = socket.gethostname()
zeroconf = Zeroconf()
context = pyudev.Context()

def build_info():
    local_adapters = get_local(cpi_log=cpi_log, do_print=False)
    if_ips = get_if_ips(log=LOG)
        
    local_data = {'hostname': HOSTNAME,
        'adapters': json.dumps(local_adapters),
        'interfaces': json.dumps(if_ips),
        'user': 'pi'
    }
    info = ServiceInfo(
        "_consolepi._tcp.local.",
        HOSTNAME + "._consolepi._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=5000,
        properties=local_data,
        server='{}.local.'.format(HOSTNAME),
    )

    return info

def update_mdns(device=None, log=LOG, action=None, *args, **kwargs):
    info = build_info()

    if device is not None:
        zeroconf.update_service(info)
        zeroconf.unregister_service(info)
        sleep(1)
        zeroconf.register_service(info)
        log.info('mdns monitor detected change: {} {}'.format(device.action, device.sys_name))


def run():
    info = build_info()
    zeroconf.register_service(info)
    # monitor udev for add - remove of usb-serial adapters 
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by('usb-serial')    
    observer = pyudev.MonitorObserver(monitor, name='udev_monitor', callback=update_mdns)
    observer.start()
    while True:
        sleep(1)

    # return observer

if __name__ == '__main__':

    observer=(run())

    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("Unregistering...")
        zeroconf.unregister_service(build_info())
        zeroconf.close()
        observer.send_stop()
