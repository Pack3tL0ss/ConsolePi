#!/etc/ConsolePi/venv/bin/python3

import time
import socket
from typing import Any, Dict, List, Union
from halo import Halo
from sys import stdin
from log_symbols import LogSymbols as log_sym  # Enum
from consolepi import utils, log, config, json  # type: ignore
from aiohttp import ClientSession
import asyncio
from aiohttp.client_exceptions import ContentTypeError, ClientConnectorError
# from pydantic import BaseModel
# from consolepi.gdrive import GoogleDrive  !!--> Import burried in refresh method to speed menu load times on older platforms

# Source = Literal["cloud", "mdns"]

# from .models import Remote


class Remotes:
    """Remotes Object Contains attributes for discovered remote ConsolePis

    bypass_cloud overrides the config value for cloud (gdrive sync)
        Used by mdns services which don't need cloud updates.
    """
    def __init__(self, local, cpiexec, bypass_cloud: bool = False):
        self.cpiexec = cpiexec
        self.pop_list = []
        self.old_api_log_sent = False
        self.log_sym_warn = log_sym.WARNING.value
        self.log_sym_error = log_sym.ERROR.value
        self.local = local
        self.connected: bool = False
        self.cache_update_pending = False
        self.spin = Halo(spinner="dots")
        self.running_spinners = []
        self.cloud = None  # Set in refresh method if reachable
        self.do_cloud = False if bypass_cloud is True else config.cfg.get("cloud", False)
        CLOUD_CREDS_FILE = config.static.get("CLOUD_CREDS_FILE")
        if not CLOUD_CREDS_FILE:
            self.no_creds_error()
        if self.do_cloud and config.cloud_svc == "gdrive":
            if utils.is_reachable("www.googleapis.com", 443, silent=False):
                self.local_only = False
                if not utils.valid_file(CLOUD_CREDS_FILE):
                    self.no_creds_error()
            else:
                log.warning(
                    f"failed to connect to {config.cloud_svc} - operating in local only mode",
                    show=True,
                )
                self.local_only = True
        self.data = asyncio.run(
            self.get_remote(
                data=config.remote_update()
            )  # re-get cloud.json to capture any updates via mdns
        )

    def no_creds_error(self):
        cloud_svc = config.cfg.get("cloud_svc", "UNDEFINED!")
        log.warning(
            f"Required {cloud_svc} credentials files are missing refer to GitHub for details"
        )
        log.warning(f"Disabling {cloud_svc} updates")
        log.show("Cloud Function Disabled by script - No Credentials Found")
        self.do_cloud = config.cfg["do_cloud"] = False

    def _sort_by_timeout(self, data: Dict[str, dict]) -> Dict[str, dict]:
        try:
            data = {host: {**d, "timeout": getattr(config.remote_timeout, host)} for host, d in data.items()}
            # places remotes that were not reachable in previous attempts first followed by remotes with the longest configured timeouts
            # We want remotes that have the potential to take longer added to the event loop first
            return dict(sorted(data.items(), key=lambda x: 999 if not x[1]["rem_ip"] else x[1]["timeout"], reverse=True))
        except Exception as e:
            log.exception(f"Exception during attempt to sort remotes by timeout\n{e}")
            return data

    # get remote consoles from local cache refresh function will check/update cloud file and update local cache
    async def get_remote(self, data: dict = None, rename: bool = False) -> Dict[str, Any]:
        spin = self.spin
        _get_remote_start = time.perf_counter()

        async def verify_remote(remotepi: str, data: dict, rename: bool) -> None:
            """sub to verify reachability and api data for remotes

            params:
            remotepi: The hostname currently being processed
            data: dict remote ConsolePi dict with hostname as key
            rename: bool set True to perform rename request (TODO not sure this is used.)
            """
            this = data[remotepi]
            if stdin.isatty():
                self.spin.stop()
                self.spin.start(f"verifying {remotepi}")
            self.running_spinners += [remotepi]
            res = await self.api_reachable(remotepi, this, rename=rename)
            _ = self.running_spinners.pop(self.running_spinners.index(remotepi))
            if stdin.isatty():  # restore spin text to any spinners that are still runnning
                self.spin.stop() if res.reachable else self.spin.fail(f'verifying {remotepi}')
                if self.running_spinners:
                    self.spin.start(f"verifying {self.running_spinners[-1]}")
                else:
                    if config.remotes:
                        self.spin.succeed(
                            "[GET REM] Querying Remotes via API to verify reachability and adapter data\n\t"
                            f"Found {len(config.remotes)} Remote ConsolePis in {time.perf_counter() - _get_remote_start:.2f}"
                        )
                    else:
                        self.spin.warn(
                            "[GET REM] Querying Remotes via API to verify reachability and adapter data\n\t"
                            "No Reachable Remote ConsolePis Discovered"
                        )

            this = res.data
            if res.update:
                self.cache_update_pending = True

            if not res.reachable:
                log.warning(
                    f"[GET REM] Found {remotepi} in Local Cloud Cache: UNREACHABLE"
                )
                this["fail_cnt"] = (this.get("fail_cnt", 0) + 1)
                self.pop_list += [remotepi]
                self.cache_update_pending = True
            else:
                self.connected = True
                if this.get("fail_cnt"):
                    this["fail_cnt"] = 0
                    self.cache_update_pending = True
                if res.update:
                    log.info(f"[GET REM] Updating Cache - Found {remotepi} in Local Cloud Cache, "
                             f"reachable via {this['rem_ip']}")

            data[remotepi] = this

        if data is None or len(data) == 0:
            data = config.remotes  # remotes from local cloud cache

        if not data:
            log.info("No Remotes found in Local Cache")
            data = {}  # convert None type to empy dict
        else:
            # if self is in the remote-data remove and warn user (can occur in rare scenarios i.e. hostname changes)
            if socket.gethostname() in data:
                del data[socket.gethostname()]
                log.show(
                    "Local cache included entry for self - do you have other ConsolePis using the same hostname?"
                )

            # Verify Remote ConsolePi details and reachability
            if stdin.isatty():
                spin.start(
                    "Querying Remotes via API to verify reachability and adapter data"
                )

            data = self._sort_by_timeout(data)
            _ = await asyncio.gather(*[verify_remote(remotepi, data, rename) for remotepi in data])

        # update local cache if any ConsolePis found UnReachable
        if self.cache_update_pending:
            if self.pop_list:
                for remotepi in self.pop_list:
                    if (
                        data[remotepi]["fail_cnt"] >= 3
                    ):  # NoQA remove from local cache after 3 failures (cloud or mdns will repopulate if discovered)
                        removed = data.pop(remotepi)
                        log.warning(
                            "[GET REM] {} has been removed from Local Cache after {} failed attempts".format(
                                remotepi, removed["fail_cnt"]
                            ),
                            show=True,
                        )
                    else:
                        log.show(f"Cached Remote '{remotepi}' is unreachable")

            # update local cache file if rem_ip or adapter data changed
            # TODO check logic I think both this method and update_local_cloud_file are checking reachability
            #      During debug manually pop a device from data dict, then below command re-adds it think update_local_cloud_file
            #      is merging with config.remotes and checking reachability?
            data = self.update_local_cloud_file(data)
            self.pop_list = []
            self.cache_update_pending = False

        # TODO this is working, prob change adapters to a list of models
        # remotes = [Remote(**{"name": k, **data[k]}) for k in data]
        return data

    # Update with Data from ConsolePi.csv on Gdrive and local cache populated by mdns.  Update Gdrive with our data
    def refresh(self, bypass_cloud: bool = False):
        remote_consoles: Union[List[Dict[str, Any]], None] = None
        cpiexec = self.cpiexec
        local = self.local
        cloud_svc: str = config.cfg.get("cloud_svc", "error")

        # TODO refactor wait_for_threads to have an all key or accept a list
        with Halo(text="Waiting For threads to complete", spinner="dots1"):
            if cpiexec.wait_for_threads(thread_type="remotes") and (
                config.power and cpiexec.wait_for_threads(name="_toggle_refresh")
            ):
                log.show(
                    "Timeout Waiting for init or toggle threads to complete try again later or"
                    " investigate logs"
                )
                return

        # -- // Update/Refresh Local Data (Adapters/Interfaces) \\ --
        local.data = local.build_local_dict(refresh=True)
        log.debugv(f"Final Data set collected for {local.hostname}: {local.data}")

        # -- // Get details from Google Drive - once populated will skip \\ --
        if not bypass_cloud and self.do_cloud and not self.local_only:
            if cloud_svc == "gdrive" and self.cloud is None:
                # burried import until I find out why this import takes so @#%$@#% long.  Not imported until 1st refresh is called
                with Halo(text="Loading Google Drive Library", spinner="dots1"):
                    from consolepi.gdrive import GoogleDrive  # type: ignore
                self.cloud = GoogleDrive(hostname=local.hostname)
                log.info("[MENU REFRESH] Gdrive init")

            # Pass Local Data to update_sheet method get remotes found on sheet as return
            # update sheets function updates local_cloud_file
            _msg = "[MENU REFRESH] Updating to/from {}".format(cloud_svc)
            log.info(_msg)
            if stdin.isatty():
                self.spin.start(_msg)
            # -- // SYNC DATA WITH GDRIVE \\ --
            remote_consoles = self.cloud.update_files(
                local.data
            )  # local data refreshed above
            if remote_consoles and "Gdrive-Error:" not in remote_consoles:
                if stdin.isatty():
                    self.spin.succeed(f"{_msg}\n\tFound {len(remote_consoles)} Remotes via Gdrive Sync")
                    for r in remote_consoles:
                        # -- Convert Any Remotes with old API schema to new API schema --
                        if isinstance(remote_consoles[r].get("adapters", {}), list):
                            remote_consoles[r]["adapters"] = self.convert_adapters(
                                remote_consoles[r]["adapters"]
                            )
                            log.warning(
                                f"Adapter data for {r} retrieved from cloud in old API format... Converted"
                            )
            elif "Gdrive-Error:" in remote_consoles:
                if stdin.isatty():
                    self.spin.fail(
                        "{}\n\t{} {}".format(_msg, self.log_sym_error, remote_consoles)
                    )
                log.show(remote_consoles)  # display error returned from gdrive module
                remote_consoles = []
            else:
                if stdin.isatty():
                    self.spin.warn(_msg + "\n\tNo Remotes Found via Gdrive Sync")

            if len(remote_consoles) > 0:
                _msg = f"[MENU REFRESH] Updating Local Cache with data from {cloud_svc}"
                log.info(_msg)
                if stdin.isatty():
                    self.spin.start(_msg)
                self.update_local_cloud_file(remote_consoles)
                if stdin.isatty():
                    self.spin.succeed(_msg)  # no real error correction here
            else:
                log.warning(
                    f"[MENU REFRESH] No Remote ConsolePis found on {cloud_svc}",
                    show=True,
                )
        else:
            if self.do_cloud and not bypass_cloud:
                log.show(
                    f"Not Updating from {cloud_svc} due to connection failure\n"
                    "Close and re-launch menu if network access has been restored"
                )

        # Update Remote data with data from local_cloud cache / cloud
        self.data = asyncio.run(self.get_remote(data=remote_consoles))

    def update_local_cloud_file(
        self, remote_consoles=None, current_remotes=None, local_cloud_file=None
    ):
        """Update local cloud cache (cloud.json).

        Verifies the newly discovered data is more current than what we already know and updates the local cloud.json file if so
        The Menu uses cloud.json to populate remote menu items

        params:
            remote_consoles: The newly discovered data (from Gdrive or mdns)
            current_remotes: The current remote data fetched from the local cloud cache (cloud.json)
                - func will retrieve this if not provided
            local_cloud_file The path to the local cloud file (global var cloud.json)

        returns:
        dict: The resulting remote console dict representing the most recent data for each remote.
        """
        local_cloud_file = (
            config.static.get("LOCAL_CLOUD_FILE")
            if local_cloud_file is None
            else local_cloud_file
        )

        if len(remote_consoles) > 0:
            if current_remotes is None:
                current_remotes = self.data = config.remote_update()  # grabs the remote data from local cloud cache

        # update current_remotes dict with data passed to function
        if len(remote_consoles) > 0:
            if current_remotes is not None:
                for _ in current_remotes:
                    if _ not in remote_consoles:
                        if (
                            "fail_cnt" not in current_remotes[_]
                            or current_remotes[_]["fail_cnt"] < 2
                        ):
                            remote_consoles[_] = current_remotes[_]
                        elif (
                            remote_consoles.get(_)
                            and "fail_cnt" not in remote_consoles[_]
                            and "fail_cnt" in current_remotes[_]
                        ):
                            remote_consoles[_]["fail_cnt"] = current_remotes[_][
                                "fail_cnt"
                            ]
                    else:

                        # -- VERBOSE DEBUG --
                        log.debugv(
                            "[CACHE UPD] \n--{}-- \n    remote upd_time: {}\n    remote rem_ip: {}\n    remote source: {}\n    cache rem upd_time: {}\n    cache rem_ip: {}\n    cache source: {}\n".format(  # NoQA
                                _,
                                time.strftime(
                                    "%a %x %I:%M:%S %p %Z",
                                    time.localtime(remote_consoles[_]["upd_time"]),
                                )
                                if "upd_time" in remote_consoles[_]
                                else None,  # NoQA
                                remote_consoles[_]["rem_ip"]
                                if "rem_ip" in remote_consoles[_]
                                else None,
                                remote_consoles[_]["source"]
                                if "source" in remote_consoles[_]
                                else None,
                                time.strftime(
                                    "%a %x %I:%M:%S %p %Z",
                                    time.localtime(current_remotes[_]["upd_time"]),
                                )
                                if "upd_time" in current_remotes[_]
                                else None,  # NoQA
                                current_remotes[_]["rem_ip"]
                                if "rem_ip" in current_remotes[_]
                                else None,
                                current_remotes[_]["source"]
                                if "source" in current_remotes[_]
                                else None,
                            )
                        )
                        # -- END VERBOSE DEBUG --

                        # No Change Detected (data passed to function matches cache)
                        if "last_ip" in current_remotes[_]:
                            del current_remotes[_]["last_ip"]
                        if remote_consoles[_] == current_remotes[_]:
                            log.debug(
                                "[CACHE UPD] {} No Change in info detected".format(_)
                            )

                        # only factor in existing data if source is not mdns
                        elif (
                            "upd_time" in remote_consoles[_]
                            or "upd_time" in current_remotes[_]
                        ):
                            if (
                                "upd_time" in remote_consoles[_]
                                and "upd_time" in current_remotes[_]
                            ):
                                if (
                                    current_remotes[_]["upd_time"]
                                    > remote_consoles[_]["upd_time"]
                                ):
                                    remote_consoles[_] = current_remotes[_]
                                    log.info(
                                        f"[CACHE UPD] {_} Keeping existing data from {current_remotes[_].get('source', '')} "
                                        "based on more current update time"
                                    )
                                elif (
                                    remote_consoles[_]["upd_time"]
                                    > current_remotes[_]["upd_time"]
                                ):
                                    log.info(
                                        "[CACHE UPD] {} Updating data from {} "
                                        "based on more current update time".format(
                                            _, remote_consoles[_]["source"]
                                        )
                                    )
                                else:  # -- Update Times are equal --
                                    if (
                                        current_remotes[_].get("adapters")
                                        and remote_consoles[_].get("adapters")
                                        and current_remotes[_]["adapters"].keys()
                                        != remote_consoles[_]["adapters"].keys()
                                    ) or remote_consoles[_].get(
                                        "interfaces", {}
                                    ) != current_remotes[
                                        _
                                    ].get(
                                        "interfaces", {}
                                    ):
                                        log.warning(
                                            "[CACHE UPD] {} current cache update time and {} update time are equal"
                                            " but data appears to have changed. Updating".format(
                                                _, remote_consoles[_]["source"]
                                            )
                                        )
                            elif "upd_time" in current_remotes[_]:
                                remote_consoles[_] = current_remotes[_]
                                log.info(
                                    "[CACHE UPD] {} Keeping existing data based *existence* of update time "
                                    "which is lacking in this update from {}".format(
                                        _, remote_consoles[_]["source"]
                                    )
                                )

            for _ in range(0, 2):
                try:
                    with open(local_cloud_file, "w") as cloud_file:
                        cloud_file.write(
                            json.dumps(remote_consoles, indent=4, sort_keys=True)
                        )
                        utils.set_perm(
                            local_cloud_file
                        )  # a hack to deal with perms ~ consolepi-details del func
                        break
                except PermissionError:
                    utils.set_perm(local_cloud_file)

        else:
            log.warning(
                "[CACHE UPD] cache update called with no data passed, doing nothing"
            )

        return remote_consoles

    async def get_adapters_via_api(self, ip: str, port: int = 5000, rename: bool = False, log_host: str = None):
        """Send RestFul GET request to Remote ConsolePi to collect adapter info

        params:
        ip(str): ip address or FQDN of remote ConsolePi
        rename(bool): TODO
        log_host(str): friendly string for logging purposes "hostname(ip)"

        returns:
        adapter dict for remote if successful and adapters exist
        status_code 200 if successful but no adapters or Falsey or response status_code if an error occurred.
        22 if unable to reach API, but can reach port 22 (ssh)
        """
        if not log_host:
            log_host = ip
        url = f"http://{ip}:{port}/api/v1.0/adapters"
        if rename:
            url = f"{url}?refresh=true"

        log.debug(url)

        headers = {
            "Accept": "*/*",
            "Cache-Control": "no-cache",
            "Host": f"{ip}:{port}",
            "accept-encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "cache-control": "no-cache",
        }

        ret = None
        try:
            _start = time.perf_counter()
            async with ClientSession() as client:
                resp = await client.request(
                    method="GET",
                    url=url,
                    headers=headers,
                    timeout=getattr(config.remote_timeout, log_host),
                )
                _elapsed = time.perf_counter() - _start
                if resp.ok:
                    try:
                        ret = await resp.json()
                        ret = ret["adapters"] if ret["adapters"] else resp.status
                        _msg = f"Adapters Successfully retrieved via API for Remote ConsolePi: {log_host}, elapsed {_elapsed:.2f}s"
                        log.info("[API RQST OUT] {}".format(_msg))
                        log.debugv(
                            "[API RQST OUT] Response: \n{}".format(
                                json.dumps(ret, indent=4, sort_keys=True)
                            )
                        )
                    except (json.decoder.JSONDecodeError, ContentTypeError):
                        log.error(f'[API RQST OUT] Puked on payload from {log_host} \n{await resp.text()}')
                        ret = resp.status
        except (asyncio.TimeoutError, ClientConnectorError):
            log.warning(f"[API RQST OUT] Remote ConsolePi: {log_host} TimeOut when querying via API - Unreachable.")
        except Exception as e:
            log.show(f'Exception: {e.__class__.__name__}, in remotes.get_adapters_via_api() check logs')
            log.exception(e)

        if not ret:  # hit an exception / or not reachable
            if utils.is_reachable(ip, port=22, silent=True):
                ret = 22  # indicates only available via ssh

        return ret

    async def api_reachable(self, remote_host: str, cache_data: dict, rename: bool = False):
        """Check Rechability & Fetch adapter data via API for remote ConsolePi

        params:
            remote_host:str, The hostname of the Remote ConsolePi
            cache_data:dict, The ConsolePi dictionary for the remote (from cache file)
            rename:bool, rename = True will do api call with refresh=True Query parameter
                which tells the api to first update connection data from ser2net as it likely
                changed as a result of remote rename operation.

        returns:
            APIReachableResponse object with the following attributes
                update: bool flag indicating if data was updated (I think)
                data: dict remote consolepi dict
                rechable: bool if the consolepi is reachable
        """

        class ApiReachableResponse:
            def __init__(self, update, data, reachable):
                self.update = update
                self.data = data
                self.reachable = reachable

        update = False
        local = self.local

        _iface_dict = cache_data["interfaces"]
        rem_ip_list = [
            _iface_dict[_iface].get("ip")
            for _iface in _iface_dict
            if not _iface.startswith("_") and _iface_dict[_iface].get("ip") not in local.ip_list
        ]

        # if inbound data includes rem_ip make sure to try that first
        for _ip in [cache_data.get("rem_ip"), cache_data.get("last_ip")]:
            if _ip:
                if _ip not in rem_ip_list:
                    rem_ip_list.insert(0, _ip)
                elif rem_ip_list.index(_ip) != 0:
                    rem_ip_list.remove(_ip)
                    rem_ip_list.insert(0, _ip)

        rem_ip = _adapters = None
        for _ip in rem_ip_list:
            log.debug(f"[API_REACHABLE] verifying {remote_host}")
            _adapters = await self.get_adapters_via_api(_ip, port=int(cache_data.get("api_port", 5000)), rename=rename, log_host=f"{remote_host}({_ip})")
            if _adapters:
                rem_ip = _ip  # Remote is reachable
                if not isinstance(_adapters, int):  # indicates status_code returned (error or no adapters found)
                    if isinstance(_adapters, list):  # indicates need for conversion from old api format
                        _adapters = self.convert_adapters(_adapters)
                        if not self.old_api_log_sent:
                            log.warning(
                                f"{remote_host} provided old api schema.  Recommend Upgrading to current."
                            )
                            self.old_api_log_sent = True
                    # Only compare config dict for each adapter as udev dict will generally be different due to time_since_init
                    if not cache_data.get("adapters") or {
                        a: {"config": _adapters[a].get("config", {})} for a in _adapters
                    } != {
                        a: {"config": cache_data["adapters"][a].get("config", {})}
                        for a in cache_data["adapters"]
                    }:
                        cache_data["adapters"] = _adapters
                        update = True  # --> Update if adapter dict is different
                    else:
                        cached_udev = [False for a in cache_data["adapters"] if 'udev' not in cache_data["adapters"][a]]
                        if False in cached_udev:
                            cache_data["adapters"] = _adapters
                            update = True  # --> Update if udev key not in existing data (udev not sent to cloud)
                elif _adapters == 200:
                    log.show(
                        f"Remote {remote_host} is reachable via {_ip},"
                        " but has no adapters attached\nit's still available in remote shell menu"
                    )
                elif _adapters == 22:
                    log.show(
                        f"Remote {remote_host}({_ip}) did not respond to API request,"
                        " but appears to be reachable via SSH\nit's available in remote shell menu"
                    )

                # remote was reachable update last_ip, even if returned bad status_code still reachable
                if not cache_data.get("last_ip", "") == _ip:
                    cache_data["last_ip"] = _ip
                    update = True  # --> Update if last_ip is different than currently reachable IP
                break

        if cache_data.get("rem_ip") != rem_ip:
            cache_data["rem_ip"] = rem_ip
            update = True  # --> Update if rem_ip didn't match (was previously unreachable)

        if not _adapters:
            reachable = False
            if isinstance(cache_data.get("adapters"), list):
                _adapters = cache_data.get("adapters")
                _adapters = {
                    _adapters[_adapters.index(d)]["dev"]: {
                        "config": {
                            k: _adapters[_adapters.index(d)][k]
                            for k in _adapters[_adapters.index(d)]
                        }
                    }
                    for d in _adapters
                }
                cache_data["adapters"] = _adapters
                _msg = (
                    f"{remote_host} Cached adapter data was in old format... Converted to new.\n"
                    f"\t\t{remote_host} Should be upgraded to the current version of ConsolePi."
                )
                log.warning(_msg, show=True)
                update = True  # --> Convert to new and Update if cache data was in old format
        else:
            reachable = True

        return ApiReachableResponse(update, cache_data, reachable)

    def convert_adapters(self, adapters):
        return {
            adapters[adapters.index(d)]["dev"]: {
                "config": {
                    k: adapters[adapters.index(d)][k]
                    for k in adapters[adapters.index(d)]
                }
            }
            for d in adapters
        }
