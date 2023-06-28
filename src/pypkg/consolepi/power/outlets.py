#!/etc/ConsolePi/venv/bin/python3

import json
import threading
import time
from typing import Any, Dict, List, Tuple, Union

try:
    import RPi.GPIO as GPIO
    is_rpi = True
except (RuntimeError, ModuleNotFoundError, ImportError):
    is_rpi = False

from consolepi import log, config, requests, utils  # type: ignore
from consolepi.power import DLI  # type: ignore

TIMING = False


class ConsolePiPowerException(Exception):
    pass


class Outlets:
    def __init__(self):
        if is_rpi:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
        self._dli = {}

        # Some convenience Bools used by menu to determine what options to display
        self.dli_exists = True if 'dli' in config.outlet_types or config.do_dli_menu else False
        self.tasmota_exists = True if 'tasmota' in config.outlet_types else False
        self.esphome_exists = True if 'esphome' in config.outlet_types else False  # TODO Future
        self.gpio_exists = True if 'gpio' in config.outlet_types else False
        self.linked_exists = True if config.linked_exists else False
        if self.dli_exists or self.tasmota_exists or self.esphome_exists or self.gpio_exists:
            self.outlets_exists = True
        else:
            self.outlets_exists = False

        self.data: Dict[str, Any] = config.outlets

        if config.power:
            self.pwr_start_update_threads()

    def linked(self):
        pass

    def do_tasmota_cmd(self, address, command=None):
        '''
        Perform Operation on Tasmota outlet:
        params:
        address: IP or resolvable hostname
        command:
            True | 'ON': power the outlet on
            False | 'OFF': power the outlet off
            'Toggle': Toggle the outlet
            'cycle': Cycle Power on outlets that are powered On

        TODO: Right now this method does not verify if port is currently in an ON state
            before allowing 'cycle', resulting in it powering on the port consolepi-menu
            verifies status before allowing the command, but *may* be that other outlet
            are handled by this library.. check & make consistent
        TODO: remove int returns and re-factor all returns to use a return class (like requests)
        '''
        # sub to make the api call to the tasmota device
        def tasmota_req(**kwargs):
            querystring = kwargs['querystring']
            try:
                response = requests.request("GET", url, headers=headers, params=querystring, timeout=config.so_timeout)
                if response.status_code == 200:
                    if json.loads(response.text)['POWER'] == 'ON':
                        _response = True
                    elif json.loads(response.text)['POWER'] == 'OFF':
                        _response = False
                    else:
                        _response = 'invalid state returned {}'.format(response.text)
                else:
                    _response = '[{}] error returned {}'.format(response.status_code, response.text)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                _response = 'Unreachable'
            except requests.exceptions.RequestException as e:
                log.debug(f"[tasmota_req] {url.replace('http://', '').replace('https://', '').split('/')[0]} Exception: {e}")
                _response = 'Unreachable ~ hit catchall exception handler'  # determine if other exceptions types are possible
            return _response
        # -------- END SUB --------

        url = 'http://' + address + '/cm'
        headers = {
            'Cache-Control': "no-cache",
            'Connection': "keep-alive",
            'cache-control': "no-cache"
        }

        querystring = {"cmnd": "Power"}
        cycle = False
        if command is not None:
            if isinstance(command, bool):
                command = 'ON' if command else 'OFF'

            command = command.upper()
            if command in ['ON', 'OFF', 'TOGGLE']:
                querystring = {"cmnd": f"Power {command}"}
            elif command == 'CYCLE':
                cur_state = tasmota_req(querystring={"cmnd": "Power"})
                if isinstance(cur_state, bool):
                    if cur_state:
                        querystring = {"cmnd": "Power OFF"}
                        cycle = True
                    else:
                        return False  # return False for cycle if outlet was off indicating state is invalid for cycle
                else:
                    return cur_state  # an error occurred getting current state
            else:
                raise ConsolePiPowerException(f'Invalid Type {type(command)} passed to do_tasmota_cmd')

        # -- // Send Request to TASMOTA \\ --
        r = tasmota_req(querystring=querystring)
        if cycle:
            if isinstance(r, bool):
                if not r:
                    time.sleep(config.cycle_time)
                    r = tasmota_req(querystring={"cmnd": "Power ON"})
                else:
                    return 'Unexpected response, port returned on state expected off'
        return r

    def do_esphome_cmd(self, address, relay_id, command=None):
        '''Perform Operation on espHome outlets.

        Arguments:
            address {str} -- ip of fqdn of espHome outlet
            relay_id {str} -- The id of the relay/port

        Keyword Arguments:
            command {Bool|str|None} -- The command to perform on the outlet (default: {None})
                None (Default): get current state of outlet
                True | 'ON':    power the outlet on
                False | 'OFF':  power the outlet off
                'Toggle':       Toggle the outlet
                'cycle':        Cycle Power on outlets that are powered On

        Returns:
            Bool or str -- Bool indicating state of outlet after operation or str with error text
        '''
        def esphome_req(*args, command=command):
            '''sub function to perform operation on outlet
            '''
            try:
                method = "GET" if command is None else "POST"
                response = requests.request(method, url=url,
                                            headers=headers, timeout=config.so_timeout)
                if response.status_code == 200:
                    if command is None:
                        _response = response.json().get('value')
                    else:
                        # espHome returns status Code 200 with no content for /toggle
                        if command in ['toggle', 'cycle']:
                            _response = not cur_state
                        else:
                            _response = command  # success return bool command
                else:
                    _response = '[{}] error returned {}'.format(response.status_code, response.text)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                _response = 'Unreachable'
            except requests.exceptions.RequestException as e:
                log.debug(f"[esphome_req] {url.replace('http://', '').replace('https://', '').split('/')[0]} Exception: {e}")
                _response = 'Unreachable'  # So I can determine if other exceptions types are possible when unreachable
            return _response
        # -------- END SUB --------

        url = status_url = 'http://' + address + '/switch/' + str(relay_id)
        headers = {
            'Cache-Control': "no-cache",
            'Connection': "keep-alive",
            'cache-control': "no-cache"
        }
        # -- Get initial State of Outlet --
        cur_state = esphome_req(command=None)

        cycle = False
        if command is None:
            return cur_state
        elif isinstance(command, bool):
            if command:  # Turn On Outlet
                url = status_url + '/turn_on'
                if cur_state is True:
                    return cur_state
            else:  # Turn Off Outlet
                url = status_url + '/turn_off'
                if cur_state is False:
                    return cur_state
        elif command in ['toggle', 'cycle']:
            url = status_url + '/toggle'
            if command == 'cycle':
                if cur_state:
                    cycle = True
                else:
                    return False  # Cycle invalid for outlets in off state
        else:
            return f'[PWR-ESP] DEV Note: Invalid command \'{command}\' passed to func'

        # -- // Send Request to esphome \\ --
        r = esphome_req(command=command)
        if isinstance(r, bool):
            if cycle:
                if r is False:
                    cur_state = False
                    time.sleep(config.cycle_time)
                    r = esphome_req()
                else:
                    return '[PWR-ESP] Unexpected response, port returned on state expected off'
        return r

    def load_dli(self, address, username, password):
        '''
        Returns instace of DLI class

        Response: tuple
            DLI-class-object, Bool: True if class was previously instantiated ~ needs update
                                    False indicating class was just instantiated ~ data is fresh
            i.e.: (<dli object>, True)
        '''
        if not self._dli.get(address):
            try:
                self._dli[address] = DLI(address, username, password, timeout=config.dli_timeout, log=log)
            except Exception as e:
                log.warning(f"[PWR-DLI] DLI @ {address} is now unreachable {e.__class__.__name__}", show=True)
                return None, None
            # --// Return Pass or fail based on reachability \\--
            if self._dli[address].reachable:
                return self._dli[address], False
            else:
                return None, None

        # --// DLI Already Loaded \\--
        else:
            return self._dli[address], True

    def pwr_start_update_threads(self, upd_linked: bool = False, failures: Dict[str, Any] = {}, t_name: str = 'init'):
        kwargs = {'upd_linked': upd_linked, 'failures': failures}
        outlets = self.data.get('defined', {})
        if not failures:
            if 'failures' in outlets:
                failures = outlets['failures']
        if failures:  # re-attempt connection to failed power controllers on refresh
            outlets = {**outlets, **failures}
            failures = {}

        # this shouldn't happen, but prevents spawning multiple updates for same outlet
        _outlets = outlets.copy()
        if _outlets is not None:
            for k in _outlets:
                found = False
                for t in threading.enumerate():
                    if t.name == f'{t_name}_pwr_{k}':
                        found = True
                        break
                if not found:
                    threading.Thread(target=self.pwr_get_outlets, args=[{k: _outlets[k]}],
                                     kwargs=kwargs, name=t_name + '_pwr_' + k).start()

    def update_linked_devs(self, outlet: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Union[str, int]]]:
        '''Update linked devs for dli outlets if they exist

        Params:
            dict -- the outlet dict to be updated

        Returns:
            tuple -- 0: dict: updated outlet dict or same dict if no linked_devs
                     1: list: list of all ports linked on this dli (used to initiate query against the dli)
        '''
        this_dli = self._dli.get(outlet['address'])
        _p = []
        if outlet.get('linked_devs'):
            for dev in outlet['linked_devs']:
                if isinstance(outlet['linked_devs'][dev], list):
                    [_p.append(int(_)) for _ in outlet['linked_devs'][dev] if int(_) not in _p]
                elif int(outlet['linked_devs'][dev]) not in _p:
                    _p.append(int(outlet['linked_devs'][dev]))

            if isinstance(_p, int):
                outlet['is_on'] = {_p: this_dli.outlets[_p]}
            else:
                outlet['is_on'] = {port: this_dli.outlets[port] for port in _p}

        return outlet, _p

    def dli_close_all(self, dlis=None):
        '''Close Connection to any connected dli Web Power Switches

        Arguments:
            dlis {dict} -- dict of dli objects
        '''
        dlis = self._dli if not dlis else dlis
        for address in dlis:
            if dlis[address].dli:
                if getattr(dlis[address], 'rest'):
                    threading.Thread(target=dlis[address].dli.close).start()
                else:
                    threading.Thread(target=dlis[address].dli.session.close).start()

    def pwr_get_outlets(self, outlet_data: Dict[str, Any] = {}, upd_linked: bool = False, failures: Dict[str, Any] = {}) -> Dict[str, Any]:
        '''Get Details for Outlets defined in ConsolePi.yaml power section

        On Menu Launch this method is called in parallel (threaded) for each outlet
        On Refresh all outlets are passed to the method

        params: - All Optional
            outlet_data:dict, The outlets that need to be updated, if not provided will get all outlets defined in ConsolePi.yaml
            upd_linked:Bool, If True will update just the linked ports, False is for dli and will update
                all ports for the dli.
            failures:dict: when refreshing outlets pass in previous failures so they can be re-tried
        '''
        # re-attempt connection to failed power controllers on refresh
        log.debug(f"[PWR VRFY (pwr_get_outlets)] Processing {', '.join(outlet_data.keys())}")
        if not failures:
            failures = outlet_data.get('failures', {}) if outlet_data.get('failures') else self.data.get('failures', {})

        outlet_data = self.data.get('defined', {}) if not outlet_data else outlet_data
        if failures:
            outlet_data = {**outlet_data, **failures}
            failures = {}

        dli_power = self.data.get('dli_power', {})
        esp_power = self.data.get('esp_power', {})

        for k in outlet_data:
            outlet = outlet_data[k]
            _start = time.perf_counter()

            # -- // GPIO \\ --
            if outlet['type'].upper() == 'GPIO':
                if not is_rpi:
                    log.warning('GPIO Outlet Defined, GPIO Only Supported on RPi - ignored', show=True)
                    continue
                noff = True if 'noff' not in outlet else outlet['noff']
                GPIO.setup(outlet['address'], GPIO.OUT)
                outlet_data[k]['is_on'] = bool(GPIO.input(outlet['address'])) if noff \
                    else not bool(GPIO.input(outlet['address']))

            # -- // tasmota \\ --
            elif outlet['type'] == 'tasmota':
                response = self.do_tasmota_cmd(outlet['address'])
                outlet['is_on'] = response
                if response not in [0, 1, True, False]:
                    failures[k] = outlet_data[k]
                    failures[k]['error'] = f'[PWR-TASMOTA] {k}:{failures[k]["address"]} {response} - Removed'
                    log.warning(failures[k]['error'], show=True)

            # -- // esphome \\ --
            elif outlet['type'] == 'esphome':
                # TODO have do_esphome accept list, slice, or str for one or multiple relays
                relays = utils.listify(outlet.get('relays', k))  # if they have not specified the relay try name of outlet
                outlet['is_on'] = {}
                esp_ok = True
                for r in relays:
                    response = self.do_esphome_cmd(outlet['address'], r)
                    outlet['is_on'][r] = {'state': response, 'name': r}
                    if response not in [True, False]:
                        failures[k] = outlet_data[k]
                        failures[k]['error'] = f'[PWR-ESP] {k}:{r} ({failures[k]["address"]}) {response} - Removed'
                        log.warning(failures[k]['error'], show=True)
                        esp_ok = False
                        break

                # add multi-port esp_outlets to dli_menu, unless all outlets are linked anyway
                # if esp is 8 ports add it to dli regardless (dli are 8 and they get that treatment)
                if esp_ok and len(relays) > 1 or (esp_ok and len(relays) == 8):
                    no_linkage_relays = [r for r in relays if f"'{r}'" not in str(outlet_data[k]["linked_devs"])]
                    if no_linkage_relays:
                        esp_power[outlet_data[k]["address"]] = outlet_data[k]["is_on"]

            # -- // dli \\ --
            elif outlet['type'].lower() == 'dli':
                if TIMING:
                    dbg_line = '------------------------ // NOW PROCESSING {} \\\\ ------------------------'.format(k)
                    print('\n{}'.format('=' * len(dbg_line)))
                    print('{}\n{}\n{}'.format(dbg_line, outlet_data[k], '-' * len(dbg_line)))
                    print('{}'.format('=' * len(dbg_line)))

                # -- // VALIDATE CONFIG FILE DATA FOR DLI \\ --
                all_good = True  # initial value
                for _ in ['address', 'username', 'password']:
                    if not outlet.get(_):
                        all_good = False
                        failures[k] = outlet_data[k]
                        failures[k]['error'] = f'[PWR-DLI {k}] {_} missing from {failures[k]["address"]} ' \
                            'configuration - skipping'
                        log.error(f'[PWR-DLI {k}] {_} missing from {failures[k]["address"]} '
                                  'configuration - skipping', show=True)
                        break
                if not all_good:
                    continue

                (this_dli, _update) = self.load_dli(outlet['address'], outlet['username'], outlet['password'])
                if this_dli is None or this_dli.dli is None:
                    failures[k] = outlet_data[k]
                    failures[k]['error'] = '[PWR-DLI {}] {} Unreachable - Removed'.format(k, failures[k]['address'])
                    log.warning(f"[PWR-DLI {k}] {failures[k]['address']} Unreachable - Removed", show=True)
                else:
                    if TIMING:
                        xstart = time.perf_counter()
                        print('this_dli.outlets: {} {}'.format(this_dli.outlets, 'update' if _update else 'init'))
                        print(json.dumps(dli_power, indent=4, sort_keys=True))

                    # upd_linked is for faster update in power menu only refreshes data for linked ports vs entire dli
                    if upd_linked and self.data['dli_power'].get(outlet['address']):
                        if outlet.get('linked_devs'):
                            (outlet, _p) = self.update_linked_devs(outlet)
                            if k in outlet_data:
                                outlet_data[k]['is_on'] = this_dli[_p]
                            else:
                                log.error(f'[PWR GET_OUTLETS] {k} appears to be unreachable')

                            # TODO not actually using the error returned this turned into a hot mess
                            if isinstance(outlet['is_on'], dict) and not outlet['is_on']:
                                all_good = False
                            # update dli_power for the refreshed / linked ports
                            else:
                                for _ in outlet['is_on']:
                                    dli_power[outlet['address']][_] = outlet['is_on'][_]
                    else:
                        if _update:
                            dli_power[outlet['address']] = this_dli.get_dli_outlets()  # data may not be fresh trigger dli update

                            # handle error connecting to dli during refresh - when connect worked on menu launch
                            if not dli_power[outlet['address']]:
                                failures[k] = outlet_data[k]
                                failures[k]['error'] = f"[PWR-DLI] {k} {failures[k]['address']} Unreachable - Removed"
                                log.warning(f'[PWR-DLI {k}] {failures[k]["address"]} Unreachable - Removed',
                                            show=True)
                                continue
                        else:  # dli was just instantiated data is fresh no need to update
                            dli_power[outlet['address']] = this_dli.outlets

                        if outlet.get('linked_devs'):
                            (outlet, _p) = self.update_linked_devs(outlet)

                if TIMING:
                    print('[TIMING] this_dli.outlets: {}'.format(time.perf_counter() - xstart))  # type: ignore

            log.debug(f"{outlet['type'].lower()} {k} Updated. Elapsed Time(secs): {time.perf_counter() - _start}")
            # -- END for LOOP for k in outlet_data --

        # Move failed outlets from the keys that populate the menu to the 'failures' key
        # failures are displayed in the footer section of the menu, then re-tried on refresh
        for _dev in failures.copy():
            if outlet_data.get(_dev):
                del outlet_data[_dev]
            if self.data['defined'].get(_dev):
                del self.data['defined'][_dev]
            if failures[_dev]['address'] in dli_power:
                del dli_power[failures[_dev]['address']]
            self.data['failures'][_dev] = failures[_dev]

        # restore outlets that failed on menu launch but found reachable during refresh
        for _dev in outlet_data.copy():
            if _dev not in self.data['defined']:
                self.data['defined'][_dev] = outlet_data[_dev]
            if _dev in self.data['failures']:
                del self.data['failures'][_dev]

        self.data['dli_power'] = dli_power
        self.data['esp_power'] = esp_power

        log.debug(f"[PWR VRFY (pwr_get_outlets)] Done Processing {', '.join(outlet_data.keys())}")
        return self.data

    def pwr_toggle(self, pwr_type, address, desired_state=None, port=None, noff=True, noconfirm=False):
        '''Toggle Power On the specified port

        args:
            pwr_type: valid types = 'dli', 'tasmota', 'GPIO' (not case sensitive)
            address: for dli and tasmota: str - ip or fqdn
        kwargs:
            desired_state: bool The State True|False (True = ON) you want the outlet to be in
                if not provided the method will query the current state of the port and set desired_state to the inverse
            port: Only required for dli: can be type str | int | list.
                valid:
                    int: representing the dli outlet #
                    list: list of outlets(int) to perform operation on
                    str: 'all' ~ to perform operation on all outlets
            noff: Bool, default: True.  = normally off, only applies to GPIO based outlets.
                If an outlet is normally off (True) = the relay/outlet is off if no power is applied via GPIO
                Setting noff to False flips the ON/OFF evaluation so the menu will show the port is ON when no power is applied.

        returns:
            Bool representing resulting port state (True = ON)
        '''
        # --// REMOVE ONCE VERIFIED \\--
        # if isinstance(desired_state, str):  # menu should be passing in True/False no on off now. can remove once that's verified
        #     desired_state = False if desired_state.lower() == 'off' else True
        #     print('\ndev_note: pwr_toggle passed str not bool for desired_state check calling function {}'.format(desired_state))
        #     time.sleep(5)

        # -- // Toggle dli web power switch port \\ --
        if pwr_type.lower() == 'dli':
            if port is not None:
                return self._dli[address].toggle(port, toState=desired_state)

        # -- // Toggle GPIO port \\ --
        elif pwr_type.upper() == 'GPIO':
            gpio = address
            # get current state and determine inverse if toggle called with no desired_state specified
            if desired_state is None:
                cur_state = bool(GPIO.input(gpio)) if noff else not bool(GPIO.input(gpio))
                desired_state = not cur_state
            if desired_state:
                GPIO.output(gpio, int(noff))
            else:
                GPIO.output(gpio, int(not noff))
            return bool(GPIO.input(gpio)) if noff else not bool(GPIO.input(gpio))

        # -- // Toggle TASMOTA port \\ --
        elif pwr_type.lower() == 'tasmota':
            if desired_state is None:
                desired_state = not self.do_tasmota_cmd(address)
            return self.do_tasmota_cmd(address, desired_state)

        # -- // Toggle espHome port \\ --
        elif pwr_type.lower() == 'esphome':
            if desired_state is None:
                desired_state = not self.do_esphome_cmd(address, port)
            return self.do_esphome_cmd(address, port, desired_state)

        else:
            raise Exception('pwr_toggle: Invalid type ({}) or no name provided'.format(pwr_type))

    def pwr_cycle(self, pwr_type, address, port=None, noff=True):
        '''returns Bool True = Power Cycle success, False Not performed Outlet OFF

        TODO Check error handling if unreachable
        '''
        pwr_type = pwr_type.lower()
        # --// CYCLE DLI PORT \\--
        if pwr_type == 'dli':
            if port is not None:
                return self._dli[address].cycle(port)
            else:
                raise ConsolePiPowerException('pwr_cycle: port must be provided for outlet type dli')

        # --// CYCLE GPIO PORT \\--
        elif pwr_type == 'gpio':
            gpio = address
            # normally off states are normal 0:off, 1:on - if not normally off it's reversed 0:on 1:off
            cur_state = GPIO.input(gpio) if noff else not GPIO.input(gpio)
            if cur_state:
                GPIO.output(gpio, int(not noff))
                time.sleep(config.cycle_time)
                GPIO.output(gpio, int(noff))
                response = bool(GPIO.input(gpio))
                return response if noff else not response
            else:
                return False  # Cycle is not valid on ports that are already off

        # --// CYCLE TASMOTA PORT \\--
        elif pwr_type == 'tasmota':
            # response = self.do_tasmota_cmd(address)  # this logic is handled in the function now
            # if response:  # Only Cycle if outlet is currently ON
            return self.do_tasmota_cmd(address, 'cycle')

        # --// CYCLE ESPHOME PORT \\--
        elif pwr_type == 'esphome':
            return self.do_esphome_cmd(address, port, 'cycle')

    def pwr_rename(self, type, address, name=None, port=None):
        if name is None:
            try:
                name = input('New name for {} port: {} >> '.format(address, port))
            except KeyboardInterrupt:
                print('Rename Aborted!')
                return 'Rename Aborted'
        if type.lower() == 'dli':
            if port is not None:
                response = self._dli[address].rename(port, name)
                if response:
                    self.data['dli_power'][address][port]['name'] = name
            else:
                response = 'ERROR port must be provided for outlet type dli'
        elif type.lower() in ['gpio', 'tasmota', 'esphome']:
            print('rename of GPIO, tasmota, and espHome ports not yet implemented')
            print('They can be renamed manually by updating ConsolePi.yaml')
            response = 'rename of GPIO, tasmota, and espHome ports not yet implemented'
            # TODO get group name based on address, read json file into dict, change the name write it back
            #      and update dict
        else:
            raise ConsolePiPowerException('pwr_rename: Invalid type ({}) or no name provided'.format(type))

        return response

    def pwr_all(self, outlets=None, action='toggle', desired_state=None):
        '''
        Returns List of responses representing state of outlet after exec
            Valid response is Bool where True = ON
            Errors are returned in str format
        '''
        if action == 'toggle' and desired_state is None:
            return 'Error: desired final state must be provided'  # should never hit this

        if outlets is None:
            outlets = self.pwr_get_outlets()['defined']
        responses = []
        for grp in outlets:
            outlet = outlets[grp]
            # if no_all: true in config outlet is ignored during all off/on operations
            if outlet.get("no_all"):
                continue
            noff = True if 'noff' not in outlet else outlet['noff']
            if action == 'toggle':
                # skip any defined dlis that don't have any linked_outlets defined
                # if not outlet['type'] == 'dli' or outlet.get('linked_devs')):
                if outlet['type'] == 'dli':
                    if outlet.get('linked_devs'):
                        responses.append(
                            self.pwr_toggle(outlet['type'], outlet['address'], desired_state=desired_state, port=self.update_linked_devs(outlet)[1], noff=noff, noconfirm=True)
                        )
                elif outlet['type'] == 'esphome':
                    _relays = utils.listify(outlet.get('relays'))
                    for p in _relays:
                        responses.append(self.pwr_toggle(outlet['type'], outlet['address'], desired_state=desired_state,
                                         port=p, noff=noff, noconfirm=True))
                else:
                    responses.append(self.pwr_toggle(outlet['type'], outlet['address'], desired_state=desired_state,
                                     noff=noff, noconfirm=True))
            elif action == 'cycle':
                if outlet['type'] == 'dli':
                    if 'linked_ports' in outlet:
                        linked_ports = utils.listify(outlet['linked_ports'])
                        for p in linked_ports:
                            # Start a thread for each port run in parallel
                            # menu status for (linked) power menu is updated on load
                            threading.Thread(
                                target=self.pwr_cycle,
                                args=[outlet['type'], outlet['address']],
                                kwargs={'port': p, 'noff': noff},
                                name=f'cycle_{p}'
                            ).start()
                elif outlet['type'] == 'esphome':
                    relays = utils.listify(outlet.get('relays', []))
                    for p in relays:
                        # Start a thread for each port run in parallel
                        threading.Thread(
                            target=self.pwr_cycle,
                            args=[outlet['type'], outlet['address']],
                            kwargs={'port': p, 'noff': noff},
                            name=f'cycle_{p}'
                        ).start()
                else:
                    threading.Thread(
                        target=self.pwr_cycle,
                        args=[outlet['type'], outlet['address']],
                        kwargs={'noff': noff},
                        name='cycle_{}'.format(outlet['address'])
                    ).start()

        # Wait for all threads to complete
        while True:
            threads = 0
            for t in threading.enumerate():
                if 'cycle' in t.name or 'toggle_' in t.name:
                    threads += 1
            if threads == 0:
                break

        return responses
