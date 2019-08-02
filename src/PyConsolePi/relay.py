#!/etc/ConsolePi/venv/bin/python3

import RPi.GPIO as GPIO
import json
from os import path
from time import sleep


relay_file = '/etc/ConsolePi/relay.json'


class Relays:

    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        self.relay_data = self.get_relays()


    def get_relays(self):
        if path.isfile(relay_file):
            with open (relay_file, 'r') as _relay_file:
                relay_data = _relay_file.read()
            relay_data = json.loads(relay_data)
        else:
            relay_data = None

        if relay_data is not None:
            for k in relay_data:
                GPIO.setup(relay_data[k]['GPIO'], GPIO.OUT)
                relay_data[k]['is_on'] = GPIO.input(relay_data[k]['GPIO'])

        return relay_data

    def do_toggle(self, gpio, desired_state=None):
        if desired_state is None:
            GPIO.output(gpio, 1) if not GPIO.input(gpio) else GPIO.output(gpio, 0)
        else:
            desired_state = desired_state.lower()
            GPIO.output(gpio, 0) if desired_state == 'off' else GPIO.output(gpio, 1)

        return GPIO.input(gpio)

    def get_state(self, gpio):
        GPIO.setup(gpio)
        return GPIO.input(gpio)

if __name__ == '__main__':
    relays = Relays()
    print(json.dumps(relays.relay_data, sort_keys=True, indent=4))