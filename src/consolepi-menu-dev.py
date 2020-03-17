#!/etc/ConsolePi/venv/bin/python

import json
import readline # NoQA - allows input to accept backspace
import sys
import re
import threading
import itertools
from collections import OrderedDict as od
from halo import Halo

# --// ConsolePi imports \\--
sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi.consolepi import ConsolePi  # NoQA
from consolepi.udevrename import Rename  # NoQA
from consolepi import log, utils, config  # NoQA
# from consolepi.gdrive import GoogleDrive # <-- hidden import burried in refresh method of consolepi.remotes.Remotes(...).refresh

MIN_WIDTH = 55
MAX_COLS = 5


class ConsolePiMenu(Rename):

    def __init__(self, bypass_remotes=False):
        self.cpi = ConsolePi(bypass_remotes=bypass_remotes)
        self.cpiexec = self.cpi.cpiexec
        self.baud = config.default_baud
        self.go = True
        self.spin = Halo(spinner='dots')
        self.states = {
            True: '{{green}}ON{{norm}}',
            False: '{{red}}OFF{{norm}}'
        }
        self.log_sym_2bang = '\033[1;33m!!\033[0m'
        self.display_con_settings = False
        self.menu = self.cpi.menu
        self.menu.ignored_errors = [
            re.compile('Connection to .* closed')
        ]
        self.do_menu_load_warnings()
        super().__init__()

    def print_attribute(self, ch, locs={}):
        '''Debugging Function allowing user to print class attributes / function returns.

        Params:
            ch {str}: the input from user prompt
            locs: locals() from calling function

        Returns:
            Bool | None -- True if ch is an attribute No return otherwise
        '''
        _attrs = [a for a in self.cpi.__dir__() if not a.startswith('_')]
        _attrs += ['cpi', 'this', 'self', 'menu', 'cloud', 'config', 'log']
        if '.' in ch and len(ch) > 2 and ch.split('.')[0] in _attrs:
            cpi = self.cpi
            cpiexec = cpi.cpiexec  # NoQA
            local = cpi.local  # NoQA
            if hasattr(cpi, 'remotes'):
                remotes = cpi.remotes
                cloud = remotes.cloud  # NoQA
            pwr = cpi.pwr  # NoQA
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
                try:
                    exec(f"self._class = {_class_str}")
                    if hasattr(self._class, _attr):  # NoQA
                        _var = f"self.var = {ch}"
                    else:
                        log.show(f"DEBUG: '{_class_str}' object has no attribute '{_attr}'")
                        return True
                except AttributeError as e:
                    log.show(f'DEBUG: Attribute error {e}')

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
                                try:
                                    if 'function' in var[k]:
                                        var[k]['function'] = f"{_class_str}{var[k]['function'].__name__}()"
                                except TypeError:
                                    continue
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
                    log.show(f'DEBUG: {e}')
                return True

    def do_menu_load_warnings(self):
        '''Displays warnings based on data collected/validated during menu load.'''

        # -- // Not running as root \\ --
        if not config.root:
            log.show('Running without sudo privs ~ Results may vary!\n'
                     'Use consolepi-menu to launch menu')

        # -- // No Local Adapters Found \\ --
        if not self.cpi.local.adapters:
            log.show('No Local Adapters Detected')

    def picocom_help(self):
        print('----------------------- picocom Command Sequences -----------------------\n')
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
        print('\n-------------------------------------------------------------------------\n')
        input('Press Enter to Continue... ')

    # -- // POWER MENU \\ --
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
                self.cpiexec.wait_for_threads()
                outlets = pwr.data['defined']
        else:
            outlets = self.cpiexec.outlet_update()

        if not outlets:
            log.show('No Linked Outlets are connected')
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
                        log.show(f'{r} - {pwr.data["defined"][r]["errors"]}')
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
                            log.show(f"DEV NOTE {r} outlet state is not bool: {outlet['error']}")

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

            menu.print_menu(body, header=header, subhead=subhead, footer=footer)
            choice_c = self.wait_for_input(locs=locals())
            choice = choice_c.lower
            if choice not in ['b', 'r']:
                cpi.cpiexec.menu_exec(choice_c, menu_actions, calling_menu='power_menu')
            elif choice == 'b':
                return
            elif choice == 'r':
                if pwr.dli_exists:
                    with Halo(text='Refreshing Outlets', spinner='dots'):
                        outlets = self.cpiexec.outlet_update(refresh=True, upd_linked=True)

    def wait_for_input(self, prompt=" >> ", terminate=False, locs={}):
        '''Get input from user.

        User Can Input One of the following for special handling:
        'debug': toggles debug (menu only doens't effect logging)
        'exit': exits the program
        a 3+ character string with '.' in it:  Which results in the print_attribute
        debug function being called.

        Other than exit, Any user input matching the above will result in a '' string
        being returned which results in a menu re-print.

        Keyword Arguments:
            prompt {str} -- input prompt (default: {" >> "})
            lower {bool} -- return lower case user input (default: {True})
            terminate {bool} -- terminates program if Ctrl+C/Ctrl+D (default: {False})
            locs {dict} -- locals from calling func for use in debug print func (default: {{}})

        Returns:
            str -- If user input is not 'exit' (which exits the program) will return an
                   empty str if pre-processed by one of the common funcs
                   otherwise returns the input provided by the user (lower() by default).
        '''
        menu = self.menu

        class choice():
            def __init__(self, clear=False):
                if not clear:
                    ch = input(prompt)
                    self.lower = ch.lower()
                    self.orig = ch
                else:
                    self.lower = ''
                    self.orig = ''

        try:
            if config.debug:
                menu.menu_rows += 1  # TODO REMOVE AFTER SIMPLIFIED
                prompt = f' m[r:{menu.menu_rows}, c:{menu.menu_cols}] a[r:{menu.rows}, c:{menu.cols}]{prompt}'

            ch = choice()

            # -- // toggle debug \\ --
            if ch.lower == 'debug':
                log.show(f'debug toggled {self.states[config.debug]} --> {self.states[not config.debug]}')
                config.debug = not config.debug
                if config.debug:
                    log.setLevel(10)  # logging.DEBUG = 10
                ch = choice(clear=True)

            # -- // always accept 'exit' \\ --
            elif ch.lower == 'exit':
                self.exit()

            # -- // Menu Debugging Tool prints attributes/function returns \\ --
            elif '.' in ch.orig and self.print_attribute(ch.orig, locs):
                ch = choice(clear=True)
            # else:
                # return user input back to calling function
            menu.menu_rows = 0  # TODO REMOVE AFTER SIMPLIFIED

            return ch

        except (KeyboardInterrupt, EOFError):
            if terminate:
                print('Exiting based on User Input')
                self.exit()
            else:
                log.show('Operation Aborted')
                print('')  # prevents header and prompt on same line in debug
                return choice(clear=True)

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
                self.cpiexec.wait_for_threads('init')

        if not pwr.dli_exists:
            log.show('All Defined dli Web Power Switches are unreachable')
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
            subhead = ['enter item # to toggle power state on outlet']
            if True in state_list:
                subhead.append('enter c + item # i.e. "c2" to cycle power on outlet')
            subhead.append('enter r + item # i.e. "r2" to rename the outlet')

            footer = {'opts': ['back', 'refresh']}
            if (not calling_menu == 'power_menu' and pwr.data) and (pwr.gpio_exists or pwr.tasmota_exists or pwr.linked_exists):
                menu_actions['p'] = self.power_menu
                footer['opts'].insert(0, 'power')
                footer['overrides'] = {'power': ['p', 'Power Control Menu (linked, GPIO, tasmota)']}

            # for dli menu remove any tasmota errors
            for _error in log.error_msgs:
                if 'TASMOTA' in _error:
                    log.error_msgs.remove(_error)

            self.menu.print_menu(outer_body, header=header, subhead=subhead, footer=footer, subs=slines,
                                 force_cols=True, by_tens=True)

            choice_c = self.wait_for_input(locs=locals())
            choice = choice_c.lower
            if choice == 'r':
                self.spin.start('Refreshing Outlets')
                dli_dict = self.cpiexec.outlet_update(refresh=True, key='dli_power')
                self.spin.succeed()
            elif choice == 'b':
                return
            else:
                cpi.cpiexec.menu_exec(choice_c, menu_actions, calling_menu='dli_menu')

    def key_menu(self):
        cpi = self.cpi
        # config = cpi.config
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
                    log.warning('[KEY_MENU] {} lacks rem_ip skipping'.format(host))
                    continue

                rem_ip = rem[host].get('rem_ip')
                if rem_ip:
                    rem_user = rem[host].get('user', config.static.get('FALLBACK_USER', 'pi'))
                    mlines.append(f'{host} @ {rem_ip}')
                    this = (host, rem_ip, rem_user)
                    menu_actions[str(item)] = {'function': self.cpiexec.gen_copy_key, 'args': [this]}
                    all_list.append(this)
                    item += 1

            # -- all option to loop through all remotes and deploy keys --
            footer = {'opts': 'back',
                      'before': ['a.  {{cyan}}*all*{{norm}} remotes listed above', '']}
            menu_actions['a'] = {'function': self.cpiexec.gen_copy_key, 'args': [all_list]}
            self.menu.print_menu(mlines, subs=subs, header=header, footer=footer, do_format=False)
            choice_c = self.wait_for_input(locs=locals())
            choice = choice_c.lower

            cpi.cpiexec.menu_exec(choice_c, menu_actions, calling_menu='key_menu')

    def gen_adapter_lines(self, adapters, item=1, remote=False, rem_user=None, host=None, rename=False):
        cpi = self.cpi
        if hasattr(cpi, 'remotes'):
            rem = cpi.remotes.data
        else:
            rem = {}
        menu_actions = {}
        mlines = []
        flow_pretty = self.flow_pretty

        # -- // Manually Defined Hosts \\ --
        if adapters.get('_hosts'):
            for h in adapters['_hosts']:
                menu_line = adapters['_hosts'][h].get('menu_line')
                if not menu_line:
                    host_pretty = h.replace('/host/', '')
                    _addr = adapters['_hosts'][h]['address']
                    _m = adapters['_hosts'][h].get('method')
                    if ':' in _addr:
                        _a, _p = _addr.split(':')
                        _a = utils.get_host_short(_a)
                        _addr = _a if (_m == 'telnet' and _p == '23') or \
                            (_m == 'ssh' and _p == '22') else f'{_a}:{_p}'
                    menu_line = f'{host_pretty} @ {_addr}'
                mlines.append(menu_line)
                menu_actions[str(item)] = {'cmd': adapters['_hosts'][h].get('cmd'),
                                           'exec_kwargs': {'tee_stderr': True}, 'pwr_key': h,
                                           'pre_msg': f"Establishing {_m} session To {host_pretty}..."}
                item += 1

            return mlines, menu_actions, item

        # -- // Local Adapters \\ --
        for _dev in sorted(adapters.items(), key=lambda i: i[1]['config'].get('port', 0)):
            dev = _dev[0]
            cfg_dict = adapters[dev].get('config', adapters[dev])
            if cfg_dict.get('port', 0) != 0:
                def_indicator = ''
            else:
                def_indicator = '**'
                self.display_con_settings = True
            baud = cfg_dict.get('baud', self.baud)
            dbits = cfg_dict.get('dbits', 8)
            flow = cfg_dict.get('flow', 'n')
            parity = cfg_dict.get('parity', 'n')
            sbits = cfg_dict.get('sbits', 1)
            dev_pretty = dev.replace('/dev/', '')

            # Generate Adapter Menu Line
            menu_line = f'{dev_pretty} {def_indicator}[{baud} {dbits}{parity[0].upper()}{sbits}]'
            if flow != 'n' and flow in flow_pretty:
                menu_line += f' {flow_pretty[flow]}'
            mlines.append(menu_line)

            # fallback_cmd should never be used as the cmd should always be in the dev dict
            loc_cmd = f'picocom {dev} --baud {baud} --flow {flow} --databits {dbits} --parity {parity}'
            # -- // Adapter menu_actions \\ --
            if not remote:
                # Generate connect command used to connect to device
                _cmd = cfg_dict.get('cmd', loc_cmd)
                if not rename:
                    menu_actions[str(item)] = {'cmd': _cmd, 'pwr_key': dev,
                                               'pre_msg': f"Connecting To {dev_pretty}..."}
                else:
                    rn_this = {dev: adapters[dev]}
                    menu_actions[str(item)] = {'function': self.do_rename_adapter, 'args': [dev]}
                    menu_actions['s' + str(item)] = {'function': self.cpiexec.show_adapter_details, 'args': [rn_this]}
                    menu_actions['c' + str(item)] = {'cmd': _cmd, 'pre_msg': f"Connecting To {dev_pretty}..."}

            # -- // REMOTE ADAPTERS \\ --
            else:
                if not rem_user:  # the user advertised by the remote we ssh to the remote with this user
                    rem_user = config.FALLBACK_USER

                # Generate connect command used to connect to remote device
                # TODO simplify once api updated to use new libraries
                rem_pfx = f'sudo -u {config.loc_user} ssh -t {rem_user}@{rem[host].get("rem_ip")}'
                fallback_cmd = f'{rem_pfx} \"{config.REM_LAUNCH} {loc_cmd}\"'
                _cmd = cfg_dict.get('cmd', fallback_cmd)
                if 'ssh -t' not in _cmd:
                    _cmd = f'{rem_pfx} \"{config.REM_LAUNCH} {_cmd}\"'

                connect = {'cmd': _cmd, 'pre_msg': f"Connecting To {dev_pretty} on {host}..."}
                if not rename:
                    menu_actions[str(item)] = connect
                else:
                    menu_actions['c' + str(item)] = connect
                    menu_actions['c ' + str(item)] = connect

                    _cmd = f'{rem_pfx} \"/\etc/\ConsolePi/\src/\consolepi-menu-dev.py rn {dev}\"'  # NoQA
                    menu_actions[str(item)] = {'cmd': _cmd,
                                               'pre_msg': f"Connecting To {host} to Rename {dev_pretty}...",
                                               'host': host}
                    rn_this = {dev: adapters[dev]}
                    if rn_this[dev].get('udev'):
                        menu_actions['s' + str(item)] = {'function': self.cpiexec.show_adapter_details, 'args': [rn_this]}
                        menu_actions['s ' + str(item)] = {'function': self.cpiexec.show_adapter_details, 'args': [rn_this]}
                    else:
                        _msg = 'Adapter Attributes not found in remote data, this feature is still in dev for remotes.'
                        menu_actions['s' + str(item)] = {'function': log.show, 'args': [_msg]}
                        menu_actions['s ' + str(item)] = {'function': log.show, 'args': [_msg]}

            item += 1

        return mlines, menu_actions, item

    def rename_menu(self, direct_launch=False, from_name=None):
        cpi = self.cpi
        local = cpi.local
        remotes = cpi.remotes
        choice = ''
        menu_actions = {}
        # -- rename invoked from another ConsolePi (remote rename) --
        if direct_launch and from_name:
            self.do_rename_adapter(from_name)
            self.trigger_udev()
            sys.exit()
        while choice not in ['b']:
            if choice == 'r':
                local.adapters = local.build_adapter_dict(refresh=True)
                remotes.data = remotes.get_remote(data=config.remote_update())
            loc = local.adapters
            rem = remotes.data

            slines = []
            outer_body = []
            slines.append('Rename Local Adapters')   # list of strings index to index match with body list of lists
            mlines, menu_actions, item = self.gen_adapter_lines(loc, rename=True)
            outer_body.append(mlines)
            rem_item = item

            for host in remotes.data:
                if rem[host].get('adapters'):
                    slines.append(f'Rename Adapters on {host}')
                    mlines, rem_menu_actions, item = self.gen_adapter_lines(rem[host]['adapters'], item=item,
                                                                            remote=True, rem_user=rem[host].get('rem_user'),
                                                                            host=host, rename=True)
                    outer_body.append(mlines)
                    menu_actions = {**menu_actions, **rem_menu_actions}

            # if not mlines:
            #     log.show('No Local Adapters')
            #     break

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
            menu_actions['x'] = self.exit

            self.menu.print_menu(outer_body, header='Define/Rename Adapters', footer=footer, subs=slines, do_format=False)

            choice_c = self.wait_for_input(locs=locals())
            choice = choice_c.lower
            if choice in menu_actions:
                if not choice == 'b':
                    cpi.cpiexec.menu_exec(choice_c, menu_actions, calling_menu='rename_menu')
                    if choice.isdigit() and int(choice) >= rem_item:
                        print('Triggering Refresh due to Remote Name Change')
                        remotes.refresh()
            else:
                if choice:
                    if choice != 'b' or direct_launch:
                        log.show('Invalid Selection \'{}\''.format(choice))

        # trigger refresh udev and restart ser2net after rename
        if self.udev_pending:
            error = self.trigger_udev()
            if error:
                log.show(error)

    # ------ // MAIN MENU \\ ------ #
    def main_menu(self):
        cpi = self.cpi
        menu = cpi.menu
        loc = cpi.local.adapters
        pwr = cpi.pwr
        remotes = cpi.remotes
        rem = cpi.remotes.data
        outer_body = []
        slines = []
        item = 1
        foot_opts = []

        menu_actions = {
            'h': self.picocom_help,
            'r': remotes.refresh,
            'x': self.exit,
            # 'sh': self.cpiexec.launch_shell
        }
        if config.power and pwr.data:
            if pwr.linked_exists or pwr.gpio_exists or pwr.tasmota_exists:
                menu_actions['p'] = self.power_menu
            elif pwr.dli_exists:  # if no linked outlets but dlis "p" also sends to dli_menu (valid but not displayed)
                menu_actions['p'] = self.dli_menu

            if pwr.dli_exists:
                menu_actions['d'] = self.dli_menu

        # Direct launch to power menu's if nothing to show in main and power enabled.
        if not loc and not rem and (not config.hosts or not config.hosts.get('main')) and config.power:
            log.show('No Adapters Found, Outlets Defined... Launching to Power Menu\n'
                     'use option "b" to access main menu options')
            if pwr.dli_exists and not pwr.linked_exists:
                cpi.cpiexec.menu_exec('d', menu_actions)
            else:
                cpi.cpiexec.menu_exec('p', menu_actions)

        # Build menu items for each locally connected serial adapter
        if loc:
            mlines, loc_menu_actions, item = self.gen_adapter_lines(loc)
            if loc_menu_actions:
                menu_actions = {**loc_menu_actions, **menu_actions}

            outer_body.append(mlines)   # list of lists where each list = printed menu lines
            slines.append('[LOCAL] Directly Connected')   # Sub-heads: list of str idx to idx match with outer_body list of lists

        # Build menu items for each serial adapter found on remote ConsolePis
        rem_mlines = []
        rem_slines = []
        rem_outer_body = []
        for host in sorted(rem):
            if rem[host].get('rem_ip') and len(rem[host]['adapters']) > 0:
                remotes.connected = True
                rem_mlines, rem_menu_actions, item = self.gen_adapter_lines(rem[host]['adapters'], item=item, remote=True,
                                                                            rem_user=rem[host].get('rem_user'), host=host)
                if rem_menu_actions:
                    menu_actions = {**menu_actions, **rem_menu_actions}

                rem_outer_body.append(rem_mlines)
                rem_slines.append('[Remote] {} @ {}'.format(host, rem[host]['rem_ip']))

        # -- // COMPACT MODE \\ --
        if remotes.connected:
            if config.compact_mode:
                slines.append('[Remote] On Remote ConsolePis')
                outer_body.append(list(itertools.chain.from_iterable(rem_outer_body)))
            else:
                slines += rem_slines
                outer_body += rem_outer_body

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

        if loc or remotes.connected:
            foot_opts.append('picohelp')

        if config.power:  # and config.outlets is not None:
            if pwr.outlets_exists:
                foot_opts.append('power')
            if pwr.dli_exists:
                foot_opts.append('dli')

        if remotes.connected or config.hosts:
            if remotes.connected:
                foot_opts.append('key')
                menu_actions['k'] = self.key_menu

            foot_opts.append('rshell')
            menu_actions['rs'] = self.rshell_menu

        # foot_opts.append('shell') # Not really needed can just do bash -l from menu
        if loc:  # and config.root:
            foot_opts.append('rn')
            menu_actions['rn'] = self.rename_menu
        foot_opts.append('refresh')

        menu.print_menu(outer_body, header='{{cyan}}Console{{red}}Pi{{norm}} {{cyan}}Serial Menu{{norm}}',
                        footer={'opts': foot_opts}, subs=slines, do_format=False)

        choice_c = self.wait_for_input(locs=locals(), terminate=True)
        choice = choice_c.lower
        cpi.cpiexec.menu_exec(choice_c, menu_actions)
        return

    # ------ // REMOTE SHELL MENU \\ ------ #
    def rshell_menu(self, do_ssh_hosts=False):
        choice = ''
        cpi = self.cpi
        local = cpi.local
        # config = cpi.config
        rem = cpi.remotes.data
        menu_actions = {
            'rshell_menu': self.rshell_menu,
            'b': self.main_menu,
            'x': self.exit
        }

        while choice not in ['x', 'b']:
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
                    menu_actions[str(item)] = {'cmd': _cmd,
                                               'pre_msg': f'Establishing ssh session To {host}...'}
                    item += 1
            outer_body.append(mlines)

            # Build menu items for each manually defined host in hosts.json / ConsolePi.yaml
            if config.hosts:
                for _sub in config.hosts['rshell']:
                    subs.append(_sub)
                    ssh_hosts = config.hosts['rshell'][_sub]
                    mlines, host_menu_actions, item = self.gen_adapter_lines({'_hosts': ssh_hosts}, item=item)
                    menu_actions = {**menu_actions, **host_menu_actions}
                    outer_body.append(mlines)

            footer = {'opts': 'back'}
            self.menu.print_menu(outer_body, header='Remote Shell Menu',
                                 subhead='Enter item # to connect to remote',
                                 footer=footer, subs=subs)

            choice_c = self.wait_for_input(locs=locals())
            choice = choice_c.lower

            cpi.cpiexec.menu_exec(choice_c, menu_actions, calling_menu='rshell_menu')

    # -- // CONNECTION MENU \\ --
    def con_menu(self, rename=False, con_dict=None):
        menu = self.cpi.menu
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

            ch = self.wait_for_input(locs=locals()).lower
            try:
                if ch == 'b':
                    break
                menu_actions[ch]()  # could parse and store if decide to use this for something other than rename

            except KeyError as e:
                if ch:
                    log.show('Invalid selection {}, please try again.'.format(e))

    # -- // BAUD MENU \\ --
    def baud_menu(self):
        # config = self.cpi.config
        menu = self.cpi.menu
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
                _cur_baud = menu_actions[key]
                print(' {0}. {1}'.format(key, _cur_baud if _cur_baud != self.baud else '[{}]'.format(_cur_baud)))

            menu.menu_formatting('footer', text=text)
            ch = self.wait_for_input(" Baud >>  ", locs=locals()).lower

            # -- Evaluate Response --
            try:
                if ch == 'c':
                    while True:
                        self.baud = self.wait_for_input(' Enter Desired Baud Rate >> ').lower
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
                if ch:
                    log.show('Invalid selection {} please try again.'.format(e))

        return self.baud

    # -- // DATA BITS MENU \\ --
    def data_bits_menu(self):
        menu = self.cpi.menu
        valid = False
        while not valid:
            menu.menu_formatting('header', text=' Enter Desired Data Bits ')
            print('\n Default 8, Current [{}], Valid range 5-8'.format(self.data_bits))
            menu.menu_formatting('footer', text=' b.  Back')
            choice = self.wait_for_input(' Data Bits >>  ', locs=locals()).orig
            try:
                if choice.lower() == 'x':
                    self.exit()
                elif choice.lower() == 'b':
                    valid = True
                elif int(choice) >= 5 and int(choice) <= 8:
                    self.data_bits = choice
                    valid = True
                else:
                    log.show('Invalid selection {} please try again.'.format(choice))
            except ValueError:
                if choice:
                    log.show('Invalid selection {} please try again.'.format(choice))

        return self.data_bits

    # -- // PARITY MENU \\ --
    def parity_menu(self):
        menu = self.cpi.menu

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
            choice = self.wait_for_input(' Parity >> ', locs=locals()).lower
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
                    log.show('Invalid selection {} please try again.'.format(choice))
        return self.parity

    # -- // FLOW MENU \\ --
    def flow_menu(self):
        menu = self.cpi.menu

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
            choice = self.wait_for_input(' Flow >>  ', locs=locals()).lower
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
                        log.show('Invalid selection {} please try again.'.format(choice))
            except Exception as e:
                if choice:
                    log.show('Invalid selection {} please try again.'.format(e))

        return self.flow

    # -- // EXIT \\ --
    def exit(self):
        self.go = False

        cpi = self.cpi
        if cpi.pwr._dli:
            threading.Thread(target=cpi.pwr.dli_close_all).start()

        # - if exit directly from rename menu after performing a rename trigger / reload udev
        if self.udev_pending:
            cmd = 'sudo udevadm control --reload && sudo udevadm trigger && '\
                  'sudo systemctl stop ser2net && sleep 1 && sudo systemctl start ser2net '
            with Halo(text='Triggering reload of udev do to name change', spinner='dots1'):
                error = utils.do_shell_cmd(cmd, shell=True)
            if error:
                print(error)

        sys.exit(0)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ['rn', 'rename', 'addconsole']:
            cpi_menu = ConsolePiMenu(bypass_remotes=True)
            if len(sys.argv) == 2:
                cpi_menu.rename_menu(direct_launch=True)
            else:
                cpi_menu.do_rename_adapter(from_name=sys.argv[2])
                if cpi_menu.udev_pending:
                    error = cpi_menu.trigger_udev()
                    if error:
                        print(error, file=sys.stderr)
        else:
            cpi_menu = ConsolePiMenu(bypass_remotes=True)
            var_in = sys.argv[1].replace('self', 'menu')
            if 'outlet' in var_in:
                cpi_menu.cpiexec.wait_for_threads()
            cpi_menu.print_attribute(var_in)
    else:
        # -- // LAUNCH MENU \\ --
        cpi_menu = ConsolePiMenu()
        while cpi_menu.go:
            cpi_menu.main_menu()
        print('hit')  # DEBUG
        cpi_menu.exit()
