#!/etc/ConsolePi/venv/bin/python3

import json
import time
from os import path

import requests
import RPi.GPIO as GPIO
from consolepi.dlirest import DLI

TIMING = False
CYCLE_TIME = 3

class Outlets:

    def __init__(self, power_file='/etc/ConsolePi/power.json', log=None):
        # pylint: disable=maybe-no-member
        self.power_file = power_file
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        self._dli = {}
        self.outlet_data = {}



    def do_tasmota_cmd(self, address, command=None):
        url = 'http://' + address + '/cm'
        headers = {
            'Cache-Control': "no-cache",
            'Connection': "keep-alive",
            'cache-control': "no-cache"
            }
        
        if command is not None:
            command = command.upper()
            if command in ['ON', 'OFF', 'TOGGLE']:
                querystring = {"cmnd":"Power {}".format(command)}
            elif command == 'CYCLE':
                cycle = True
            else:
                raise KeyError
        else:
            querystring = {"cmnd":"Power"}  # get status
        
        def tasmota_req(*args, **kwargs):
            try:
                response = requests.request("GET", url, headers=headers, params=querystring, timeout=1)
                if response.status_code == 200:
                    if json.loads(response.text)['POWER'] == 'ON':
                        out_state = True
                    elif json.loads(response.text)['POWER'] == 'OFF':
                        out_state = False
                    else:
                        out_state = 'invalid state returned {}'.format(response.text)
                else:
                    out_state = '[{}] error returned {}'.format(response.status_code, response.text)
            except requests.exceptions.Timeout:
                out_state = 408
            except requests.exceptions.RequestException:
                out_state = 404
            return out_state

        r = tasmota_req()
        if cycle:
            time.sleep(CYCLE_TIME)
            if not r:
                r = tasmota_req()
            else:
                print('Unexpected response, port returned on state expected off')
                return 404
        return r

    def load_dli(self, address, username, password):
        '''
        Returns instace of DLI class if class has not been instantiated for the provided 
        dli web power switch.  returns an existing instance if it's already been instantiated.
        '''
        if address not in self._dli or not self._dli[address]:
            print('[DLI] Getting Outlets {}'.format(address))
            self._dli[address] = DLI(address, username, password)
            return self._dli[address], False
        else:
            return self._dli[address], True

    def get_outlets(self, upd_linked=False):
        '''
        Get Outlet details
        '''
        if not self.outlet_data:
            if path.isfile(self.power_file):
                with open (self.power_file, 'r') as _power_file:
                    outlet_data = _power_file.read()
                outlet_data = json.loads(outlet_data)
            else:
                outlet_data = None
                return
        else:
            outlet_data = self.outlet_data['linked'] if 'linked' in self.outlet_data else None
        
        failures = {}
        if outlet_data is not None:
            dli_power = {} if 'dli_power' not in self.outlet_data else self.outlet_data['dli_power']
            for k in outlet_data:
                outlet = outlet_data[k]
                if outlet['type'].upper() == 'GPIO':
                    noff = outlet['noff']
                    GPIO.setup(outlet['address'], GPIO.OUT)  # pylint: disable=maybe-no-member
                    outlet['is_on'] = bool(GPIO.input(outlet['address'])) if noff else not bool(GPIO.input(outlet['address'])) # pylint: disable=maybe-no-member
                elif outlet['type'] == 'tasmota':
                    response = self.do_tasmota_cmd(outlet['address'])
                    outlet['is_on'] = response
                elif outlet['type'].lower() == 'dli':
                    if TIMING:
                        dbg_line = '------------------------ // NOW PROCESSING {} \\\\ ------------------------'.format(k)
                        print('\n{}'.format('=' * len(dbg_line)))
                        print('{}\n{}\n{}'.format(dbg_line, outlet_data[k], '-' * len(dbg_line)))
                        print('{}'.format('=' * len(dbg_line)))
                    all_good = True
                    for _ in ['address', 'username', 'password']:
                        if _ not in outlet or outlet[_] is None:
                            all_good = False
                            failures[k] = outlet_data[k]
                            failures[k]['error'] = '[PWR-DLI {}] {} missing from {} configuration - skipping'.format(k, _, failures[k]['address']) 
                            # Log here, delete item from dict? TODO
                            break
                    if all_good:
                        (this_dli, _update) = self.load_dli(outlet['address'], outlet['username'], outlet['password'])
                        if this_dli.dli is None:
                            failures[k] = outlet_data[k]
                            failures[k]['error'] = '[PWR-DLI {}] {} Unreachable - Removed'.format(k, failures[k]['address']) 
                            # failures[k] = outlet
                        else:
                            if TIMING:
                                xstart = time.time() # TIMING
                                print('this_dli.outlets: {} {}'.format(this_dli.outlets, 'update' if _update else 'init'))
                                print(json.dumps(dli_power, indent=4, sort_keys=True))
                            if _update:
                                if not upd_linked:
                                    dli_power[outlet['address']] = this_dli.get_dli_outlets()
                                    if 'linked_ports' in outlet and outlet['linked_ports'] is not None:
                                        _p = outlet['linked_ports']
                                        if isinstance(_p, int):
                                            outlet['is_on'] = {_p: this_dli.outlets[_p]}
                                        else:
                                            outlet['is_on'] = {}
                                            for _ in _p:
                                                outlet['is_on'][_] = dli_power[outlet['address']][_]
                                else:
                                    if 'linked_ports' in outlet and outlet['linked_ports'] is not None:
                                        _p = outlet['linked_ports']
                                        outlet['is_on'] = this_dli[_p]
                                        for _ in outlet['is_on']:
                                            dli_power[outlet['address']][_] = outlet['is_on'][_]
                            else:
                                dli_power[outlet['address']] = this_dli.outlets
                                if 'linked_ports' in outlet and outlet['linked_ports'] is not None:
                                    _p = outlet['linked_ports']
                                    if isinstance(_p, int):
                                        outlet['is_on'] = {_p: this_dli.outlets[_p]}
                                    else:
                                        outlet['is_on'] = {}
                                        for _ in _p:
                                            outlet['is_on'][_] = dli_power[outlet['address']][_]
                            if TIMING:
                                print('[TIMING] this_dli.outlets: {}'.format(time.time() - xstart)) # TIMING

        for _dev in failures:
            print(failures[_dev]['error'])
            del outlet_data[_dev]
        self.outlet_data = {
            'linked': outlet_data,
            'failures': failures,
            'dli_power': dli_power
            }
        return self.outlet_data

    def pwr_toggle(self, pwr_type, address, desired_state=None, port=None, noff=True):   # TODO refactor to pwr_toggle 
        def confirm(address=address, port=port, pwr_type=pwr_type):
            while True:
                choice = input('Please Confirm: Power \033[1;31mOFF\033[0m {} outlet {}{}? (y/n)>> '.format(
                    pwr_type, address, '' if port is None else ' Port: ' + str(port)))
                ch = choice.lower()
                if ch in ['y', 'yes', 'n', 'no']:
                    if ch in ['n', 'no']:
                        return 'Toggle \033[1;31mOFF\033[0m Aborted by user'
                    else:
                        break
                else:
                    print('Invalid Response: {}'.format(choice))
        if desired_state is not None and not desired_state:
            confirm()
        if pwr_type.lower() == 'dli':
            if port is not None:
                response = self._dli[address].toggle(port, toState=desired_state)
            else:
                raise Exception('pwr_toggle: port must be provided for outlet type dli')
        elif pwr_type.upper() == 'GPIO':
            gpio = address
            if desired_state is None:
                cur_state = bool(GPIO.input(gpio)) if noff else not bool(GPIO.input(gpio)) # pylint: disable=maybe-no-member
                if cur_state:   # if port is on prompt for confirmation prior to power off
                    confirm()
                GPIO.output(gpio, int(noff)) if not cur_state else GPIO.output(gpio, int(not noff))  # pylint: disable=maybe-no-member
            else:
                desired_state = desired_state.lower()
                GPIO.output(gpio, int(not noff)) if desired_state == 'off' else GPIO.output(gpio, int(noff)) # pylint: disable=maybe-no-member
            response = bool(GPIO.input(gpio)) if noff else not bool(GPIO.input(gpio)) # pylint: disable=maybe-no-member
        elif pwr_type.lower() == 'tasmota':
            # TODO power off confirm for tasmota
            if desired_state is None:
                response = self.do_tasmota_cmd(address, 'toggle')
            else:
                desired_state = desired_state.lower()
                response = self.do_tasmota_cmd(address, desired_state)
        else:
            raise Exception('pwr_toggle: Invalid type ({}) or no name provided'.format(pwr_type))
        # print('pwr_toggle response: {}'.format(response)) # Remove Debug Line
        return response

    def pwr_cycle(self, pwr_type, address, port=None, noff=True):
        pwr_type = pwr_type.lower()
        if pwr_type == 'dli':
            if port is not None:
                response = self._dli[address].cycle(port)
            else:
                raise Exception('pwr_cycle: port must be provided for outlet type dli')
        elif pwr_type == 'gpio':
            # normally off states are normal 0:off 1:on - if not normally off it's reversed 0:on 1:off
            # pylint: disable=maybe-no-member
            gpio = address
            cur_state = GPIO.input(gpio) if noff else not GPIO.input(gpio)
            if cur_state:
                GPIO.output(gpio, int(not noff))
                time.sleep(CYCLE_TIME)
                GPIO.output(gpio, int(noff))
                response = (bool(GPIO.input(gpio)))
                response = not response if noff else response
            else:
                response = False
        elif pwr_type == 'tasmota':
            response = self.do_tasmota_cmd(address, 'cycle')
        # print('pwr_cycle response: {}'.format(response)) # Remove Debug Line
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
                    self.outlet_data['dli_power'][address][port]['name'] = name
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
        # print('pwr_rename response: {}'.format(response)) # Remove Debug Line
        return response

    # Does not appear to be used can prob remove
    def get_state(self, type, address, port=None):
        if type.upper() == 'GPIO':
            GPIO.setup(address)  # pylint: disable=maybe-no-member
            response = GPIO.input(address)  # pylint: disable=maybe-no-member
        elif type.lower() == 'tasmota':
            response = self.do_tasmota_cmd(address)
        elif type.lower() == 'dli':
            if port is not None:
                response = self._dli[address].state(port)
            else:
                response = 'ERROR no port provided for dli port'

        return response

if __name__ == '__main__':
    pwr = Outlets('/etc/ConsolePi/power.json')
    outlets = pwr.get_outlets()
    print(json.dumps(outlets, indent=4, sort_keys=True))
    upd = pwr.get_outlets(upd_linked=True)
    print(json.dumps(upd, indent=4, sort_keys=True))
