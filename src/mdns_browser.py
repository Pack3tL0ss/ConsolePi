#!/etc/ConsolePi/venv/bin/python3

""" Browse for other ConsolePis on the network
"""

import json
import time
from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

import sys
sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi.consolepi import ConsolePi  # NoQA

try:
    import better_exceptions  # NoQA pylint: disable=import-error
except Exception:
    pass

RESTART_INTERVAL = 300  # time in seconds browser service will restart


class MDNS_Browser:

    def __init__(self, log=None, show=False):
        self.cpi = ConsolePi()
        self.debug = self.cpi.config.cfg.get('debug', False)
        self.show = show
        self.log = log if log is not None else self.cpi.log
        self.stop = False
        self.discovered = []    # for display when running interactively, resets @ every restart
        self.d_discovered = []  # used when running as daemon (doesn't reset)
        self.startup_logged = False
        self.zc = None

    def on_service_state_change(self,
                                zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        cpi = self.cpi
        mdns_data = None
        update_cache = False
        log = self.log
        if state_change is ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                if info.server.split('.')[0] != cpi.local.hostname:
                    if info.properties:
                        properties = info.properties

                        mdns_data = {k.decode('UTF-8'):
                                     v.decode('UTF-8') if not v.decode('UTF-8')[0] in ['[', '{'] else json.loads(v.decode('UTF-8'))  # NoQA
                                     for k, v in properties.items()}

                        hostname = mdns_data.get('hostname')
                        interfaces = mdns_data.get('interfaces', [])
                        # interfaces = json.loads(properties[b'interfaces'].decode("utf-8"))

                        log_out = json.dumps(mdns_data, indent=4, sort_keys=True)
                        log.debug(f'[MDNS DSCVRY] {hostname} Properties Discovered via mdns:\n{log_out}')

                        rem_ip = mdns_data.get('rem_ip')
                        if not rem_ip:
                            if len(mdns_data.get('interfaces', [])) == 1:
                                rem_ip = [interfaces[i]['ip'] for i in interfaces]
                                rem_ip = rem_ip[0]
                            else:
                                rem_ip = None if hostname not in cpi.remotes.data or 'rem_ip' not in cpi.remotes.data[hostname] \
                                    else cpi.remotes.data[hostname]['rem_ip']

                        cur_known_adapters = cpi.remotes.data.get(hostname, {'adapters': None}).get('adapters')

                        # -- Log new entry only if this is the first time it's been discovered --
                        if hostname not in self.d_discovered:
                            self.d_discovered.append(hostname)
                            log.info('[MDNS DSCVRY] {}({}) Discovered via mdns'.format(
                                hostname, rem_ip if rem_ip is not None else '?'))

                        from_mdns_adapters = mdns_data.get('adapters')
                        mdns_data['rem_ip'] = rem_ip
                        mdns_data['adapters'] = from_mdns_adapters if from_mdns_adapters is not None else cur_known_adapters
                        mdns_data['source'] = 'mdns'
                        mdns_data['upd_time'] = int(time.time())
                        mdns_data = {hostname: mdns_data}

                        # update from API only if no adapter data exists either in cache or from mdns that triggered this
                        # adapter data is updated on menu_launch
                        if not mdns_data[hostname]['adapters'] or hostname not in cpi.remotes.data:
                            log.info('[MDNS DSCVRY] {} provided no adapter data Collecting via API'.format(
                                    info.server.split('.')[0]))
                            # TODO check this don't think needed had a hung process on one of my Pis added it to be safe
                            try:
                                res = cpi.remotes.api_reachable(hostname, mdns_data[hostname])
                                update_cache = res.update
                                mdns_data[hostname] = res.data
                                # reachable = res.reachable
                            except Exception as e:
                                log.error(f'Exception occured verifying reachability via API for {hostname}:\n{e}')

                        if self.show:
                            if hostname in self.discovered:
                                self.discovered.remove(hostname)
                            self.discovered.append('{}{}'.format(hostname, '*' if update_cache else ''))
                            print(hostname + '({}) Discovered via mdns.'.format(rem_ip if rem_ip is not None else '?'))

                            try:
                                print('{}\n{}'.format(
                                    'mdns: None' if from_mdns_adapters is None else 'mdns: {}'.format(
                                                [d.replace('/dev/', '') for d in from_mdns_adapters]
                                                if not isinstance(from_mdns_adapters, list) else
                                                [d['dev'].replace('/dev/', '') for d in from_mdns_adapters]),
                                    'cache: None' if cur_known_adapters is None else 'cache: {}'.format(
                                                [d.replace('/dev/', '') for d in cur_known_adapters]
                                                if not isinstance(cur_known_adapters, list) else
                                                [d['dev'].replace('/dev/', '') for d in cur_known_adapters])))
                            except TypeError as e:
                                print(f'EXCEPTION: {e}')
                            print(f'\nDiscovered ConsolePis: {self.discovered}')
                            print("press Ctrl-C to exit...\n")

                        log.debug('[MDNS DSCVRY] {} Final data set:\n{}'.format(hostname,
                                                                                json.dumps(mdns_data, indent=4, sort_keys=True)))
                        if update_cache:
                            cpi.remotes.data = cpi.remotes.update_local_cloud_file(remote_consoles=mdns_data)
                            log.info(f'[MDNS DSCVRY] {hostname} Local Cache Updated after mdns discovery')
                    else:
                        log.warning(f'[MDNS DSCVRY] {hostname}: No properties found')
            else:
                log.warning(f'[MDNS DSCVRY] {info}: No info found')

    def run(self):
        log = self.log
        zeroconf = Zeroconf()
        if not self.startup_logged:
            log.info(f"[MDNS DSCVRY] Discovering ConsolePis via mdns - Debug Logging: {self.debug}, lvl: {log.level}")
            self.startup_logged = True
        browser = ServiceBrowser(zeroconf, "_consolepi._tcp.local.", handlers=[self.on_service_state_change])  # NoQA pylint: disable=unused-variable
        return zeroconf


if __name__ == '__main__':
    if len(sys.argv) > 1:
        mdns = MDNS_Browser(show=True)
        RESTART_INTERVAL = 30  # when running in interactive mode reduce restart interval
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
            if mdns.zc is not None:
                mdns.zc.close()
            mdns.discovered = []

    except KeyboardInterrupt:
        pass
    finally:
        if mdns.zc is not None:
            mdns.zc.close()
