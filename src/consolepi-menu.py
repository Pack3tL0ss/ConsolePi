#!/etc/ConsolePi/venv/bin/python

import os
import json
import socket
import subprocess
import shlex
import serial.tools.list_ports
from collections import OrderedDict as od

# get ConsolePi imports
from consolepi.common import get_config
from consolepi.common import get_if_ips
from consolepi.common import update_local_cloud_file
from consolepi.common import ConsolePi_Log
from consolepi.gdrive import GoogleDrive

# -- GLOBALS --
DEBUG = get_config('debug')
CLOUD_SVC = get_config('cloud_svc').lower()
LOG_FILE = '/var/log/ConsolePi/cloud.log'
LOCAL_CLOUD_FILE = '/etc/ConsolePi/cloud.data'
TIMEOUT = 2


class ConsolePiMenu:

    def __init__(self):
        cpi_log = ConsolePi_Log(debug=DEBUG, log_file=LOG_FILE)
        self.log = cpi_log.log
        self.plog = cpi_log.log_print
        self.go = True
        self.baud = 9600
        self.data_bits = 8
        self.parity = 'n'
        self.parity_pretty = {'o': 'Odd', 'e': 'Even', 'n': 'No'}
        self.flow = 'n'
        self.flow_pretty = {'x': 'Xon/Xoff', 'h': 'RTS/CTS', 'n': 'No'}
        self.if_ips = get_if_ips(self.log)
        self.data = {'local': self.get_local(), 'remote': self.get_remote()}
        self.DEBUG = DEBUG
        self.hostname = socket.gethostname()
        self.menu_actions = {
            'main_menu': self.main_menu,
            'c': self.con_menu,
            'h': self.picocom_help,
            'r': self.refresh,
            'x': self.exit
        }
        if CLOUD_SVC == 'gdrive':
            self.cloud = GoogleDrive(self.log)

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
        log = self.log
        plog = self.plog
        plog('Detecting Locally Attached Serial Adapters')
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
                            log.info('get_local: found dev: {} TELNET port: {}'.format(tty_dev, tty_port))
                            break
                        else:
                            tty_port = 7000  # this is error - placeholder value Telnet port is not currently used
                serial_list.append({'dev': tty_dev, 'port': tty_port})
                if tty_port == 7000:
                    log.error('No ser2net.conf deffinition found for {}'.format(tty_dev))
                    print('No ser2net.conf deffinition found for {}'.format(tty_dev))
        else:
            log.error('No ser2net.conf file found unable to extract port deffinitions')
            print('No ser2net.conf file found unable to extract port deffinitions')

        return serial_list

    # get remote consoles from local cache refresh function will check/update cloud file and update local cache
    def get_remote(self, data=None):
        log = self.log
        self.plog('Fetching Remote ConsolePis with attached Serial Adapters from local cache')
        if data is None:
            data = {}
            if os.path.isfile(LOCAL_CLOUD_FILE):
                with open(LOCAL_CLOUD_FILE, mode='r') as cloud_file:
                    data = json.load(cloud_file)
            else:
                log.error('Unable to populate remote ConsolePis - file {0} not found'.format(LOCAL_CLOUD_FILE))

        # Add remote commands to remote_consoles dict for each adapter
        for remotepi in data:
            this = data[remotepi]
            print('  {} Found...  Checking reachability'.format(remotepi))
            for _iface in this['interfaces']:
                _ip = this['interfaces'][_iface]
                if _ip not in self.if_ips.values():
                    if self.check_reachable(_ip, 22):
                        this['rem_ip'] = _ip
                        log.info('get_remote: Found {0}, reachable via {1}'.format(remotepi, _ip))
                        for adapter in this['adapters']:
                            _dev = adapter['dev']
                            adapter['rem_cmd'] = shlex.split('ssh -t {0}@{1} "picocom {2} -b{3} -f{4} -d{5} -p{6}"'.format(
                                this['user'], _ip, _dev, self.baud, self.flow, self.data_bits, self.parity))
                        break  # Stop Looping through interfaces we found a reachable one
                    else:
                        this['rem_ip'] = None

        return data

    # Update ConsolePi.csv on Google Drive and pull any data for other ConsolePis
    def refresh(self):
        print('Updating to/from Cloud... Standby')
        # Update Local Adapters
        self.data['local'] = self.get_local()

        # Format Local Data for update_sheet method
        local_data = {self.hostname: {'user': 'pi'}}
        local_data[self.hostname]['adapters'] = self.data['local']
        local_data[self.hostname]['interfaces'] = self.if_ips
        self.log.info('Final Data set collected for {}: {}'.format(self.hostname, local_data))

        # Pass Local Data to update_sheet method get remotes found on sheet as return
        # update sheets function updates local_cloud_file
        remote_consoles = self.cloud.update_files(local_data)
        if len(remote_consoles) > 0:
            update_local_cloud_file(LOCAL_CLOUD_FILE, remote_consoles)

        # Update instance with remotes from local_cloud_file
        self.data['remote'] = self.get_remote(data=remote_consoles)

    # =======================
    #     MENUS FUNCTIONS
    # =======================

    def menu_formatting(self, section, text=None):
        if section == 'header':
            if not self.DEBUG:
                os.system('clear')
            print('=' * 74)
            a = 74 - len(text)
            b = int(a/2 - 2)
            if text is not None:
                if isinstance(text, list):
                    for t in text:
                        print(' {0} {1} {0}'.format('-' * b, t))
                else:
                    print(' {0} {1} {0}'.format('-' * b, text))
            print('=' * 74 + '\n')
        elif section == 'footer':
            print('')
            if text is not None:
                if isinstance(text, list):
                    for t in text:
                        print(t)
                else:
                    print(text)
            print('x. exit\n')
            print('=' * 74)
            print('* Remote Adapters based on local cahce only use refresh option to update *')
            print('=' * 74)

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
        print('   [LOCAL] Connect to Local Adapters')
        print('   ' + '-' * 33)

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
            if rem[host]['rem_ip'] is not None:
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
            self.baud, self.data_bits, self.parity.upper(), self.flow_pretty[self.flow]), 'h. Display picocom help',
             'r. Refresh (Find new adapters on Local and Remote ConsolePis)']
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
        self.go = False
        # sys.exit(0)

# =======================
#      MAIN PROGRAM
# =======================


# Main Program
if __name__ == "__main__":
    # Launch main menu
    menu = ConsolePiMenu()
    while menu.go:
        menu.main_menu()
