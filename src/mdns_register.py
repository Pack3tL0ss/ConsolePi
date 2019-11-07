#!/etc/ConsolePi/venv/bin/python3

from consolepi.common import ConsolePi_data
from consolepi.common import bash_command
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
    bash_command('export BETTER_EXCEPTIONS=1')
except ImportError:
    pass

UPDATE_DELAY = 30

class MDNS_Register:

    def __init__(self):
        self.config = ConsolePi_data(do_print=False)
        self.hostname = self.config.hostname
        self.zeroconf = Zeroconf()
        self.context = pyudev.Context()

    # Have now hard-coded this to *not* send adapter data, the payload is typically too large
    # ConsolePi that discovers will follow up discovery with an API call to gather adapter data
    def build_info(self, squash=None, local_adapters=None):
        config = self.config
        hostname = self.hostname
        local_adapters = local_adapters if local_adapters is not None else config.local
        # local_adapters = config.get_local(do_print=False)
        log = config.log
        if_ips = config.get_if_ips()
        
        local_data = {'hostname': hostname,
            'user': 'pi'
        }

        # if squash is None: # if data set is too large for mdns browser on other side will retrieve via API
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

        log.debug('[MDNS REG] Current content of local_data \n{}'.format(json.dumps(local_data, indent=4, sort_keys=True)))
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

    def update_mdns(self, device=None, action=None, *args, **kwargs):
        config = self.config
        zeroconf = self.zeroconf
        log = config.log
        info = self.try_build_info()

        def sub_restart_zc():
            log.info('[MDNS REG] mdns_refresh thread Start... Delaying {} Seconds'.format(UPDATE_DELAY))
            time.sleep(UPDATE_DELAY)  # Wait x seconds and then update, to accomodate multiple add removes
            zeroconf.update_service(info)
            zeroconf.unregister_service(info)
            time.sleep(5)
            zeroconf.register_service(info)
            log.info('[MDNS REG] mdns_refresh thread Completed')

        if device is not None:
            abort_mdns=False
            for thread in threading.enumerate():
                if 'mdns_refresh' in thread.name:
                    log.debug('[MDNS REG] Another mdns_refresh thread already queued, this thread will abort')
                    abort_mdns = True
                    break

            if not abort_mdns:
                threading.Thread(target=sub_restart_zc, name='mdns_refresh', args=()).start()
                log.debug('[MDNS REG] mdns_refresh Thread Started.  Current Threads:\n    {}'.format(threading.enumerate()))

            log.info('[MDNS REG] detected change: {} {}'.format(device.action, device.sys_name))
            if config.cloud:     # pylint: disable=maybe-no-member
                abort=False
                for thread in threading.enumerate():
                    if 'cloud_update' in thread.name:
                        log.debug('[MDNS REG] Another cloud Update thread already queued, this thread will abort')
                        abort = True
                        break

                if not abort:
                    threading.Thread(target=self.trigger_cloud_update, name='cloud_update', args=()).start()
                    log.debug('[MDNS REG] Cloud Update Thread Started.  Current Threads:\n    {}'.format(threading.enumerate()))

    def try_build_info(self):
        config = self.config
        log = config.log
        # TODO Figure out how to calculate the struct size
        # Try sending with all data
        try:
            info = self.build_info()
        except struct.error as e:
            log.debug('[MDNS REG] data is too big for mdns, removing adapter data \n    {} {}'.format(e.__class__.__name__, e))
            log.debug('[MDNS REG] offending payload \n    {}'.format(json.dumps(config.local, indent=4, sort_keys=True)))
            # Too Big - Try sending without adapter data
            try:
                info = self.build_info(squash='adapters')
            except struct.error as e:
                log.warning('[MDNS REG] data is still too big for mdns, reducing interface payload \n    {} {}'.format(e.__class__.__name__, e))
                log.debug('[MDNS REG] offending interface data \n    {}'.format(json.dumps(config.interfaces, indent=4, sort_keys=True)))
                # Still too big - Try reducing advertised interfaces (generally an issue with WAN emulator)
                info = self.build_info(squash='interfaces')

        return info

    def trigger_cloud_update(self):
        config = self.config
        log = config.log
        log.info('[MDNS REG] Cloud Update triggered delaying {} seconds'.format(UPDATE_DELAY))
        time.sleep(UPDATE_DELAY)  # Wait 30 seconds and then update, to accomodate multiple add removes
        data = {config.hostname: {'adapters': config.get_local(do_print=False), 'interfaces': config.interfaces, 'user': 'pi'}}
        log.debug('[MDNS REG] Final Data set collected for {}: \n{}'.format(config.hostname, data))

        if config.cloud_svc == 'gdrive':  # pylint: disable=maybe-no-member
            cloud = GoogleDrive(log)

        remote_consoles = cloud.update_files(data)

        # Send remotes learned from cloud file to local cache
        if len(remote_consoles) > 0 and 'Gdrive-Error' not in remote_consoles:
            config.update_local_cloud_file(remote_consoles)
            log.info('[MDNS REG] Cloud Update Completed, Found {} Remote ConsolePis'.format(len(remote_consoles)))
        else:
            log.warn('[MDNS REG] Cloud Update Completed, No remotes found, or Error Occured')

    def run(self):
        zeroconf = self.zeroconf
        info = self.try_build_info()

        zeroconf.register_service(info)
        # monitor udev for add - remove of usb-serial adapters 
        monitor = pyudev.Monitor.from_netlink(self.context)
        # monitor.filter_by('usb-serial')    
        monitor.filter_by('usb')    
        observer = pyudev.MonitorObserver(monitor, name='udev_monitor', callback=self.update_mdns)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            print("Unregistering...")
            zeroconf.unregister_service(self.build_info())
            zeroconf.close()
            observer.send_stop()

if __name__ == '__main__':
    mdnsreg = MDNS_Register()
    mdnsreg.run()


