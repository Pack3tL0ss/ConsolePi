#!/etc/ConsolePi/venv/bin/python3

from consolepi.common import ConsolePi_data
# from consolepi.common import get_local
# from consolepi.common import get_if_ips
# from consolepi.common import get_config
from zeroconf import ServiceInfo, Zeroconf
from time import sleep
import json
import socket
import pyudev
import threading


#DEBUG = get_config('debug')
config = ConsolePi_data(do_print=False)
log = config.log
# reference_value = get_local(log)
hostname = config.hostname
zeroconf = Zeroconf()
context = pyudev.Context()

def build_info(error=False):
    local_adapters = config.get_local(do_print=False)
    if_ips = config.get_if_ips()
    

    local_data = {'hostname': hostname,
        'interfaces': json.dumps(if_ips),
        'user': 'pi'
    }
    if not error:
        local_data['adapters'] = json.dumps(local_adapters),  # if data set is too large for mdns browser will retrieve via API

    info = ServiceInfo(
        "_consolepi._tcp.local.",
        hostname + "._consolepi._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=5000,
        properties=local_data,
        server='{}.local.'.format(hostname),
    )

    return info

def update_mdns(device=None, log=log, action=None, *args, **kwargs):
    try:
        info = build_info()
    except struct.error:
        info = build_info(error=True)

    if device is not None:
        zeroconf.update_service(info)
        zeroconf.unregister_service(info)
        sleep(1)
        zeroconf.register_service(info)
        log.info('mdns monitor detected change: {} {}'.format(device.action, device.sys_name))


def run():
    try:
        info = build_info()
    except struct.error:
        info = build_info(error=True)

    zeroconf.register_service(info)
    # monitor udev for add - remove of usb-serial adapters 
    monitor = pyudev.Monitor.from_netlink(context)
    # monitor.filter_by('usb-serial')    
    monitor.filter_by('usb')    
    observer = pyudev.MonitorObserver(monitor, name='udev_monitor', callback=update_mdns)
    observer.start()
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

if __name__ == '__main__':
    run()


