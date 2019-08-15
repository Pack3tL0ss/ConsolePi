#!/etc/ConsolePi/venv/bin/python3

from consolepi.common import ConsolePi_data
from zeroconf import ServiceInfo, Zeroconf
import time
import json
import socket
import pyudev
import threading
import struct
from consolepi.gdrive import GoogleDrive
try:
    import better_exceptions # pylint: disable=import-error
except ImportError:
    pass

config = ConsolePi_data(do_print=False)
log = config.log
hostname = config.hostname
zeroconf = Zeroconf()
context = pyudev.Context()

# Have now hard-coded this to *not* send adapter data, the payload is typically too large
# ConsolePi that discovers will follow up discovery with an API call to gather adapter data
def build_info(squash=None):
    local_adapters = config.get_local(do_print=False)
    if_ips = config.get_if_ips()
    

    local_data = {'hostname': hostname,
        'user': 'pi'
    }

    # if squash is None: # if data set is too large for mdns browser on other side will retrieve via API
    #     local_data['adapters'] = json.dumps(local_adapters)
    
    if squash is not None:
        if squash == 'interfaces':
            squashed_if_ips = {}
            for _if in if_ips:
                if '.' not in _if and 'docker' not in _if and 'ifb' not in _if:
                    squashed_if_ips[_if] = if_ips[_if]
                    local_data['interfaces'] = json.dumps(squashed_if_ips)
        else:
            local_data['interfaces'] = json.dumps(if_ips)
    else:
        local_data['adapters'] = json.dumps(local_adapters)
        local_data['interfaces'] = json.dumps(if_ips)

    log.debug('[MDNS REG]: Current content of local_data \n{}'.format(json.dumps(local_data, indent=4, sort_keys=True)))
    # print(struct.calcsize(json.dumps(local_data).encode('utf-8')))

    info = ServiceInfo(
        "_consolepi._tcp.local.",
        hostname + "._consolepi._tcp.local.",
        addresses=[socket.inet_aton("127.0.0.1")],
        port=5000,
        properties=local_data,
        server='{}.local.'.format(hostname)
    )

    return info

def update_mdns(device=None, log=log, action=None, *args, **kwargs):
    info = try_build_info()

    if device is not None:
        zeroconf.update_service(info)
        zeroconf.unregister_service(info)
        time.sleep(5)
        zeroconf.register_service(info)
        log.info('[MDNS REG]: detected change: {} {}'.format(device.action, device.sys_name))
        if config.cloud:     # pylint: disable=maybe-no-member
            abort=False
            for thread in threading.enumerate():
                if 'cloud_update' in thread.name:
                    log.debug('[MDNS REG]: Another cloud Update thread already queued, this thread will abort')
                    abort = True
                    break

            if not abort:
                threading.Thread(target=trigger_cloud_update, name='cloud_update', args=()).start()
                log.info('[MDNS REG]: Cloud Update Thread Started.  Current Threads:\n{}'.format(threading.enumerate()))

def try_build_info():
    # TODO Figure out how to calculate the struct size
    # Try sending with all data
    try:
        info = build_info()
    except struct.error as e:
        log.warning('[MDNS REG]: data is too big for mdns, removing adapter data \n{} {}'.format(e.__class__.__name__, e))
        log.debug('[MDNS REG]: offending adapter data \n{}'.format(json.dumps(config.get_local(do_print=False), indent=4, sort_keys=True)))
        # Too Big - Try sending without adapter data
        try:
            info = build_info(squash='adapters')
        except struct.error as e:
            log.warning('[MDNS REG]: data is still too big for mdns, reducing interface payload \n{} {}'.format(e.__class__.__name__, e))
            log.debug('[MDNS REG]: offending interface data \n{}'.format(json.dumps(config.get_if_ips(), indent=4, sort_keys=True)))
            # Still too big - Try reducing advertised interfaces (generally an issue with WAN emulator)
            info = build_info(squash='interfaces')

    return info

def trigger_cloud_update():
    log.info('[CLOUD TRIGGER (udev)]: Cloud Update triggered by serial adapter add/remove - waiting 30 seconds for other changes')
    time.sleep(30)  # Wait 30 seconds and then update, to accomodate multiple add removes
    data = {config.hostname: {'adapters': config.get_local(do_print=False), 'interfaces': config.get_if_ips(), 'user': 'pi'}}
    log.debug('[CLOUD TRIGGER (udev)]: Final Data set collected for {}: \n{}'.format(config.hostname, data))

    if config.cloud_svc == 'gdrive':  # pylint: disable=maybe-no-member
        cloud = GoogleDrive(log)
    remote_consoles = cloud.update_files(data)

    # Send remotes learned from cloud file to local cache
    if len(remote_consoles) > 0:
        config.update_local_cloud_file(remote_consoles)

def run():
    info = try_build_info()

    zeroconf.register_service(info)
    # monitor udev for add - remove of usb-serial adapters 
    monitor = pyudev.Monitor.from_netlink(context)
    # monitor.filter_by('usb-serial')    
    monitor.filter_by('usb')    
    observer = pyudev.MonitorObserver(monitor, name='udev_monitor', callback=update_mdns)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("Unregistering...")
        zeroconf.unregister_service(build_info())
        zeroconf.close()
        observer.send_stop()

if __name__ == '__main__':
    run()


