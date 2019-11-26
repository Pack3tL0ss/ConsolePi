#!/etc/ConsolePi/venv/bin/python

import ast
import json
import os
import re
import readline
import shlex
import subprocess
import sys
import threading
from collections import OrderedDict as od

import pyudev
# --// ConsolePi imports \\--
from consolepi.common import (ConsolePi_data, bash_command, check_reachable, json_print, format_eof, get_serial_prompt,
                              error_handler, user_input_bool, detect_adapters, append_to_file)
from halo import Halo
from log_symbols import LogSymbols as log_sym  # Enum

# from consolepi.gdrive import GoogleDrive # <-- hidden import burried in refresh method of ConsolePiMenu Class


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
        self.spin2 = Halo(spinner='shark')
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
        self.log_sym_2bang = '\033[1;33m!!\033[0m'
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
        self.dli_exists = self.gpio_exists = self.tasmota_exists = self.linked_exists = False
        if config.power and config.outlets:
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
                if 'linked_devs' in config.outlets[outlet_group] and config.outlets[outlet_group]['linked_devs']:
                    self.linked_exists = True
                if self.dli_exists and self.gpio_exists and self.tasmota_exists and self.linked_exists:
                    break
        if config.power and config.outlet_failures:
            self.get_dli_outlets()   # Update error msg with failure
        self.DEBUG = config.debug
        self.menu_actions = {
            'main_menu': self.main_menu,
            'h': self.picocom_help,
            'r': self.refresh,
            'x': self.exit
        }
        self.http_codes = {404: 'Not Found', 408: 'Request Timed Out - UNREACHABLE'}
        self.display_con_settings = False
        # if self.display_con_settings:
        #     self.menu_actions['c'] = self.con_menu
        if config.power and config.outlets:
            if self.linked_exists or self.gpio_exists or self.tasmota_exists:
                self.menu_actions['p'] = self.power_menu
            if self.dli_exists:
                self.menu_actions['d'] = self.dli_menu
        if not config.root:
            self.error_msgs.append('Running without sudo privs ~ Results may vary!')
            self.error_msgs.append('Use consolepi-menu to launch menu')
        self.udev_pending = False
        

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


    def do_rename_adapter(self, from_name):
        from_name = from_name.replace('/dev/', '')
        config = self.config
        c = self.colors
        error = False
        use_def = True
        c_from_name = '{}{}{}'.format(c['red'], from_name, c['norm'])

        ser2net_parity = {
            'n': 'NONE',
            'e': 'EVEN',
            'o': 'ODD'
        }
        ser2net_flow = {
            'n': '',
            'x': ' -XONXOFF',
            'y': ' -RTSCTS'
        }

        def do_ser2net_line(to_name=None, baud=self.baud, dbits=self.data_bits, parity=ser2net_parity[self.parity], flow=ser2net_flow[self.flow]):
            if os.path.isfile(config.SER2NET_FILE):  # pylint: disable=maybe-no-member
                ports = [re.findall(r'^(7[0-9]{3}):telnet',line) for line in open(config.SER2NET_FILE)]  # pylint: disable=maybe-no-member
                next_port = int(max(ports)[0]) + 1
                next_port = '7001' if not next_port else next_port

            else:
                res = bash_command('sudo cp /etc/ConsolePi/src/ser2net.conf /etc/', eval_errors=False)
                next_port = '7001' # added here looks like flawed logic below
                if res:
                    return res
                else: # TODO this logic looks flawed
                    next_port = '7001'

            ser2net_line = ('\n{telnet_port}:telnet:0:/dev/{alias}:{baud} {dbits}DATABITS {parity} 1STOPBIT {flow} banner'.format(
            telnet_port=next_port,
            alias=to_name,
            baud=baud,
            dbits=dbits,
            parity=parity,
            flow=flow))

            # format_eof(config.SER2NET_FILE) # pylint: disable=maybe-no-member
            # with open(config.SER2NET_FILE, 'a+') as s:  # pylint: disable=maybe-no-member
            #     s.write(ser2net_line)
            append_to_file(config.SER2NET_FILE, ser2net_line)


        def add_to_udev(udev_line, section_marker, label=None):
            found = ser_label_exists = get_next = False # init
            goto = '' # init
            if os.path.isfile(config.RULES_FILE):   # pylint: disable=maybe-no-member
                with open(config.RULES_FILE) as x:  # pylint: disable=maybe-no-member
                    for line in x:
                        if line.strip() == udev_line.strip():
                            return # Line is already in file Nothing to do.
                        if get_next:
                            goto = line
                            get_next = False
                        if section_marker.replace(' END', '') in line:
                            get_next = True
                        elif section_marker in line:
                            found = True
                        elif label and 'LABEL="{}"'.format(label) in line:
                            ser_label_exists = True

                    last_line = line
                        
                goto = goto.split('GOTO=')[1].replace('"', '').strip() if 'GOTO=' in goto else None
                if goto is None:
                    goto = last_line.strip().strip('LABEL=').replace('"', '') if 'LABEL=' in last_line else None
            else:
                error = bash_command('sudo cp /etc/ConsolePi/src/10-ConsolePi.rules /etc/udev/rules.d/')
                found = True
                goto = 'END'

            if goto and 'GOTO=' not in udev_line:
                udev_line = '{}, GOTO="{}"'.format(udev_line, goto)
            
            if label and not ser_label_exists:
                udev_line = 'LABEL="{}"\\n{}'.format(label, udev_line)
            
            # -- // UPDATE RULES FILE WITH FORMATTED LINE \\ --
            if found:
                udev_line = '{}\\n{}'.format(udev_line, section_marker)
                cmd = "sed -i 's/{}/{}/' {}".format(section_marker, udev_line, config.RULES_FILE) # pylint: disable=maybe-no-member
                error = bash_command(cmd, eval_errors=False)
                if error:
                    return error
            else: # Not Using new 10-ConsolePi.rules template just append to file
                if section_marker == '# END BYSERIAL-DEVS':
                    append_to_file(config.RULES_FILE, udev_line)  # pylint: disable=maybe-no-member
                    # with open(config.RULES_FILE, 'a') as r:  # pylint: disable=maybe-no-member
                    #     r.write(udev_line)
                else: # if not by serial device the new template is required
                    return 'Unable to Add Line, please use the new 10.ConsolePi.rules found in src dir and\n' \
                        'add you\'re current rules to the BYSERIAL-DEVS section.'


        # -- Collect desired name from user
        try:
            to_name = None
            while not to_name:
                to_name = input(' [rename {}]: Provide desired name: '.format(c_from_name))
            to_name = to_name.replace('/dev/', '') # strip /dev/ if they thought they needed to include it
            to_name = to_name.replace(' ', '_') # replace any spaces with _ as not allowed (udev rule symlink)
        except KeyboardInterrupt:
            return 'Rename Aborted based on User Input'
        c_to_name = '{}{}{}'.format(c['green'], to_name, c['norm'])

        if user_input_bool(' Please Confirm Rename {} --> {}'.format(c_from_name, c_to_name)):
            _files = [config.SER2NET_FILE, config.RULES_FILE] # pylint: disable=maybe-no-member
            if 'ttyUSB' in from_name or 'ttyACM' in from_name:
                use_def = user_input_bool(' Use default connection values [{} {}{}1 Flow: {}]'.format(
                    self.baud, self.data_bits, self.parity.upper(), self.flow_pretty[self.flow]))
                if not use_def:
                    self.con_menu(rename=True)

                # context = pyudev.Context()
                # _tty = pyudev.Devices.from_name(context, 'tty', from_name)
                
                # id_prod = _tty.get('ID_MODEL_ID')
                # id_serial = _tty.get('ID_SERIAL_SHORT')
                # id_vendor = _tty.get('ID_VENDOR_ID')

                # Collect locally attached adapters (new func)
                devs = detect_adapters()
                if from_name in devs['by_name']:
                    _tty = devs['by_name'][from_name]
                    id_prod = _tty['id_prod']
                    id_model = _tty['id_model'] # pylint: disable=unused-variable
                    id_vendorid = _tty['id_vendorid']
                    id_vendor = _tty['id_vendor'] # pylint: disable=unused-variable
                    id_serial = _tty['id_serial']
                    id_ifnum = _tty['id_ifnum']
                    id_path = _tty['id_path']
                    root_dev = _tty['root_dev']
                else:
                    return 'ERROR: Adapter no longer found'

                if not root_dev:
                    return 'Did you really create an alias using with  ttyUSB or ttyACM in it (same as root devices)? Rename failed cause you\'re silly'

                if id_prod and id_serial and id_vendorid:

                    if id_serial not in devs['dup_ser']:
                        
                        udev_line = ('SUBSYSTEM=="tty", ATTRS{{idVendor}}=="{}", ATTRS{{idProduct}}=="{}", ' \
                            'ATTRS{{serial}}=="{}", SYMLINK+="{}"'.format(
                                id_vendorid, id_prod, id_serial, to_name))

                        error = None
                        while not error:
                            error = add_to_udev(udev_line, '# END BYSERIAL-DEVS')
                            error = do_ser2net_line(to_name=to_name)
                            break
                    
                    else:   # Multi-Port Adapter with presenting same serial for all ports (different ports)
                        # SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6011", ATTRS{serial}=="FT4213OP", GOTO="FT4213OP"
                        udev_line = ('SUBSYSTEM=="tty", ATTRS{{idVendor}}=="{0}", ATTRS{{idProduct}}=="{1}", ' \
                            'ATTRS{{serial}}=="{2}", GOTO="{2}"'.format(
                                id_vendorid, id_prod, id_serial))
                        
                        error = None
                        while not error:
                            error = add_to_udev(udev_line, '# END BYPORT-POINTERS')
                            # ENV{ID_USB_INTERFACE_NUM}=="00", SYMLINK+="FT4232H_port1", GOTO="END"
                            udev_line = ('ENV{{ID_USB_INTERFACE_NUM}}=="{}", SYMLINK+="{}"'.format(
                                    id_ifnum, to_name))
                            error = add_to_udev(udev_line, '# END BYPORT-DEVS', label=id_serial)
                            error = do_ser2net_line(to_name=to_name)
                            break


                else: # -- Adapter missing details (most likely serial#) --
                    config.log.warn('[ADD ADAPTER] Unable to add udev rule: idVendor={}, idProduct={}, serial#={}'.format(
                                id_vendorid, id_prod, id_serial))
                    print(''' 
                        This Device Does not present a serial # (LAME!).  So the adapter itself can\'t be uniquely identified.
                        If the adapter will remain plugged into the same port (directly or on HUB).  The name / alias can be
                        mapped to the USB port.  Any adapter or device for that matter that is plugged into this port will
                        use this alias.

                        Alternatively We can just do a non-persistent rename, which will go away once the you exit the menu.
                     
                        ''')

                    do_bypath = user_input_bool(' Permanently map an alias to the USB port')
                    if not do_bypath:
                        do_temp = user_input_bool(' Give the Adapter a non persistent name for the duration of this menu session')
                        if do_temp:
                            pass # by not setting an error the name will be updated below
                        else:
                            error = ['Unable to add udev rule adapter missing details', 'idVendor={}, idProduct={}, serial#={}'.format(
                                id_vendorid, id_prod, id_serial)]
                    else:
                        udev_line = ('SUBSYSTEM=="tty", ENV{ID_PATH}=="{}", SYMLINK+="{}"'.format(id_path, to_name))
                        # TODO add line with vendor & model - need lame ass adapter with no serial to test
                        #   This would at least limit the alias to that vendor/model adapter.

            else:   # renaming previously named port.  
                for _file in _files:
                    cmd = 'sudo sed -i "s/{0}{3}/{1}{3}/g" {2} && grep -q "{1}{3}" {2} && [ $(grep -c "{0}{3}" {2}) -eq 0 ]'.format(
                        from_name,
                        to_name,
                        _file,
                        ':' if 'ser2net.conf' in _file else ''
                        )
                    error = bash_command(cmd)
                    if error:
                        return [error.split('\n'), 'Failed to change {} --> {} in {}'.format(from_name, to_name, _file)]

            if not error:
                for _dev in config.local[config.hostname]['adapters']:
                    if _dev['dev'].replace('/dev/', '') == from_name:
                        _dev['dev'] = '/dev/' + to_name # TODO Strip the /dev/ once verified no ill effects
                        if not use_def:
                            _dev['baud'] = self.baud
                            _dev['flow'] = self.flow
                            _dev['parity'] = self.parity
                            _dev['dbits'] = self.data_bits
                        break
                self.data['local'] = config.local
                self.udev_pending = True    # toggle for exit function if they exit directly from rename memu

        else:
            return 'Aborted based on user input'


    def get_dli_outlets(self, refresh=False, upd_linked=False, key='outlets'):
        # pylint: disable=maybe-no-member
        config = self.config
        config.outlet_update(refresh=refresh, upd_linked=upd_linked)
        if config.outlet_failures:
            for _ in config.outlet_failures:
                self.error_msgs.append(config.outlet_failures[_]['error'])
        return getattr(config, key)         

    # get remote consoles from local cache refresh function will check/update cloud file and update local cache
    def get_remote(self, data=None, refresh=False):
        config = self.config
        log = config.log
        _msg = '[GET REM] Getting Remote ConsolePis with attached Serial Adapters from local cache'
        self.spin.start(_msg)
        log.info('[GET REM] Starting fetch from local cache')

        if data is None or len(data) == 0:
            data = config.get_local_cloud_file()

        # / Get Remotes from cache spinner update
        if data:
            self.spin.succeed()
        else:
            self.spin.warn(_msg + '\n\t' + self.log_sym_warn + 'No Remotes in Local Cache')

        if config.hostname in data:
            del data[config.hostname]
            log.error('[GET REM] Local cache included entry for self - do you have other ConsolePis using the same hostname?')
            self.error_msgs.append('[WARNING] Local cache included entry for self - do you have other ConsolePis using the same hostname?')

        # Verify Remote ConsolePi details and reachability
        print('\n-- Verifying Reachability of Remotes --')
        update_cache = False
        pop_list = []
        for remotepi in data:
            this = data[remotepi]
            # print('  {} Found...  Checking reachability'.format(remotepi), end='')
            self.spin.start('{}'.format(remotepi))
            if 'rem_ip' in this and this['rem_ip'] is not None and check_reachable(this['rem_ip'], 22):
                self.spin.succeed()
                log.info('[GET REM] Found {0} in Local Cache, reachable via {1}'.format(remotepi, this['rem_ip']))
                #this['adapters'] = build_adapter_commands(this)
            else:
                update_cache = True # If rem_ip wasn't valid update even if no reachable ip found.  (to update fail cnt)
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
                if 'fail_cnt' in data[remotepi] and data[remotepi]['fail_cnt'] < 2: # Removal Error will display no need for both
                    self.error_msgs.append('Cached Remote \'{}\' is unreachable'.format(remotepi))
                self.spin.fail()
                pop_list.append(remotepi)  # Remove Unreachable remote from cache
        
        # update local cache if any ConsolePis found UnReachable
        if update_cache:
            if len(pop_list) > 0:
                for remotepi in pop_list:
                    if 'fail_cnt' in data[remotepi]:
                            data[remotepi]['fail_cnt'] += 1
                            if data[remotepi]['fail_cnt'] >= 3: # remove from local cache after 3 failures (cloud or mdns will repopulate if discovered)
                                removed = data.pop(remotepi)
                                log.warning('[GET REM] {} has been removed from Local Cache after {} failed attempts'.format(
                                    remotepi, removed['fail_cnt']))
                                self.error_msgs.append('{} removed from local cache after 3 failed attempts to connect'.format(remotepi))
                    else:
                        data[remotepi]['fail_cnt'] = 1
            data = config.update_local_cloud_file(data)

        return data

    # Update with Data from ConsolePi.csv on Gdrive and local cache populated by mdns.  Update Gdrive with our data
    # TODO rem_update deprecated and can be removed
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
            config.local = {self.hostname: {'adapters': config.get_local(), 'interfaces': config.get_if_ips(), 'user': 'pi'}}
            self.data['local'] = config.local
            log.debug('Final Data set collected for {}: {}'.format(self.hostname, self.data['local']))

        # Get details from Google Drive - once populated will skip
        if self.do_cloud and not self.local_only:
            if config.cloud_svc == 'gdrive' and self.cloud is None:
                # burried import until I find out why this import takes so @#%$@#% long.  Not imported until 1st refresh is called
                with Halo(text='Loading Google Drive Library', spinner='dots1'):
                    from consolepi.gdrive import GoogleDrive
                self.cloud = GoogleDrive(config.log, hostname=self.hostname)
                log.info('[MENU REFRESH] Gdrive init')

            # Pass Local Data to update_sheet method get remotes found on sheet as return
            # update sheets function updates local_cloud_file
            _msg = '[MENU REFRESH] Updating to/from {}'.format(config.cloud_svc)
            log.info(_msg)
            self.spin.start(_msg)
            # -- // SYNC DATA WITH GDRIVE \\ --
            remote_consoles = self.cloud.update_files(self.data['local'])
            if remote_consoles and 'Gdrive-Error:' not in remote_consoles:
                self.spin.succeed(_msg + '\n\tFound {} Remotes via Gdrive Sync'.format(len(remote_consoles)))
            elif 'Gdrive-Error:' in remote_consoles:
                self.spin.fail('{}\n\t{} {}'.format(_msg, self.log_sym_error, remote_consoles))
                self.error_msgs.append(remote_consoles) # display error returned from gdrive module
            else:
                self.spin.warn(_msg + '\n\tNo Remotes Found via Gdrive Sync')
            if len(remote_consoles) > 0:
                _msg = '[MENU REFRESH] Updating Local Cache with data from {}'.format(config.cloud_svc)
                log.info(_msg)
                self.spin.start(_msg)
                config.update_local_cloud_file(remote_consoles)
                self.spin.succeed(_msg)
            else:
                plog('[MENU REFRESH] No Remote ConsolePis found on {}'.format(config.cloud_svc), level='warning')
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
        head_len = len(self.menu_formatting('header', text=header, do_print=False)[0])
        # TODO don't think foot_len is being calculated correctly
        foot_len = len(self.menu_formatting('footer', text=footer, do_print=False)[0])
        ''' 
        generate list for each sections where each line is padded to width of longest line
        collect width of longest line and # of rows/menu-entries for each section

        All of this is used to format the header/footer width and to ensure consistent formatting
        during print of multiple columns
        '''
        body = [body] if isinstance(body[0], str) else body
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
        THIS SECTION IS UNDER DEV NOT USED YET
        print multiple sections vertically - determine best cut point to start next column
        ''' 
        # _rows = line_dict['body']['rows']
        # tot_body_rows = sum(_rows)
        # # TODO what if rows for 1 section is greater than term rows
        # tty_body_avail = (config.rows - head_len - foot_len)
        # _begin = 0
        # _end = 1
        # _iter_start_stop = []
        # _pass = 0
        # # -- won't fit in a single column calc sections we can put in the column
        # # #if not tot_body_rows < tty_body_avail:   # Force at least 2 cols while testing
        # while True:
        #     r = sum(_rows[_begin:_end])
        #     if not r > tty_body_avail and not r > tot_body_rows / 2:
        #         _end += 1
        #     else:
        #         # _end = _end - 1 if sum(_rows[_begin:_end]) > tty_body_avail and _end > 1 else _end
        #         _iter_start_stop.append([_begin, _end])
        #         _begin = _end
        #         _end = _begin + 1

        #     if _end == (len(_rows)):
        #         _iter_start_stop.append([_begin, _end])
        #         break
        #     elif _pass > 10:
        #         self.error_msgs.append('menu formatter exceeded 10 passses and gave up!!!')
        #         config.log('menu formatter exceeded 10 passses and gave up!!!')
        #     _pass += 1
        
        # # This is a reset of what was initially done above.  This method still being tested
        # sections = []
        # _tot_width = []
        # for _i in _iter_start_stop:
        #     this_max_width = max(line_dict['body']['width'][_i[0]:_i[1]])
        #     _tot_width.append(this_max_width)
        #     _column_list = []
        #     # i = 0
        #     for _s in line_dict['body']['sections'][_i[0]:_i[1]]:
        #         for _line in _s:
        #             _fnl_line = '{}{}'.format(_line, ' ' * (this_max_width - len(_line)))
        #             _s[_s.index(_line)] = _fnl_line
        #         _column_list += _s
        #         # i += 1
        #     sections.append(_column_list)

        # line_dict['body']['sections'] = sections     
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
                        self.error_msgs.append('tty too small for full menu display')
                        self.error_msgs.append('Use Scrollback')
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
        # colors = self.colors

        # -- append any errors from config (ConsolePi_data object)
        if config.error_msgs:
            self.error_msgs += config.error_msgs
            config.error_msgs = []

        # -- Adjust width if there is an error msg longer then the current width            
        if self.error_msgs:
            _error_lens = []
            for _error in self.error_msgs:
                _error_lens.append(self.format_line(_error)[0])
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
                _line_len, _line = self.format_line(_line)
                width_list.append(_line_len)
                mlines.append(_line)
                index += 1
            max_len = 0 if not width_list else max(width_list)
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
            mlines.append(' x.  exit\n')
            mlines.append('=' * width)

            # --// ERRORs - append to footer \\-- #
            if len(self.error_msgs) > 0:
                errors = [] 
                [errors.append(e) for e in self.error_msgs if e not in errors] # Remove Duplicates only occurs when menu launches direct to Power menu
                for _error in errors:
                    error_len, _error = self.format_line(_error.strip())    # remove trail and leading spaces for error msgs
                    # x = ((width - (len(_error) + 2)) / 2 ) - 1 # _error + 3 is for log_sym
                    x = ((width - (error_len + 4)) / 2 )
                    # mlines.append('*{}{}  {}{}*'.format(' ' * int(x),self.log_sym_warn, _error, ' ' * int(x) if x == int(x) else ' ' * (int(x) + 1)))
                    mlines.append('{}{}{}{}{}'.format(self.log_sym_2bang, ' ' * int(x), _error, ' ' * int(x) if x == int(x) else ' ' * (int(x) + 1), self.log_sym_2bang))
                mlines.append('=' * width)
                if do_print:
                    self.error_msgs = [] # clear error messages after print

        else:
            print('formatting function passed an invalid section')
            
        # --// DISPLAY THE MENU \\--
        if do_print:
            for _line in mlines:
                print(_line)

        return mlines, max_len

    def pad_lines(self, line_list, max_width, width_list, sub=True):
        for _line in line_list:
            i = line_list.index(_line)
            line_list[i] = '{}{}'.format(_line, ' ' * (max_width - width_list[i]))
        return line_list

    def format_line(self, line):
        # accepts line as str with menu formatting placeholders ({{red}}, {{green}}, etc)
        # OR line as bool when bool it will convert it to a formatted ON/OFF str
        # returns 2 value tuple line length, formatted-line
        if isinstance(line, bool):
            line = '{{green}}ON{{norm}}' if line else '{{red}}OFF{{norm}}'
        colors = self.colors
        _l = line
        for c in colors:
            _l = _l.replace('{{' + c + '}}', '')
            line = line.replace('{{' + c + '}}', colors[c])
        return len(_l), line

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
        # colors = self.colors
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
                    self.spin.start('Refreshing Outlets')
                    outlets = self.get_dli_outlets(refresh=True, upd_linked=True)
                    self.spin.stop()
            if not self.DEBUG:
                os.system('clear')

            self.menu_formatting('header', text=' Power Control Menu ')
            print('  enter item # to toggle power state on outlet')
            print('  enter c + item # i.e. "c2" to cycle power on outlet')
            print('')

            # Build menu items for each linked outlet
            state_list = []
            for r in sorted(outlets):
                outlet = outlets[r]
                
                # strip off all but hostname if address is fqdn
                if isinstance(outlet['address'], str):
                    _address = outlet['address'].split('.')[0] if '.' in outlet['address'] and not config.canbeint(outlet['address'].split('.')[0]) else outlet['address']

                # header = '     [{}] {}{}'.format(outlet['type'], r, ' @ ' + _address if outlet['type'].lower() == 'dli' else '')
                # -- // DLI OUTLET MENU LINE(s) \\ --
                if outlet['type'].lower() == 'dli':
                    if 'linked_ports' in outlet and outlet['linked_ports'] and outlet['is_on']:     # Avoid orphan header when no outlets are linked to a defined dli
                        # print('\n' + header + '\n     ' + '-' * (len(header) - 5))
                        for dli_port in outlet['is_on']:
                            _outlet = outlet['is_on'][dli_port]
                            _state = states[_outlet['state']]
                            state_list.append(_outlet['state'])
                            _state = self.format_line(_state)[1]
                            # print(' {}. [{}] port {} ({})'.format(item, _state, dli_port, _outlet['name']))
                            print(' {}. [{}] {} ({} Port:{})'.format(item, _state, _outlet['name'], _address, dli_port))
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
                # -- // GPIO or tasmota OUTLET MENU LINE \\ --
                else:
                    # pwr functions put any errors (aborts) in config.outlets[grp]['error']
                    if 'errors' in config.outlets[r]:
                        self.error_msgs.append('{} - {}'.format(r, config.outlets[r]['errors']))
                        del config.outlets[r]['errors']
                    if isinstance(outlet['is_on'], bool):
                        _state = states[outlet['is_on']]
                        state_list.append(outlet['is_on'])
                        # print('\n' + header + '\n     ' + '-' * (len(header) - 5))
                        _state = self.format_line(_state)[1]
                        print(' {}. [{}] {}'.format(item, _state, r))
                        menu_actions[str(item)] = {
                            'function': config.pwr_toggle,
                            'args': [outlet['type'], outlet['address']],
                            'kwargs': {
                                'noff': True if not 'noff' in outlet else outlet['noff']},
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
                    else:   # refactored power.py get_outlets this should never hit
                        self.error_msgs.append('DEV NOTE {} outlet state is not bool: {}'.format(r, outlet['error']))
            
            if item > 2:
                print('')
                if False in state_list:
                    print(' all on:    Turn all outlets {}ON{}'.format(self.colors['green'], self.colors['norm']))
                    menu_actions['all on'] = {
                        'function': config.pwr_all, # pylint: disable=maybe-no-member
                        'kwargs': {'outlets': outlets, 'action': 'toggle', 'desired_state': True}
                        }
                if True in state_list:
                    print(' all off:   Turn all outlets {}OFF{}'.format(self.colors['red'], self.colors['norm']))
                    menu_actions['all off'] = {
                        'function': config.pwr_all, # pylint: disable=maybe-no-member
                        'kwargs': {'outlets': outlets, 'action': 'toggle', 'desired_state': False}
                        }
                    print(' cycle all: Cycle all outlets {2}ON{1}{3}{0}OFF{1}{3}{2}ON{1}'.format(self.colors['red'], self.colors['norm'], self.colors['green'], u'\u00B7'))
                    menu_actions['cycle all'] = {
                        'function': config.pwr_all, # pylint: disable=maybe-no-member
                        'kwargs': {'outlets': outlets, 'action': 'cycle'}
                        }
            
            text = [' b.  Back', ' r.  Refresh']
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
                ' b.  Back{{r}}menu # alone will toggle the port,',
                ' r.  Refresh{{r}}c# to cycle or r# to rename [i.e. \'c1\']'
            ]
            if (not calling_menu == 'power_menu' and config.outlets) and (self.gpio_exists or self.tasmota_exists or self.linked_exists):
                menu_actions['p'] = self.power_menu
                footer.insert(0, ' p.  Power Control Menu (linked, GPIO, tasmota)')
            # for dli menu remove in tasmota errors
            # self.error_msgs = [self.error_msgs.remove(_error) for _error in self.error_msgs if 'TASMOTA' in _error]
            for _error in self.error_msgs:
                if 'TASMOTA' in _error:
                    self.error_msgs.remove(_error)
            self.print_mlines(outer_body, header=header, footer=footer, subs=slines, force_cols=True, by_tens=True)

            choice = input(" >>  ").lower()
            if choice == 'r': 
                self.spin.start('Refreshing Outlets')
                dli_dict = self.get_dli_outlets(refresh=True, key='dli_pwr')
                self.spin.succeed()
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
            print('\n a.  Send SSH key to *all* remotes listed above')
            menu_actions['a'] = {'function': config.gen_copy_key, \
            'kwargs': {'rem_user': rem_user}}
        
            self.menu_formatting('footer', text=' b.  Back')
            choice = input(" >>  ")
            
            self.exec_menu(choice, actions=menu_actions, calling_menu='key_menu')

    def gen_adapter_lines(self, adapters, item=1, remote=False, host=None, rename=False):
        rem = self.data['remote']
        config = self.config
        flow_pretty = {
            'x': 'xon/xoff',
            'h': 'RTS/CTS',
            'n': 'NONE'
        }
        menu_actions = {}
        mlines = []
        for _dev in sorted(adapters, key = lambda i: i['port']):
            this_dev = _dev['dev']
            try:
                def_indicator = ''
                baud = _dev['baud']
                dbits = _dev['dbits']
                flow = _dev['flow']
                parity = _dev['parity']
            except KeyError:
                def_indicator = '**'
                baud = self.baud
                flow = self.flow
                dbits = self.data_bits
                parity = self.parity
                self.display_con_settings = True

            # Generate Menu Line
            menu_line = '{} {}[{} {}{}1]'.format(
                this_dev.strip('/dev/'), def_indicator, baud, dbits, parity[0].upper())
            if flow != 'n' and flow in flow_pretty:
                menu_line += ' {}'.format(flow_pretty[flow])
            mlines.append(menu_line)

            if not remote:
                if not rename:
                    # -- // LOCAL ADAPTERS \\ --
                    # Generate Command executed for Menu Line
                    _cmd = 'picocom {0} -b{1} -f{2} -d{3} -p{4}'.format(this_dev, baud, flow, dbits, parity)
                    menu_actions[str(item)] = {'cmd': _cmd}
                else:
                    menu_actions[str(item)] = {'function': self.do_rename_adapter, 'args': [this_dev]}
                    menu_actions['s' + str(item)] = {'function': self.show_adapter_details, 'args': [this_dev]}
                    menu_actions['q' + str(item)] = {'function': self.show_serial_prompt, 'args': [this_dev]}
            else:
                # -- // REMOTE ADAPTERS \\ --
                _cmd = 'ssh -t {0}@{1} "{2} picocom {3} -b{4} -f{5} -d{6} -p{7}"'.format(
                    rem[host]['user'], rem[host]['rem_ip'], config.REM_LAUNCH, _dev['dev'], baud, flow, dbits, parity) # pylint: disable=maybe-no-member
                menu_actions[str(item)] = {'cmd': _cmd} 
            item += 1

        return mlines, menu_actions, item

    def show_adapter_details(self, adapter):
        config = self.config
        dev_name = adapter.replace('/dev/', '')
        _dev = config.new_adapters['by_name'][dev_name]
        print( ' --- Details For {} --- '.format(dev_name))
        for k in sorted(_dev.keys()):
            print('{}: {}'.format(k, _dev[k]))
        print('')

        input('\nPress Any Key To Continue\n')

    def show_serial_prompt(self, adapter):
        with Halo(text='Prompt Displayed on Port: ', spinner='dots1', placement='right'):
            p = get_serial_prompt(adapter)
            e = self.format_line('{{red}}No text was rcvd from port{{norm}}')[1]
        print('Prompt Displayed on Port: {}'.format(p if p else e))
        
        input('\nPress Any Key To Continue\n')

    def rename_menu(self):
        # config = self.config
        choice = ''
        menu_actions = {}
        while choice not in ['b']:
            loc = self.data['local'][self.hostname]['adapters']
            if not self.DEBUG:
                os.system('clear')               

            slines = []
            mlines, menu_actions, item = self.gen_adapter_lines(loc, rename=True) # pylint: disable=unused-variable
            slines.append('Select Adapter to Rename')   # list of strings index to index match with body list of lists
            foot = [
                ' s#. prepend s to the menu-item to show details for the adapter i.e. \'s1\'',
                ' q#. prepend q to the menu-item to attempt to get/display a prompt from the device i.e. \'q1\'',
                '',
                ' b.  Back'
            ]
            self.print_mlines(mlines, header='Rename Local Adapters',footer=foot, subs=slines, do_format=False)
            menu_actions['x'] = self.exit

            choice = input(" >>  ").lower()
            if choice in menu_actions:
                if not choice == 'b':
                    self.exec_menu(choice, actions=menu_actions, calling_menu='rename_menu')
            else:
                if choice and choice != 'b':
                    self.error_msgs.append('Invalid Selection \'{}\''.format(choice))

        # trigger refresh udev and restart ser2net after rename
        if self.udev_pending:
            cmd = 'sudo udevadm control --reload && sudo udevadm trigger && sudo systemctl stop ser2net && sleep 1 && sudo systemctl start ser2net '
            with Halo(text='Triggering reload of udev do to name change', spinner='dots1'):
                error = bash_command(cmd)
            if not error:
                self.udev_pending = False
            else:
                return error

    def main_menu(self):
        loc = self.data['local'][self.hostname]['adapters']
        rem = self.data['remote']
        config = self.config
        if not self.DEBUG:
            os.system('clear')

        # Launch to Power Menu if no adapters or remotes are found
        if not loc and not rem and config.power and config.outlets:
                self.error_msgs.append('No Adapters Found, Outlets Found... Launching to Power Menu')
                self.error_msgs.append('use option "b" to access main menu options')
                if self.dli_exists and not self.linked_exists:
                    self.exec_menu('dli_menu')
                else:
                    self.exec_menu('power_menu')
                
        # Build menu items for each locally connected serial adapter
        outer_body = []
        slines = []
        mlines, menu_actions, item = self.gen_adapter_lines(loc)
        if menu_actions:
            self.menu_actions = {**self.menu_actions, **menu_actions}

        outer_body.append(mlines)   # list of lists where each list = printed menu lines
        slines.append('[LOCAL] Directly Connected')   # Sub-headers: list of strings index to index match with outer_body list of lists
            
        # Build menu items for each serial adapter found on remote ConsolePis
        for host in sorted(rem):
            if rem[host]['rem_ip'] is not None and len(rem[host]['adapters']) > 0:
                self.remotes_connected = True
                mlines, menu_actions, item = self.gen_adapter_lines(rem[host]['adapters'], item=item, remote=True, host=host)
                if menu_actions:
                    self.menu_actions = {**self.menu_actions, **menu_actions}

                outer_body.append(mlines)   # list of lists where each list = printed menu lines
                slines.append('[Remote] {} @ {}'.format(host, rem[host]['rem_ip']))   # list of strings index to index match with body list of lists

        # -- General Menu Command Options --
        text = []
        if self.display_con_settings: # pylint disable=no-member
            text.append(' c.  Change default Serial Settings **[{0} {1}{2}1 flow={3}] '.format(
                self.baud, self.data_bits, self.parity.upper(), self.flow_pretty[self.flow]))
            self.menu_actions['c'] = self.con_menu
        text.append(' h.  Display picocom help')
        if config.power and config.outlets is not None:
            if self.linked_exists or self.gpio_exists or self.tasmota_exists:
                text.append(' p.  Power Control Menu')
            if self.dli_exists:
                text.append(' d.  [dli] Web Power Switch Menu')
        if self.remotes_connected:
            self.menu_actions['k'] = self.key_menu
            self.menu_actions['s'] = self.rshell_menu
            text.append(' k.  Distribute SSH Key to Remote Hosts')
            text.append(' s.  Remote Shell Menu (Connect to Remote ConsolePi Shell)')
        if loc: # and config.root:
            text.append(' rn. Rename Local Adapters')
            self.menu_actions['rn'] = self.rename_menu
        text.append(' r.  Refresh')

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

            text = ' b.  Back'
            self.menu_formatting('footer', text=text)
            choice = input(" >>  ")
            self.exec_menu(choice, actions=menu_actions, calling_menu='rshell_menu')


    # Execute menu
    def exec_menu(self, choice, actions=None, calling_menu='main_menu'):
        menu_actions = actions if actions is not None else self.menu_actions
        config = self.config
        log = config.log
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
                            desired_state = True
                            # TODO remove /dev/ from power.json (don't require /dev/)
                            if '/dev/' in c[1] or ( len(c) >= 4 and '/dev/' in c[3] ):
                                menu_dev = c[1] if c[0] != 'ssh' else c[3].split()[1]
                                menu_dev = menu_dev.replace('/dev/', '') if menu_dev not in config.outlet_by_dev else menu_dev
                                if menu_dev in config.outlet_by_dev:    # See Dictionary Reference for structure
                                    for outlet in config.outlet_by_dev[menu_dev]:
                                        _addr = outlet['address']

                                        # -- // DLI web power switch Auto Power On \\ --
                                        if outlet['type'].lower() == 'dli':
                                            host_short = _addr.split('.')[0] if '.' in _addr and not config.canbeint(_addr.split('.')[0]) else _addr
                                            # is_on is a dict for dli outlets in the
                                            # 'is_on': {<dli-port>: 'name': <dli-port-name>, 'state': <True|False>} ... where True = ON
                                            for p in outlet['is_on']:
                                                self.spin.start('Ensuring linked outlet: [{}]:{} port: {}({}) is powered on'.format(
                                                    outlet['type'], host_short, p, outlet['is_on'][p]['name']))
                                                if not outlet['is_on'][p]['state']:   # This is just checking what's in the dict not querying the DLI
                                                    r = config.pwr_toggle(outlet['type'], outlet['address'], desired_state=desired_state, port=p)
                                                    if isinstance(r, bool):
                                                        if r:
                                                            self.spin.succeed()
                                                            # start a thread to update outlet state in background
                                                            threading.Thread(target=config.outlet_update, kwargs={'refresh': True, 'upd_linked': True}, name='auto_pwr_refresh_dli').start()
                                                        else:
                                                            self.spin.fail()
                                                    else:
                                                        self.spin.fail('Error operating linked outlet {} @ {} ({})'.format(
                                                            menu_dev.replace('/dev/', ''), outlet['address'], r))
                                                        log.warning('{} Error operating linked outlet @ {}'.format(menu_dev, outlet['address']))
                                                        self.error_msgs.append('Error operating linked outlet @ {}'.format(outlet['address']))
                                                else: # Outlet is already in powered on state
                                                    self.spin.succeed()
                                                
                                        # -- // GPIO & TASMOTA Auto Power On \\ --
                                        else:
                                            msg = 'Ensuring linked outlet: {} ({}:{}) is powered on'.format(
                                                    outlet['grp_name'], outlet['type'], outlet['address'])
                                            self.spin.start(msg)
                                            r = config.pwr_toggle(outlet['type'], outlet['address'], desired_state=desired_state,
                                                noff=outlet['noff'] if outlet['type'].upper() == 'GPIO' else True)
                                            # TODO Below (first if) should never happen just a fail-safe after refactoring the returns from power.py Can eventually remove
                                            if not isinstance(r, bool) and isinstance(r, int) and r <= 1: 
                                                self.error_msgs.append('the return from {} {} was an int({})'.format(
                                                    outlet['type'], outlet['address'], r
                                                ))
                                            elif isinstance(r, int) and r > 1:  # return is an error
                                                self.spin.fail('{}\n{} {}'.format(
                                                    msg, self.log_sym_error, self.http_codes[r]))
                                                r = False
                                            else:   # return is bool which is what we expect
                                                if r:
                                                    self.spin.succeed()
                                                    threading.Thread(target=config.get_outlets, name='auto_pwr_refresh_' + outlet['type']).start()
                                                else:
                                                    self.spin.fail()
                                                    self.error_msgs.append('Error operating linked outlet @ {}'.format(outlet['address']))
                                                    log.warning('{} Error operating linked outlet @ {}'.format(menu_dev, outlet['address']))

                        # --// execute the command \\--
                        try:
                            result = subprocess.run(c, stderr=subprocess.PIPE)
                            _stderr = result.stderr.decode('UTF-8')
                            if _stderr or result.returncode == 1:
                                # print('\n' + _stderr.replace('ERROR: ', ''))
                                _error = error_handler(c, _stderr) # pylint: disable=maybe-no-member
                                if _error:
                                    self.error_msgs.append(_error)
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
                            else: # no spinner
                                response = menu_actions[ch]['function'](*args, **kwargs)
                            # --// Power Menus \\--
                            if calling_menu in ['power_menu', 'dli_menu']:
                                if menu_actions[ch]['function'].__name__ == 'pwr_all':
                                    with Halo(text='Refreshing Outlet States', spinner='dots'):
                                        self.get_dli_outlets(refresh=True, upd_linked=True)
                                else:
                                    _grp = menu_actions[ch]['key']
                                    _type = menu_actions[ch]['args'][0]
                                    _addr = menu_actions[ch]['args'][1]
                                    # --// EVAL responses for dli outlets \\--
                                    if _type == 'dli':
                                        host_short = _addr.split('.')[0] if '.' in _addr and not config.canbeint(_addr.split('.')[0]) else _addr
                                        _port = menu_actions[ch]['kwargs']['port']
                                        # --// Operations performed on ALL outlets \\--
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
                                                            t.join()    # if refresh thread is running join ~ wait for it to complete. # TODO Don't think this works or below 
                                                                        # wouldn't have been necessary.
                                                            # toggle all returns True (ON) or False (OFF) if command successfully sent.  In reality the ports 
                                                            # may not be in the  state yet, but dli is working it.  Update menu items to reflect end state
                                                            for p in config.dli_pwr[_addr]:     
                                                                config.dli_pwr[_addr][p]['state'] = response
                                                            break
                                                self.spin.stop()
                                            # Cycle operation returns False if outlet is off, only valid on powered outlets
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
                                        # --// str responses are errors append to error_msgs \\--
                                        elif isinstance(response, str) and _port is not None:
                                            self.error_msgs.append(response)
                                        # --// Can Remove After Refactoring all responses to bool or str \\--
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
                                    # --// EVAL responses for GPIO and tasmota outlets \\--
                                    else:
                                        if menu_actions[ch]['function'].__name__ == 'pwr_toggle':
                                            if _grp in config.outlets:
                                                if isinstance(response, bool):
                                                    config.outlets[_grp]['is_on'] = response
                                                else:
                                                    config.outlets[_grp]['errors'] = response
                                        elif menu_actions[ch]['function'].__name__ == 'pwr_cycle' and not response:
                                            self.error_msgs.append('Cycle is not valid for Outlets in the off state')
                                        elif menu_actions[ch]['function'].__name__ == 'pwr_rename':
                                            self.error_msgs.append('rename not yet implemented for {} outlets'.format(_type))
                            elif calling_menu in['key_menu', 'rename_menu']:
                                if response:
                                    response = [response] if isinstance(response, str) else response
                                    for _ in response:
                                        if _: # strips empty lines
                                            self.error_msgs.append(_)
                        else:   # not confirmed
                            self.error_msgs.append('Operation Aborted by User')
                elif menu_actions[ch].__name__ in ['power_menu', 'dli_menu']:
                    menu_actions[ch](calling_menu=calling_menu)
                else:
                    menu_actions[ch]()
            except KeyError as e:
                self.error_msgs.append('Invalid selection {}, please try again.'.format(e))
                return False # indicates an error
        return True

    def confirm_and_spin(self, action_dict, *args, **kwargs):
        '''
        called by the exec menu. 
        Collects user Confirmation if operation warrants it (Powering off or cycle outlets)
        and Generates appropriate spinner text

        returns tuple
            0: Bool True if user confirmed False if aborted
            1: str spinner_text used in exec_menu while function runs
            3: str name (for rename operation)
        '''
        config = self.config
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
                    port_name = config.dli_pwr[_addr][port]['name']
                    to_state = not config.dli_pwr[_addr][port]['state']
            else:
                port = '{}:{}'.format(_type, _addr)
                port_name = _grp
                to_state = not config.outlets[_grp]['is_on']
        if _type == 'dli' or _type == 'tasmota':
            host_short = _addr.split('.')[0] if '.' in _addr and not config.canbeint(_addr.split('.')[0]) else _addr
        else:
            host_short = None
        
        prompt = spin_text = name = confirmed = None # init
        if _func == 'pwr_all':
            # self.spin.start('Powering *ALL* Outlets {}'.format(self.states[kwargs['desired_state']]))
            if kwargs['action'] == 'cycle':
                prompt = '{} Power Cycle All Powered {} Outlets'.format('' if _type is None else _type + ':' + host_short, _on_str)
                spin_text = 'Cycling All{} Ports'.format('' if _type is None else ' ' + _type + ':' + host_short)
            elif kwargs['action'] == 'toggle':
                if not kwargs['desired_state']:
                    prompt = 'Power All{} Outlets {}'.format('' if _type is None else ' ' + _type + ':' + host_short, _off_str)
                spin_text = 'Powering {} ALL{} Outlets'.format(self.format_line(kwargs['desired_state'])[1], '' if _type is None else _type + ' :' + host_short)
        elif _func == 'pwr_toggle':
            if _type == 'dli' and port == 'all':
                prompt = 'Power {} ALL {} Outlets'.format(
                    _off_str if not to_state else _on_str, host_short)
            elif not to_state:
                if _type == 'dli':
                    prompt = 'Power {} {} Outlet {}({})'.format(
                        _off_str, host_short, port, port_name)
                else: # GPIO or TASMOTA
                    prompt = 'Power {} Outlet {}({}:{})'.format(
                        _off_str, _grp, _type, _addr)
            spin_text = 'Powering {} {}Outlet{}'.format(self.format_line(to_state)[1], 'ALL ' if port == 'all' else '', 's' if port == 'all' else '')
        elif _func == 'pwr_rename':
            try:
                name = input('New name for{} Outlet {}: '.format(
                    ' ' + host_short if host_short else '',
                    port_name if not _type == 'dli' else str(port) + '(' + port_name + ')'))
            except KeyboardInterrupt:
                name = None
                confirmed = False
            if name:
                old_name = port_name
                _rnm_str = '{red}{old_name}{norm} --> {green}{name}{norm}'.format(
                    red='{{red}}', green='{{green}}', norm='{{norm}}', old_name=old_name, name=name)
                if _type == 'dli':
                    # _rnm_str = '{{red}}{}{{norm}} --> {{green}}{}{{norm}}'.format(port_name, name)
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
            else: # GPIO or TASMOTA
                prompt = 'Cycle Power on Outlet {}({})'.format(
                    port_name, port)
            spin_text = 'Cycling {}Outlet{}'.format('ALL ' if port == 'all' else '', 's' if port == 'all' else '')


        if prompt:
            prompt = self.format_line(prompt)[1]
            confirmed = confirmed if confirmed is not None else user_input_bool(prompt)
        else:
            confirmed = True

        return confirmed, spin_text, name

    # Connection SubMenu
    def con_menu(self, rename=False):
        menu_actions = {
            '1': self.baud_menu,
            '2': self.data_bits_menu,
            '3': self.parity_menu,
            '4': self.flow_menu,
            'b': self.main_menu if not rename else self.do_rename_adapter, # not called
            'x': self.exit
        }
        while True:
            self.menu_formatting('header', text=' Connection Settings Menu ')
            print(' 1. Baud [{}]'.format(self.baud))
            print(' 2. Data Bits [{}]'.format(self.data_bits))
            print(' 3. Parity [{}]'.format(self.parity_pretty[self.parity]))
            print(' 4. Flow [{}]'.format(self.flow_pretty[self.flow]))
            text = ' b.  Back'
            self.menu_formatting('footer', text=text)
            choice = input(" >>  ")
            ch = choice.lower()
            try:
                if ch == 'b':
                    break
                else:
                    menu_actions[ch]() # lower menu's return values could parse and store if decide to use this for something other than rename

            except KeyError as e:
                if choice:
                    self.error_msgs.append(e)
        return

    # Baud Menu
    def baud_menu(self):
        config = self.config
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
            self.menu_formatting('header', text=' Select Desired Baud Rate ')

            for key in menu_actions:
                # if not callable(menu_actions[key]):
                _cur_baud = menu_actions[key]
                print(' {0}. {1}'.format(key, _cur_baud if _cur_baud != self.baud else '[{}]'.format(_cur_baud)))

            self.menu_formatting('footer', text=text)
            choice = input(" Baud >>  ")
            ch = choice.lower()

            # -- Evaluate Response --
            try:
                if ch == 'c':
                    while True:
                        self.baud = input(' Enter Desired Baud Rate >>  ')
                        if not config.canbeint(self.baud):
                            print('Invalid Entry {}'.format(self.baud))
                        elif int(self.baud) not in std_baud:
                            _choice = input(' {} is not a standard baud rate are you sure? (y/n) >> '.format(self.baud)).lower()
                            if not _choice in ['y', 'yes']:
                                break
                        else:
                            break
                    # menu_actions['con_menu']()
                elif ch == 'b':
                    break # return to con_menu
                elif ch == 'x':
                    self.exit()
                # elif type(menu_actions[ch]) == int:
                else:
                    self.baud = menu_actions[ch]
                    break
                    # menu_actions['con_menu']()
            except KeyError as e:
                if choice:
                    self.error_msgs.append('Invalid selection {} please try again.'.format(e))
                # menu_actions['baud_menu']()

        return self.baud

    # Data Bits Menu
    def data_bits_menu(self):
        valid = False
        while not valid:
            self.menu_formatting('header', text=' Enter Desired Data Bits ')
            print(' Default 8, Current {}, Valid range 5-8'.format(self.data_bits))
            self.menu_formatting('footer', text=' b.  Back')
            choice = input(' Data Bits >>  ')
            try:
                if choice.lower() == 'x':
                    self.exit()
                elif choice.lower() == 'b':
                    valid = True
                elif int(choice) >= 5 and int(choice) <= 8:
                    self.data_bits = choice
                    valid = True
                else:
                    self.error_msgs.append('Invalid selection {} please try again.'.format(choice))
            except ValueError:
                if choice:
                    self.error_msgs.append('Invalid selection {} please try again.'.format(choice))
        # self.con_menu()
        return self.data_bits

    def parity_menu(self):
        def print_menu():
            self.menu_formatting('header', text=' Select Desired Parity ')
            print(' Default No Parity\n')
            print(' 1. None')
            print(' 2. Odd')
            print(' 3. Even')
            text = ' b.  Back'
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
                self.exit()
            else:
                valid = False
                if choice:
                    self.error_msgs.append('Invalid selection {} please try again.'.format(choice))
        return self.parity

    def flow_menu(self):
        def print_menu():
            self.menu_formatting('header', text=' Select Desired Flow Control ')
            print(' Default No Flow\n')
            print(' 1. No Flow Control (default)')
            print(' 2. Xon/Xoff (software)')
            print(' 3. RTS/CTS (hardware)')
            text = ' b.  Back'
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
                    # self.con_menu()
                    pass
                elif choice == 'x':
                    self.exit()
                else:
                    if choice:
                        self.error_msgs.append('Invalid selection {} please try again.'.format(choice))
            except Exception as e:
                if choice:
                    self.error_msgs.append('Invalid selection {} please try again.'.format(e))
        # self.exec_menu('c', calling_menu='flow_menu')
        return self.flow

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
        # - if exit directly from rename menu after performing a rename trigger / reload udev
        if self.udev_pending:
            cmd = 'sudo udevadm control --reload && sudo udevadm trigger && sudo systemctl stop ser2net && sleep 1 && sudo systemctl start ser2net '
            with Halo(text='Triggering reload of udev do to name change', spinner='dots1'):
                error = bash_command(cmd)
            if error:
                print(error)
        
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
