#!/etc/ConsolePi/venv/bin/python

# import ast
import json
import os
# import re
import readline # NoQA - allows input to accept backspace
import shlex
import subprocess
import sys
import re
import time
import threading
from collections import OrderedDict as od
from halo import Halo

# --// ConsolePi imports \\--
sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import ConsolePi  # NoQA
from consolepi import Rename  # NoQA
from consolepi import Menu  # NoQA
# from consolepi.gdrive import GoogleDrive # <-- hidden import burried in refresh method of ConsolePiMenu Class

MIN_WIDTH = 55
MAX_COLS = 5


class ConsolePiMenu(Rename):

    def __init__(self, bypass_remote=False):
        self.cpi = ConsolePi(bypass_remote=bypass_remote)
        self.utils = self.cpi.utils
        self.baud = self.cpi.config.default_baud
        self.go = True
        self.debug = self.cpi.config.cfg.get('debug', False)
        self.spin = Halo(spinner='dots')
        self.states = {
            True: '{{green}}ON{{norm}}',
            False: '{{red}}OFF{{norm}}'
        }
        self.error_msgs = []
        self.log_sym_2bang = '\033[1;33m!!\033[0m'
        self.log = self.cpi.config.log
        self.display_con_settings = False
        self.menu = Menu(self)
        self.menu.ignored_errors = [
            re.compile('Connection to .* closed')
        ]
        self.do_menu_load_warnings()
        self.shell_cmds = ['ping', 'ssh', 'telnet', 'picocom', 'ip ', 'ifconfig', 'netstat', 'sudo ', 'printenv', 'cat ', 'tail ']
        super().__init__()

    def print_menu(self, *args, **kwargs):
        '''combine error_msgs and pass to menu formatter/print functions'''

        kwargs['error_msgs'] = self.cpi.error_msgs + self.error_msgs
        self.cpi.error_msgs = self.error_msgs = []
        self.menu.print_mlines(*args, **kwargs)

    def print_attribute(self, ch, locs={}):
        '''Debugging Function allowing user to print class attributes / function returns.

        Params:
            ch {str}: the input from user prompt
            locs: locals() from calling function

        Returns:
            Bool | None -- True if ch is an attribute No return otherwise
        '''
        if '.' in ch and len(ch) > 2:
            cpi = self.cpi
            local = cpi.local  # NoQA
            remotes = cpi.remotes
            cloud = remotes.cloud  # NoQA
            pwr = cpi.pwr  # NoQA
            config = cpi.config  # NoQA
            utils = cpi.utils  # NoQA
            menu = self.menu # NoQA
            _var = None
            _class_str = '.'.join(ch.split('.')[0:-1])
            _attr = ch.split('.')[-1].split('[')[0].split('(')[0]
            if _class_str.split('.')[0] == 'this':
                _var = f'self.var = locs.get("{_attr}", "Attribute/Variable Not Found")'
                if '[' in ch:
                    _var += f"[{ch.split('.')[-1].split('[')[1]}"
                if '(' in ch:
                    _var += f"({ch.split('.')[-1].split('(')[1]}"
            else:
                exec(f'self._class = {_class_str}')
                if hasattr(self._class, _attr):  # NoQA
                    _var = f"self.var = {ch}"
                else:
                    cpi.error_msgs.append(f"DEBUG: '{_class_str}' object has no attribute '{_attr}'")
                    return True

            if _var:
                try:
                    exec(_var)
                    if isinstance(self.var, (dict, list)):
                        _class_str = _class_str.replace('this', '')
                        if _class_str:
                            _class_str += '.'
                        if isinstance(self.var, dict):
                            var = {k: v if not callable(v) else f'{_class_str}{v.__name__}()' for k, v in self.var.items()}
                            for k in var:
                                if 'function' in var[k]:
                                    var[k]['function'] = f"{_class_str}{var[k]['function'].__name__}()"
                        else:
                            var = [v if not callable(v) else f'{_class_str}{v.__name__}()' for v in self.var]
                        print(json.dumps(var, indent=4, sort_keys=True))
                        print(f'{type(self.var)} length: {len(self.var)}')
                    else:
                        print(self.var)
                        print(f'type: {type(self.var)}\n'
                              if isinstance(self.var, str) and 'Not Found' not in self.var else '\n')
                    input('Press Enter to Continue... ')
                except Exception as e:
                    if hasattr(self, 'var'):
                        print(self.var)
                        input('Press Enter to Continue... ')
                    cpi.error_msgs.append(f'DEBUG: {e}')
                return True

    def exec_shell_cmd(self, cmd):
        '''Allow user to perform supported commands directly from menu

        Arguments:
            cmd {str} -- command to be passed to shell

        Returns:
            bool|None -- True if cmd matched supported cmd
        '''
        for c in self.shell_cmds:
            if c in cmd:
                try:
                    if 'sudo ' not in cmd:
                        cmd = f'sudo -u {self.cpi.local.user} {cmd}'
                    elif 'sudo -u ' not in cmd:
                        cmd = cmd.replace('sudo ', '')
                    subprocess.run(cmd, shell=True)
                except (KeyboardInterrupt, EOFError):
                    pass
                input('Press Enter to Continue... ')
                return True

    def do_menu_load_warnings(self):
        '''Displays and logs warnings based on data collected/validated during menu load.'''

        # -- // Not running as root \\ --
        if not self.cpi.config.root:
            self.menu.log_and_show('Running without sudo privs ~ Results may vary!\n'
                                   'Use consolepi-menu to launch menu', logit=False)

        # -- // Remotes with older API schema \\ --
        for adapters in [self.cpi.remotes.data[r].get('adapters', {}) for r in self.cpi.remotes.data]:
            if isinstance(adapters, list):
                _msg = 'You have remotes running older versions ~ older API schema.  You Should Upgrade those Remotes'
                self.menu.log_and_show(_msg, log=self.cpi.config.log.warning)
                break

        # -- // No Local Adapters Found \\ --
        if not self.cpi.local.adapters:
            self.menu.error_msgs.append('No Local Adapters Detected')

    def picocom_help(self):
        print('##################### picocom Command Sequences ########################\n')
        print(' This program will launch serial session via picocom')
        print(' This is a list of the most common command sequences in picocom')
        print(' To use them press and hold ctrl then press and release each character\n')
        print('   ctrl+ a - x Exit session - reset the port')
        print('   ctrl+ a - q Exit session - without resetting the port')
        print('   ctrl+ a - b set baudrate')
        print('   ctrl+ a - u increase baud')
        print('   ctrl+ a - d decrease baud')
        print('   ctrl+ a - i change the number of databits')
        print('   ctrl+ a - f cycle through flow control options')
        print('   ctrl+ a - y cycle through parity options')
        print('   ctrl+ a - v Show configured port options')
        print('   ctrl+ a - c toggle local echo')
        print('\n########################################################################\n')
        input('Press Enter to Continue... ')

    def power_menu(self, calling_menu='main_menu'):
        cpi = self.cpi
        pwr = cpi.pwr
        menu = self.menu
        states = self.states
        menu_actions = {
            'b': self.main_menu,
            'x': self.exit,
            'power_menu': self.power_menu,
        }
        choice = ''

        # Ensure Power Threads are complete
        if not cpi.pwr_init_complete:
            with Halo(text='Waiting for Outlet init threads to complete', spinner='dots'):
                cpi.wait_for_threads()
                outlets = pwr.data['defined']
        else:
            outlets = cpi.outlet_update()

        if not outlets:
            cpi.error_msgs.append('No Linked Outlets are connected')
            return

        while choice not in ['x', 'b']:
            item = 1

            header = 'Power Control Menu'
            subhead = [
                '  enter item # to toggle power state on outlet',
                '  enter c + item # i.e. "c2" to cycle power on outlet'
            ]

            # Build menu items for each linked outlet
            state_list = []
            body = []
            footer = {'opts': [], 'before': []}
            for r in sorted(outlets):
                outlet = outlets[r]

                # -- // Linked DLI OUTLET MENU LINE(s) \\ --
                if outlet['type'].lower() == 'dli':
                    if outlet.get('linked_devs') and outlet.get('is_on'):  # Avoid orphan header when no outlets are linked
                        for dli_port in outlet['is_on']:
                            _outlet = outlet['is_on'][dli_port]
                            _state = states[_outlet['state']]
                            state_list.append(_outlet['state'])
                            _state = menu.format_line(_state).text
                            _name = ' ' + _outlet['name'] if 'ON' in _state else _outlet['name']
                            body.append(f"[{_state}] {_name} ({r} Port:{dli_port})")
                            menu_actions[str(item)] = {
                                'function': pwr.pwr_toggle,
                                'args': [outlet['type'], outlet['address']],
                                'kwargs': {'port': dli_port, 'desired_state': not _outlet['state']},
                                'key': r
                                }
                            menu_actions['c' + str(item)] = {
                                'function': pwr.pwr_cycle,
                                'args': ['dli', outlet['address']],
                                'kwargs': {'port': dli_port},
                                'key': 'dli_pwr'
                                }
                            menu_actions['r' + str(item)] = {
                                'function': pwr.pwr_rename,
                                'args': ['dli', outlet['address']],
                                'kwargs': {'port': dli_port},
                                'key': 'dli_pwr'
                                }
                            item += 1

                # -- // GPIO or tasmota OUTLET MENU LINE \\ --
                else:
                    # pwr functions put any errors (aborts) in pwr.data[grp]['error']
                    if pwr.data['defined'][r].get('errors'):
                        cpi.error_msgs.append(f'{r} - {pwr.data["defined"][r]["errors"]}')
                        del pwr.data['defined'][r]['errors']
                    if isinstance(outlet.get('is_on'), bool):
                        _state = states[outlet['is_on']]
                        state_list.append(outlet['is_on'])
                        _state = menu.format_line(_state).text
                        body.append(f"[{_state}] {' ' + r if 'ON' in _state else r} ({outlet['type']}:{outlet['address']})")
                        menu_actions[str(item)] = {
                            'function': pwr.pwr_toggle,
                            'args': [outlet['type'], outlet['address']],
                            'kwargs': {'noff': outlet.get('noff', True)},
                            'key': r
                            }
                        menu_actions['c' + str(item)] = {
                            'function': pwr.pwr_cycle,
                            'args': [outlet['type'], outlet['address']],
                            'kwargs': {'noff': outlet.get('noff', True)},
                            'key': r
                            }
                        menu_actions['r' + str(item)] = {
                            'function': pwr.pwr_rename,
                            'args': [outlet['type'], outlet['address']],
                            'key': r
                            }
                        item += 1
                    else:   # refactored power.py pwr_get_outlets this should never hit
                        if outlet.get('is_on'):
                            cpi.error_msgs.append(f"DEV NOTE {r} outlet state is not bool: {outlet['error']}")

            if item > 2:
                if False in state_list:
                    footer['before'].append('all on: Turn all outlets {{green}}ON{{norm}}')
                    menu_actions['all on'] = {
                        'function': pwr.pwr_all,
                        'kwargs': {'outlets': outlets, 'action': 'toggle', 'desired_state': True}
                        }
                if True in state_list:
                    footer['before'].append('all off: Turn all outlets {{red}}OFF{{norm}}')
                    menu_actions['all off'] = {
                        'function': pwr.pwr_all,
                        'kwargs': {'outlets': outlets, 'action': 'toggle', 'desired_state': False}
                        }
                    footer['before'].append('cycle all: Cycle all outlets '
                                            '{{green}}ON{{norm}}{{dot}}{{red}}OFF{{norm}}{{dot}}{{green}}ON{{norm}}')

                    menu_actions['cycle all'] = {
                        'function': pwr.pwr_all,
                        'kwargs': {'outlets': outlets, 'action': 'cycle'}
                        }
                footer['before'].append('')

            footer['opts'] = ['back', 'refresh']
            if pwr.dli_exists and not calling_menu == 'dli_menu':
                footer['opts'].insert(0, 'dli')
                menu_actions['d'] = self.dli_menu

            self.print_menu(body, header=header, subhead=subhead, footer=footer)
            choice = self.wait_for_input(lower=True)
            if choice not in ['b', 'r']:
                self.exec_menu(choice, menu_actions, calling_menu='power_menu')
            elif choice == 'b':
                return
            elif choice == 'r':
                if pwr.dli_exists:
                    with Halo(text='Refreshing Outlets', spinner='dots'):
                        outlets = cpi.outlet_update(refresh=True, upd_linked=True)

    def wait_for_input(self, prompt=" >> ", lower=False, terminate=False, locs={}):
        menu = self.menu
        try:
            if self.debug:
                menu.menu_rows += 1  # TODO REMOVE AFTER SIMPLIFIED
                prompt = f' m[r:{menu.menu_rows}, c:{menu.menu_cols}] a[r:{menu.rows}, c:{menu.cols}]{prompt}'
            choice = input(prompt) if not lower else input(prompt).lower()
            # debug toggles debug
            if choice == 'debug':
                self.cpi.error_msgs.append(f'debug toggled {self.states[self.debug]} --> {self.states[not self.debug]}')
                self.cpi.error_msgs.append('Changing debug in menu does not impact logging, '
                                           'Change in Config a re-launch for that.')
                self.debug = not self.debug
                return
            elif self.exec_shell_cmd(choice):
                return
            # DEBUG Func to print attributes/function returns
            elif '.' in choice and self.print_attribute(choice, locs):
                return
            menu.menu_rows = 0  # TODO REMOVE AFTER SIMPLIFIED
            return choice
        except (KeyboardInterrupt, EOFError):
            if terminate:
                print('Exiting based on User Input')
                self.exit()
            else:
                menu.error_msgs.append('Operation Aborted')
                print('')  # prevents header and prompt on same line in debug
                return ''

    # ------ // DLI WEB POWER SWITCH MENU \\ ------ #
    def dli_menu(self, calling_menu='power_menu'):
        cpi = self.cpi
        pwr = cpi.pwr
        menu_actions = {
            'b': self.power_menu,
            'x': self.exit,
            'dli_menu': self.dli_menu,
            'power_menu': self.power_menu
        }
        # states = self.states
        choice = ''
        if not cpi.pwr_init_complete:
            with Halo(text='Waiting for Outlet init Threads to Complete...',
                      spinner='dots'):
                cpi.wait_for_threads('init')

        if not pwr.dli_exists:
            cpi.error_msgs.append('All Defined dli Web Power Switches are unreachable')
            return

        dli_dict = pwr.data['dli_power']
        while choice not in ['x', 'b']:
            index = start = 1
            outer_body = []
            slines = []
            for dli in sorted(dli_dict):
                state_list = []
                mlines = []
                port_dict = dli_dict[dli]
                # strip off all but hostname if address is fqdn
                host_short = dli.split('.')[0] if '.' in dli and not dli.split('.')[0].isdigit() else dli

                # -- // MENU ITEMS LOOP \\ --
                for port in port_dict:
                    pname = port_dict[port]['name']
                    cur_state = port_dict[port]['state']
                    state_list.append(cur_state)
                    to_state = not cur_state
                    on_pad = ' ' if cur_state else ''
                    mlines.append('[{}] {}{}{}'.format(
                        self.states[cur_state], on_pad, 'P' + str(port) + ': ' if port != index else '', pname))
                    menu_actions[str(index)] = {
                        'function': pwr.pwr_toggle,
                        'args': ['dli', dli],
                        'kwargs': {'port': port, 'desired_state': to_state},
                        'key': 'dli_pwr'
                        }
                    menu_actions['c' + str(index)] = {
                        'function': pwr.pwr_cycle,
                        'args': ['dli', dli],
                        'kwargs': {'port': port},
                        'key': 'dli_pwr'
                        }
                    menu_actions['r' + str(index)] = {
                        'function': pwr.pwr_rename,
                        'args': ['dli', dli],
                        'kwargs': {'port': port},
                        'key': 'dli_pwr'
                        }
                    index += 1

                # add final entry for all operations
                if True not in state_list:
                    _line = 'ALL {{green}}ON{{norm}}'
                    desired_state = True
                elif False not in state_list:
                    _line = 'ALL {{red}}OFF{{norm}}'
                    desired_state = False
                else:
                    _line = 'ALL [on|off]. i.e. "{} off"'.format(index)
                    desired_state = None
                # build appropriate menu_actions item will represent ALL ON or ALL OFF if current state
                # of all outlets is the inverse
                # if there is a mix item#+on or item#+off will both be valid but item# alone will not.
                if desired_state in [True, False]:
                    menu_actions[str(index)] = {
                        'function': pwr.pwr_toggle,
                        'args': ['dli', dli],
                        'kwargs': {'port': 'all', 'desired_state': desired_state},
                        'key': 'dli_pwr'
                        }
                elif desired_state is None:
                    for s in ['on', 'off']:
                        desired_state = True if s == 'on' else False
                        menu_actions[str(index) + ' ' + s] = {
                            'function': pwr.pwr_toggle,
                            'args': ['dli', dli],
                            'kwargs': {'port': 'all', 'desired_state': desired_state},
                            'key': 'dli_pwr'
                            }
                mlines.append(_line)
                index += 1

                # Add cycle line if any outlets are currently ON
                if True in state_list:
                    mlines.append('Cycle ALL')
                    menu_actions[str(index)] = {
                        'function': pwr.pwr_cycle,
                        'args': ['dli', dli],
                        'kwargs': {'port': 'all'},
                        'key': 'dli_pwr'
                        }
                index = start + 10
                start += 10

                outer_body.append(mlines)   # list of lists where each list = printed menu lines
                slines.append(host_short)   # list of strings index to index match with body list of lists

            header = 'DLI Web Power Switch'
            footer = {'opts': ['back', 'refresh']}
            footer['rjust'] = {
                'back': 'menu # alone will toggle the port,',
                'refresh': 'c# to cycle or r# to rename [i.e. \'c1\']'
            }
            if (not calling_menu == 'power_menu' and pwr.data) and (pwr.gpio_exists or pwr.tasmota_exists or pwr.linked_exists):
                menu_actions['p'] = self.power_menu
                footer['opts'].insert(0, 'power')
                footer['overrides'] = {'power': ['p', 'Power Control Menu (linked, GPIO, tasmota)']}

            # for dli menu remove any tasmota errors
            for _error in cpi.error_msgs:
                if 'TASMOTA' in _error:
                    cpi.error_msgs.remove(_error)

            self.print_menu(outer_body, header=header, footer=footer, subs=slines,
                            force_cols=True, by_tens=True)

            choice = self.wait_for_input(locs=locals())
            if choice == 'r':
                self.spin.start('Refreshing Outlets')
                dli_dict = cpi.outlet_update(refresh=True, key='dli_power')
                self.spin.succeed()
            elif choice == 'b':
                return
            else:
                self.exec_menu(choice, menu_actions, calling_menu='dli_menu')

    def key_menu(self):
        cpi = self.cpi
        config = cpi.config
        rem = cpi.remotes.data
        choice = ''
        menu_actions = {
            'b': self.main_menu,
            'x': self.exit,
            'key_menu': self.key_menu
        }
        while choice.lower() not in ['x', 'b']:
            header = ' Remote SSH Key Distribution Menu '

            # Build menu items for each serial adapter found on remote ConsolePis
            item = 1
            all_list = []
            mlines = []
            subs = ['Send SSH Public Key to...']
            for host in sorted(rem):
                if 'rem_ip' not in rem[host]:
                    config.log.warning('[KEY_MENU] {} lacks rem_ip skipping'.format(host))
                    continue

                rem_ip = rem[host].get('rem_ip')
                if rem_ip:
                    rem_user = rem[host].get('user', config.static.get('FALLBACK_USER', 'pi'))
                    mlines.append(f'{host} @ {rem_ip}')
                    this = (host, rem_ip, rem_user)
                    menu_actions[str(item)] = {'function': cpi.gen_copy_key, 'args': [this]}
                    all_list.append(this)
                    item += 1

            # -- all option to loop through all remotes and deploy keys --
            footer = {'opts': 'back',
                      'before': ['a.  {{cyan}}*all*{{norm}} remotes listed above', '']}
            menu_actions['a'] = {'function': cpi.gen_copy_key, 'args': [all_list]}
            self.print_menu(mlines, subs=subs, header=header, footer=footer, do_format=False)
            choice = self.wait_for_input(locs=locals())

            self.exec_menu(choice, menu_actions, calling_menu='key_menu')

    def gen_adapter_lines(self, adapters, item=1, remote=False, rem_user=None, host=None, rename=False):
        cpi = self.cpi
        config = cpi.config
        rem = cpi.remotes.data
        utils = cpi.utils
        menu_actions = {}
        mlines = []
        flow_pretty = self.flow_pretty

        # If remotes present adapter data in old format convert to new
        if isinstance(adapters, list):
            adapters = {adapters[adapters.index(d)]['dev']: {'config': {k: adapters[adapters.index(d)][k]
                        for k in adapters[adapters.index(d)]}} for d in adapters}

        # -- // Manually Defined Hosts \\ --
        elif adapters.get('_hosts'):
            for h in adapters['_hosts']:
                menu_line = adapters['_hosts'][h].get('menu_line')
                if not menu_line:
                    host_pretty = h.replace('/host/', '')
                    _addr = adapters['_hosts'][h]['address']
                    if ':' in _addr:
                        _a, _p = _addr.split(':')
                        _a = utils.get_host_short(_a)
                        _m = adapters['_hosts'][h].get('method')
                        _addr = _a if (_m == 'telnet' and _p == '23') or \
                            (_m == 'ssh' and _p == '22') else f'{_a}:{_p}'
                    menu_line = f'{host_pretty} @ {_addr}'
                mlines.append(menu_line)
                menu_actions[str(item)] = {'cmd': adapters['_hosts'][h].get('cmd'), 'exec_kwargs': {'tee_stderr': True}}
                item += 1

            return mlines, menu_actions, item

        for _dev in sorted(adapters.items(), key=lambda i: i[1]['config'].get('port', 0)):
            this_dev = adapters[_dev[0]].get('config', adapters[_dev[0]])
            if this_dev.get('port', 0) != 0:
                def_indicator = ''
            else:
                def_indicator = '**'
                self.display_con_settings = True
            baud = this_dev.get('baud', self.baud)
            dbits = this_dev.get('dbits', 8)
            flow = this_dev.get('flow', 'n')
            parity = this_dev.get('parity', 'n')
            sbits = this_dev.get('sbits', 1)
            dev_pretty = _dev[0].replace('/dev/', '')

            # Generate Menu Line
            menu_line = f'{dev_pretty} {def_indicator}[{baud} {dbits}{parity[0].upper()}{sbits}]'
            if flow != 'n' and flow in flow_pretty:
                menu_line += f' {flow_pretty[flow]}'
            mlines.append(menu_line)

            # -- // LOCAL ADAPTERS \\ --
            if not remote:
                # Generate connect command used to connect to device
                fallback_cmd = f'picocom {this_dev} --baud {baud} --flow {flow} --databits {dbits} --parity {parity}'
                _cmd = this_dev.get('cmd', fallback_cmd)
                if not rename:
                    menu_actions[str(item)] = {'cmd': _cmd, 'pwr_key': _dev[0]}
                else:
                    rn_this = {_dev[0]: adapters[_dev[0]]}
                    menu_actions[str(item)] = {'function': self.do_rename_adapter, 'args': [_dev[0]]}
                    menu_actions['s' + str(item)] = {'function': cpi.show_adapter_details, 'args': [rn_this]}
                    menu_actions['c' + str(item)] = {'cmd': _cmd}

            # -- // REMOTE ADAPTERS \\ --
            # TODO can just make the command once and prepend remote bit for remotes.
            else:
                if not rem_user:  # the user advertised by the remote we ssh to the remote with this user
                    rem_user = config.FALLBACK_USER

                # Generate connect command used to connect to remote device
                fallback_cmd = f'sudo -u {config.loc_user} ssh -t {rem_user}@{rem[host].get("rem_ip")} \"{config.REM_LAUNCH}' \
                               f' picocom {_dev[0]} --baud {baud} --flow {flow} --databits {dbits} --parity {parity}\"'
                _cmd = this_dev.get('cmd', fallback_cmd)
                menu_actions[str(item)] = {'cmd': _cmd}
            item += 1

        return mlines, menu_actions, item

    def rename_menu(self, direct_launch=False):
        cpi = self.cpi
        local = cpi.local
        choice = ''
        menu_actions = {}
        while choice not in ['b']:
            if choice == 'r':
                local.adapters = local.build_adapter_dict(refresh=True)
            loc = local.adapters

            slines = []
            mlines, menu_actions, item = self.gen_adapter_lines(loc, rename=True)

            if not mlines:
                cpi.error_msgs.append('No Local Adapters')
                break

            slines.append('Select Adapter to Rename')   # list of strings index to index match with body list of lists
            footer = {'before': [
                's#. Show details for the adapter i.e. \'s1\'',
                'c#. Connect to the device i.e. \'c1\'',
                '',
                'The system is updated with new adapter(s) when you leave this menu.',
                ''
            ], 'opts': []}
            if not direct_launch:
                footer['opts'].append('back')

            footer['opts'].append('refresh')
            menu_actions['r'] = None

            self.print_menu(mlines, header='Define/Rename Local Adapters', footer=footer, subs=slines, do_format=False)
            menu_actions['x'] = self.exit

            choice = self.wait_for_input(lower=True, locs=locals())
            if choice in menu_actions:
                if not choice == 'b':
                    self.exec_menu(choice, menu_actions, calling_menu='rename_menu')
            else:
                if choice:
                    if choice != 'b' or direct_launch:
                        cpi.error_msgs.append('Invalid Selection \'{}\''.format(choice))

        # trigger refresh udev and restart ser2net after rename
        if self.udev_pending:
            error = self.trigger_udev()
            cpi.error_msgs.append(error)

    # ------ // MAIN MENU \\ ------ #
    def main_menu(self):
        cpi = self.cpi
        config = cpi.config
        remotes = cpi.remotes
        loc = cpi.local.adapters
        pwr = cpi.pwr
        rem = remotes.data
        outer_body = []
        slines = []
        item = 1

        menu_actions = {
            'h': self.picocom_help,
            'r': remotes.refresh,
            'x': self.exit,
            'sh': cpi.launch_shell
        }
        if config.power and pwr.data:
            if pwr.linked_exists or pwr.gpio_exists or pwr.tasmota_exists:
                menu_actions['p'] = self.power_menu
            elif pwr.dli_exists:  # if no linked outlets but dlis defined p sends to dli_menu
                menu_actions['p'] = self.dli_menu

            if pwr.dli_exists:
                menu_actions['d'] = self.dli_menu

        # DIRECT LAUNCH TO POWER IF NO ADAPTERS (given there are outlets)
        if not loc and not rem and config.power:
            cpi.error_msgs.append('No Adapters Found, Outlets Defined... Launching to Power Menu')
            cpi.error_msgs.append('use option "b" to access main menu options')
            if pwr.dli_exists and not pwr.linked_exists:
                self.exec_menu('d', menu_actions)
            else:
                self.exec_menu('p', menu_actions)

        # Build menu items for each locally connected serial adapter
        if loc:
            mlines, loc_menu_actions, item = self.gen_adapter_lines(loc)
            if loc_menu_actions:
                menu_actions = {**loc_menu_actions, **menu_actions}

            outer_body.append(mlines)   # list of lists where each list = printed menu lines
            slines.append('[LOCAL] Directly Connected')   # Sub-heads: list of str idx to idx match with outer_body list of lists

        # Build menu items for each serial adapter found on remote ConsolePis
        for host in sorted(rem):
            if rem[host].get('rem_ip') and len(rem[host]['adapters']) > 0:
                remotes.connected = True
                mlines, rem_menu_actions, item = self.gen_adapter_lines(rem[host]['adapters'], item=item, remote=True,
                                                                        rem_user=rem[host].get('rem_user'), host=host)
                if rem_menu_actions:
                    menu_actions = {**menu_actions, **rem_menu_actions}

                outer_body.append(mlines)
                slines.append('[Remote] {} @ {}'.format(host, rem[host]['rem_ip']))

        # Build menu items for each manually defined host with show_in_main = True
        # TODO add background reachability check
        if config.hosts and config.hosts.get('main'):
            hosts = config.hosts['main']
            for g in hosts:
                mlines, host_menu_actions, item = self.gen_adapter_lines({'_hosts': hosts[g]}, item=item, host=g)
                if host_menu_actions:
                    menu_actions = {**menu_actions, **host_menu_actions}

                outer_body.append(mlines)
                slines.append(g)

        # -- // General Menu Command Options \\ --
        text = []
        if self.display_con_settings:
            text.append(f' c.  Change default Serial Settings **[{self.baud} {self.data_bits}{self.parity.upper()}1'
                        f' flow={self.flow_pretty[self.flow]}]')
            menu_actions['c'] = self.con_menu
        text.append(' h.  Display picocom help')

        if config.power:  # and config.outlets is not None:
            if pwr.outlets_exists:
                text.append(' p.  Power Control Menu')
            if pwr.dli_exists:
                text.append(' d.  [dli] Web Power Switch Menu')

        if remotes.connected or config.hosts:
            text.append(' s.  Remote Shell Menu')
            menu_actions['s'] = self.rshell_menu
            if remotes.connected:
                text.append(' k.  Distribute SSH Key to Remote Hosts')
                menu_actions['k'] = self.key_menu

        text.append(' sh. Enter Local Shell')
        if loc:  # and config.root:
            text.append(' rn. Rename Local Adapters')
            menu_actions['rn'] = self.rename_menu
        text.append(' r.  Refresh')

        self.print_menu(outer_body, header='{{cyan}}Console{{red}}Pi{{norm}} {{cyan}}Serial Menu{{norm}}',
                        footer=text, subs=slines, do_format=False)

        choice = self.wait_for_input(locs=locals())
        self.exec_menu(choice, menu_actions)
        return

    # ------ // REMOTE SHELL MENU \\ ------ #
    def rshell_menu(self, do_ssh_hosts=False):
        choice = ''
        cpi = self.cpi
        local = cpi.local
        config = cpi.config
        rem = cpi.remotes.data
        menu_actions = {
            'rshell_menu': self.rshell_menu,
            'b': self.main_menu,
            'x': self.exit
        }

        while choice.lower() not in ['x', 'b']:
            # if not self.DEBUG:
            #     os.system('clear')
            outer_body = []
            mlines = []
            subs = []
            item = 1

            # Build menu items for each reachable remote ConsolePi
            subs.append('Remote ConsolePis')
            for host in sorted(rem):
                if rem[host].get('rem_ip'):
                    mlines.append(f'{host} @ {rem[host]["rem_ip"]}')
                    _rem_user = rem[host].get('user', config.FALLBACK_USER)
                    _cmd = f'sudo -u {local.user} ssh -t {_rem_user}@{rem[host]["rem_ip"]}'
                    menu_actions[str(item)] = {'cmd': _cmd}
                    item += 1
            outer_body.append(mlines)

            # Build menu items for each manually defined host in hosts.json / ConsolePi.yaml
            if config.hosts:
                mlines = []
                for _sub in config.hosts['rshell']:
                    subs.append(_sub)
                    ssh_hosts = config.hosts['rshell'][_sub]
                    for host in sorted(ssh_hosts):
                        r = ssh_hosts[host]
                        if 'address' in r:
                            mlines.append(f"{host.split('/')[-1]} @ {r['address']}")
                            _host = r['address'].split(':')[0]
                            _port = '' if ':' not in r['address'] else r['address'].split(':')[1]
                            if 'method' in r and r['method'].lower() == 'ssh':
                                # configure fallback command
                                _cmd = 'sudo -u {0} ssh -t {3} {1}@{2}'.format(config.loc_user,
                                                                               r.get('username', config.FALLBACK_USER),
                                                                               _host, '' if not _port else '-p {}'.format(_port))
                                _cmd = r.get('cmd', _cmd)
                            elif 'method' in r and r['method'].lower() == 'telnet':
                                # configure fallback command
                                _cmd = 'sudo -u {0} telnet {1} {2}'.format(config.loc_user,
                                                                           r['address'].split(':')[0], _port)
                                _cmd = r.get('cmd', _cmd)
                            menu_actions[str(item)] = {'cmd': _cmd, 'pwr_key': host, 'exec_kwargs': {'tee_stderr': True}}
                            item += 1

                    outer_body.append(mlines)

            text = ' b.  Back'
            self.print_menu(outer_body, header='Remote Shell Menu',
                            subhead='Enter item # to connect to remote',
                            footer=text, subs=subs)
            choice = self.wait_for_input(locs=locals())
            self.exec_menu(choice, menu_actions, calling_menu='rshell_menu')

    # ------ // EXECUTE MENU SELECTIONS \\ ------ #
    def exec_menu(self, choice, menu_actions, calling_menu='main_menu'):
        cpi = self.cpi
        pwr = cpi.pwr
        config = cpi.config
        utils = cpi.utils
        if not self.debug and calling_menu not in ['dli_menu', 'power_menu']:
            os.system('clear')

        if not choice or choice.lower() in menu_actions and menu_actions[choice.lower()] is None:
            self.menu.rows, self.menu.cols = utils.get_tty_size()  # re-calc tty size in case they've adjusted the window
            # self.cpi.local.adapters = self.cpi.local.build_adapter_dict(refresh=True)  # always refresh local adapters
            return

        if choice.lower() == 'exit':
            self.exit()
        else:
            ch = choice.lower()
            try:  # Invalid Selection
                if isinstance(menu_actions[ch], dict):
                    if menu_actions[ch].get('cmd'):
                        # TimeStamp for picocom session log file if defined
                        menu_actions[ch]['cmd'] = menu_actions[ch]['cmd'].replace('{{timestamp}}', time.strftime('%F_%H.%M'))

                        # -- // AUTO POWER ON LINKED OUTLETS \\ --
                        if config.power and 'pwr_key' in menu_actions[ch]:  # pylint: disable=maybe-no-member
                            cpi.exec_auto_pwron(menu_actions[ch]['pwr_key'])

                        # --// execute the command \\--
                        try:
                            _error = None
                            if 'exec_kwargs' in menu_actions[ch]:
                                c = menu_actions[ch]['cmd']
                                _error = utils.do_shell_cmd(c, **menu_actions[ch]['exec_kwargs'])
                            else:
                                c = shlex.split(menu_actions[ch]['cmd'])
                                result = subprocess.run(c, stderr=subprocess.PIPE)
                                _stderr = result.stderr.decode('UTF-8')
                                if _stderr or result.returncode == 1:
                                    _error = utils.error_handler(c, _stderr)

                            if _error:
                                self.cpi.error_msgs.append(_error)

                            # -- // resize the terminal to handle serial connections that jack the terminal size \\ --
                            c = ' '.join([str(i) for i in c])
                            if 'picocom' in c:  # pylint: disable=maybe-no-member
                                os.system('/etc/ConsolePi/src/consolepi-commands/resize >/dev/null')

                        except KeyboardInterrupt:
                            self.error_msgs.append('Aborted last command based on user input')

                    elif 'function' in menu_actions[ch]:
                        args = menu_actions[ch]['args'] if 'args' in menu_actions[ch] else []
                        kwargs = menu_actions[ch]['kwargs'] if 'kwargs' in menu_actions[ch] else {}
                        confirmed, spin_text, name = self.confirm_and_spin(menu_actions[ch], *args, **kwargs)
                        if confirmed:
                            # update kwargs with name from confirm_and_spin method
                            if menu_actions[ch]['function'].__name__ == 'pwr_rename':
                                kwargs['name'] = name

                            # // -- CALL THE FUNCTION \\--
                            if spin_text:  # start spinner if spin_text set by confirm_and_spin
                                with Halo(text=spin_text, spinner='dots2'):
                                    response = menu_actions[ch]['function'](*args, **kwargs)
                            else:  # no spinner
                                response = menu_actions[ch]['function'](*args, **kwargs)

                            # --// Power Menus \\--
                            if calling_menu in ['power_menu', 'dli_menu']:
                                if menu_actions[ch]['function'].__name__ == 'pwr_all':
                                    with Halo(text='Refreshing Outlet States', spinner='dots'):
                                        cpi.outlet_update(refresh=True, upd_linked=True)  # TODO can I move this to Outlets Class
                                else:
                                    _grp = menu_actions[ch]['key']
                                    _type = menu_actions[ch]['args'][0]
                                    _addr = menu_actions[ch]['args'][1]
                                    # --// EVAL responses for dli outlets \\--
                                    if _type == 'dli':
                                        host_short = utils.get_host_short(_addr)
                                        _port = menu_actions[ch]['kwargs']['port']
                                        # --// Operations performed on ALL outlets \\--
                                        if isinstance(response, bool) and _port is not None:
                                            if menu_actions[ch]['function'].__name__ == 'pwr_toggle':
                                                self.spin.start('Request Sent, Refreshing Outlet States')
                                                # threading.Thread(target=self.get_dli_outlets, kwargs={'upd_linked': True, 'refresh': True}, name='pwr_toggle_refresh').start()
                                                upd_linked = True if calling_menu == 'power_menu' else False  # else dli_menu
                                                threading.Thread(target=cpi.outlet_update, kwargs={'upd_linked': upd_linked, 'refresh': True}, name='pwr_toggle_refresh').start()
                                                if _grp in pwr.data['defined']:
                                                    pwr.data['defined'][_grp]['is_on'][_port]['state'] = response
                                                elif _port != 'all':
                                                    pwr.data['dli_power'][_addr][_port]['state'] = response
                                                else:  # dli toggle all
                                                    for t in threading.enumerate():
                                                        if t.name == 'pwr_toggle_refresh':
                                                            t.join()    # if refresh thread is running join ~ wait for it to complete.
                                                            # TODO Don't think this works or below
                                                            # wouldn't have been necessary.

                                                            # toggle all returns True (ON) or False (OFF) if command successfully sent.  In reality the ports
                                                            # may not be in the  state yet, but dli is working it.  Update menu items to reflect end state
                                                            for p in pwr.data['dli_power'][_addr]:
                                                                pwr.data['dli_power'][_addr][p]['state'] = response
                                                            break
                                                self.spin.stop()
                                            # Cycle operation returns False if outlet is off, only valid on powered outlets
                                            elif menu_actions[ch]['function'].__name__ == 'pwr_cycle' and not response:
                                                self.error_msgs.append('{} Port {} if Off.  Cycle is not valid'.format(host_short, _port))
                                            elif menu_actions[ch]['function'].__name__ == 'pwr_rename':
                                                if response:
                                                    _name = pwr._dli[_addr].name(_port)
                                                    if _grp in pwr.data.get('defined', {}):
                                                        pwr.data['defined'][_grp]['is_on'][_port]['name'] = _name
                                                    else:
                                                        # threading.Thread(target=self.get_dli_outlets, kwargs={'upd_linked': True, 'refresh': True}, name='pwr_rename_refresh').start()
                                                        threading.Thread(target=cpi.outlet_update, kwargs={'upd_linked': True, 'refresh': True}, name='pwr_rename_refresh').start()
                                                    pwr.data['dli_power'][_addr][_port]['name'] = _name
                                        # --// str responses are errors append to error_msgs \\--
                                        # TODO refactor response to use new cpi.response(...)
                                        elif isinstance(response, str) and _port is not None:
                                            cpi.error_msgs.append(response)
                                        # --// Can Remove After Refactoring all responses to bool or str \\--
                                        elif isinstance(response, int):
                                            if menu_actions[ch]['function'].__name__ == 'pwr_cycle' and _port == 'all':
                                                if response != 200:
                                                    self.error_msgs.append('Error Response Returned {}'.format(response))
                                            else:  # This is a catch as for the most part I've tried to refactor so the pwr library returns port state on success (True/False)
                                                if response in [200, 204]:
                                                    cpi.error_msgs.append('DEV NOTE: check pwr library ret=200 or 204')
                                                else:
                                                    cpi.error_msgs.append('Error returned from dli {} when attempting to {} port {}'.format(
                                                        host_short, menu_actions[ch]['function'].__name__, _port))

                                    # --// EVAL responses for GPIO and tasmota outlets \\--
                                    else:
                                        if menu_actions[ch]['function'].__name__ == 'pwr_toggle':
                                            if _grp in pwr.data.get('defined', {}):
                                                if isinstance(response, bool):
                                                    pwr.data['defined'][_grp]['is_on'] = response
                                                else:
                                                    pwr.data['defined'][_grp]['errors'] = response
                                        elif menu_actions[ch]['function'].__name__ == 'pwr_cycle' and not response:
                                            self.error_msgs.append('Cycle is not valid for Outlets in the off state')
                                        elif menu_actions[ch]['function'].__name__ == 'pwr_rename':
                                            self.error_msgs.append('rename not yet implemented for {} outlets'.format(_type))
                            elif calling_menu in['key_menu', 'rename_menu']:
                                if response:
                                    response = [response] if isinstance(response, str) else response
                                    for _ in response:
                                        if _:  # strips empty lines
                                            cpi.error_msgs.append(_)
                        else:   # not confirmed
                            cpi.error_msgs.append('Operation Aborted by User')
                elif menu_actions[ch].__name__ in ['power_menu', 'dli_menu']:
                    menu_actions[ch](calling_menu=calling_menu)
                else:
                    menu_actions[ch]()
            except KeyError as e:
                cpi.error_msgs.append('Invalid selection {}, please try again.'.format(e))
                return False  # indicates an error
        return True

    def confirm_and_spin(self, action_dict, *args, **kwargs):
        '''
        called by the exec menu.
        Collects user Confirmation if operation warrants it (Powering off or cycle outlets)
        and Generates appropriate spinner text

        returns tuple
            0: Bool True if user confirmed False if aborted (set to True when no confirmation reqd)
            1: str spinner_text used in exec_menu while function runs
            3: str name (for rename operation)
        '''
        pwr = self.cpi.pwr
        utils = self.cpi.utils
        menu = self.menu
        _func = action_dict['function'].__name__
        _off_str = '{{red}}OFF{{norm}}'
        _on_str = '{{green}}ON{{norm}}'
        _cycle_str = '{{red}}C{{green}}Y{{red}}C{{green}}L{{red}}E{{norm}}'
        _type = _addr = None
        if 'desired_state' in kwargs:
            to_state = kwargs['desired_state']
        if _func in ['pwr_toggle', 'pwr_cycle', 'pwr_rename']:
            _type = args[0].lower()
            _addr = args[1]
            _grp = action_dict['key']
            if _type == 'dli':
                port = kwargs['port']
                if not port == 'all':
                    port_name = pwr.data['dli_power'][_addr][port]['name']
                    to_state = not pwr.data['dli_power'][_addr][port]['state']
            else:
                port = f'{_type}:{_addr}'
                port_name = _grp
                to_state = not pwr.data['defined'][_grp]['is_on']
        if _type == 'dli' or _type == 'tasmota' or _type == 'esphome':
            host_short = utils.get_host_short(_addr)
        else:
            host_short = None

        prompt = spin_text = name = confirmed = None  # init
        if _func == 'pwr_all':
            # self.spin.start('Powering *ALL* Outlets {}'.format(self.states[kwargs['desired_state']]))
            if kwargs['action'] == 'cycle':
                prompt = '{} Power Cycle All Powered {} Outlets'.format('' if _type is None else _type + ':' + host_short,
                                                                        _on_str)
                spin_text = 'Cycling All{} Ports'.format('' if _type is None else ' ' + _type + ':' + host_short)
            elif kwargs['action'] == 'toggle':
                if not kwargs['desired_state']:
                    prompt = 'Power All{} Outlets {}'.format('' if _type is None else ' ' + _type + ':' + host_short, _off_str)
                spin_text = 'Powering {} ALL{} Outlets'.format(menu.format_line(kwargs['desired_state']).text,
                                                               '' if _type is None else _type + ' :' + host_short)
        elif _func == 'pwr_toggle':
            if _type == 'dli' and port == 'all':
                prompt = 'Power {} ALL {} Outlets'.format(
                    _off_str if not to_state else _on_str, host_short)
            elif not to_state:
                if _type == 'dli':
                    prompt = f'Power {_off_str} {host_short} Outlet {port}({port_name})'
                else:  # GPIO or TASMOTA
                    prompt = f'Power {_off_str} Outlet {_grp}({_type}:{_addr})'

            spin_text = 'Powering {} {}Outlet{}'.format(menu.format_line(to_state).text,
                                                        'ALL ' if port == 'all' else '',
                                                        's' if port == 'all' else '')
        elif _func == 'pwr_rename':
            try:
                name = input('New name for{} Outlet {}: '.format(
                    ' ' + host_short if host_short else '',
                    port_name if not _type == 'dli' else str(port) + '(' + port_name + ')'))
            except KeyboardInterrupt:
                name = None
                confirmed = False
                print('')  # So header doesn't print on same line as aborted prompt when DEBUG is on
            if name:
                old_name = port_name
                _rnm_str = '{red}{old_name}{norm} --> {green}{name}{norm}'.format(
                    red='{{red}}', green='{{green}}', norm='{{norm}}', old_name=old_name, name=name)
                if _type == 'dli':
                    prompt = 'Rename {} Outlet {}: {} '.format(
                         host_short, port, _rnm_str)
                else:
                    old_name = _grp
                    prompt = 'Rename Outlet {}:{} {} '.format(
                        _type, host_short, _rnm_str)

                spin_text = 'Renaming Port'

        elif _func == 'pwr_cycle':
            if _type == 'dli' and port == 'all':
                prompt = 'Power {} ALL {} Outlets'.format(
                    _cycle_str, host_short)
            elif _type == 'dli':
                prompt = 'Cycle Power on {} Outlet {}({})'.format(
                    host_short, port, port_name)
            else:  # GPIO or TASMOTA
                prompt = 'Cycle Power on Outlet {}({})'.format(
                    port_name, port)
            spin_text = 'Cycling {}Outlet{}'.format('ALL ' if port == 'all' else '', 's' if port == 'all' else '')

        if prompt:
            prompt = menu.format_line(prompt).text
            confirmed = confirmed if confirmed is not None else utils.user_input_bool(prompt)
        else:
            if _func != 'pwr_rename':
                confirmed = True

        return confirmed, spin_text, name

    # Connection SubMenu
    def con_menu(self, rename=False, con_dict=None):
        menu = self.menu
        menu_actions = {
            '1': self.baud_menu,
            '2': self.data_bits_menu,
            '3': self.parity_menu,
            '4': self.flow_menu,
            'b': self.main_menu if not rename else self.do_rename_adapter,  # not used currently
            'x': self.exit
        }
        if con_dict:
            self.con_dict = {
                'baud': self.baud,
                'data_bits': self.data_bits,
                'parity': self.parity,
                'flow': self.flow
            }
            self.baud = con_dict['baud']
            self.data_bits = con_dict['data_bits']
            self.parity = con_dict['parity']
            self.flow = con_dict['flow']

        while True:
            menu.menu_formatting('header', text=' Connection Settings Menu ')
            print('')
            print(' 1. Baud [{}]'.format(self.baud))
            print(' 2. Data Bits [{}]'.format(self.data_bits))
            print(' 3. Parity [{}]'.format(self.parity_pretty[self.parity]))
            print(' 4. Flow [{}]'.format(self.flow_pretty[self.flow]))
            text = ' b.  Back{}'.format(' (Apply Changes to Files)' if rename else '')
            menu.menu_formatting('footer', text=text)

            ch = self.wait_for_input(lower=True, locs=locals())
            try:
                if ch == 'b':
                    break
                menu_actions[ch]()  # could parse and store if decide to use this for something other than rename

            except KeyError as e:
                if ch:
                    self.menu.error_msgs.append('Invalid selection {}, please try again.'.format(e))

    # Baud Menu
    def baud_menu(self):
        config = self.cpi.config
        menu = self.menu
        menu_actions = od([
            ('1', 300),
            ('2', 1200),
            ('3', 9600),
            ('4', 19200),
            ('5', 57600),
            ('6', 115200),
            ('c', 'custom')
        ])
        text = ' b.  Back'
        std_baud = [110, 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200, 128000, 256000]

        while True:
            # -- Print Baud Menu --
            menu.menu_formatting('header', text=' Select Desired Baud Rate ')
            print('')

            for key in menu_actions:
                # if not callable(menu_actions[key]):
                _cur_baud = menu_actions[key]
                print(' {0}. {1}'.format(key, _cur_baud if _cur_baud != self.baud else '[{}]'.format(_cur_baud)))

            menu.menu_formatting('footer', text=text)
            choice = self.wait_for_input(" Baud >>  ", locs=locals())
            ch = choice.lower()

            # -- Evaluate Response --
            try:
                if ch == 'c':
                    while True:
                        self.baud = self.wait_for_input(' Enter Desired Baud Rate >> ')
                        if not self.baud.isdigit():
                            print('Invalid Entry {}'.format(self.baud))
                        elif int(self.baud) not in std_baud:
                            _choice = input(' {} is not a standard baud rate are you sure? (y/n) >> '.format(self.baud)).lower()
                            if _choice not in ['y', 'yes']:
                                break
                        else:
                            break
                elif ch == 'b':
                    break  # return to con_menu
                elif ch == 'x':
                    self.exit()
                else:
                    self.baud = menu_actions[ch]
                    break
            except KeyError as e:
                if choice:
                    self.cpi.error_msgs.append('Invalid selection {} please try again.'.format(e))

        return self.baud

    def data_bits_menu(self):
        menu = self.menu
        valid = False
        while not valid:
            menu.menu_formatting('header', text=' Enter Desired Data Bits ')
            print('\n Default 8, Current [{}], Valid range 5-8'.format(self.data_bits))
            menu.menu_formatting('footer', text=' b.  Back')
            choice = self.wait_for_input(' Data Bits >>  ', locs=locals())
            try:
                if choice.lower() == 'x':
                    self.exit()
                elif choice.lower() == 'b':
                    valid = True
                elif int(choice) >= 5 and int(choice) <= 8:
                    self.data_bits = choice
                    valid = True
                else:
                    self.cpi.error_msgs.append('Invalid selection {} please try again.'.format(choice))
            except ValueError:
                if choice:
                    self.cpi.error_msgs.append('Invalid selection {} please try again.'.format(choice))

        return self.data_bits

    def parity_menu(self):
        menu = self.menu

        def print_menu():
            menu.menu_formatting('header', text=' Select Desired Parity ')
            print('\n Default No Parity\n')
            print(f" 1. {'[None]' if self.parity == 'n' else 'None'}")
            print(f" 2. {'[Odd]' if self.parity == 'o' else 'Odd'}")
            print(f" 3. {'[Even]' if self.parity == 'e' else 'Even'}")
            text = ' b.  Back'
            menu.menu_formatting('footer', text=text)
        valid = False
        while not valid:
            print_menu()
            valid = True
            choice = self.wait_for_input(' Parity >> ', lower=True, locs=locals())
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
                if choice:
                    self.cpi.error_msgs.append('Invalid selection {} please try again.'.format(choice))
        return self.parity

    def flow_menu(self):
        menu = self.menu

        def print_menu():
            menu.menu_formatting('header', text=' Select Desired Flow Control ')
            print('')
            print(' Default No Flow\n')
            print(f" 1. {'[None]' if self.flow == 'n' else 'None'}")
            print(f" 2. {'[Xon/Xoff]' if self.flow == 'x' else 'Xon/Xoff'} (software)")
            print(f" 3. {'[RTS/CTS]' if self.flow == 'h' else 'RTS/CTS'} (hardware)")
            text = ' b.  Back'
            menu.menu_formatting('footer', text=text)
        valid = False
        while not valid:
            print_menu()
            choice = self.wait_for_input(' Flow >>  ', lower=True, locs=locals())
            if choice in ['1', '2', '3', 'b', 'x']:
                valid = True
            try:
                if choice == '1':
                    self.flow = 'n'
                elif choice == '2':
                    self.flow = 'x'
                elif choice == '3':
                    self.flow = 'h'
                elif choice == 'b':
                    pass
                elif choice == 'x':
                    self.exit()
                else:
                    if choice:
                        self.cpi.error_msgs.append('Invalid selection {} please try again.'.format(choice))
            except Exception as e:
                if choice:
                    self.cpi.error_msgs.append('Invalid selection {} please try again.'.format(e))

        return self.flow

    # -- // Exit The Menu \\ --
    def exit(self):
        self.go = False
        cpi = self.cpi
        if cpi.pwr._dli:
            for address in cpi.pwr._dli:
                if cpi.pwr._dli[address].dli:
                    if getattr(cpi.pwr._dli[address], 'rest'):
                        threading.Thread(target=cpi.pwr._dli[address].dli.close).start()
                    else:
                        threading.Thread(target=cpi.pwr._dli[address].dli.session.close).start()
        # - if exit directly from rename menu after performing a rename trigger / reload udev
        if self.udev_pending:
            cmd = 'sudo udevadm control --reload && sudo udevadm trigger && '\
                  'sudo systemctl stop ser2net && sleep 1 && sudo systemctl start ser2net '
            with Halo(text='Triggering reload of udev do to name change', spinner='dots1'):
                error = cpi.utils.do_shell_cmd(cmd, shell=True)
            if error:
                print(error)

        sys.exit(0)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ['rn', 'rename', 'addconsole']:
            menu = ConsolePiMenu(bypass_remote=True)
            while menu.go:
                menu.rename_menu(direct_launch=True)
        else:
            menu = ConsolePiMenu(bypass_remote=True)
            var_in = sys.argv[1].replace('self', 'menu')
            if 'outlet' in var_in:
                menu.cpi.wait_for_threads()
            menu.print_attribute(var_in)
    else:
        # -- // LAUNCH MENU \\ --
        menu = ConsolePiMenu()
        while menu.go:
            menu.main_menu()
        print('hit')  # DEBUG
        menu.exit()
