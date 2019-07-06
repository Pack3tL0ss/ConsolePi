#!/etc/ConsolePi/venv/bin/python3

""" Browse for other ConsolePis on the network """

import socket
from time import sleep
from typing import cast
import json
from threading import Thread

from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf
# from consolepi.common import ConsolePi_Log
from consolepi.common import ConsolePi_data

HOSTNAME = socket.gethostname()

class MDNS_Browser:

    def __init__(self, log=None):
        self.config = ConsolePi_data(do_print=False)
        self.log = log if log is not None else self.config.log
        # self.mdata = None
        self.stop = False
        self.zc = self.run()
        self.update = self.config.update_local_cloud_file
        # self.run()

    def on_service_state_change(self,
        zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        mdns_data = None
        config = self.config
        log = self.log
        if state_change is ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                if info.server.split('.')[0] != config.hostname:
                    log.info('ConsolePi: {} Discovered via mdns'.format(info.server.split('.')[0]))
                    if info.properties:
                        properties = info.properties
                        hostname = properties[b'hostname'].decode("utf-8")
                        user = properties[b'user'].decode("utf-8")
                        interfaces = json.loads(properties[b'interfaces'].decode("utf-8"))
                        adapters = json.loads(properties[b'adapters'].decode("utf-8"))
                        mdns_data = {hostname: {'interfaces': interfaces, 'adapters': adapters, 'user': user}}
                        log.info('-mdns discovery- Final data set for {}:\n{}'.format(info.server.split('.')[0], mdns_data))
                        self.update(remote_consoles=mdns_data)
                        log.info('Local Cloud Cache Updated with {} data discovered via mdns'.format(info.server.split('.')[0]))
                    else:
                        log.warning('{}: No properties found'.format(info.server.split('.')[0]))
            else:
                log.warning('{}: No info found'.format(info.server.split('.')[0]))

            # if mdns_data is not None:
            #    if self.mdata is None:
            #        self.mdata = mdns_data
            #    else:
            #        self.mdata[hostname] = mdns_data[hostname]

    def run(self):
        log = self.log
        zeroconf = Zeroconf()
        log.info("Discovering ConsolePis via mdns")
        browser = ServiceBrowser(zeroconf, "_consolepi._tcp.local.", handlers=[self.on_service_state_change])
        # while not self.stop:
        # sleep(2.0)
        # print('start')
        # Thread(target=zeroconf.close()).start()
        # print('end')
        return zeroconf

if __name__ == '__main__':
    mdns = MDNS_Browser()
    print("\nBrowsing services, press Ctrl-C to exit...\n")
    try:
        while True:
            sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        mdns.zc.close()

