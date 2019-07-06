#!/etc/ConsolePi/venv/bin/python

# TODO Check for unused imports #
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
import threading

# get ConsolePi imports
from consolepi.common import check_reachable
from consolepi.common import gen_copy_key
from consolepi.gdrive import GoogleDrive
from consolepi.common import ConsolePi_data


# -- GLOBALS --
# DO_DHCP=False   # DHCP update function now disabled, MDNS makes it unecessary
# LOCAL_CLOUD_FILE = '/etc/ConsolePi/cloud.data'
# LOG_FILE = '/var/log/ConsolePi/cloud.log'


# Depricated - mdns is now automatically triggered via systemd file in background
DO_MDNS = False
if DO_MDNS:
    from consolepi.mdns_browse import MDNS_Browser
    from time import sleep

rem_user = 'pi'
rem_pass = None

class ConsolePiMenu:

    def __init__(self, bypass_remote=False, do_print=True):
        config = ConsolePi_data()
        self.config = config
        self.error = None
        if DO_MDNS:
            self.mdns = MDNS_Browser(config.log)
            self.zcstop = threading.Thread(target=self.mdns.zc.close)

        self.cloud = None  # Set in refresh method if reachable
        self.do_cloud = config.cloud
        if self.do_cloud and config.cloud_svc == 'gdrive':
            if check_reachable('www.googleapis.com', 443):
                self.local_only = False
                if not os.path.isfile('/etc/ConsolePi/cloud/gdrive/.credentials/credentials.json'):
                    config.plog('Required {} credentials files are missing refer to GitHub for details'.format(config.cloud_svc), level='warning')
                    config.plog('Disabling {} updates'.format(config.cloud_svc), level='warning')
                    self.error = ' {} credentials not found'.format(config.cloud_svc)
                    self.do_cloud = False
            else:
                config.plog('failed to connect to {}, operating in local only mode'.format(config.cloud_svc), level='warning')
                self.local_only = True

        self.go = True
        self.baud = 9600
        self.data_bits = 8
        self.parity = 'n'
        self.flow = 'n'
        self.parity_pretty = {'o': 'Odd', 'e': 'Even', 'n': 'No'}
        self.flow_pretty = {'x': 'Xon/Xoff', 'h': 'RTS/CTS', 'n': 'No'}
        self.hostname = config.hostname
        self.if_ips = config.interfaces
        self.ip_list = []
        for _iface in self.if_ips:
            self.ip_list.append(self.if_ips[_iface]['ip'])    
        self.data = {'local': config.local}
        if not bypass_remote:
            self.data['remote'] = self.get_remote()
        self.DEBUG = config.debug
        self.menu_actions = {
            'main_menu': self.main_menu,
            'key_menu': self.key_menu,
            'c': self.con_menu,
            'h': self.picocom_help,
            'k': self.key_menu,
            'r': self.refresh,
            'x': self.exit
        }

    # get remote consoles from local cache refresh function will check/update cloud file and update local cache
    def get_remote(self, data=None, refresh=False):
        config = self.config
        log = config.log
        plog = config.plog
        plog('Fetching Remote ConsolePis with attached Serial Adapters from local cache')

        if data is None:
            data = config.get_local_cloud_file()

        # Depricated now done in background systemd
        if DO_MDNS:
            plog('Discovering Remotes via mdns')
            m_data = self.mdns.mdata
            if m_data is not None:
                for _ in m_data:
                    plog('    {} Discovered via mdns'.format(_))
                data = config.update_local_cloud_file(m_data)

        # if DO_DHCP:
        #     if refresh or not config.do_cloud or self.local_only:
        #         data = self.update_from_dhcp_leases(data)

        if config.hostname in data:
            data.pop(self.hostname)
            config.log.warning('Local Cloud cache included entry for self - there is a logic error someplace')

        def build_adapter_commands(data):
            for adapter in data['adapters']:
                _dev = adapter['dev']
                adapter['rem_cmd'] = shlex.split('ssh -t {0}@{1} "picocom {2} -b{3} -f{4} -d{5} -p{6}"'.format(
                    data['user'], _ip, _dev, self.baud, self.flow, self.data_bits, self.parity))
            return data['adapters']

        # Add remote commands to remote_consoles dict for each adapter
        for remotepi in data:
            this = data[remotepi]
            print('  {} Found...  Checking reachability'.format(remotepi), end='')
            if 'rem_ip' in this and check_reachable(this['rem_ip'], 22):
                print(': Success', end='\n')
                log.info('get_remote: Found {0} in Local Cloud Cache, reachable via {1}'.format(remotepi, _ip))
                this['adapters'] = build_adapter_commands(this)
                # for adapter in this['adapters']:
                #     _dev = adapter['dev']
                #     adapter['rem_cmd'] = shlex.split('ssh -t {0}@{1} "picocom {2} -b{3} -f{4} -d{5} -p{6}"'.format(
                #         this['user'], _ip, _dev, self.baud, self.flow, self.data_bits, self.parity))
            else:
                for _iface in this['interfaces']:
                    _ip = this['interfaces'][_iface]['ip']
                    if _ip not in self.ip_list:
                        if check_reachable(_ip, 22):
                            this['rem_ip'] = _ip
                            print(': Success', end='\n')
                            log.info('get_remote: Found {0} in Local Cloud Cache, reachable via {1}'.format(remotepi, _ip))
                            this['adapters'] = build_adapter_commands(this)
                            # for adapter in this['adapters']:
                            #     _dev = adapter['dev']
                            #     adapter['rem_cmd'] = shlex.split('ssh -t {0}@{1} "picocom {2} -b{3} -f{4} -d{5} -p{6}"'.format(
                            #         this['user'], _ip, _dev, self.baud, self.flow, self.data_bits, self.parity))
                            break  # Stop Looping through interfaces we found a reachable one
                        else:
                            this['rem_ip'] = None

            if this['rem_ip'] is None:
                log.warning('get_remote: Found {0} in Local Cloud Cache: UNREACHABLE'.format(remotepi))
                print(': !!! UNREACHABLE !!!', end='\n')

        return data

    # Update ConsolePi.csv on Google Drive and pull any data for other ConsolePis
    def refresh(self, rem_update=False):
        remote_consoles = None
        config = self.config
        # Update Local Adapters
        if not rem_update:
            self.data['local'] = config.local
            config.log.info('Final Data set collected for {}: {}'.format(self.hostname, self.data['local']))

        # Get details from Google Drive - once populated will skip
        if self.do_cloud and not self.local_only:
            if config.cloud_svc == 'gdrive' and self.cloud is None:
                self.cloud = GoogleDrive(config.log, hostname=self.hostname)

            # Pass Local Data to update_sheet method get remotes found on sheet as return
            # update sheets function updates local_cloud_file
            config.plog('Updating to/from {}'.format(config.cloud_svc))
            remote_consoles = self.cloud.update_files(self.data['local'])
            if len(remote_consoles) > 0:
                config.plog('Updating Local Cache with data from {}'.format(config.cloud_svc))
                config.update_local_cloud_file(remote_consoles)
            else:
                config.plog('No Remote ConsolePis found on {}'.format(config.cloud_svc))
        else:
            if self.do_cloud:
                print('Not Updating from {} due to connection failure'.format(config.cloud_svc))
                print('Close and re-launch menu if network access has been restored')

        # Update Remote data with data from local_cloud cache (and dhcp leases)
        self.data['remote'] = self.get_remote(data=remote_consoles, refresh=True)


    def update_from_remote(self, rem_data):
        config = self.config
        log = config.log
        rem_data = ast.literal_eval(rem_data)
        if isinstance(rem_data, dict):
            log.info('Remote Update Received via ssh: {}'.format(rem_data))
            cache_data = config.get_local_cloud_file()
            for host in rem_data:
                cache_data[host] = rem_data[host]
            log.info('Updating Local Cloud Cache with data recieved from {}'.format(host))
            config.update_local_cloud_file(cache_data)
            self.refresh(rem_update=True)

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
            if not self.do_cloud:
                if self.error is None:
                    print('*                          Cloud Function Disabled                       *')
                else:
                    print('*        Cloud Function Disabled by script - no credentials found        *')
            elif self.local_only:
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

    def key_menu(self):
        item = 1
        rem = self.data['remote']
        if not self.DEBUG:
            os.system('clear')
        self.menu_actions['b'] = self.main_menu

        self.menu_formatting('header', text=' Remote SSH Key Distribution Menu ')
        print('  Available Remote Hosts')
        print('  ' + '-' * 33)

        # Build menu items for each serial adapter found on remote ConsolePis
        for host in rem:
            if rem[host]['rem_ip'] is not None:
                rem_ip = rem[host]['rem_ip']
                print('{0}. Send SSH key to {1} @ {2}'.format(item, host, rem_ip))
                self.menu_actions[str(item)] = {'function': gen_copy_key, 'args': rem[host]['rem_ip']}
                item += 1

        text = 'b. Back'
        self.menu_formatting('footer', text=text)
        choice = input(" >>  ")
        self.exec_menu(choice, actions=self.menu_actions, calling_menu='key_menu')

    def main_menu(self):
        loc = self.data['local'][self.hostname]['adapters']
        rem = self.data['remote']
        remotes_connected = False
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
                remotes_connected = True
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
        if remotes_connected:
            text.append('k. Distribute SSH Key to Remote Hosts')
        r = 'r. Refresh (Find new adapters on Local and Remote ConsolePis)' if self.do_cloud and not self.local_only else 'r. Refresh (Find new Local adapters)'
        text.append(r)

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
                    elif 'function' in menu_actions[ch]:
                        # hardcoded for the gen key function
                        print(menu_actions[ch]['args'])
                        args = menu_actions[ch]['args']
                        menu_actions[ch]['function'](args, rem_user=rem_user, hostname=self.hostname, copy=True)
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
        if DO_MDNS:
            self.zcstop.start()
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
        # threading doesn't work ssh process terminates
        # threading.Thread(target=menu.update_from_remote, args=(sys.argv[1])).start()
        menu.update_from_remote(sys.argv[1])
        print(menu.data['local'])
    else:
        # Launch main menu
        menu = ConsolePiMenu()
        while menu.go:
            menu.main_menu()
