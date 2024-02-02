#!/etc/ConsolePi/venv/bin/python3

""" Browse for other ConsolePis on the network
"""

import json
import time
import sys
from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf
import setproctitle
import asyncio

from rich.traceback import install
install(show_locals=True)

sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import log, config  # type: ignore # NoQA
from consolepi.consolepi import ConsolePi  # type: ignore # NoQA


RESTART_INTERVAL = 300  # time in seconds browser service will restart

setproctitle.setproctitle("consolepi-mdnsbrowser")


class MDNS_Browser:

    def __init__(self, show=False):
        config.cloud = False  # mdns doesn't need to sync w cloud
        self.cpi = ConsolePi(bypass_outlets=True, bypass_cloud=True)
        self.debug = config.cfg.get('debug', False)
        self.show = show
        self.stop = False
        self.discovered = []    # for display when running interactively, resets @ every restart
        self.d_discovered = []  # used when running as daemon (doesn't reset)
        self.no_adapters = []  # If both mdns and API report no adapters for remote add to list to prevent subsequent API calls
        self.startup_logged = False
        self.zc = Zeroconf()

    def on_service_state_change(self,
                                zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        if self.cpi.local.hostname == name.split(".")[0]:
            return
        if state_change is not ServiceStateChange.Added:
            return

        info = zeroconf.get_service_info(service_type, name)
        if not info:
            log.warning(f'[MDNS DSCVRY] {name}: No info found')
            return
        if not hasattr(info, "properties") or not info.properties:
            log.warning(f'[MDNS DSCVRY] {name}: No properties found')
            return

        properties = info.properties

        cpi = self.cpi
        mdns_data = None
        update_cache = False
        try:
            mdns_data = {
                k.decode('UTF-8'):
                v.decode('UTF-8') if len(v) == 0 or not v.decode('UTF-8')[0] in ['[', '{'] else json.loads(v.decode('UTF-8'))  # NoQA
                for k, v in properties.items()
            }
        except Exception as e:
            log.exception(
                f"[MDNS DSCVRY] {e.__class__.__name__} occured while parsing mdns_data:\n {mdns_data}\n"
                f"Exception: \n{e}"
            )
            log.error(f"[MDNS DSCVRY] entry from {name} ignored due to parsing exception.")
            return

        hostname = mdns_data.get('hostname')
        interfaces = mdns_data.get('interfaces', [])

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
            self.d_discovered += [hostname]
            log.info('[MDNS DSCVRY] {}({}) Discovered via mdns'.format(
                hostname, rem_ip if rem_ip is not None else '?'))

        from_mdns_adapters = mdns_data.get('adapters')
        mdns_data['rem_ip'] = rem_ip
        mdns_data['adapters'] = from_mdns_adapters if from_mdns_adapters else cur_known_adapters
        mdns_data['source'] = 'mdns'
        mdns_data['upd_time'] = int(time.time())
        mdns_data = {hostname: mdns_data}

        # update from API only if no adapter data exists either in cache or from mdns that triggered this
        # adapter data is updated on menu_launch either way
        if (not mdns_data[hostname]['adapters'] and hostname not in self.no_adapters) or \
                hostname not in cpi.remotes.data:
            log.info(f"[MDNS DSCVRY] {info.server.split('.')[0]} provided no adapter data Collecting via API")
            # TODO check this don't think needed had a hung process on one of my Pis added it to be safe
            try:
                # TODO we are setting update time here so always result in a cache update with the restart timer
                res = asyncio.run(cpi.remotes.api_reachable(hostname, mdns_data[hostname]))
                update_cache = res.update
                if not res.data.get('adapters'):
                    self.no_adapters.append(hostname)
                elif hostname in self.no_adapters:
                    self.no_adapters.remove(hostname)
                mdns_data[hostname] = res.data
            except Exception as e:
                log.exception(f'Exception occurred verifying reachability via API for {hostname}:\n{e}')

        if self.show:
            if hostname in self.discovered:
                self.discovered.remove(hostname)
            self.discovered.append('{}{}'.format(hostname, '*' if update_cache else ''))
            print(hostname + '({}) Discovered via mdns.'.format(rem_ip if rem_ip is not None else '?'))

            try:
                print(
                    '{}\n{}\n{}'.format(
                        'mdns: None' if from_mdns_adapters is None else 'mdns: {}'.format(
                            [d.replace('/dev/', '') for d in from_mdns_adapters]
                            if not isinstance(from_mdns_adapters, list) else
                            [d['dev'].replace('/dev/', '') for d in from_mdns_adapters]
                        ),
                        'api (mdns trigger): None' if not mdns_data[hostname]['adapters'] else 'api (mdns trigger): {}'.format(
                            [d.replace('/dev/', '') for d in mdns_data[hostname]['adapters']]
                            if not isinstance(mdns_data[hostname]['adapters'], list) else
                            [d['dev'].replace('/dev/', '') for d in mdns_data[hostname]['adapters']]
                        ),
                        'cache: None' if cur_known_adapters is None else 'cache: {}'.format(
                            [d.replace('/dev/', '') for d in cur_known_adapters]
                            if not isinstance(cur_known_adapters, list) else
                            [d['dev'].replace('/dev/', '') for d in cur_known_adapters]
                        )
                    )
                )
            except TypeError as e:
                print(f'EXCEPTION: {e}')

            print(f'\nDiscovered ConsolePis: {self.discovered}')
            print("press Ctrl-C to exit...\n")

        log.debugv(
            f"[MDNS DSCVRY] {hostname} Final data set:\n{json.dumps(mdns_data, indent=4, sort_keys=True)}"
        )

        # TODO could probably just put the call to cache update in the api_reachable method
        if update_cache:
            if 'hostname' in mdns_data[hostname]:
                del mdns_data[hostname]['hostname']
            cpi.remotes.data = cpi.remotes.update_local_cloud_file(remote_consoles=mdns_data)
            log.info(f'[MDNS DSCVRY] {hostname} Local Cache Updated after mdns discovery')

    def run(self):
        self.zc = Zeroconf()
        if not self.startup_logged:
            log.info(f"[MDNS DSCVRY] Discovering ConsolePis via mdns - Debug Enabled: {self.debug}")
            self.startup_logged = True
        return ServiceBrowser(self.zc, "_consolepi._tcp.local.", handlers=[self.on_service_state_change])  # NoQA pylint: disable=unused-variable


if __name__ == '__main__':
    program_start = int(time.time())
    if len(sys.argv) > 1:
        mdns = MDNS_Browser(show=True)
        RESTART_INTERVAL = 30  # when running in interactive mode reduce restart interval
        print("\nBrowsing services, press Ctrl-C to exit...\n")
    else:
        mdns = MDNS_Browser()

    try:
        while True:
            try:
                browser = mdns.run()
            except AttributeError:
                # hopefully this handles "Zeroconf object has no attribute '_handlers_lock'"
                log.warning('[MDNS BROWSE] caught _handlers_lock exception retrying in 5 sec')
                time.sleep(5)
                continue
            except Exception as e:
                # Catch any other errors, usually related to transient connectivity issues."
                log.warning(f'[MDNS BROWSE] caught {e.__class__.__name__} retrying in 5 sec.\nException:\n{e}')
                time.sleep(5)
                continue
            # re-init zeroconf browser every RESTART_INTERVAL seconds
            start = time.time()
            while time.time() < start + RESTART_INTERVAL:
                time.sleep(start + RESTART_INTERVAL - time.time())
            if mdns.zc is not None:
                mdns.zc.close()

            duration = f"{RESTART_INTERVAL / 60}m" if RESTART_INTERVAL > 60 else f"{RESTART_INTERVAL}s"
            mdns.discovered = []

    except KeyboardInterrupt:
        pass
    finally:
        if mdns.zc is not None:
            mdns.zc.close()
