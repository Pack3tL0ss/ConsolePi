#!/etc/ConsolePi/venv/bin/python3

import RPi.GPIO as GPIO
import json
from os import path
from time import sleep
import requests


power_file = '/etc/ConsolePi/power.json'


class Outlets:

    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

    def do_tasmota_cmd(self, address, command=None):
        url = 'http://' + address + '/cm'
        if command is not None:
            if command.lower() in ['on', 'off', 'toggle']:
                querystring = {"cmnd":"Power {}".format(command.upper())}
            else:
                raise KeyError
        else:
            querystring = {"cmnd":"Power"}
        
        headers = {
            'Cache-Control': "no-cache",
            'Connection': "keep-alive",
            'cache-control': "no-cache"
            }

        try:
            response = requests.request("GET", url, headers=headers, params=querystring, timeout=1)
            if response.status_code == 200:
                if json.loads(response.text)['POWER'] == 'ON':
                    out_state = 1
                elif json.loads(response.text)['POWER'] == 'OFF':
                    out_state = 0
                else:
                    out_state = 'invalid state returned {}'.format(response.text)
            else:
                out_state = '[{}] error returned {}'.format(response.status_code, response.text)
        except requests.exceptions.Timeout:
            out_state = 408
        except requests.exceptions.RequestException:
            out_state = 404

        return out_state

    def get_outlets(self):
        if path.isfile(power_file):
            with open (power_file, 'r') as _power_file:
                outlet_data = _power_file.read()
            outlet_data = json.loads(outlet_data)
        else:
            outlet_data = None

        if outlet_data is not None:
            for k in outlet_data:
                outlet = outlet_data[k]
                if outlet['type'].upper() == 'GPIO':
                    GPIO.setup(outlet['address'], GPIO.OUT)
                    outlet['is_on'] = GPIO.input(outlet['address'])
                elif outlet['type'] == 'tasmota':
                    response = self.do_tasmota_cmd(outlet['address'])
                    outlet['is_on'] = response

        return outlet_data

    def do_toggle(self, type, address, desired_state=None):
        gpio = address
        if desired_state is None:
            if type.upper() == 'GPIO':
                GPIO.output(gpio, 1) if not GPIO.input(gpio) else GPIO.output(gpio, 0)
            elif type == 'tasmota':
                response = self.do_tasmota_cmd(address, 'toggle')
        else:
            desired_state = desired_state.lower()
            if type == 'GPIO':
                GPIO.output(gpio, 0) if desired_state == 'off' else GPIO.output(gpio, 1)
            elif type == 'tasmota':
                response = self.do_tasmota_cmd(address, desired_state)

        response = GPIO.input(gpio) if type == 'GPIO' else response

        return response

    def get_state(self, type, address):
        if type.upper() == 'GPIO':
            GPIO.setup(gpio)
            response = GPIO.input(gpio)
        elif type.lower() == 'tasmota':
            response = self.do_tasmota_cmd(address)

        return response

if __name__ == '__main__':
    outlets = Outlets()
    print(json.dumps(outlets.get_outlets(), sort_keys=True, indent=4))