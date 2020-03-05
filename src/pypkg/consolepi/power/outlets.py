#!/etc/ConsolePi/venv/bin/python3

import json
import threading
import time

import requests

try:
    import RPi.GPIO as GPIO
    is_rpi = True
except RuntimeError:
    is_rpi = False

from halo import Halo

from consolepi.power import DLI

try:
    import better_exceptions
    better_exceptions.MAX_LENGTH = None
except ImportError:
    pass

TIMING = False
CYCLE_TIME = 3


class Outlets:

    def __init__(self, cpi):
        self.cpi = cpi
        self.log = cpi.config.log
        self.spin = Halo(spinner='dots')
        if is_rpi:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
        self._dli = {}

        # Some convenience Bools used by menu to determine what options to display
        self.dli_exists = True if 'dli' in cpi.config.outlet_types else False
        self.tasmota_exists = True if 'tasmota' in cpi.config.outlet_types else False
        self.esphome_exists = True if 'esphome' in cpi.config.outlet_types else False  # TODO Future
        self.gpio_exists = True if 'gpio' in cpi.config.outlet_types else False
        self.linked_exists = True if cpi.config.linked_exists else False
        if self.dli_exists or self.tasmota_exists or self.esphome_exists or self.gpio_exists:
            self.outlets_exists = True
        else:
            self.outlets_exists = False

        self.data = cpi.config.outlets
        # self.pwr_init_complete = False
        if cpi.config.power:
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
        def tasmota_req(*args, **kwargs):
            querystring = kwargs['querystring']
            try:
                response = requests.request("GET", url, headers=headers, params=querystring, timeout=3)
                if response.status_code == 200:
                    if json.loads(response.text)['POWER'] == 'ON':
                        _response = True
                    elif json.loads(response.text)['POWER'] == 'OFF':
                        _response = False
                    else:
                        _response = 'invalid state returned {}'.format(response.text)
                else:
                    _response = '[{}] error returned {}'.format(response.status_code, response.text)
            except requests.exceptions.Timeout:
                _response = 'Reqest Timed Out'
            except requests.exceptions.RequestException as e:
                _response = 'Exception Occured: {}'.format(e)
            return _response
        # -------- END SUB --------

        url = 'http://' + address + '/cm'
        headers = {
            'Cache-Control': "no-cache",
            'Connection': "keep-alive",
            'cache-control': "no-cache"
            }

        cycle = False
        if command is not None:
            if isinstance(command, bool):
                command = 'ON' if command else 'OFF'

            command = command.upper()
            if command in ['ON', 'OFF', 'TOGGLE']:
                querystring = {"cmnd": f"Power {command}"}
            elif command == 'CYCLE':  # Power off if cycle is command, powered back on below
                if tasmota_req(querystring={"cmnd": "Power"}):
                    querystring = {"cmnd": "Power OFF"}
                    cycle = True
                else:
                    return 'Cycle is only valid for ports that are Currently ON'
            else:
                raise KeyError
        else:  # if no command specified return the status of the port
            querystring = {"cmnd": "Power"}

        # -- // Send Request to TASMOTA \\ --
        r = tasmota_req(querystring=querystring)
        if cycle:
            if not r:
                time.sleep(CYCLE_TIME)
                r = tasmota_req(querystring={"cmnd": "Power ON"})
            else:
                return 'Unexpected response, port returned on state expected off'
        return r

    def load_dli(self, address, username, password):
        '''
        Returns instace of DLI class

        Response: tuple
            DLI-class-object, Bool: True if class was previously instantiated ~ needs update
                                    False indicating class was just instantiated ~ data is fresh
        '''
        if not self._dli.get(address):
            self._dli[address] = DLI(address, username, password, log=self.log)
            # --// Return Pass or fail based on reachability \\--
            if self._dli[address].reachable:
                return self._dli[address], False
            else:
                return None, None

        # --// DLI Already Loaded \\--
        else:
            return self._dli[address], True

    def pwr_start_update_threads(self, upd_linked=False, failures={}, t_name='init'):
        kwargs = {'upd_linked': upd_linked, 'failures': failures}
        outlet_data = self.data.get('defined')
        if not failures:
            if 'failures' in outlet_data:
                failures = outlet_data['failures']
        if failures:  # re-attempt connection to failed power controllers on refresh
            outlet_data = {**outlet_data, **failures}
            failures = {}

        # this shouldn't happen, but prevents spawning multiple updates for same outlet
        if outlet_data is not None:
            for k in outlet_data:
                found = False
                for t in threading.enumerate():
                    if t.name == f'{t_name}_pwr_{k}':
                        found = True
                        break
                if not found:
                    threading.Thread(target=self.pwr_get_outlets, args=[{k: outlet_data[k]}],
                                     kwargs=kwargs, name=t_name + '_pwr_' + k).start()

    def update_linked_devs(self, outlet):
        '''Update linked devs for dli outlets if they exist

        Params:
            dict -- the outlet dict to be updated

        Returns:
            tuple -- 0: dict: updated outlet dict or same dict if no linked_devs
                        1: list: list of all ports linked on this dli (used to initiate query against the dli)
        '''
        this_dli = self._dli.get(outlet['address'])
        if outlet.get('linked_devs'):
            _p = []
            for dev in outlet['linked_devs']:
                if isinstance(outlet['linked_devs'][dev], list):
                    [_p.append(int(_)) for _ in outlet['linked_devs'][dev]]
                else:
                    _p.append(int(outlet['linked_devs'][dev]))

            if isinstance(_p, int):
                outlet['is_on'] = {_p: this_dli.outlets[_p]}
            else:
                outlet['is_on'] = {_: self.data['dli_power'][outlet['address']][_] for _ in _p}

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

    def pwr_get_outlets(self, outlet_data={}, upd_linked=False, failures={}):
        '''Get Details for Outlets defined in power.json

        params: - All Optional
            outlet_data:dict, The outlets that need to be updated, if not provided will get all outlets defined in power.json
            upd_linked:Bool, If True will update just the linked ports, False is for dli and will update
                all ports for the dli.
            failures:dict: when refreshing outlets pass in previous failures so they can be re-tried
        '''
        config = self.cpi.config
        # re-attempt connection to failed power controllers on refresh
        failures = outlet_data.get('failures') if not failures else failures
        failures = self.data.get('failures') if not failures else failures
        outlet_data = self.data.get('defined') if not outlet_data else outlet_data
        if failures:
            outlet_data = {**outlet_data, **failures}
            failures = {}

        dli_power = self.data.get('dli_power', {})

        for k in outlet_data:
            outlet = outlet_data[k]
            _start = time.time()
            # -- // GPIO \\ --
            if outlet['type'].upper() == 'GPIO':
                if not is_rpi:
                    continue
                noff = True if 'noff' not in outlet else outlet['noff']  # default normally off to True if not provided
                GPIO.setup(outlet['address'], GPIO.OUT)  # pylint: disable=maybe-no-member
                outlet_data[k]['is_on'] = bool(GPIO.input(outlet['address'])) if noff \
                    else not bool(GPIO.input(outlet['address']))  # pylint: disable=maybe-no-member
            # -- // tasmota \\ --
            elif outlet['type'] == 'tasmota':
                response = self.do_tasmota_cmd(outlet['address'])
                outlet['is_on'] = response
                if response not in [0, 1, True, False]:
                    failures[k] = outlet_data[k]
                    failures[k]['error'] = f'[PWR-TASMOTA {k}:{failures[k]["address"]}] Returned Error - Removed'
                    config.log_and_show(f'[PWR-TASMOTA {k}:{failures[k]["address"]}] Returned Error - Removed')
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
                        config.log_and_show(f'[PWR-DLI {k}] {_} missing from {failures[k]["address"]} '
                                            'configuration - skipping')
                        break
                if not all_good:
                    continue

                (this_dli, _update) = self.load_dli(outlet['address'], outlet['username'], outlet['password'])
                if this_dli is None or this_dli.dli is None:
                    failures[k] = outlet_data[k]
                    failures[k]['error'] = '[PWR-DLI {}] {} Unreachable - Removed'.format(k, failures[k]['address'])
                    config.log_and_show(f"[PWR-DLI {k}] {failures[k]['address']} Unreachable - Removed")
                else:
                    if TIMING:
                        xstart = time.time()
                        print('this_dli.outlets: {} {}'.format(this_dli.outlets, 'update' if _update else 'init'))
                        print(json.dumps(dli_power, indent=4, sort_keys=True))

                    # upd_linked is for faster update in power menu only refreshes data for linked ports vs entire dli
                    if upd_linked and self.data['dli_power'].get(outlet['address']):
                        if outlet.get('linked_devs'):
                            (outlet, _p) = self.update_linked_devs(outlet)
                            if k in outlet_data:
                                outlet_data[k]['is_on'] = this_dli[_p]
                            else:
                                self.log.error('[PWR GET_OUTLETS] {} appears to be unreachable'.format(k))

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
                                failures[k]['error'] = '[PWR-DLI {}] {} Unreachable - Removed'.format(k, failures[k]['address'])
                                config.log_and_show(f'[PWR-DLI {k}] {failures[k]["address"]} Unreachable - Removed',
                                                    log=config.log.warning)
                                continue
                        else:  # dli was just instantiated data is fresh no need to update
                            dli_power[outlet['address']] = this_dli.outlets

                        if outlet.get('linked_devs'):
                            (outlet, _p) = self.update_linked_devs(outlet)

                if TIMING:
                    print('[TIMING] this_dli.outlets: {}'.format(time.time() - xstart))  # TIMING
            config.log.debug(f'dli {k} Updated. Elapsed Time(secs): {time.time() - _start}')
            # -- END for LOOP for k in outlet_data --

        # Move failed outlets from the keys that populate the menu to the 'failures' key
        # failures are displayed in the footer section of the menu, then re-tried on refresh
        for _dev in failures:
            if _dev in outlet_data:
                del outlet_data[_dev]
            if failures[_dev]['address'] in dli_power:
                del dli_power[failures[_dev]['address']]
        self.data['failures'] = failures
        self.data['dli_power'] = dli_power

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
        if isinstance(desired_state, str):  # menu should be passing in True/False no on off now. can remove once that's verified
            desired_state = False if desired_state.lower() == 'off' else True
            print('\ndev_note: pwr_toggle passed str not bool for desired_state check calling function {}'.format(desired_state))
            time.sleep(5)

        # -- // Toggle dli web power switch port \\ --
        if pwr_type.lower() == 'dli':
            if port is not None:
                response = self._dli[address].toggle(port, toState=desired_state)
            # else:
            #     raise Exception('pwr_toggle: port must be provided for outlet type dli')

        # -- // Toggle GPIO port \\ --
        elif pwr_type.upper() == 'GPIO':
            gpio = address
            # get current state and determine inverse if toggle called with no desired_state specified
            if desired_state is None:
                cur_state = bool(GPIO.input(gpio)) if noff else not bool(GPIO.input(gpio))  # pylint: disable=maybe-no-member
                desired_state = not cur_state
            if desired_state:
                GPIO.output(gpio, int(noff))  # pylint: disable=maybe-no-member
            else:
                GPIO.output(gpio, int(not noff))  # pylint: disable=maybe-no-member
            response = bool(GPIO.input(gpio)) if noff else not bool(GPIO.input(gpio))  # pylint: disable=maybe-no-member

        # -- // Toggle TASMOTA port \\ --
        elif pwr_type.lower() == 'tasmota':
            if desired_state is None:
                desired_state = not self.do_tasmota_cmd(address)
            response = self.do_tasmota_cmd(address, desired_state)

        else:
            raise Exception('pwr_toggle: Invalid type ({}) or no name provided'.format(pwr_type))

        return response

    def pwr_cycle(self, pwr_type, address, port=None, noff=True):
        '''
        returns Bool True = Power Cycle success, False Not performed Outlet OFF
            TODO Check error handling if unreachable
        '''
        pwr_type = pwr_type.lower()
        # --// CYCLE DLI PORT \\--
        if pwr_type == 'dli':
            if port is not None:
                response = self._dli[address].cycle(port)
            else:
                raise Exception('pwr_cycle: port must be provided for outlet type dli')

        # --// CYCLE GPIO PORT \\--
        elif pwr_type == 'gpio':
            # normally off states are normal 0:off 1:on - if not normally off it's reversed 0:on 1:off
            # pylint: disable=maybe-no-member
            gpio = address
            cur_state = GPIO.input(gpio) if noff else not GPIO.input(gpio)
            if cur_state:
                GPIO.output(gpio, int(not noff))
                time.sleep(CYCLE_TIME)
                GPIO.output(gpio, int(noff))
                response = bool(GPIO.input(gpio))
                response = response if noff else not response
            else:
                response = False  # Cycle is not valid on ports that are alredy off

        # --// CYCLE TASMOTA PORT \\--
        elif pwr_type == 'tasmota':
            response = self.do_tasmota_cmd(address)
            if response:  # Only Cycle if outlet is currently ON
                response = self.do_tasmota_cmd(address, 'cycle')

        return response

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
        elif (type.upper() == 'GPIO' or type.lower() == 'tasmota'):
            print('rename of GPIO and tasmota ports not yet implemented')
            print('They can be renamed manually by updating power.json')
            response = 'rename of GPIO and tasmota ports not yet implemented'
            # TODO get group name based on address, read json file into dict, change the name write it back
            #      and update dict
        else:
            raise Exception('pwr_rename: Invalid type ({}) or no name provided'.format(type))

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
            noff = True if 'noff' not in outlet else outlet['noff']
            if action == 'toggle':
                # skip any defined dlis that don't have any linked_outlets defined
                # if not outlet['type'] == 'dli' or outlet.get('linked_devs')):
                if outlet.get('linked_devs'):
                    responses.append(self.pwr_toggle(outlet['type'], outlet['address'], desired_state=desired_state,
                                     port=self.update_linked_devs(outlet)[1] if outlet['type'] == 'dli' else None,  # NoQA
                                     noff=noff, noconfirm=True))
            elif action == 'cycle':
                if outlet['type'] != 'dli':
                    threading.Thread(
                            target=self.pwr_cycle,
                            args=[outlet['type'], outlet['address']],
                            kwargs={'noff': noff},
                            name='cycle_{}'.format(outlet['address'])
                        ).start()
                elif 'linked_ports' in outlet:
                    if isinstance(outlet['linked_ports'], int):
                        linked_ports = [outlet['linked_ports']]
                    else:
                        linked_ports = outlet['linked_ports']
                    for p in linked_ports:
                        # Start a thread for each port run in parallel
                        # menu status for (linked) power menu is updated on load
                        threading.Thread(
                                target=self.pwr_cycle,
                                args=[outlet['type'], outlet['address']],
                                kwargs={'port': p, 'noff': noff},
                                name='cycle_{}'.format(p)
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
