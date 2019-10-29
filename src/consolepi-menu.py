#!/etc/ConsolePi/venv/bin/python

import ast
import json
import os
import readline
import shlex
import subprocess
import sys
from collections import OrderedDict as od
import threading
from halo import Halo
from log_symbols import LogSymbols as log_sym
# from consolepi.gdrive import GoogleDrive # <-- hidden import burried in refresh method of ConsolePiMenu Class

# --// ConsolePi imports \\--
from consolepi.common import (ConsolePi_data, check_reachable,
                              key_change_detector)

rem_user = 'pi'
rem_pass = None
MIN_WIDTH = 55
MAX_COLS = 5

class ConsolePiMenu():

    def __init__(self, bypass_remote=False, do_print=True):
        # pylint: disable=maybe-no-member
        config = ConsolePi_data()
        self.config = config
        self.spin = Halo(spinner='dots')
        self.error_msgs = []
        self.remotes_connected = False
        # self.error = None
        self.cloud = None  # Set in refresh method if reachable
        self.do_cloud = config.cloud  
        if self.do_cloud and config.cloud_svc == 'gdrive':  
            if check_reachable('www.googleapis.com', 443):
                self.local_only = False
                if not os.path.isfile('/etc/ConsolePi/cloud/gdrive/.credentials/credentials.json'):
                    config.plog('Required {} credentials files are missing refer to GitHub for details'.format(config.cloud_svc), level='warning')
                    config.plog('Disabling {} updates'.format(config.cloud_svc), level='warning')
                    self.error_msgs.append('Cloud Function Disabled by script - No Credentials Found')
                    self.do_cloud = False
            else:
                config.plog('failed to connect to {}, operating in local only mode'.format(config.cloud_svc), level='warning')
                self.error_msgs.append('failed to connect to {} - operating in local only mode'.format(config.cloud_svc))
                self.local_only = True
        self.log_sym_error = log_sym.ERROR.value
        self.log_sym_warn = log_sym.WARNING.value
        self.log_sym_success = log_sym.SUCCESS.value
        self.log_sym_info = log_sym.INFO.value
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
        if config.power:
            if not os.path.isfile(config.POWER_FILE):
                config.plog('Outlet Control Function enabled but no power.json configuration found - Disabling feature',
                    level='warning')
                self.error_msgs.append('Outlet Control Disabled by Script - No power.json found')
                config.power = False
        if config.power and config.outlets:
            self.dli_exists = self.gpio_exists = self.tasmota_exists = self.linked_exists = False
            for outlet_group in config.outlets:
                if config.outlets[outlet_group]['type'].lower() == 'dli':
                    self.dli_exists = True
                elif config.outlets[outlet_group]['type'].upper() == 'GPIO':
                    self.gpio_exists = True
                elif config.outlets[outlet_group]['type'].lower() == 'tasmota':
                    self.tasmota_exists = True
                else:
                    self.error_msgs.append('Outlet Control Disabled by Script - Invalid \'type\' in power.json')
                    config.power = False
                    break
                if config.outlets[outlet_group]['linked']:
                    self.linked_exists = True
                if self.dli_exists and self.gpio_exists and self.tasmota_exists and self.linked_exists:
                    break
        if config.power and config.dli_failures:
            self.get_dli_outlets()   # Update error msg with failure
        self.DEBUG = config.debug
        # self.DEBUG = True
        self.menu_actions = {
            'main_menu': self.main_menu,
            'h': self.picocom_help,
            'r': self.refresh,
            'x': self.exit
        }
        if config.display_con_settings:
            self.menu_actions['c'] = self.con_menu
        if config.power and config.outlets:
            if self.linked_exists or self.gpio_exists or self.tasmota_exists:
                self.menu_actions['p'] = self.power_menu
                self.menu_actions['power_menu'] = self.power_menu
            if self.dli_exists:
                self.menu_actions['d'] = self.dli_menu
                self.menu_actions['dli_menu'] = self.dli_menu

        self.colors = { # Bold with normal foreground
            'green': '\033[1;32m',
            'red': '\033[1;31m',
            'yellow': '\033[1;33m',
            'norm': '\033[0m'
        }
        self.states = {
            True: '{{green}}ON{{norm}}',
            False: '{{red}}OFF{{norm}}'
        }

    def get_dli_outlets(self, refresh=False, upd_linked=False, key='outlets'):
        # pylint: disable=maybe-no-member
        config = self.config
        config.outlet_update(refresh=refresh, upd_linked=upd_linked)
        if config.dli_failures:
            for _ in config.dli_failures:
                self.error_msgs.append(config.dli_failures[_]['error'])
        return getattr(config, key)         

    # get remote consoles from local cache refresh function will check/update cloud file and update local cache
    def get_remote(self, data=None, refresh=False):
        config = self.config
        log = config.log
        print('Fetching Remote ConsolePis with attached Serial Adapters from local cache')
        log.info('[GET REM] Starting fetch from local cache')

        if data is None or len(data) == 0:
            data = config.get_local_cloud_file()

        if config.hostname in data:
            del data[config.hostname]
            log.error('[GET REM] Local cache included entry for self - do you have other ConsolePis using the same hostname?')
            self.error_msgs.append('[WARNING] Local cache included entry for self - do you have other ConsolePis using the same hostname?')

        # Add remote commands to remote_consoles dict for each adapter
        update_cache = False
        pop_list = []
        for remotepi in data:
            this = data[remotepi]
            # print('  {} Found...  Checking reachability'.format(remotepi), end='')
            self.spin.start('  {} Found...  Checking reachability'.format(remotepi))
            if 'rem_ip' in this and this['rem_ip'] is not None and check_reachable(this['rem_ip'], 22):
                # print(': Success', end='\n')
                self.spin.succeed()
                log.info('[GET REM] Found {0} in Local Cache, reachable via {1}'.format(remotepi, this['rem_ip']))
                #this['adapters'] = build_adapter_commands(this)
            else:
                for _iface in this['interfaces']:
                    _ip = this['interfaces'][_iface]['ip']
                    if _ip not in self.ip_list:
                        if check_reachable(_ip, 22):
                            this['rem_ip'] = _ip
                            # print(': Success', end='\n')
                            self.spin.succeed()
                            log.info('[GET REM] Found {0} in Local Cloud Cache, reachable via {1}'.format(remotepi, _ip))
                            #this['adapters'] = build_adapter_commands(this)
                            break  # Stop Looping through interfaces we found a reachable one
                        else:
                            this['rem_ip'] = None

            if this['rem_ip'] is None:
                log.warning('[GET REM] Found {0} in Local Cloud Cache: UNREACHABLE'.format(remotepi))
                self.error_msgs.append('Cached Remote \'{}\' is unreachable'.format(remotepi))
                update_cache = True                
                # print(': !!! UNREACHABLE !!!', end='\n')
                self.spin.fail()
                pop_list.append(remotepi)  # Remove Unreachable remote from cache
        
        # update local cache if any ConsolePis found UnReachable
        if update_cache:
            if len(pop_list) > 0:
                for remotepi in pop_list:
                    if 'fail_cnt' in data[remotepi]:
                        data[remotepi]['fail_cnt'] += 1
                        if data[remotepi]['fail_cnt'] >= 3:
                            removed = data.pop(remotepi)
                            log.warning('[GET REM] {} has been removed from Local Cache after {} failed attempts'.format(
                                remotepi, removed['fail_cnt']))
                            self.error_msgs.append('Unreachable \'{}\' removed from local cache after 3 failed attempts to connect'.format(remotepi))   
                    else:
                        data[remotepi]['fail_cnt'] = 1
            data = config.update_local_cloud_file(data)

        return data

    # Update ConsolePi.csv on Google Drive and pull any data for other ConsolePis
    def refresh(self, rem_update=False):
        # pylint: disable=maybe-no-member
        remote_consoles = None
        config = self.config
        config.rows, config.cols = config.get_tty_size()
        log = config.log
        plog = config.plog
        # Update Local Adapters
        if not rem_update:
            # plog('[MENU REFRESH] Detecting Locally Attached Serial Adapters')
            self.data['local'] = {self.hostname: {'adapters': config.get_local(), 'interfaces': config.get_if_ips(), 'user': 'pi'}}
            log.debug('Final Data set collected for {}: {}'.format(self.hostname, self.data['local']))

        # Get details from Google Drive - once populated will skip
        if self.do_cloud and not self.local_only:
            if config.cloud_svc == 'gdrive' and self.cloud is None:
                from consolepi.gdrive import GoogleDrive
                self.cloud = GoogleDrive(config.log, hostname=self.hostname)
                log.info('[MENU REFRESH] Gdrive init')

            # Pass Local Data to update_sheet method get remotes found on sheet as return
            # update sheets function updates local_cloud_file
            log.info('[MENU REFRESH] Updating to/from {}'.format(config.cloud_svc))
            self.spin.start('[MENU REFRESH] Updating to/from {}'.format(config.cloud_svc))
            remote_consoles = self.cloud.update_files(self.data['local'])
            self.spin.stop()
            if len(remote_consoles) > 0:
                plog('[MENU REFRESH] Updating Local Cache with data from {}'.format(config.cloud_svc))
                config.update_local_cloud_file(remote_consoles)
            else:
                plog('[MENU REFRESH] No Remote ConsolePis found on {}'.format(config.cloud_svc))
        else:
            if self.do_cloud:
                print('Not Updating from {} due to connection failure'.format(config.cloud_svc))
                print('Close and re-launch menu if network access has been restored')

        # Update Remote data with data from local_cloud cache
        self.data['remote'] = self.get_remote(data=remote_consoles, refresh=True)

    # =======================
    #     MENUS FUNCTIONS
    # =======================
    def print_mlines(self, body, subs=None, header=None, footer=None, col_pad=5, force_cols=False,
                    do_cols=True, do_format=True, by_tens=False):
        '''
        format and print current menu.

        build the content and in the calling method and pass into this function for format & printing
        params:
            body: a list of lists or list of strings, where each inner list is made up of text for each
                    menu-item in that logical section.
            subs: a list of sub-head lines that map to each inner body list.  This is the header for 
                the specific logical grouping of menu-items
            header: The Header text for the menu
            footer: an optional text string or list of strings to be added to the menu footer.
            col_pad: how many spaces will be placed between horizontal menu sections.
            force_cols: By default the menu will print as a single column, with force_cols=True
                    it will bypass the vertical fit test - print section in cols horizontally
            do_cols: bool, If specified and set to False will bypass horizontal column printing and 
                    resulting in everything printing vertically on one screen
            do_format: bool, Only applies to sub_head auto formatting.  If specified and set to False 
                    will not perform formatting on sub-menu text.
                    Auto formatting results in '------- text -------' (width of section)
            by_tens: Will start each section @ 1, 11, 21, 31 unless the section is greater than 10
                    menu_action statements should match accordingly
            
        '''
        config = self.config
        line_dict = od({'header': {'lines': header}, 'body': {'sections': [], 'rows': [], 'width': []}, 'footer': {'lines': footer}})
        '''
        Determine header and footer length used to determine if we can print with
        a single column
        '''
        head_len = len(self.menu_formatting('header', text=header, do_print=False))
        foot_len = len(self.menu_formatting('footer', text=footer, do_print=False))
        ''' 
        generate list for each sections where each line is padded to width of longest line
        collect width of longest line and # of rows/menu-entries for each section

        All of this is used to format the header/footer width and to ensure consistent formatting
        during print of multiple columns
        '''
        body = list(body) if isinstance(body[0], str) else body
        i = 0
        item = start = 1
        for _section in body:
            if by_tens and i > 0:
                item = start + 10 if item <= start + 10 else item
                start += 10
            _item_list, _max_width = self.menu_formatting('body', 
                text=_section, sub=subs[i], index=item, do_print=False, do_format=do_format)
            line_dict['body']['width'].append(_max_width)
            line_dict['body']['rows'].append(len(_item_list))
            line_dict['body']['sections'].append(_item_list)
            item = item + len(_section)
            i += 1
        ''' 
        set the initial # of columns
        '''
        body = line_dict['body']
        cols = len(body['sections']) if len(body['sections']) <= MAX_COLS else MAX_COLS
        if not force_cols:
            tot_1_col_len = sum(line_dict['body']['rows']) + len(line_dict['body']['rows']) \
                            + head_len + foot_len
            cols = 1 if not do_cols or tot_1_col_len < config.rows else cols
        '''
        calculate max total width of widest row given # of cols and col padding
        reduce # of cols if any row overruns the tty width or reduce col padding if
        overrun is minimal
        '''
        _begin = 0
        _end = cols
        _tot_width = []
        _iter_start_stop = []
        while True:
            _tot_width.append(sum(body['width'][_begin:_end]) + (col_pad * (cols - 1))) # pad doesn't apply for first and last column
            if max(_tot_width) <= config.cols:
                if _end < len(body['sections']):
                    _iter_start_stop.append([_begin, _end])
                    _begin = _end
                    _end = _end + cols if _end + cols <= len(body['sections']) else len(body['sections'])
                else:
                    _tot_width = max(_tot_width)
                    _iter_start_stop.append([_begin, _end])
                    break
            else:   # width of this # of cols too wide for screen reduce col count
                reduce_cols = True
                if 2 * ( cols - 1 ) < max(_tot_width) - config.cols < 5 * ( cols - 1 ):
                    if col_pad != 2:
                        col_pad = 2
                        reduce_cols = False
                    else:
                        pass # reduce_cols = True
                if reduce_cols:
                    if cols > 1:
                        cols -= 1
                        _begin = 0
                        _end = cols
                        _tot_width = []
                    else:
                        self.DEBUG = True
                        self.error_msgs.append('tty too small for menu - screen clearing disabled')
                        _iter_start_stop = []
                        _tot_width = []
                        # this essentially builds a single column TODO simplify this
                        for x in range(0, len(body['sections'])):
                            _iter_start_stop.append([x, x + 1])
                            _tot_width.append(sum(body['width'][x:x + 1]) + (col_pad * (cols - 1)))
                            next
                        break

        # -- if any footer lines are longer adjust _tot_width (which is the longest line from any section)
        foot = self.menu_formatting('footer', text=footer, do_print=False)[0]
        _foot_width = []
        for line in foot:
            _foot_width.append(len(line))
        if isinstance(_tot_width, int): # TODO refactor
            _tot_width = [_tot_width]
        _tot_width = max(_foot_width) if max(_foot_width) > max(_tot_width) else max(_tot_width)
        
        if MIN_WIDTH < config.cols:
            _tot_width = MIN_WIDTH if _tot_width < MIN_WIDTH else _tot_width

        # --// PRINT MENU \\--
        self.menu_formatting('header', text=header, width=_tot_width, do_print=True)
        pad = ' ' * col_pad
        for _i in _iter_start_stop:
            _begin = _i[0]
            _end = _i[1]
            long = max(body['rows'][_begin:_end])
            wide = body['width'][_begin:_end]
            _iters = []
            for s in body['sections'][_begin:_end]:
                _iters.append(iter(s))
            for _ in range(long):
                for x in _iters:
                    _ii = _iters.index(x)
                    if _ii + _begin + 1 == _end or _ii == cols - 1:
                        this_pad = ''
                        this_end = '\n'
                    else:
                        this_pad = pad
                        this_end = ''
                    print('{:{_len}}{}'.format(next(x, ''), this_pad, _len=wide[_ii]), end=this_end)
