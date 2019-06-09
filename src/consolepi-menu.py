#!/etc/ConsolePi/venv/bin/python

import os
import sys
import json
import socket
import subprocess
import shlex
import serial.tools.list_ports
from collections import OrderedDict as od
import paramiko
import ast
import getpass

# get ConsolePi imports
from consolepi.common import get_config
from consolepi.common import get_if_ips
from consolepi.common import get_local_cloud_file
from consolepi.common import update_local_cloud_file
from consolepi.common import ConsolePi_Log
from consolepi.common import check_reachable
from consolepi.common import gen_copy_key
from consolepi.gdrive import GoogleDrive

# -- GLOBALS --
DEBUG = get_config('debug')
CLOUD_SVC = get_config('cloud_svc').lower()
LOG_FILE = '/var/log/ConsolePi/cloud.log'
LOCAL_CLOUD_FILE = '/etc/ConsolePi/cloud.data'

rem_user = 'pi'
rem_pass = None

class ConsolePiMenu:

    def __init__(self, bypass_remote=False, do_print=True):
        self.cloud = None  # Set in refresh method if reachable
        cpi_log = ConsolePi_Log(debug=DEBUG, log_file=LOG_FILE, do_print=do_print)
        self.log = cpi_log.log
        self.plog = cpi_log.log_print
        self.go = True
        self.baud = 9600
        self.data_bits = 8
        self.parity = 'n'
        self.flow = 'n'
        self.parity_pretty = {'o': 'Odd', 'e': 'Even', 'n': 'No'}
        self.flow_pretty = {'x': 'Xon/Xoff', 'h': 'RTS/CTS', 'n': 'No'}
        self.hostname = socket.gethostname()
        self.if_ips = get_if_ips(self.log)
        self.ip_list = []
        for _iface in self.if_ips:
            self.ip_list.append(self.if_ips[_iface]['ip'])
        self.data = {'local': self.get_local()}        
        if not bypass_remote:
            self.data['remote'] = self.get_remote()
        self.DEBUG = DEBUG
        self.menu_actions = {
            'main_menu': self.main_menu,
            'c': self.con_menu,
            'h': self.picocom_help,
            'r': self.refresh,
            'x': self.exit
        }

        if CLOUD_SVC == 'gdrive':
            if check_reachable('www.googleapis.com', 443):
                self.local_only = False
            else:
                self.plog('failed to connect to {}, operating in local only mode'.format(CLOUD_SVC), level='warning')
                self.local_only = True

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

        # get telnet port definitions from ser2net.conf
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
                    plog('No ser2net.conf definition found for {}'.format(tty_dev), level='warning')
        else:
            plog('No ser2net.conf file found unable to extract port definitions', level='warning')

        local_data = {self.hostname: {'user': 'pi'}}
        local_data[self.hostname]['adapters'] = serial_list
        local_data[self.hostname]['interfaces'] = self.if_ips
        log.debug('final local data set: {}'.format(local_data))
        return local_data

    # get remote consoles from local cache refresh function will check/update cloud file and update local cache
    def get_remote(self, data=None, rem_pass=rem_pass):
        reachable_list = []
        log = self.log
        plog = self.plog
        plog('Fetching Remote ConsolePis with attached Serial Adapters from local cache')
        if data is None:
            data = get_local_cloud_file(LOCAL_CLOUD_FILE)

        # check dhcp leases for ConsolePis (allows for Clustering with no network connection)
        # TODO # Change this to see if data[rem_hostname] exists, then check it's adapters
        self.rem_ip_list = []
        for remotepi in data:
            for adapter in data[remotepi]['interfaces']:
                self.rem_ip_list.append(data[remotepi]['interfaces'][adapter]['ip'])

        found = False
        with open('/var/lib/misc/dnsmasq.leases', 'r') as leases:
            for line in leases:
                if 'b8:27:eb' in line or 'dc:a6:32' in line:
                    line = line.split()
                    rem_ip = line[2]
                    rem_hostname = line[3]
                    if rem_ip not in self.rem_ip_list and check_reachable(rem_ip, 22):
                        plog('Collecting data from {0} @ {1} found in dhcp leases'.format(rem_hostname, rem_ip))
                        client = paramiko.SSHClient()
                        client.load_system_host_keys()
                        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        # Check for ssh rsa key, generate if missing, then copy to remote host
                        gen_copy_key(rem_ip, rem_user, self.hostname)
                        try:
                            plog('Initiating ssh session to {} to collect Console Data'.format(rem_ip))
                            client.connect(rem_ip, username=rem_user, timeout=5, auth_timeout=4)
                            connected = True
                        except paramiko.ssh_exception.AuthenticationException:
                            print('Certificate Authentication Failed falling back to user/pass\n\n')
                            rem_pass = getpass.getpass() if rem_pass is not None else rem_pass
                            try:
                                plog('Initiating ssh session to {} to collect Console Data'.format(rem_hostname))
                                client.connect(rem_ip, username=rem_user,password=rem_pass, timeout=5, auth_timeout=4)
                                connected = True
                            except paramiko.ssh_exception.AuthenticationException:
                                plog('Unable to Connect to {} ignoring this host'.format(rem_hostname))
                                connected = False

                        if connected:
                            # send menu command with this hosts data (remote ConsolePi will update it's own cache file)
                            stdin, stdout, stderr = client.exec_command('consolepi-menu \'{}\''.format(json.dumps(self.data['local'])))

                            for line in stdout:
                                if '/dev/' in line:
                                    rem_data = ast.literal_eval(line)
                                    found = True

                            client.close()
                            # update local cache data with data gathered from host found in dhcp leases
                            if found:
                                data[rem_hostname] = rem_data[rem_hostname]
                                data[rem_hostname]['rem_ip'] = rem_ip
                                reachable_list.append(rem_ip)
                                log.info('Succesfully Found and added {} found via dhcp lease'.format(rem_hostname))
                                update_local_cloud_file(LOCAL_CLOUD_FILE, data)
                                log.info('remote data: {}'.format(data))
                            else:
                                log.error('{} connected, but no Console Devices Found, stderr follows:'.format(rem_hostname))
                                for line in stderr:
                                    log.error(line)

        # Add remote commands to remote_consoles dict for each adapter
        for remotepi in data:
            this = data[remotepi]
            print('  {} Found...  Checking reachability'.format(remotepi), end='')
            for _iface in this['interfaces']:
                _ip = this['interfaces'][_iface]['ip']
                if _ip not in self.ip_list:
                    if _ip in reachable_list or check_reachable(_ip, 22):
                        this['rem_ip'] = _ip
                        print(': Success', end='\n')
                        log.info('get_remote: Found {0} in Local Cloud Cache, reachable via {1}'.format(remotepi, _ip))
                        for adapter in this['adapters']:
                            _dev = adapter['dev']
                            adapter['rem_cmd'] = shlex.split('ssh -t {0}@{1} "picocom {2} -b{3} -f{4} -d{5} -p{6}"'.format(
                                this['user'], _ip, _dev, self.baud, self.flow, self.data_bits, self.parity))
                        break  # Stop Looping through interfaces we found a reachable one
                    else:
                        this['rem_ip'] = None

            if this['rem_ip'] is None:
                log.warning('get_remote: Found {0} in Local Cloud Cache: UNREACHABLE'.format(remotepi))
                print(': !!! UNREACHABLE !!!', end='\n')

        return data

    # Update ConsolePi.csv on Google Drive and pull any data for other ConsolePis
    def refresh(self):
        print('Updating to/from Cloud... Standby')

        # Update Local Adapters
        self.data['local'] = self.get_local()
        self.log.info('Final Data set collected for {}: {}'.format(self.hostname, self.data['local']))

        # Get details from Google Drive - once populated will skip
        if not self.local_only and self.cloud is None:
            if CLOUD_SVC == 'gdrive':
                self.cloud = GoogleDrive(self.log)

            # Pass Local Data to update_sheet method get remotes found on sheet as return
            # update sheets function updates local_cloud_file
            remote_consoles = self.cloud.update_files(self.data['local'])
            if len(remote_consoles) > 0:
                update_local_cloud_file(LOCAL_CLOUD_FILE, remote_consoles)

            # Update instance with remotes from local_cloud_file
            self.data['remote'] = self.get_remote(data=remote_consoles)
        else:
            print('Not Updating from {} due to connection failure'.format(CLOUD_SVC))
            print('Close and re-launch menu if network access has been restored restored')

    def update_from_remote(self, rem_data):
        self.log.info('debug type rem_data: {}'.format(type(rem_data)))
        rem_data = ast.literal_eval(rem_data)
        self.log.info('debug type rem_data: {}'.format(type(rem_data)))
        if isinstance(rem_data, dict):
            self.log.info('Remote Update Received via ssh: {}'.format(rem_data))
            cache_data = get_local_cloud_file(LOCAL_CLOUD_FILE)
            for host in rem_data:
                cache_data[host] = rem_data[host]
            update_local_cloud_file(LOCAL_CLOUD_FILE, cache_data)

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
            if self.local_only:
                print('*                          !!!LOCAL ONLY MODE!!!                         *')
            else:
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
        loc = self.data['local'][self.hostname]['adapters']
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
             'r. Refresh (Find new adapters on Local and Remote ConsolePis)' if not self.local_only else
             'r. Refresh (Find new Local adapters)']

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
    # If script is called with an argument (any argument) simply prints details for this ConsolePi
    # used if ConsolePi is detected as DHCP client on another ConsolePi (for non internet connected cluster)
    if len(sys.argv) > 1:
        menu = ConsolePiMenu(bypass_remote=True, do_print=False)
        # data = {menu.hostname: {'interfaces': menu.if_ips, 'adapters': menu.data['local'][mw], 'user': 'pi'}}
        menu.update_from_remote(sys.argv[1])
        print(menu.data['local'])
    else:
        # Launch main menu
        menu = ConsolePiMenu()
        while menu.go:
            menu.main_menu()
