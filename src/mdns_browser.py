#!/etc/ConsolePi/venv/bin/python3

""" Browse for other ConsolePis on the network """

import socket
import time
from typing import cast
import json
from threading import Thread
import sys
from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf
from consolepi.common import check_reachable
from consolepi.common import ConsolePi_data
try:
    import better_exceptions # pylint: disable=import-error
except Exception:
    pass

# HOSTNAME = socket.gethostname()
RESTART_INTERVAL = 300 # time in seconds browser service will restart

class MDNS_Browser:

    def __init__(self, log=None, show=False):
        self.config = ConsolePi_data(do_print=False)
        self.show = show
        self.log = log if log is not None else self.config.log
        self.stop = False
        # self.zc = self.run()
        # self.update = self.config.update_local_cloud_file
        self.if_ips = self.config.interfaces
        self.ip_list = []
        for _iface in self.if_ips:
            self.ip_list.append(self.if_ips[_iface]['ip'])
        self.discovered = [] # for display when running interactively
        self.d_discovered = [] # used for systemd (doesn't reset)
        self.startup_logged = False

    def on_service_state_change(self,
        zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        mdns_data = None
        update_cache = False
        config = self.config
        # ip_list = config.get_ip_list()
        log = self.log
        if state_change is ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                if info.server.split('.')[0] != config.hostname:
                    # log.info('[MDNS DSCVRY] {} Discovered via mdns'.format(info.server.split('.')[0]))
                    if info.properties:
                        properties = info.properties
                        # -- DEBUG --
                        properties_decode = {}
                        for key in properties:
                            key_dec = key.decode("utf-8")                          
                            properties_decode[key_dec] = properties[key].decode("utf-8")
                        log_out = json.dumps(properties_decode, indent=4, sort_keys=True)
                        log.debug('[MDNS DSCVRY] {} Properties Discovered via mdns:\n{}'.format(
                            info.server.split('.')[0], log_out))
                        # -- /DEBUG --
                        hostname = properties[b'hostname'].decode("utf-8")
                        user = properties[b'user'].decode("utf-8")
                        interfaces = json.loads(properties[b'interfaces'].decode("utf-8"))

                        rem_ip = None if hostname not in config.remotes or 'rem_ip' not in config.remotes[hostname] else config.remotes[hostname]['rem_ip']
                        cur_known_adapters = [] if hostname not in config.remotes or not config.remotes[hostname]['adapters'] else config.remotes[hostname]['adapters']

                        # -- Log new entry only if this is the first time it's been discovered --
                        if hostname not in self.d_discovered:
                            self.d_discovered.append(hostname)
                            log.info('[MDNS DSCVRY] {}({}) Discovered via mdns:'.format(
                                hostname, rem_ip if rem_ip is not None else '?'))

                        try:
                            if isinstance(properties[b'adapters'], bytes):
                                from_mdns_adapters = json.loads(properties[b'adapters'].decode("utf-8"))
                            else:
                                from_mdns_adapters = None
                        except KeyError:
                            from_mdns_adapters = None
                            
                        mdns_data = {hostname: {'interfaces': interfaces,
                            'adapters': from_mdns_adapters if from_mdns_adapters is not None else cur_known_adapters,
                            'user': user,
                            'rem_ip': rem_ip,
                            'source': 'mdns',
                            'upd_time': int(time.time())}
                            }

                        # update from API only if no adapter data exists either in cache or from mdns that triggered this
                        # adapter data is updated on menu_launch
                        if not mdns_data[hostname]['adapters']:
                            log.info('[MDNS DSCVRY] {} provided no adapter data Collecting via API'.format(info.server.split('.')[0]))
                            update_cache, mdns_data[hostname] = config.api_reachable(mdns_data[hostname])

                        if self.show:
                            if hostname in self.discovered:
                                self.discovered.remove(hostname)
                            self.discovered.append('{}{}'.format(hostname, '*' if update_cache else ''))
                            print(hostname + '({}) Discovered via mdns:'.format(rem_ip if rem_ip is not None else '?'))
                            # print(json.dumps(mdns_data, indent=4, sort_keys=True))
                            print('{}\n{}'.format(
                                'mdns: None' if from_mdns_adapters is None else 'mdns: {}'.format([d['dev'] for d in from_mdns_adapters]),
                                'cache: None' if cur_known_adapters is None else 'cache: {}'.format([d['dev'] for d in cur_known_adapters])))
                            print('Discovered ConsolePis: {}'.format(self.discovered))
                            print("\npress Ctrl-C to exit...\n")

                        log.debug('[MDNS DSCVRY] {} Final data set:\n{}'.format(info.server.split('.')[0], json.dumps(mdns_data, indent=4, sort_keys=True)))
                        if update_cache:
                            config.update_local_cloud_file(remote_consoles=mdns_data)
                            log.info('[MDNS DSCVRY] {} Local Cache Updated after mdns discovery'.format(info.server.split('.')[0]))
                    else:
                        log.warning('[MDNS DSCVRY] {}: No properties found'.format(info.server.split('.')[0]))
            else:
                log.warning('[MDNS DSCVRY] {}: No info found'.format(info))


    def run(self):
        log = self.log
        zeroconf = Zeroconf()
        if not self.startup_logged:
            log.info("[MDNS DSCVRY] Discovering ConsolePis via mdns")
            self.startup_logged = True
        browser = ServiceBrowser(zeroconf, "_consolepi._tcp.local.", handlers=[self.on_service_state_change])  # pylint: disable=unused-variable
        return zeroconf

# if __name__ == '__main__':
#     if len(sys.argv) > 1:
#         mdns = MDNS_Browser(show=True)
#         print("\nBrowsing services, press Ctrl-C to exit...\n")
#     else:
#         mdns = MDNS_Browser()
        
#     try:
#         while True:
#             time.sleep(0.1)
#     except KeyboardInterrupt:
#         pass
#     finally:
#         mdns.zc.close()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        mdns = MDNS_Browser(show=True)
        RESTART_INTERVAL = 30 # when running in interactive mode reduce restart interval
        # mdns.zc = mdns.run()
        print("\nBrowsing services, press Ctrl-C to exit...\n")
    else:
        mdns = MDNS_Browser()
    
    try:
        while True:
            mdns.zc = mdns.run()
            start = time.time()
            # re-init zeroconf browser every RESTART_INTERVAL seconds
            while time.time() < start + RESTART_INTERVAL:
                time.sleep(0.1)
            mdns.zc.close()
            mdns.discovered = []
                
    except KeyboardInterrupt:
        pass
    finally:
        mdns.zc.close()