#!/etc/ConsolePi/venv/bin/python

# TODO Check for unused imports #
import os
import sys
import json
import subprocess
import shlex
from collections import OrderedDict as od
import ast
import readline
from threading import Thread

# get ConsolePi imports
from consolepi.common import check_reachable
from consolepi.common import gen_copy_key
from consolepi.gdrive import GoogleDrive
from consolepi.common import ConsolePi_data
from consolepi.power import Outlets

rem_user = 'pi'
rem_pass = None

class ConsolePiMenu(Outlets):

    def __init__(self, bypass_remote=False, do_print=True):
        super().__init__()
        # pylint: disable=maybe-no-member
        config = ConsolePi_data()
        self.config = config
        self.remotes_connected = False
        self.error = None
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
        self.outlet_data = self.get_outlets() if config.power else None
        self.DEBUG = config.debug
        self.menu_actions = {
            'main_menu': self.main_menu,
            'key_menu': self.key_menu,
            'c': self.con_menu,
            'p': self.power_menu,
            'h': self.picocom_help,
            'k': self.key_menu,
            'r': self.refresh,
            's': self.rshell_menu,
            'x': self.exit
        }

    # get remote consoles from local cache refresh function will check/update cloud file and update local cache
    def get_remote(self, data=None, refresh=False):
        config = self.config
        log = config.log
        # plog = config.plog
        print('Fetching Remote ConsolePis with attached Serial Adapters from local cache')
        log.info('[GET REM] Starting fetch from local cache')

        if data is None:
            data = config.get_local_cloud_file()

        if config.hostname in data:
            data.pop(self.hostname)
            log.warning('[GET REM] Local cache included entry for self - there is a logic error someplace')

        # Add remote commands to remote_consoles dict for each adapter
        update_cache = False
        for remotepi in data:
            this = data[remotepi]
            print('  {} Found...  Checking reachability'.format(remotepi), end='')
            if 'rem_ip' in this and this['rem_ip'] is not None and check_reachable(this['rem_ip'], 22):
                print(': Success', end='\n')
                log.info('[GET REM] Found {0} in Local Cache, reachable via {1}'.format(remotepi, this['rem_ip']))
                #this['adapters'] = build_adapter_commands(this)
            else:
                for _iface in this['interfaces']:
                    _ip = this['interfaces'][_iface]['ip']
                    if _ip not in self.ip_list:
                        if check_reachable(_ip, 22):
                            this['rem_ip'] = _ip
                            print(': Success', end='\n')
                            log.info('[GET REM] Found {0} in Local Cloud Cache, reachable via {1}'.format(remotepi, _ip))
                            #this['adapters'] = build_adapter_commands(this)
                            break  # Stop Looping through interfaces we found a reachable one
                        else:
                            this['rem_ip'] = None

            if this['rem_ip'] is None:
                log.warning('[GET REM] Found {0} in Local Cloud Cache: UNREACHABLE'.format(remotepi))
                update_cache = True                
                print(': !!! UNREACHABLE !!!', end='\n')
                        
        # update local cache if any ConsolePis found UnReachable
        if update_cache:
            data = config.update_local_cloud_file(data)

        return data

    # Update ConsolePi.csv on Google Drive and pull any data for other ConsolePis
    def refresh(self, rem_update=False):
        # pylint: disable=maybe-no-member
        remote_consoles = None
        config = self.config
        # Update Local Adapters
        if not rem_update:
            print('Detecting Locally Attached Serial Adapters')
            self.data['local'] = {self.hostname: {'adapters': config.get_local(), 'interfaces': config.get_if_ips(), 'user': 'pi'}}
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

    # -- Deprecated function will return this ConsolePis data if consolepi-menu called with an argument (if arg is data of calling ConsolePi it's read in)
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
                print('* Remote Adapters based on local cache only use refresh option to update *')
            print('=' * 74)

    def do_flow_pretty(self, flow):
        if flow == 'x':
            flow_pretty = 'xon/xoff'
        elif flow == 'h':
            flow_pretty = 'RTS/CTS'
        elif flow == 'n':
            flow_pretty = 'NONE'
        else:
            flow_pretty = 'VALUE ERROR'
        
        return flow_pretty

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

    def power_menu(self):
        choice = ''
        outlets = self.outlet_data
        while choice.lower() not in ['x', 'b']:
            item = 1
            # if choice.lower() == 'r':
            outlets = self.get_outlets()
                # print('Refreshing Outlets')
            if not self.DEBUG:
                os.system('clear')

            self.menu_formatting('header', text=' Power Control Menu ')
            print('  Defined Power Outlets')
            print('  ' + '-' * 33)

            # Build menu items for each serial adapter found on remote ConsolePis
            for r in sorted(outlets):
                outlet = outlets[r]
                if outlet['type'].upper() == 'GPIO':
                    if outlet['noff']:
                        cur_state = 'on' if outlet['is_on'] else 'off'
                        to_state = 'off' if outlet['is_on'] else 'on'
                    else:
                        cur_state = 'off' if outlet['is_on'] else 'on'
                        to_state = 'on' if outlet['is_on'] else 'off'
                elif outlet['type'].lower() == 'tasmota':
                    cur_state = 'on' if outlet['is_on'] else 'off'
                    to_state = 'off' if outlet['is_on'] else 'on'
                
                if isinstance(outlet['is_on'], int) and outlet['is_on'] <= 1:
                    print('{0}. Turn {1} {2} [ Current State {3} ]'.format(item, r, to_state, cur_state ))
                    self.menu_actions[str(item)] = {'function': self.do_toggle, 'args': [outlet['type'], outlet['address']]}
                    item += 1
                else:
                    print('!! Skipping {} as it returned an error: {}'.format(r, outlet['is_on']))
            
            self.menu_actions['b'] = self.main_menu
            text = ['b. Back', 'r. Refresh']
            self.menu_formatting('footer', text=text)
            choice = input(" >>  ")
            if not choice.lower() == 'r':
                self.exec_menu(choice, actions=self.menu_actions, calling_menu='power_menu')
        

    def key_menu(self):
        rem = self.data['remote']
        choice = ''
        while choice.lower() not in ['x', 'b']:
            menu_actions = {
                'b': self.main_menu,
                'x': self.exit,
                'key_menu': self.key_menu
            }
            if not self.DEBUG:
                os.system('clear')
            # self.menu_actions['b'] = self.main_menu

            self.menu_formatting('header', text=' Remote SSH Key Distribution Menu ')
            print('  Available Remote Hosts')
            print('  ' + '-' * 33)
        
            # Build menu items for each serial adapter found on remote ConsolePis
            item = 1
            for host in rem:
                if rem[host]['rem_ip'] is not None:
                    rem_ip = rem[host]['rem_ip']
                    print('{0}. Send SSH key to {1} @ {2}'.format(item, host, rem_ip))
                    # self.menu_actions[str(item)] = {'function': gen_copy_key, 'args': rem[host]['rem_ip']}
                    menu_actions[str(item)] = {'function': gen_copy_key, 'args': rem[host]['rem_ip']}
                    item += 1
        
            self.menu_formatting('footer', text='b. Back')
            choice = input(" >>  ")
            
            self.exec_menu(choice, actions=menu_actions, calling_menu='key_menu')

    def main_menu(self):
        loc = self.data['local'][self.hostname]['adapters']
        rem = self.data['remote']
        # remotes_connected = False
        item = 1
        if not self.DEBUG:
            os.system('clear')
        self.menu_formatting('header', text=' ConsolePi Serial Menu ')
        print('   [LOCAL] Connect to Local Adapters')
        print('   ' + '-' * 33)

        # TODO # >> Clean this up, make sub to do this on both local and remote
        # Build menu items for each locally connected serial adapter
        for _dev in sorted(loc, key = lambda i: i['port']):
            this_dev = _dev['dev']
            try:
                def_indicator = ''
                baud = _dev['baud']
                dbits = _dev['dbits']
                flow = _dev['flow']
                parity = _dev['parity']
            except KeyError:
                def_indicator = '*'
                baud = self.baud
                flow = self.flow
                dbits = self.data_bits
                parity = self.parity

            # Generate Menu Line
            menu_line = '{0}. Connect to {1} [{2}{3} {4}{5}1]'.format(
                item, this_dev.replace('/dev/', ''), def_indicator, baud, dbits, parity[0].upper())
            flow_pretty = self.do_flow_pretty(flow)
            if flow_pretty != 'NONE':
                menu_line += ' {}'.format(flow_pretty)
            print(menu_line)

            # Generate Command executed for Menu Line
            _cmd = 'picocom {0} -b{1} -f{2} -d{3} -p{4}'.format(this_dev, baud, flow, dbits, parity)
            self.menu_actions[str(item)] = {'cmd': _cmd}
            item += 1

        # Build menu items for each serial adapter found on remote ConsolePis
        for host in sorted(rem):
            if rem[host]['rem_ip'] is not None and len(rem[host]['adapters']) > 0:
                self.remotes_connected = True
                header = '   [Remote] {} @ {}'.format(host, rem[host]['rem_ip'])
                print('\n' + header + '\n   ' + '-' * (len(header) - 3))
                for _dev in sorted(rem[host]['adapters'], key = lambda i: i['port']):
                    try:
                        def_indicator = ''
                        baud = _dev['baud']
                        dbits = _dev['dbits']
                        flow = _dev['flow']
                        parity = _dev['parity']
                    except KeyError:
                        def_indicator = '*'
                        baud = self.baud
                        flow = self.flow
                        dbits = self.data_bits
                        parity = self.parity

                    # Generate Menu Line
                    menu_line = '{0}. Connect to {1} [{2}{3} {4}{5}1]'.format(
                        item, _dev['dev'].replace('/dev/', ''), def_indicator, baud, dbits, parity[0].upper())
                    flow_pretty = self.do_flow_pretty(flow)
                    if flow_pretty != 'NONE':
                        menu_line += ' {}'.format(flow_pretty)
                    print(menu_line)

                    # Generate Command executed for Menu Line
                    _cmd = 'ssh -t {0}@{1} "picocom {2} -b{3} -f{4} -d{5} -p{6}"'.format(
                                rem[host]['user'], rem[host]['rem_ip'], _dev['dev'], baud, flow, dbits, parity)
                    self.menu_actions[str(item)] = {'cmd': _cmd}
                    item += 1

        # -- General Menu Command Options --
        text = ['c. Change *default Serial Settings [{0} {1}{2}1 flow={3}] '.format(
            self.baud, self.data_bits, self.parity.upper(), self.flow_pretty[self.flow]), 'h. Display picocom help']
        if self.outlet_data is not None:
            text.append('p. Power Control Menu')
        if self.remotes_connected:
            text.append('k. Distribute SSH Key to Remote Hosts')
            text.append('s. Remote Shell Menu (Connect to Remote ConsolePi Shell)')
        text.append('r. Refresh')

        self.menu_formatting('footer', text=text)
        choice = input(" >>  ")
        self.exec_menu(choice)

        return

    def rshell_menu(self):
        if self.remotes_connected:
            choice = ''
            rem = self.data['remote']
            while choice.lower() not in ['x', 'b']:
                if not self.DEBUG:
                    os.system('clear')
                self.menu_actions['b'] = self.main_menu
                self.menu_formatting('header', text=' Remote Shell Menu ')

                # Build menu items for each serial adapter found on remote ConsolePis
                item = 1
                for host in sorted(rem):
                    if rem[host]['rem_ip'] is not None:
                        self.remotes_connected = True
                        print('{0}. Connect to {1} @ {2}'.format(item, host, rem[host]['rem_ip']))
                        _cmd = 'ssh -t {0}@{1}'.format('pi', rem[host]['rem_ip'])
                        self.menu_actions[str(item)] = {'cmd': _cmd}
                        item += 1

                text = 'b. Back'
                self.menu_formatting('footer', text=text)
                choice = input(" >>  ")
                self.exec_menu(choice, actions=self.menu_actions, calling_menu='rshell_menu')
        else:
            print('No Reachable remote devices found')
        return

    # Execute menu
    def exec_menu(self, choice, actions=None, calling_menu='main_menu'):
        menu_actions = self.menu_actions if actions is None else actions
        # for k in menu_actions:
        #     print('{}: {}'.format(k, menu_actions[k]))
        config = self.config
        log = config.log
        if not self.DEBUG:
            os.system('clear')
        ch = choice.lower()
        if ch == '':
            menu_actions[calling_menu]()
        else:
            try:
                if isinstance(menu_actions[ch], dict):
                    if 'cmd' in menu_actions[ch]:
                        c = shlex.split(menu_actions[ch]['cmd'])
                        # c = list like (local): ['picocom', '/dev/White3_7003', '-b9600', '-fn', '-d8', '-pn']
                        #               (remote): ['ssh', '-t', 'pi@10.1.30.28', 'picocom /dev/AP303P-BARN_7001 -b9600 -fn -d8 -pn']
                        
                        # -- if Power Control function is enabled check if device is linked to an outlet and ensure outlet is pwrd on --
                        if config.power:  # pylint: disable=maybe-no-member
                            if '/dev/' in c[1] or ( len(c) >= 4 and '/dev/' in c[3] ):
                                menu_dev = c[1] if c[0] != 'ssh' else c[3].split()[1]
                                for dev in config.local[self.hostname]['adapters']:
                                    if menu_dev == dev['dev']:
                                        outlet = dev['outlet']
                                        if outlet is not None and isinstance(outlet['is_on'], int) and outlet['is_on'] <= 1:
                                            desired_state = 'on' if outlet['noff'] else 'off' # TODO Move noff logic to power.py
                                            print('Ensuring ' + menu_dev + ' is Powered On')
                                            r = self.do_toggle(outlet['type'], outlet['address'], desired_state=desired_state)
                                            if isinstance(r, int) and r > 1:
                                                print('Error operating linked outlet @ {}'.format(outlet['address']))
                                                log.warning('{} Error operating linked outlet @ {}'.format(menu_dev, outlet['address']))
                                        else:
                                            print('Linked Outlet @ {} returned an error during menu load. Skipping...'.format(outlet['address']))

                        subprocess.run(c)
                    elif 'function' in menu_actions[ch]:
                        args = menu_actions[ch]['args']
                        # this is a lame hack but for the sake of time... for now
                        try:
                            # hardcoded for the gen key function
                            menu_actions[ch]['function'](args, rem_user=rem_user, hostname=self.hostname, copy=True)
                        except TypeError as e:
                            if 'toggle()' in str(e):
                                menu_actions[ch]['function'](args[0], args[1])
                                # self.do_toggle('tasmota', '10.115.0.129')
                            else:
                                # print(e)
                                raise TypeError(e)
                            
                else:
                    menu_actions[ch]()
            except KeyError as e:
                print('Invalid selection {}, please try again.\n'.format(e))
                # menu_actions[calling_menu]()
        
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
        # threading doesn't work ssh process terminates
        # threading.Thread(target=menu.update_from_remote, args=(sys.argv[1])).start()
        menu.update_from_remote(sys.argv[1])
        print(menu.data['local'])
    else:
        # Launch main menu
        menu = ConsolePiMenu()
        while menu.go:
            menu.main_menu()
