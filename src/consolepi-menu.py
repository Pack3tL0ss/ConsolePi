#!/etc/ConsolePi/venv/bin/python

import os
# os.chdir('/etc/ConsolePi/cloud/gdrive')
# Import the necessary packages
import logging
import sys
import json
import socket
import subprocess
import shlex
import serial.tools.list_ports
from collections import OrderedDict as od

# sys.path.insert(0, '../cloud/gdrive')
# print(sys.path)
# from include.utils import get_config
config_file = '/etc/ConsolePi/ConsolePi.conf'
log_file = '/var/log/ConsolePi/cloud.log'
local_cloud_file = '/etc/ConsolePi/cloud.data'


# Get Variables from Config
def get_config(var):
    with open(config_file, 'r') as cfg:
        var_out = None
        for line in cfg:
            if var in line:
                var_out = line.replace('{0}='.format(var), '')
                var_out = var_out.replace('"'.format(var), '', 1)
                var_out = var_out.split('"')
                var_out = var_out[0]
                break

    if var_out == 'true' or var_out == 'false':
        var_out = True if var_out == 'true' else False

    return var_out


# -- GLOBALS --
DEBUG = get_config('debug')
CLOUD_SVC = get_config('cloud_svc')
TIMEOUT = 2

# Logging
LOG_FILE = log_file
log = logging.getLogger(__name__)
log.setLevel(logging.INFO if not DEBUG else logging.DEBUG)
handler = logging.FileHandler(LOG_FILE)
handler.setLevel(logging.INFO if not DEBUG else logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)


