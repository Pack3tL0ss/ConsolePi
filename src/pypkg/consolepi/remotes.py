#!/etc/ConsolePi/venv/bin/python3

import json
import requests
import threading
from halo import Halo
import time
from log_symbols import LogSymbols as log_sym  # Enum
# from consolepi.gdrive import GoogleDrive <-- burried import inside refresh method


class Remotes():
    '''Remotes Object Contains attributes for discovered remote ConsolePis'''

    def __init__(self, cpi):
        # -- init some vars --
        print(__name__)
        self.pop_list = []
        self.log_sym_warn = log_sym.WARNING.value
        self.cpi = cpi
        config = cpi.config
        self.connected = False
        self.cache_update_pending = False
        self.spin = Halo(spinner='dots')
        self.cloud = None  # Set in refresh method if reachable
        self.do_cloud = cpi.config.cfg.get('cloud', False)
        CLOUD_CREDS_FILE = config.static.get('CLOUD_CREDS_FILE')
        if not CLOUD_CREDS_FILE:
            self.no_creds_error()
        if self.do_cloud and cpi.config.cfg.get('cloud_svc') == 'gdrive':
            if cpi.utils.is_reachable('www.googleapis.com', 443):
                self.local_only = False
                if not cpi.utils.valid_file(CLOUD_CREDS_FILE):
                    self.no_creds_error()
            else:
                cpi.config.log_and_show('failed to connect to {cloud_svc} - operating in local only mode',
                                        log=cpi.config.log.warning)
                self.local_only = True
        self.data = self.get_remote(data=cpi.config.remotes)

    def no_creds_error(self):
        cpi = self.cpi
        cloud_svc = cpi.config.cfg.get('cloud_svc', 'UNDEFINED!')
        cpi.config.log_and_show(f'Required {cloud_svc} credentials files are missing refer to GitHub for details',
                                log=cpi.config.log.warning)
        cpi.config.log_and_show(f'Disabling {cloud_svc} updates', log=cpi.config.log.warning)
        cpi.config.error_msgs.append('Cloud Function Disabled by script - No Credentials Found')
        self.do_cloud = cpi.config.cfg['do_cloud'] = False

    # get remote consoles from local cache refresh function will check/update cloud file and update local cache
    def get_remote(self, data=None):
        spin = self.spin
        cpi = self.cpi
        config = cpi.config
        log = config.log
        update_cache = False
        if data is None:
            data = config.remotes

        def verify_remote_thread(remotepi, data):
            '''sub to verify reacability and api data for remotes

            params:
            remotepi: The hostname currently being processed
            data: dict remote ConsolePi dict with hostname as key
            '''
            this = data[remotepi]
            update, this = self.api_reachable(remotepi, this)
            if update:
                self.cache_update_pending = True

            if not this.get('rem_ip'):
                log.warning(f'[GET REM] Found {"remotepi"} in Local Cloud Cache: UNREACHABLE')
                this['fail_cnt'] = 1 if not this.get('fail_cnt') else this['fail_cnt'] + 1
                self.pop_list.append(remotepi)
                self.cache_update_pending = True
            else:
                self.connected = True
                if this.get('fail_cnt'):
                    this['fail_cnt'] = 0
                    self.cache_update_pending = True
                if update_cache:
                    log.info('[GET REM] Updating Cache - Found {0} in Local Cloud Cache, reachable via {1}'.format(
                              remotepi, this['rem_ip']))

            data[remotepi] = this

        if data is None or len(data) == 0:
            data = config.remotes  # remotes from local cloud cache

        if not data:
            print(self.log_sym_warn + ' No Remotes in Local Cache')
            data = {}  # convert None type to empy dict

        if self.cpi.local.hostname in data:
            del data[self.cpi.local.hostname]
            config.log_and_show('Local cache included entry for self - do you have other ConsolePis using the same hostname?')

        # Verify Remote ConsolePi details and reachability
        spin.start('Querying Remotes via API to verify reachability and adapter data')
        for remotepi in data:
            # Launch Threads to verify all remotes in parallel
            threading.Thread(target=verify_remote_thread, args=(remotepi, data), name=f'vrfy_{remotepi}').start()

        # -- wait for threads to complete --
        if not cpi.wait_for_threads(name='vrfy_', thread_type='remote'):
            if config.remotes:
                spin.succeed('[GET REM] Querying Remotes via API to verify reachability and adapter data\n\t'
                             f'Found {len(config.remotes)} Remote ConsolePis')
            else:
                spin.warn('[GET REM] Querying Remotes via API to verify reachability and adapter data\n\t'
                          'No Remote ConsolePis Discovered/Found')
        else:
            log.error('[GET REM] Remote verify threads Still running / exceeded timeout')

        # update local cache if any ConsolePis found UnReachable
        if self.cache_update_pending:
            if self.pop_list:
                for remotepi in self.pop_list:
                    if data[remotepi]['fail_cnt'] >= 3:  # NoQA remove from local cache after 3 failures (cloud or mdns will repopulate if discovered)
                        removed = data.pop(remotepi)
                        config.log_and_show('[GET REM] {} has been removed from Local Cache after {} failed attempts'.format(
                            remotepi, removed['fail_cnt']), log=config.log.warning)
                    else:
                        cpi.error_msgs.append('Cached Remote \'{}\' is unreachable'.format(remotepi))

            # update local cache file if rem_ip or adapter data changed
            data = self.update_local_cloud_file(data)
            self.pop_list = []
            self.cache_update_pending = False

        return data

    # Update with Data from ConsolePi.csv on Gdrive and local cache populated by mdns.  Update Gdrive with our data
    def refresh(self, rem_update=False):
        # pylint: disable=maybe-no-member
        remote_consoles = None
        cpi = self.cpi
        config = cpi.config
        local = cpi.local
        config.rows, config.cols = cpi.utils.get_tty_size()
        log = config.log
        cloud_svc = config.cfg.get('cloud_svc', 'error')

        # TODO refactor wait_for_threads to have an all key or accept a list
        with Halo(text='Waiting For threads to complete', spinner='dots1'):
            if cpi.wait_for_threads() and cpi.wait_for_threads(name='_toggle_refresh'):
                cpi.error_msgs.append('Timeout Waiting for init or toggle threads to complete try again later or'
                                      ' investigate logs')
                return

        # -- // Update Local Adapters \\ --
        cpi.local.data = cpi.local.build_local_dict(refresh=True)
        log.debug(f'Final Data set collected for {local.hostname}: {local.data}')

        # -- // Get details from Google Drive - once populated will skip \\ --
        if self.do_cloud and not self.local_only:
            if cloud_svc == 'gdrive' and self.cloud is None:
                # burried import until I find out why this import takes so @#%$@#% long.  Not imported until 1st refresh is called
                with Halo(text='Loading Google Drive Library', spinner='dots1'):
                    from consolepi.gdrive import GoogleDrive
                self.cloud = GoogleDrive(cpi, hostname=local.hostname)
                log.info('[MENU REFRESH] Gdrive init')

            # Pass Local Data to update_sheet method get remotes found on sheet as return
            # update sheets function updates local_cloud_file
            _msg = '[MENU REFRESH] Updating to/from {}'.format(cloud_svc)
            log.info(_msg)
            self.spin.start(_msg)
            # -- // SYNC DATA WITH GDRIVE \\ --
            remote_consoles = self.cloud.update_files(local.data)
            if remote_consoles and 'Gdrive-Error:' not in remote_consoles:
                self.spin.succeed(_msg + '\n\tFound {} Remotes via Gdrive Sync'.format(len(remote_consoles)))
            elif 'Gdrive-Error:' in remote_consoles:
                self.spin.fail('{}\n\t{} {}'.format(_msg, self.log_sym_error, remote_consoles))
                self.error_msgs.append(remote_consoles)  # display error returned from gdrive module
            else:
                self.spin.warn(_msg + '\n\tNo Remotes Found via Gdrive Sync')
            if len(remote_consoles) > 0:
                _msg = f'[MENU REFRESH] Updating Local Cache with data from {cloud_svc}'
                log.info(_msg)
                self.spin.start(_msg)
                self.update_local_cloud_file(remote_consoles)
                self.spin.succeed(_msg)  # no real error correction here
            else:
                config.log_and_show(f'[MENU REFRESH] No Remote ConsolePis found on {cloud_svc}', log=log.warning)
        else:
            if self.do_cloud:
                cpi.error_msg.append(f'Not Updating from {cloud_svc} due to connection failure')
                cpi.error_msg.append('Close and re-launch menu if network access has been restored')

        # Update Remote data with data from local_cloud cache
        config.remote = self.get_remote(data=remote_consoles)

    def update_local_cloud_file(self, remote_consoles=None, current_remotes=None, local_cloud_file=None):
        '''Update local cloud cache (cloud.json).

        Verifies the newly discovered data is more current than what we already know and updates the local cloud.json file if so
        The Menu uses cloud.json to populate remote menu items

        params:
            remote_consoles: The newly discovered data (from Gdrive or mdns)
            current_remotes: The current remote data fetched from the local cloud cache (cloud.json)
                - func will retrieve this if not provided
            local_cloud_file The path to the local cloud file (global var cloud.json)

        returns:
        dict: The resulting remote console dict representing the most recent data for each remote.
        '''
        utils = self.cpi.utils
        config = self.cpi.config
        local_cloud_file = config.static.get('LOCAL_CLOUD_FILE') if local_cloud_file is None else local_cloud_file

        log = config.log
        if len(remote_consoles) > 0:
            # if os.path.isfile(local_cloud_file):
            if current_remotes is None:
                current_remotes = config.remotes

        # update current_remotes dict with data passed to function
        if len(remote_consoles) > 0:
            if current_remotes is not None:
                for _ in current_remotes:
                    if _ not in remote_consoles:
                        if 'fail_cnt' not in current_remotes[_] or current_remotes[_]['fail_cnt'] < 2:
                            remote_consoles[_] = current_remotes[_]
                        elif 'fail_cnt' not in remote_consoles[_] and 'fail_cnt' in current_remotes[_]:
                            remote_consoles[_]['fail_cnt'] = current_remotes[_]['fail_cnt']
                    else:

                        # -- DEBUG --
                        log.debug('[CACHE UPD] \n--{}-- \n    remote upd_time: {}\n    remote rem_ip: {}\n    remote source: {}\n    cache rem upd_time: {}\n    cache rem_ip: {}\n    cache source: {}\n'.format(  # NoQA
                            _,
                            time.strftime('%a %x %I:%M:%S %p %Z', time.localtime(remote_consoles[_]['upd_time'])) if 'upd_time' in remote_consoles[_] else None,  # NoQA
                            remote_consoles[_]['rem_ip'] if 'rem_ip' in remote_consoles[_] else None,
                            remote_consoles[_]['source'] if 'source' in remote_consoles[_] else None,
                            time.strftime('%a %x %I:%M:%S %p %Z', time.localtime(current_remotes[_]['upd_time'])) if 'upd_time' in current_remotes[_] else None,  # NoQA
                            current_remotes[_]['rem_ip'] if 'rem_ip' in current_remotes[_] else None,
                            current_remotes[_]['source'] if 'source' in current_remotes[_] else None,
                            ))
                        # -- END DEBUG --

                        # No Change Detected (data passed to function matches cache)
                        if remote_consoles[_] == current_remotes[_]:
                            log.info('[CACHE UPD] {} No Change in info detected'.format(_))

                        # only factor in existing data if source is not mdns
                        elif 'upd_time' in remote_consoles[_] or 'upd_time' in current_remotes[_]:
                            if 'upd_time' in remote_consoles[_] and 'upd_time' in current_remotes[_]:
                                if current_remotes[_]['upd_time'] > remote_consoles[_]['upd_time']:
                                    remote_consoles[_] = current_remotes[_]
                                    log.info('[CACHE UPD] {} Keeping existing data based on more current update time'.format(_))
                                else:
                                    if current_remotes[_]['upd_time'] == remote_consoles[_]['upd_time']:
                                        log.warning('[CACHE UPD] {} current cache update time and {} update time is equal'
                                                    ' but contents of dict don\'t match'.format(_, remote_consoles[_]['source']))
                                    else:
                                        log.info('[CACHE UPD] {} Updating data from {} '
                                                 'based on more current update time'.format(_, remote_consoles[_]['source']))

                            elif 'upd_time' in current_remotes[_]:
                                remote_consoles[_] = current_remotes[_]
                                log.info('[CACHE UPD] {} Keeping existing data based *existence* of update time '
                                         'which is lacking in this update from {}'.format(_, remote_consoles[_]['source']))

            for _try in range(0, 2):
                try:
                    with open(local_cloud_file, 'w') as cloud_file:
                        cloud_file.write(json.dumps(remote_consoles, indent=4, sort_keys=True))
                        utils.set_perm(local_cloud_file)  # a hack to deal with perms ~ consolepi-details del func
                        break
                except PermissionError:
                    utils.set_perm(local_cloud_file)

        else:
            log.warning('[CACHE UPD] cache update called with no data passed, doing nothing')

        return remote_consoles

    def get_adapters_via_api(self, ip: str):
        '''Send RestFul GET request to Remote ConsolePi to collect adapter info

        params:
        ip(str): ip address or FQDN of remote ConsolePi

        returns:
        adapter dict for remote if successful
        Falsey or response status_code if an error occured.
        '''
        log = self.cpi.config.log
        url = f'http://{ip}:5000/api/v1.0/adapters'

        headers = {
            'Accept': "*/*",
            'Cache-Control': "no-cache",
            'Host': f"{ip}:5000",
            'accept-encoding': "gzip, deflate",
            'Connection': "keep-alive",
            'cache-control': "no-cache"
            }

        try:
            response = requests.request("GET", url, headers=headers, timeout=2)
        except (OSError, TimeoutError):
            log.warning('[API RQST OUT] Remote ConsolePi {} TimeOut when querying via API - Unreachable.'.format(ip))
            return False

        if response.ok:
            ret = json.loads(response.text)
            ret = ret['adapters'] if ret['adapters'] else response.status_code
            _msg = 'Adapters Successfully retrieved via API for Remote ConsolePi {}'.format(ip)
            log.info('[API RQST OUT] {}'.format(_msg))
            log.debug('[API RQST OUT] Response: \n{}'.format(json.dumps(ret, indent=4, sort_keys=True)))
        else:
            ret = response.status_code
            log.error('[API RQST OUT] Failed to retrieve adapters via API for Remote ConsolePi {}\n{}:{}'.format(
                                                                                            ip, ret, response.text))
        return ret

    # TODO change remote_data to cache_data it represents what is currently in cache
    def api_reachable(self, remote_host: str, remote_data: dict):
        '''Check Rechability & Fetch adapter data via API for remote ConsolePi

        params:
            remote_host:str, The hostname of the Remote ConsolePi
            remote_data:dict, The ConsolePi dictionary for the remote (from cache file)

        returns:
            tuple [0]: Bool, indicating if data is different than cache
                  [1]: dict, Updated ConsolePi dictionary for the remote
        '''
        update = False
        cpi = self.cpi
        config = cpi.config
        local = cpi.local
        log = config.log

        _iface_dict = remote_data['interfaces']
        rem_ip_list = [_iface_dict[_iface]['ip'] for _iface in _iface_dict if _iface_dict[_iface]['ip'] not in local.ip_list]

        # if inbound data includes rem_ip make sure to try that first
        if remote_data.get('rem_ip'):
            if rem_ip_list.index(remote_data['rem_ip']) != 0:
                rem_ip_list.remove(remote_data['rem_ip'])
                rem_ip_list.insert(0, remote_data['rem_ip'])

        remote_data['rem_ip'] = None
        for _ip in rem_ip_list:
            log.debug(f'[API_REACHABLE] verifying {remote_host}')
            _adapters = self.get_adapters_via_api(_ip)
            if _adapters:
                if not isinstance(_adapters, int):  # indicates an html error code was returned
                    if not remote_data['adapters'] == _adapters:
                        remote_data['adapters'] = _adapters
                        update = True  # update if cached adapters didn't match
                elif _adapters == 200:
                    cpi.error_msgs.append(f"Remote {remote_host} is reachable via {_ip},"
                                          " but has no adapters attached")
                    cpi.error_msgs.append('it\'s still available in remote shell menu')

                # remote was reachable update rem_ip, even if returned bad status_code still reachable
                if not remote_data.get('rem_ip', '') == _ip:
                    remote_data['rem_ip'] = _ip
                    update = True  # update if rem_ip didn't match
                break

        return (update, remote_data)