#                    print('{:{_len}}{}'.format(next(x, ''), pad if _ii < cols else '', _len=wide[_ii]),
#                        end='\n' if _ii + _begin + 1 == _end or _ii == cols - 1 else '')
            if _end != len(body['sections']):
                if cols > 1:
                    print('') # When multiple cols adds a 2nd \n below row of entries other than last row
        self.menu_formatting('footer', text=footer, width=_tot_width, do_print=True)
        # print(_tot_width, config.cols, config.rows)


    def menu_formatting(self, section, sub=None, text=None, width=MIN_WIDTH,
                         l_offset=1, index=1, do_print=True, do_format=True):
        config = self.config
        mlines = []
        max_len = None
        colors = self.colors

        # -- append any errors from config (ConsolePi_data object)
        if config.error_msgs:
            self.error_msgs += config.error_msgs
            config.error_msgs = []

        # -- Adjust width if there is an error msg longer then the current width            
        if self.error_msgs:
            _error_lens = []
            for _error in self.error_msgs:
                _error_lens.append(len(_error))
            width = width if width >= max(_error_lens) + 5 else max(_error_lens) + 5
            width = width if width <= config.cols else config.cols

        # --// HEADER \\--
        if section == 'header':
            if not self.DEBUG:
                os.system('clear')
            mlines.append('=' * width)
            a = width - len(text)
            b = (a/2) - 2
            if text:
                c = int(b) if b == int(b) else int(b) + 1
                if isinstance(text, list):
                    for t in text:
                        mlines.append(' {0} {1} {2}'.format('-' * int(b), t, '-' * c))
                else:
                    mlines.append(' {0} {1} {2}'.format('-' * int(b), text, '-' * c))
            mlines.append('=' * width)
            mlines.append('')
        
        # --// FOOTER \\--
        elif section == 'footer':
            mlines.append('')
            if text:
                if isinstance(text, list):
                    for t in text:
                        if '{{r}}' in t:
                            _t = t.split('{{r}}')
                            mlines.append('{}{}'.format(_t[0], _t[1].rjust(width - len(_t[0]))))
                        else:
                            mlines.append(t)
                else:
                    if '{{r}}' in text:
                        _t = text.split('{{r}}')
                        mlines.append('{}{}'.format(_t[0], _t[1].rjust(width - len(_t[0]))))
                    else:
                        mlines.append(text)
            mlines.append(' x. exit\n')
            mlines.append('=' * width)

            # --// ERRORs - append to footer \\-- #
            if len(self.error_msgs) > 0:
                for _error in self.error_msgs:
                    x = ((width - (len(_error) + 2)) / 2 ) - 1 # _error + 3 is for log_sym
                    mlines.append('*{}{} {}{}*'.format(' ' * int(x),self.log_sym_warn, _error, ' ' * int(x) if x == int(x) else ' ' * (int(x) + 1)))
                mlines.append('=' * width)
                if do_print:
                    self.error_msgs = [] # clear error messages

        # --// BODY \\--
        elif section == 'body':
            max_len = 0
            blines = list(text) if isinstance(text, str) else text
            pad = True if len(blines) + index > 10 else False
            indent = l_offset + 4 if pad else l_offset + 3
            width_list = []
            for _line in blines:
                # -- format spacing of item entry --
                _i = str(index) + '. ' if not pad or index > 9 else str(index) + '.  '
                # -- generate line and calculate line length --
                _line = ' ' * l_offset + _i + _line
                _l = _line
                for c in colors:
                    _l = _l.replace('{{' + c + '}}', '')
                width_list.append(len(_l.replace('\n', '')))
                for c in colors:
                    _line = _line.replace('{{' + c + '}}', colors[c])
                mlines.append(_line)
                index += 1
            max_len = max(width_list)
            if sub:
                # -- Add sub lines to top of menu item section --
                x = ((max_len - len(sub)) / 2 ) - (l_offset + (indent/2))
                mlines.insert(0, '')
                width_list.insert(0, 0)
                if do_format:
                    mlines.insert(1, '{0}{1} {2} {3}'.format(' ' * indent, '-' * int(x), sub, '-' * int(x) if x == int(x) else '-' * (int(x) + 1)))
                    width_list.insert(1, len(mlines[1]))
                else:
                    mlines.insert(1, ' ' * indent + sub)
                    width_list.insert(1, len(mlines[1]))
                max_len = max(width_list) # update max_len in case subheading is the longest line in the section
                mlines.insert(2, ' ' * indent + '-' * (max_len - indent))
                width_list.insert(2, len(mlines[2]))

            # -- adding padding to line to full width of longest line in section --
            mlines = self.pad_lines(mlines, max_len, width_list) # Refactoring in progress
        else:
            print('formatting function passed an invalid section')
        if do_print:
            for _line in mlines:
                print(_line)

        return mlines, max_len

    def pad_lines(self, line_list, max_width, width_list, sub=True):
        for _line in line_list:
            i = line_list.index(_line)
            line_list[i] = '{}{}'.format(_line, ' ' * (max_width - width_list[i]))
        return line_list

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

    def power_menu(self, calling_menu='main_menu'):
        config = self.config
        outlets = self.get_dli_outlets()
        states = self.states
        colors = self.colors
        menu_actions = {
            'b': self.main_menu,
            'x': self.exit,
            'power_menu': self.power_menu,
        }           
        choice = ''
        while choice.lower() not in ['x', 'b']:
            item = 1
            if choice.lower() == 'r': 
                if self.dli_exists:
                    print('Refreshing Outlets')
                    outlets = self.get_dli_outlets(refresh=True, upd_linked=True)
            if not self.DEBUG:
                os.system('clear')

            self.menu_formatting('header', text=' Power Control Menu ')
            print('  enter item # to toggle power state on outlet')
            print('  enter c + item # i.e. "c2" to cycle power on outlet')

            # Build menu items for each linked outlet
            state_list = []
            for r in sorted(outlets):
                outlet = outlets[r]
                
                # strip off all but hostname if address is fqdn
                if isinstance(outlet['address'], str):
                    _address = outlet['address'].split('.')[0] if '.' in outlet['address'] and not config.canbeint(outlet['address'].split('.')[0]) else outlet['address']

                header = '     [{}] {}{}'.format(outlet['type'], r, ' @ ' + _address if outlet['type'].lower() == 'dli' else '')
                # print('\n' + header + '\n     ' + '-' * (len(header) - 5))
                if outlet['type'].lower() == 'dli':
                    if outlet['is_on']:     # Avoid orphan header when no outlets are linked to a defined dli
                        print('\n' + header + '\n     ' + '-' * (len(header) - 5))
                        for dli_port in outlet['is_on']:
                            _outlet = outlet['is_on'][dli_port]
                            _state = states[_outlet['state']]
                            state_list.append(_outlet['state'])
                            for c in colors:
                                _state = _state.replace('{{' + c + '}}', colors[c])
                            print(' {}. [{}] port {} ({})'.format(item, _state, dli_port, _outlet['name']))
                            menu_actions[str(item)] = {
                                'function': config.pwr_toggle,
                                'args': [outlet['type'], outlet['address']],
                                'kwargs': {'port': dli_port, 'desired_state': not _outlet['state']},
                                'key': r
                                }
                            menu_actions['c' + str(item)] = {
                                'function': config.pwr_cycle,
                                'args': ['dli', outlet['address']],
                                'kwargs': {'port': dli_port},
                                'key': 'dli_pwr'
                                }
                            menu_actions['r' + str(item)] = {
                                'function': config.pwr_rename,
                                'args': ['dli', outlet['address']],
                                'kwargs': {'port': dli_port},
                                'key': 'dli_pwr'
                                }
                            item += 1
                else: # -- GPIO or tasmota outlets --
                    # if ( isinstance(outlet['is_on'], int) and outlet['is_on'] <= 1 ) or isinstance(outlet['is_on'], bool):
                    if isinstance(outlet['is_on'], bool):
                        _state = states[outlet['is_on']]
                        state_list.append(outlet['is_on'])
                        print('\n' + header + '\n     ' + '-' * (len(header) - 5))
                        for c in colors:
                            _state = _state.replace('{{' + c + '}}', colors[c])
                        print(' {}. [{}] {}'.format(item, _state, r))
                        menu_actions[str(item)] = {
                            'function': config.pwr_toggle,
                            'args': [outlet['type'], outlet['address']],
                            'kwargs': {'noff': True if not 'noff' in outlet else outlet['noff']},
                            'key': r
                            }
                        menu_actions['c' + str(item)] = {
                            'function': config.pwr_cycle,
                            'args': [outlet['type'], outlet['address']],
                            'kwargs': {'noff': True if not 'noff' in outlet else outlet['noff']},
                            'key': r
                            }
                        menu_actions['r' + str(item)] = {
                            'function': config.pwr_rename,
                            'args': [outlet['type'], outlet['address']],
                            'key': r
                            }
                        item += 1
                    # elif isinstance(outlet['is_on'], dict) and outlet['type'] == 'dli':
                    #     pass
                    else:
                        # print('     !! Skipping {} as it returned an error: {}'.format(r, outlet['is_on']))
                        self.error_msgs.append('{} not displayed - Error: {}'.format(r, outlet['is_on']))
            
            if item > 2:
                print('')
                if False in state_list:
                    print(' all on:    Turn all outlets {}ON{}'.format(self.colors['green'], self.colors['norm']))
                    menu_actions['all on'] = {
                        'function': config.pwr_all, # pylint: disable=maybe-no-member
                        'kwargs': {'outlets': outlets, 'desired_state': True}
                        }
                if True in state_list:
                    print(' all off:   Turn all outlets {}OFF{}'.format(self.colors['red'], self.colors['norm']))
                    menu_actions['all off'] = {
                        'function': config.pwr_all, # pylint: disable=maybe-no-member
                        'kwargs': {'outlets': outlets, 'desired_state': False}
                        }
                    print(' cycle all: Cycle all outlets {2}ON{1}{3}{0}OFF{1}{3}{2}ON{1}'.format(self.colors['red'], self.colors['norm'], self.colors['green'], u'\u00B7'))
                    menu_actions['cycle all'] = {
                        'function': config.pwr_all, # pylint: disable=maybe-no-member
                        'kwargs': {'outlets': outlets, 'action': 'cycle'}
                        }
            
            text = [' b. Back', ' r. Refresh']
            if self.dli_exists and not calling_menu == 'dli_menu':
                text.insert(0, ' d. [dli] Web Power Switch Menu')
                menu_actions['d'] = self.dli_menu
            self.menu_formatting('footer', text=text)
            choice = input(" >>  ").lower()
            if choice not in ['b', 'r']:
                self.exec_menu(choice, actions=menu_actions, calling_menu='power_menu')
            elif choice == 'b':
                return


    def dli_menu(self, calling_menu='power_menu'):
        config = self.config
        dli_dict = self.get_dli_outlets(key='dli_pwr')
        menu_actions = {
            'b': self.power_menu,
            'x': self.exit,
            'dli_menu': self.dli_menu,
            'power_menu': self.power_menu
        }
        states = self.states
        choice = ''
        while choice not in ['x', 'b']:
            if not self.DEBUG:
                os.system('clear')

            index = start = 1
            outer_body = []
            slines = []
            for dli in sorted(dli_dict):
                state_dict = []
                mlines = []
                port_dict = dli_dict[dli] # pylint: disable=unsubscriptable-object
                # strip off all but hostname if address is fqdn
                host_short = dli.split('.')[0] if '.' in dli and not config.canbeint(dli.split('.')[0]) else dli

                # -- // MENU ITEMS LOOP \\ --
                for port in port_dict:
                    pname = port_dict[port]['name']
                    cur_state = port_dict[port]['state']
                    state_dict.append(cur_state)
                    to_state = not cur_state
                    on_pad = ' ' if cur_state else ''
                    mlines.append('[{}] {}{}{}'.format(
                        states[cur_state], on_pad, 'P' + str(port) + ': ' if port != index else '', pname))
                    menu_actions[str(index)] = {
                        'function': config.pwr_toggle,
                        'args': ['dli', dli],
                        'kwargs': {'port': port, 'desired_state': to_state},
                        'key': 'dli_pwr'
                        } 
                    menu_actions['c' + str(index)] = {
                        'function': config.pwr_cycle,
                        'args': ['dli', dli],
                        'kwargs': {'port': port},
                        'key': 'dli_pwr'
                        }
                    menu_actions['r' + str(index)] = {
                        'function': config.pwr_rename,
                        'args': ['dli', dli],
                        'kwargs': {'port': port},
                        'key': 'dli_pwr'
                        }
                    index += 1
                # add final entry for all operations
                if True not in state_dict:
                    _line = 'ALL {{green}}ON{{norm}}'
                    desired_state = True
                elif False not in state_dict:
                    _line = 'ALL {{red}}OFF{{norm}}'
                    desired_state = False
                else:
                    _line = 'ALL [on|off]. i.e. "{} off"'.format(index)
                    desired_state = None
                # build appropriate menu_actions item will represent ALL ON or ALL OFF if current state of all outlets is the inverse
                # if there is a mix item#+on or item#+off will both be valid but item# alone will not.
                if desired_state in [True, False]:
                    menu_actions[str(index)] = {
                        'function': config.pwr_toggle,
                        'args': ['dli', dli],
                        'kwargs': {'port': 'all', 'desired_state': desired_state},
                        'key': 'dli_pwr'
                        }
                elif desired_state is None:
                    for s in ['on', 'off']:
                        desired_state = True if s == 'on' else False
                        menu_actions[str(index) + ' ' + s] = {
                        'function': config.pwr_toggle,
                        'args': ['dli', dli],
                        'kwargs': {'port': 'all', 'desired_state': desired_state},
                        'key': 'dli_pwr'
                        }
                mlines.append(_line)
                # Add cycle line if any outlets are currently ON
                index += 1
                if True in state_dict:
                    mlines.append('Cycle ALL')
                    menu_actions[str(index)] = {
                        'function': config.pwr_cycle,
                        'args': ['dli', dli],
                        'kwargs': {'port': 'all'},
                        'key': 'dli_pwr'
                        }
                index = start + 10
                start += 10
                

                outer_body.append(mlines)   # list of lists where each list = printed menu lines
                slines.append(host_short)   # list of strings index to index match with body list of lists

            header = 'DLI Web Power Switch'
            footer = [
                ' b. Back{{r}}menu # alone will toggle the port,',
                ' r. Refresh{{r}}c# to cycle or r# to rename [i.e. \'c1\']'
            ]
            if (not calling_menu == 'power_menu' and config.outlets) and (self.gpio_exists or self.tasmota_exists or self.linked_exists):
                menu_actions['p'] = self.power_menu
                footer.insert(0, ' p. Power Control Menu (linked, GPIO, tasmota)')
            self.print_mlines(outer_body, header=header, footer=footer, subs=slines, force_cols=True, by_tens=True)

            choice = input(" >>  ")
            if choice == 'r': 
                print('Refreshing Outlets')
                dli_dict = self.get_dli_outlets(refresh=True, key='dli_pwr')
            elif choice == 'b':
                return
            else:
                self.exec_menu(choice, actions=menu_actions, calling_menu='dli_menu')

    def key_menu(self):
        config = self.config
        rem = self.data['remote']
        choice = ''
        menu_actions = {
            'b': self.main_menu,
            'x': self.exit,
            'key_menu': self.key_menu
        }
        while choice.lower() not in ['x', 'b']:
            if not self.DEBUG:
                os.system('clear')

            self.menu_formatting('header', text=' Remote SSH Key Distribution Menu ')
        
            # Build menu items for each serial adapter found on remote ConsolePis
            item = 1
            for host in sorted(rem):
                if rem[host]['rem_ip'] is not None:
                    rem_ip = rem[host]['rem_ip']
                    rem_user = rem[host]['user'] if 'user' in rem[host] else rem_user
                    print(' {0}. Send SSH key to {1} @ {2}'.format(item, host, rem_ip))
                    menu_actions[str(item)] = {'function': config.gen_copy_key, 'args': [rem[host]['rem_ip']], \
                        'kwargs': {'rem_user': rem_user}}
                    item += 1
            
            # -- add option to loop through all remotes and deploy keys --
            print('\n a. Send SSH key to *all* remotes listed above')
            menu_actions['a'] = {'function': config.gen_copy_key, \
            'kwargs': {'rem_user': rem_user}}
        
            self.menu_formatting('footer', text=' b. Back')
            choice = input(" >>  ")
            
            self.exec_menu(choice, actions=menu_actions, calling_menu='key_menu')

    def main_menu(self):
        loc = self.data['local'][self.hostname]['adapters']
        rem = self.data['remote']
        config = self.config
        flow_pretty = {
            'x': 'xon/xoff',
            'h': 'RTS/CTS',
            'n': 'NONE'
        }
        item = 1
        if not self.DEBUG:
            os.system('clear')

        # TODO # >> Clean this up, make sub to do this on both local and remote
        # Build menu items for each locally connected serial adapter
        outer_body = []
        slines = []
        mlines = []
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
            menu_line = '{} [{}{} {}{}1]'.format(
                this_dev.replace('/dev/', ''), def_indicator, baud, dbits, parity[0].upper())
            if flow != 'n' and flow in flow_pretty:
                menu_line += ' {}'.format(flow_pretty[flow])
            mlines.append(menu_line)

            # Generate Command executed for Menu Line
            _cmd = 'picocom {0} -b{1} -f{2} -d{3} -p{4}'.format(this_dev, baud, flow, dbits, parity)
            self.menu_actions[str(item)] = {'cmd': _cmd}
            item += 1

        outer_body.append(mlines)   # list of lists where each list = printed menu lines
        slines.append('[LOCAL] Directly Connected')   # list of strings index to index match with body list of lists
            
        # Build menu items for each serial adapter found on remote ConsolePis
        for host in sorted(rem):
            if rem[host]['rem_ip'] is not None and len(rem[host]['adapters']) > 0:
                self.remotes_connected = True
                mlines = []
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
                    menu_line = '{} [{}{} {}{}1]'.format(
                        _dev['dev'].replace('/dev/', ''), def_indicator, baud, dbits, parity[0].upper())
                    if flow != 'n' and flow in flow_pretty:
                        menu_line += ' {}'.format(flow_pretty[flow])
                    mlines.append(menu_line)
                    # pylint: disable=maybe-no-member
                    _cmd = 'ssh -t {0}@{1} "{2} picocom {3} -b{4} -f{5} -d{6} -p{7}"'.format(
                                 rem[host]['user'], rem[host]['rem_ip'], config.REM_LAUNCH, _dev['dev'], baud, flow, dbits, parity)
                    self.menu_actions[str(item)] = {'cmd': _cmd} 
                    item += 1

                outer_body.append(mlines)   # list of lists where each list = printed menu lines
                slines.append('[Remote] {} @ {}'.format(host, rem[host]['rem_ip']))   # list of strings index to index match with body list of lists

        # -- General Menu Command Options --
        text = []
        if config.display_con_settings: # pylint disable=no-member
            text.append(' c. Change *default Serial Settings [{0} {1}{2}1 flow={3}] '.format(
                self.baud, self.data_bits, self.parity.upper(), self.flow_pretty[self.flow]))
        text.append(' h. Display picocom help')
        if config.power and config.outlets is not None:
            if self.linked_exists or self.gpio_exists or self.tasmota_exists:
                text.append(' p. Power Control Menu')
            if self.dli_exists:
                text.append(' d. [dli] Web Power Switch Menu')
        if self.remotes_connected:
            self.menu_actions['k'] = self.key_menu
            self.menu_actions['s'] = self.rshell_menu
            text.append(' k. Distribute SSH Key to Remote Hosts')
            text.append(' s. Remote Shell Menu (Connect to Remote ConsolePi Shell)')
        text.append(' r. Refresh')

        self.print_mlines(outer_body, header='ConsolePi Serial Menu', footer=text, subs=slines, do_format=False)
        
        choice = input(" >>  ")
        self.exec_menu(choice)
        return

    def rshell_menu(self):
        choice = ''
        rem = self.data['remote']
        menu_actions = {
            'rshell_menu': self.rshell_menu,
            'b': self.main_menu,
            'x': self.exit
        }

        while choice.lower() not in ['x', 'b']:
            if not self.DEBUG:
                os.system('clear')
            self.menu_formatting('header', text=' Remote Shell Menu ')

            # Build menu items for each reachable remote ConsolePi
            item = 1
            for host in sorted(rem):
                if rem[host]['rem_ip'] is not None:
                    print(' {0}. Connect to {1} @ {2}'.format(item, host, rem[host]['rem_ip']))
                    _cmd = 'ssh -t {0}@{1}'.format('pi', rem[host]['rem_ip'])
                    menu_actions[str(item)] = {'cmd': _cmd}
                    item += 1

            text = ' b. Back'
            self.menu_formatting('footer', text=text)
            choice = input(" >>  ")
            self.exec_menu(choice, actions=menu_actions, calling_menu='rshell_menu')


    # Execute menu
    def exec_menu(self, choice, actions=None, calling_menu='main_menu'):
        menu_actions = actions if actions is not None else self.menu_actions
        config = self.config
        log = config.log
        # plog = config.plog
        if not self.DEBUG and calling_menu not in ['dli_menu', 'power_menu']:
            os.system('clear')
        ch = choice.lower()
        if ch == '':
            return
            # menu_actions[calling_menu]()
        else:
            try:
                if isinstance(menu_actions[ch], dict):
                    if 'cmd' in menu_actions[ch]:
                        c = shlex.split(menu_actions[ch]['cmd'])
                        # c = list like (local): ['picocom', '/dev/White3_7003', '-b9600', '-fn', '-d8', '-pn']
                        #               (remote): ['ssh', '-t', 'pi@10.1.30.28', 'picocom /dev/AP303P-BARN_7001 -b9600 -fn -d8 -pn']
                        
                        # -- // AUTO POWER ON LINKED OUTLETS \\ --
                        if config.power:  # pylint: disable=maybe-no-member
                            # TODO use new config.outlet_by_dev
                            # TODO remove /dev/ from power.json (don't require /dev/)
                            if '/dev/' in c[1] or ( len(c) >= 4 and '/dev/' in c[3] ):
                                menu_dev = c[1] if c[0] != 'ssh' else c[3].split()[1]
                                for dev in config.local[self.hostname]['adapters']:
                                    if menu_dev == dev['dev']:
                                        outlet = dev['outlet']
                                        if outlet is not None:
                                            desired_state = True
                                            # self.spin.start('Ensuring ' + menu_dev.replace('/dev/', '') + ' is Powered On')
                                            # linked_ports = [ '{}:{}'.format(port, outlet['is_on'][port]['name']) for port in outlet['is_on'] ] if isinstance(outlet['is_on'], dict) else ''
                                            # if linked_ports:
                                            #     msg = ''
                                            #     for p in linked_ports:
                                            #         msg += p + ', '
                                            #     linked_ports = msg.rstrip(', ')
                                            # self.spin.start('Ensuring linked outlet(s): [{}]:{} {} ~ powered on'.format(
                                            #     outlet['type'], outlet['address'], linked_ports))
                                            # -- // DLI Auto Power On \\ --
                                            if outlet['type'] == 'dli':
                                                need_update = False
                                                _addr = outlet['address']
                                                host_short = _addr.split('.')[0] if '.' in _addr and not config.canbeint(_addr.split('.')[0]) else _addr
                                                for p in outlet['is_on']:
                                                    # fail = False
                                                    self.spin.start('Ensuring linked outlet: [{}]:{} port: {}({}) is powered on'.format(
                                                        outlet['type'], host_short, p, outlet['is_on'][p]['name']))
                                                    if not outlet['is_on'][p]['state']:
                                                        r = config.pwr_toggle(outlet['type'], outlet['address'], desired_state=desired_state, port=p)
                                                        if isinstance(r, bool):
                                                            if r:
                                                                self.spin.succeed()
                                                                need_update = True
                                                            else:
                                                                self.spin.fail()
                                                        else:
                                                            self.spin.fail('Error operating linked outlet {} @ {} ({})'.format(
                                                                menu_dev.replace('/dev/', ''), outlet['address'], r))
                                                            log.warning('{} Error operating linked outlet @ {}'.format(menu_dev, outlet['address']))
                                                            self.error_msgs.append('Error operating linked outlet @ {}'.format(outlet['address']))
                                                        # if not r or not isinstance(r, bool):
                                                        #     fail = True
                                                    else:
                                                        # if fail is not None: # ensure spin.success is only hit once
                                                            self.spin.succeed() # port is already on
                                                        # fail = None
                                                # if isinstance(fail, bool) and not fail:
                                                #     self.spin.succeed()
                                                if need_update:
                                                    threading.Thread(target=config.outlet_update, kwargs={'refresh': True, 'upd_linked': True}, name='auto_pwr_refresh_dli').start()
                                                # elif fail is not None:
                                                #     self.spin.fail('Error operating linked outlet {} @ {} ({})'.format(
                                                #         menu_dev.replace('/dev/', ''), outlet['address'], r))
                                                #     log.warning('{} Error operating linked outlet @ {}'.format(menu_dev, outlet['address']))
                                                #     self.error_msgs.append('Error operating linked outlet @ {}'.format(outlet['address']))
                                            # -- // GPIO & TASMOTA Auto Power On \\ --
                                            else:
                                                self.spin.start('Ensuring linked outlet: [{}]:{} is powered on'.format(
                                                        outlet['type'], outlet['address']))
                                                r = config.pwr_toggle(outlet['type'], outlet['address'], desired_state=desired_state,
                                                    noff=outlet['noff'] if outlet['type'].upper() == 'GPIO' else True)
                                                if not isinstance(r, bool) and isinstance(r, int) and r <= 1:
                                                    self.error_msgs.append('the return from {} {} was an int({})'.format(
                                                        outlet['type'], outlet['address'], r
                                                    ))
                                                elif isinstance(r, int) and r > 1:
                                                    self.spin.fail('outlet returned error {}'.format(r))
                                                    r = False
                                                if r:
                                                    self.spin.succeed()
                                                    threading.Thread(target=config.get_outlets, name='auto_pwr_refresh_' + outlet['type']).start()
                                                else:
                                                    self.spin.fail()
                                                    self.error_msgs.append('Error operating linked outlet @ {}'.format(outlet['address']))
                                                    log.warning('{} Error operating linked outlet @ {}'.format(menu_dev, outlet['address']))
                                        # else:
                                        #     print('Linked Outlet returned an error during menu load. Skipping...')

                        try:
                            result = subprocess.run(c, stderr=subprocess.PIPE)
                            _stderr = result.stderr.decode('UTF-8')
                            if _stderr:
                                print(_stderr)
                                _error = key_change_detector(c, _stderr) # pylint: disable=maybe-no-member
                                if _error:
                                    self.error_msgs.append(_error)

                        except KeyboardInterrupt:
                            self.error_msgs.append('Aborted last command based on user input')

                    elif 'function' in menu_actions[ch]:
                        args = menu_actions[ch]['args'] if 'args' in menu_actions[ch] else []
                        kwargs = menu_actions[ch]['kwargs'] if 'kwargs' in menu_actions[ch] else {}
                        response = menu_actions[ch]['function'](*args, **kwargs)
                        if calling_menu in ['power_menu', 'dli_menu']:
                            if menu_actions[ch]['function'].__name__ == 'pwr_all':
                                self.get_dli_outlets(refresh=True, upd_linked=True)
                            else:
                                _grp = menu_actions[ch]['key']
                                _type = menu_actions[ch]['args'][0]
                                _addr = menu_actions[ch]['args'][1]
                                if _type == 'dli':
                                    host_short = _addr.split('.')[0] if '.' in _addr and not config.canbeint(_addr.split('.')[0]) else _addr
                                    _port = menu_actions[ch]['kwargs']['port']
                                    if isinstance(response, bool) and _port is not None:
                                        if menu_actions[ch]['function'].__name__ == 'pwr_toggle':
                                            self.spin.start('Request Sent, Refreshing Outlet States')
                                            threading.Thread(target=self.get_dli_outlets, kwargs={'upd_linked': True, 'refresh': True}, name='pwr_toggle_refresh').start()
                                            if _grp in config.outlets:
                                                config.outlets[_grp]['is_on'][_port]['state'] = response
                                            elif _port != 'all':
                                                config.dli_pwr[_addr][_port]['state'] = response
                                            else:  # dli toggle all
                                                for t in threading.enumerate():
                                                    if t.name == 'pwr_toggle_refresh':
                                                        t.join()
                                                        # toggle all returns True (ON) or False (OFF) if command successfully sent.  In reality the ports 
                                                        # may not be in the  state yet, but dli is working it.  Update menu items to reflect end state
                                                        for p in config.dli_pwr[_addr]:     
                                                            config.dli_pwr[_addr][p]['state'] = response
                                                        break
                                            self.spin.succeed()
                                        elif menu_actions[ch]['function'].__name__ == 'pwr_cycle' and not response:
                                            self.error_msgs.append('{} Port {} if Off.  Cycle is not valid'.format(host_short, _port))
                                        elif menu_actions[ch]['function'].__name__ == 'pwr_rename':
                                            if response:
                                                _name = config._dli[_addr].name(_port)
                                                if _grp in config.outlets:
                                                    config.outlets[_grp]['is_on'][_port]['name'] = _name
                                                else:
                                                    threading.Thread(target=self.get_dli_outlets, kwargs={'upd_linked': True, 'refresh': True}, name='pwr_rename_refresh').start()
                                                config.dli_pwr[_addr][_port]['name'] = _name
                                    elif isinstance(response, str) and _port is not None:
                                        self.error_msgs.append(response)
                                    elif isinstance(response, int):
                                        if menu_actions[ch]['function'].__name__ == 'pwr_cycle' and _port == 'all':
                                            if response != 200:
                                                self.error_msgs.append('Error Response Returned {}'.format(response))
                                        else: # This is a catch as for the most part I've tried to refactor so the pwr library returns port state on success (True/False)
                                            if response in [200, 204]:
                                                self.error_msgs.append('DEV NOTE: check pwr library ret=200 or 204')
                                            else:
                                                self.error_msgs.append('Error returned from dli {} when attempting to {} port {}'.format(
                                                    host_short, menu_actions[ch]['function'].__name__, _port))
                                else:   # type GPIO and tasmota
                                    if menu_actions[ch]['function'].__name__ == 'pwr_toggle':
                                        if _grp in config.outlets:
                                            config.outlets[_grp]['is_on'] = response if isinstance(response, bool) else None
                                    elif menu_actions[ch]['function'].__name__ == 'pwr_cycle' and not response:
                                        self.error_msgs.append('Cycle is not valid for Outlets in the off state')
                                    elif menu_actions[ch]['function'].__name__ == 'pwr_rename':
                                        self.error_msgs.append('rename not yet implemented for {} outlets'.format(_type))
                        elif calling_menu == 'key_menu':
                            if response:
                                for _ in response:
                                    self.error_msgs.append(_)
                elif menu_actions[ch].__name__ in ['power_menu', 'dli_menu']:
                    menu_actions[ch](calling_menu=calling_menu)
                else:
                    menu_actions[ch]()
            except KeyError as e:
                self.error_msgs.append('Invalid selection {}, please try again.'.format(e))
                return False # indicates an error
        return True

    # Connection SubMenu
    def con_menu(self, valid=False):
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
        while not valid:
            self.menu_formatting('header', text=' Connection Settings Menu ')
            print(' 1. Baud [{}]'.format(self.baud))
            print(' 2. Data Bits [{}]'.format(self.data_bits))
            print(' 3. Parity [{}]'.format(self.parity_pretty[self.parity]))
            print(' 4. Flow [{}]'.format(self.flow_pretty[self.flow]))
            text = ' b. Back'
            self.menu_formatting('footer', text=text)
            choice = input(" >>  ")
            valid = self.exec_menu(choice, actions=menu_actions, calling_menu='con_menu')
        # return

    # Baud Menu
    def baud_menu(self):
        config = self.config
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
        std_baud = [110, 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200, 128000, 256000]
        while True:
            self.menu_formatting('header', text=' Select Desired Baud Rate ')

            for key in menu_actions:
                if not callable(menu_actions[key]):
                    print(' {0}. {1}'.format(key, menu_actions[key]))

            text = ' b. Back'
            self.menu_formatting('footer', text=text)
            choice = input(" Baud >>  ")
            ch = choice.lower()
            try:
                if type(menu_actions[ch]) == int:
                    self.baud = menu_actions[ch]
                    menu_actions['con_menu']()
                elif ch == 'c':
                    while True:
                        self.baud = input(' Enter Desired Baud Rate >>  ')
                        if not config.canbeint(self.baud):
                            print('Invalid Entry {}'.format(self.baud))
                        elif int(self.baud) not in std_baud:
                            _choice = input(' {} is not a standard baud rate are you sure? (y/n) >> '.format(self.baud)).lower()
                            if _choice in ['y', 'yes']:
                                break
                        else:
                            break
                    menu_actions['con_menu']()
                else:
                    menu_actions[ch]()
                    break
            except KeyError as e:
                self.error_msgs.append('Invalid selection {} please try again.'.format(e))
                # menu_actions['baud_menu']()
        return

    # Data Bits Menu
    def data_bits_menu(self):
        valid = False
        while not valid:
            self.menu_formatting('header', text=' Enter Desired Data Bits ')
            print(' Default 8, Current {}, Valid range 5-8'.format(self.data_bits))
            self.menu_formatting('footer', text=' b. Back')
            choice = input(' Data Bits >>  ')
            try:
                if choice.lower() == 'x':
                    sys.exit(0)
                elif choice.lower() == 'b':
                    valid = True
                elif int(choice) >= 5 and int(choice) <= 8:
                    self.data_bits = choice
                    valid = True
                else:
                    self.error_msgs.append('Invalid selection {} please try again.'.format(choice))
            except ValueError:
                self.error_msgs.append('Invalid selection {} please try again.'.format(choice))
        self.con_menu()
        return

    def parity_menu(self):
        def print_menu():
            self.menu_formatting('header', text=' Select Desired Parity ')
            print(' Default No Parity\n')
            print(' 1. None')
            print(' 2. Odd')
            print(' 3. Even')
            text = ' b. Back'
            self.menu_formatting('footer', text=text)
        valid = False
        while not valid:
            print_menu()
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
                sys.exit(0)
            else:
                valid = False
                self.error_msgs.append('Invalid selection {} please try again.'.format(choice))
        self.con_menu()

    def flow_menu(self):
        def print_menu():
            self.menu_formatting('header', text=' Select Desired Flow Control ')
            print(' Default No Flow\n')
            print(' 1. No Flow Control (default)')
            print(' 2. Xon/Xoff (software)')
            print(' 3. RTS/CTS (hardware)')
            text = ' b. Back'
            self.menu_formatting('footer', text=text)
        valid = False
        while not valid:
            print_menu()
            choice = input(' Flow >>  ').lower()
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
                    self.con_menu()
                elif choice == 'x':
                    self.exit()
                else:
                    self.error_msgs.append('Invalid selection {} please try again.'.format(choice))
            except Exception as e:
                self.error_msgs.append('Invalid selection {} please try again.'.format(e))
        self.exec_menu('c', calling_menu='flow_menu')

    # Back to main menu
    def back(self):
        self.menu_actions['main_menu']()

    # Exit program
    def exit(self):
        self.go = False
        config = self.config
        if config._dli:
            for address in config._dli:
                if config._dli[address].dli:
                    if getattr(config._dli[address], 'rest'):
                        config._dli[address].dli.close()
                    else:
                        config._dli[address].dli.session.close()
        sys.exit(0)

# =======================
#      MAIN PROGRAM
# =======================


# Main Program
if __name__ == "__main__":
    # if argument passed to menu load the class and print the argument (used to print variables/debug)    
    if len(sys.argv) > 1:
        menu = ConsolePiMenu(bypass_remote=True, do_print=True)
        config = menu.config
        var_in = sys.argv[1].replace('self', 'menu')
        exec('var  = ' + var_in)
        if isinstance(var, (dict, list)):                    # pylint: disable=undefined-variable
            print(json.dumps(var, indent=4, sort_keys=True)) # pylint: disable=undefined-variable
        else:
            print(var)                                       # pylint: disable=undefined-variable
    else:
        # Launch main menu
        menu = ConsolePiMenu()
        while menu.go:
            menu.main_menu()