class ConsolePiMenu:

    def __init__(self, DEBUG):
        self.baud = 9600
        self.data_bits = 8
        self.parity = 'n'
        self.parity_pretty = {'o': 'Odd', 'e': 'Even', 'n': 'No'}
        self.flow = 'n'
        self.flow_pretty = {'x': 'Xon/Xoff', 'h': 'RTS/CTS', 'n': 'No'}
        self.data = {'local': self.get_local(), 'remote': self.get_remote()}
        self.DEBUG = DEBUG
        self.menu_actions = {
            'main_menu': self.main_menu,
            'c': self.con_menu,
            'h': self.picocom_help,
            'x': self.exit
        }

    # check remote ConsolePi is reachable
    def check_reachable(self, ip, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        try:
            sock.connect((ip, port))
            reachable = True
        except (socket.error, TimeoutError):
            # print('ERROR: %s is not reachable' % hostname)
            reachable = False
        sock.close()
        return reachable

    def get_local(self):
        print('Detecting Locally Attached Serial Adapters')
        this = serial.tools.list_ports.grep('.*ttyUSB[0-9]*', include_links=True)
        tty_list = {}
        tty_alias_list = {}
        for x in this:
            _device_path = x.device_path.split('/')
            if x.device.replace('/dev/', '') != _device_path[len(_device_path)-1]:
                tty_alias_list[x.device_path] = x.device
            else:
                tty_list[x.device_path] = x.device

        final_tty_list = []
        for k in tty_list:
            if k in tty_alias_list:
                final_tty_list.append(tty_alias_list[k])
            else:
                final_tty_list.append(tty_list[k])

        # get telnet port deffinitions from ser2net.conf
        # and build adapters dict
        serial_list = []
        if os.path.isfile('/etc/ser2net.conf'):
            for tty_dev in final_tty_list:
                with open('/etc/ser2net.conf', 'r') as cfg:
                    for line in cfg:
                        if tty_dev in line:
                            tty_port = line.split(':')
                            tty_port = tty_port[0]
                            log.info('get_serial_ports: found {} {}'.format(tty_dev, tty_port))
                            break
                        else:
                            tty_port = 7000
                serial_list.append({'dev': tty_dev, 'port': tty_port})
                if tty_port == 7000:
                    log.error('No ser2net.conf deffinition found for {}'.format(tty_dev))
                    print('No ser2net.conf deffinition found for {}'.format(tty_dev))
        else:
            log.error('No ser2net.conf file found unable to extract port deffinitions')
            print('No ser2net.conf file found unable to extract port deffinitions')

        return serial_list

    def get_remote(self):
        print('Looking for Remote ConsolePis with attached Serial Adapters')
        data = {}
        if os.path.isfile(local_cloud_file):
            with open(local_cloud_file, mode='r') as cloud_file:
                data = json.load(cloud_file)
        else:
            log.error('Unable to populate remote ConsolePis - file {0} not found'.format(local_cloud_file))

        # Add remote commands to remote_consoles dict for each adapter
        for remotepi in data:
            this = data[remotepi]
            print('  {} Found...  Checking reachability'.format(remotepi))
            for _iface in this['interfaces']:
                _ip = this['interfaces'][_iface]
                if self.check_reachable(_ip, 22):
                    this['rem_ip'] = _ip
                    for adapter in this['adapters']:
                        _dev = adapter['dev']
                        adapter['rem_cmd'] = shlex.split('ssh -t {0}@{1} "picocom {2} -b{3} -f{4} -d{5} -p{6}"'.format(
                            this['user'], _ip, _dev, self.baud, self.flow, self.data_bits, self.parity))
                    break  # Stop Looping through interfaces we found a reachable one
        return data

    # =======================
    #     MENUS FUNCTIONS
    # =======================

    def menu_formatting(self, section, text=None):
        if section == 'header':
            if not self.DEBUG:
                os.system('clear')
            print('=' * 45)
            a = 45 - len(text)
            b = int(a/2 - 2)
            if text is not None:
                if isinstance(text, list):
                    for t in text:
                        print(' {0} {1} {0}'.format('-' * b, t))
                else:
                    print(' {0} {1} {0}'.format('-' * b, text))
            print('=' * 45 + '\n')
        elif section == 'footer':
            print('')
            if text is not None:
                if isinstance(text, list):
                    for t in text:
                        print(t)
                else:
                    print(text)
            print('x. exit\n')
            print('=' * 45)

    def picocom_help(self):
        print('##################### picocom Command Sequences ########################\n')
        print(' This program will launch serial session via picocom')
        print(' This is a list of the most common command sequences in picocom')
        print(' To use them press and hold ctrl then press and release each character\n')
        print('   ctrl+ a - x Exit session - reset the port')
        print('   ctrl+ a - q Exit session - without resetting the port')
        print('   ctrl+ a - u increase baud')
        print('   ctrl+ a - d decrease baud')
        print('   ctrl+ a - f cycle through flow control options')
        print('   ctrl+ a - y cycle through parity options')
        print('   ctrl+ a - b cycle through data bits')
        print('   ctrl+ a - v Show configured port options')
        print('   ctrl+ a - c toggle local echo')
        print('\n########################################################################\n')
        input('Press Enter to Continue')

    def main_menu(self):
        loc = self.data['local']
        rem = self.data['remote']
        item = 1
        if not self.DEBUG:
            os.system('clear')
        self.menu_formatting('header', text=' ConsolePi Serial Menu ')
        print('   Connect to Local Devices')
        print('   ' + '-' * 24)

        # Build menu items for each locally connected serial adapter
        for _dev in loc:
            this_dev = _dev['dev']
            print('{0}. Connect to {1}'.format(item, this_dev.replace('/dev/', '')))

            # >> Future Store serial port connections settings by host/adapter locally so they are persistent
            _cmd = 'picocom {0} -b{1} -f{2} -d{3} -p{4}'.format(this_dev, self.baud, self.flow, self.data_bits, self.parity)
            self.menu_actions[str(item)] = {'cmd': _cmd}
            item += 1

        # Build menu items for each serial adapter found on remote ConsolePis
        for host in rem:
            header = '   [Remote] {} @ {}'.format(host, rem[host]['rem_ip'])
            print('\n' + header + '\n   ' + '-' * (len(header) - 3))
            for _dev in rem[host]['adapters']:
                print('{0}. Connect to {1}'.format(item, _dev['dev'].replace('/dev/', '')))
                # self.menu_actions[str(item)] = {'cmd': _dev['rem_cmd']}
                _cmd = 'ssh -t {0}@{1} "picocom {2} -b{3} -f{4} -d{5} -p{6}"'.format(
                            rem[host]['user'], rem[host]['rem_ip'], _dev['dev'], self.baud, self.flow, self.data_bits, self.parity)
                self.menu_actions[str(item)] = {'cmd': _cmd}
                item += 1

        text = ['c. Change Serial Settings [{0} {1}{2}1 flow={3}] '.format(
            self.baud, self.data_bits, self.parity.upper(), self.flow_pretty[self.flow]), 'h. Display picocom help']
        self.menu_formatting('footer', text=text)
        choice = input(" >>  ")
        self.exec_menu(choice)

        return

    # Execute menu
    def exec_menu(self, choice, actions=None, calling_menu='main_menu'):
        menu_actions = self.menu_actions if actions is None else actions
        if not self.DEBUG:
            os.system('clear')
        ch = choice.lower()
        if ch == '':
            self.menu_actions[calling_menu]()
        else:
            try:
                if isinstance(menu_actions[ch], dict):
                    if 'cmd' in menu_actions[ch]:
                        c = shlex.split(menu_actions[ch]['cmd'])
                        subprocess.run(c)
                else:
                    menu_actions[ch]()
            except KeyError:
                print("Invalid selection, please try again.\n")
                menu_actions[calling_menu]()
        return

    # Connection SubMenu
    def con_menu(self):
        menu_actions = {
            'main_menu': self.main_menu,
            'con_menu': self.con_menu,
            '1': self.baud_menu,
            '2': self.data_bits_menu,
            '3': self.parity_menu,
            '4': self.flow_menu,
            'b': self.main_menu,
            'x': self.exit
        }
        self.menu_formatting('header', text=' Connection Settings Menu ')
        print('1. Baud [{}]'.format(self.baud))
        print('2. Data Bits [{}]'.format(self.data_bits))
        print('3. Parity [{}]'.format(self.parity_pretty[self.parity]))
        print('4. Flow [{}]'.format(self.flow_pretty[self.flow]))
        text = 'b. Back'
        self.menu_formatting('footer', text=text)
        choice = input(" >>  ")
        self.exec_menu(choice, actions=menu_actions, calling_menu='con_menu')
        return

    # Baud Menu
    def baud_menu(self):
        menu_actions = od([
            ('main_menu', self.main_menu),
            ('con_menu', self.con_menu),
            ('baud_menu', self.baud_menu),
            ('1', 300),
            ('2', 1200),
            ('3', 9600),
            ('4', 19200),
            ('5', 57600),
            ('6', 115200),
            ('c', 'custom'),
            ('b', self.con_menu),
            ('x', self.exit)
        ])

        self.menu_formatting('header', text=' Select Desired Baud Rate ')

        for key in menu_actions:
            if not callable(menu_actions[key]):
                print('{0}. {1}'.format(key, menu_actions[key]))

        text = 'b. Back'
        self.menu_formatting('footer', text=text)
        choice = input(" Baud >>  ")
        ch = choice.lower()
        try:
            if type(menu_actions[ch]) == int:
                self.baud = menu_actions[ch]
                menu_actions['con_menu']()
            elif ch == 'c':
                self.baud = input(' Enter Desired Baud Rate >>  ')
                menu_actions['con_menu']()
            else:
                menu_actions[ch]()
        except KeyError:
            print("\n!!! Invalid selection, please try again.\n")
            menu_actions['baud_menu']()
        return

    # Data Bits Menu
    def data_bits_menu(self):
        valid = False
        while not valid:
            self.menu_formatting('header', text=' Enter Desired Data Bits ')
            print('Default 8, Current {}, Valid range 5-8'.format(self.data_bits))
            self.menu_formatting('footer')
            choice = input(' Data Bits >>  ')
            try:
                if choice.lower() == 'x':
                    self.exit()
                elif int(choice) >= 5 and int(choice) <= 8:
                    self.data_bits = choice
                    valid = True
                else:
                    print("\n!!! Invalid selection, please try again.\n")
            except ValueError:
                print("\n!! Invalid selection, please try again.\n")
        self.con_menu()
        return

    def parity_menu(self):
        self.menu_formatting('header', text=' Select Desired Parity ')
        print('Default No Parity\n')
        print('1. None')
        print('2. Odd')
        print('3. Even')
        text = 'b. Back'
        self.menu_formatting('footer', text=text)
        valid = False
        while not valid:
            valid = True
            choice = input(' Parity >>  ')
            choice = choice.lower()
            if choice == '1':
                self.parity = 'n'
            elif choice == '2':
                self.parity = 'o'
            elif choice == '3':
                self.parity = 'e'
            elif choice == 'b':
                pass
            elif choice == 'x':
                self.exit()
            else:
                valid = False
                print('\n!!! Invalid selection, please try again.\n')

            if valid:
                self.con_menu()
        return

    def flow_menu(self):
        def print_menu():
            self.menu_formatting('header', text=' Select Desired Parity ')
            print('Default No Flow\n')
            print('1. No Flow Control (default)')
            print('2. Xon/Xoff (software)')
            print('3. RTS/CTS (hardware)')
            text = 'b. Back'
            self.menu_formatting('footer', text=text)
        print_menu()
        valid = False
        while not valid:
            valid = True
            choice = input(' Flow >>  ')
            choice = choice.lower()
            try:
                if choice == '1':
                    self.flow = 'n'
                elif choice == '2':
                    self.flow = 'x'
                elif choice == '3':
                    self.flow = 'h'
                elif choice.lower() == 'b':
                    pass
                elif choice == 'x':
                    self.exit()
                else:
                    valid = False
                    print("\n!!! Invalid selection, please try again.\n")
                    print_menu()
            except Exception as e:
                valid = False
                print('\n[{}]\n!!! Invalid selection, please try again.\n'.format(e))
                print_menu()
            if valid:
                self.con_menu()
        return

    # Back to main menu
    def back(self):
        self.menu_actions['main_menu']()

    # Exit program
    def exit(self):
        sys.exit(0)

# =======================
#      MAIN PROGRAM
# =======================


# Main Program
if __name__ == "__main__":
    # Launch main menu
    menu = ConsolePiMenu(DEBUG)
    while True:
        menu.main_menu()
