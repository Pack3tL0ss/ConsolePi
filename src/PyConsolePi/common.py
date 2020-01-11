#!/etc/ConsolePi/venv/bin/python3

import logging
import netifaces as ni
import os
import pwd
import grp
import json
import socket
import subprocess
import shlex
import threading
import requests
import time
import shlex
from pathlib import Path
import pyudev
import psutil
from sys import stdin
from halo import Halo
import serial
from log_symbols import LogSymbols as log_sym  # Enum
try:
    from .power import Outlets
except ImportError:
    from consolepi.power import Outlets

try:
    import better_exceptions
    better_exceptions.MAX_LENGTH = None
except ImportError:
    pass

# Common Static Global Variables
DNS_CHECK_FILES = ['/etc/resolv.conf', '/run/dnsmasq/resolv.conf']
CONFIG_FILE = '/etc/ConsolePi/ConsolePi.conf'
LOCAL_CLOUD_FILE = '/etc/ConsolePi/cloud.json'
CLOUD_LOG_FILE = '/var/log/ConsolePi/cloud.log'
RULES_FILE = '/etc/udev/rules.d/10-ConsolePi.rules'
SER2NET_FILE = '/etc/ser2net.conf'
USER = 'pi' # currently not used, user pi is hardcoded using another user may have unpredictable results as it hasn't been tested
HOME = str(Path.home())
POWER_FILE = '/etc/ConsolePi/power.json'
VALID_BAUD = ['300', '1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200']
REM_LAUNCH = '/etc/ConsolePi/src/remote_launcher.py'
if not 'consolepi-commands' in os.environ["PATH"]:
    os.environ["PATH"] += os.pathsep + '/etc/ConsolePi/src/consolepi-commands'

class ConsolePi_Log:

    def __init__(self, log_file=CLOUD_LOG_FILE, do_print=True, debug=None):
        self.debug = debug if debug is not None else get_config('debug')
        self.log_file = log_file
        self.do_print = do_print
        self.log = self.set_log()
        self.plog = self.log_print

    def set_log(self):
        log = logging.getLogger(__name__)
        log.setLevel(logging.INFO if not self.debug else logging.DEBUG)
        handler = logging.FileHandler(self.log_file)
        handler.setLevel(logging.INFO if not self.debug else logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        handler.setFormatter(formatter)
        log.addHandler(handler)
        return log
    
    def log_print(self, msg, level='info', end='\n'):
        getattr(self.log, level)(msg)
        if self.do_print:
            msg = msg.split('] ', 1)[1] if ']' in msg else msg
            msg = '{}: {}'.format(level.upper(), msg) if level != 'info' else msg
            print(msg, end=end)


class ConsolePi_data():

    def __init__(self, log_file=CLOUD_LOG_FILE, do_print=True):
        # super().__init__(POWER_FILE)
        # init ConsolePi.conf values
        self.cfg_file_ver = None
        self.push = None
        self.push_all = None
        self.push_api_key = None
        self.push_iden = None
        self.ovpn_enable = None
        self.vpn_check_ip = None
        self.net_check_ip = None
        self.local_domain = None
        self.wlan_ip = None
        self.wlan_ssid = None
        self.wlan_psk = None
        self.wlan_country = None
        self.cloud = None
        self.cloud_svc = None
        self.power = None
        self.debug = None

        # build attributes from ConsolePi.conf values
        # and GLOBAL variables
        config = self.get_config_all()
        for key, value in config.items():
            if type(value) == str:
                try:
                    exec('self.{} = "{}"'.format(key, value))
                except Exception as e:
                    print(key, value, e)
            else:
                try:
                    exec('self.{} = {}'.format(key, value))
                except Exception as e:
                    print(key, value, e)
        # from globals
        for key, value in globals().items():
            if type(value) == str:
                exec('self.{} = "{}"'.format(key, value))
            elif type(value) == bool or type(value) == int:
                exec('self.{} = {}'.format(key, value))
            elif type(value) == list:
                x = []
                for _ in value:
                    x.append(_)
                exec('self.{} = {}'.format(key, x))

        self.log_sym_error = log_sym.ERROR.value
        self.spin = Halo(spinner='dots')
        self.do_print = do_print
        self.log_file = log_file
        cpi_log = ConsolePi_Log(log_file=log_file, do_print=do_print, debug=self.debug) # pylint: disable=maybe-no-member
        self.log = cpi_log.log
        self.plog = cpi_log.plog
        self.pwr = Outlets(POWER_FILE, log=self.log)
        self.hostname = socket.gethostname()
        self.error_msgs = []
        # self.outlet_failures = {}
        # self.outlets = None # if not self.power or not os.path.isfile(POWER_FILE) else self.outlets # pylint: disable=maybe-no-member
        self.outlet_by_dev = None
        self.pwr_init_complete = False
        if self.power: # pylint: disable=maybe-no-member
            if os.path.isfile(POWER_FILE):
                # self.pwr.outlet_data = self.pwr.pwr_get_outlets_from_file()['linked']
                if self.pwr.outlet_data:
                    # self.get_outlet_types(self.pwr.outlet_data)
                    self.pwr.pwr_start_update_threads(self.pwr.outlet_data) # Update status for each outlet in background
                    # - this thread monitors pwr threads and updates init_complete
                    # threading.Thread(target=self.wait_for_threads).start()
                    # self.wait_for_threads()

                    # self.outlet_by_dev = (self.outlets['linked'])
            else:
                self.pwr_init_complete = True
                self.log.warning('Powrer Outlet Control is enabled but no power.json defined - Disabling')
                self.power = False
        self.adapters = self.get_adapters(do_print=do_print)
        self.interfaces = self.get_if_ips()
        self.ip_list = self.get_ip_list()
        # self.local = {self.hostname: {'adapters': self.adapters, 'interfaces': self.interfaces, 'user': 'pi'}}
        self.local = self.local_data_repr()
        self.remotes = self.get_local_cloud_file()
        if stdin.isatty():
            self.rows, self.cols = self.get_tty_size()
        self.root = True if os.geteuid() == 0 else False
        self.new_adapters = self.detect_adapters()        

    def get_tty_size(self):
        size = subprocess.run(['stty', 'size'], stdout=subprocess.PIPE)
        rows, cols = size.stdout.decode('UTF-8').split()
        return int(rows), int(cols)

    # def outlet_update(self, upd_linked=False, refresh=False):
    #     '''
    #     Called by init and consolepi-menu refresh
    #     '''
    #     if self.power: # pylint: disable=maybe-no-member
    #         if not hasattr(self, 'outlets') or refresh:
    #             _outlets = self.pwr.pwr_get_outlets(self.pwr.outlet_data, upd_linked=upd_linked, failures=self.pwr.outlet_data['failures'])
    #             self.outlets = _outlets['linked']
    #             self.outlet_failures = _outlets['failures']
    #             self.dli_pwr = _outlets['dli_power']
    #             self.pwr.outlet_data = _outlets
    #             return _outlets

    def outlet_update(self, upd_linked=False, refresh=False, key='linked', outlets=None):
        '''
        Called by consolepi-menu refresh
        '''
        log = self.log
        if self.power: # pylint: disable=maybe-no-member
            outlets = self.pwr.outlet_data if outlets is None else outlets
            if not self.pwr_init_complete or refresh:
                _outlets = self.pwr.pwr_get_outlets(outlet_data=outlets, upd_linked=upd_linked, failures=self.pwr.outlet_data['failures'])
                # self.outlets = _outlets['linked']
                # self.outlet_failures = _outlets['failures']
                # self.dli_pwr = _outlets['dli_power']
                self.pwr.outlet_data = _outlets
            else:
                _outlets = outlets

            if key in _outlets:
                return _outlets[key]
            else:
                msg = 'Invalid key ({}) passed to outlet_update. Returning "linked" (defined)'.format(key)
                log.error(msg)
                self.error_msgs.append(msg)
                return _outlets['linked']

    def local_data_repr(self, adapters=None, interfaces=None, outlets=None):
        adapters = self.adapters if adapters is None else adapters
        interfaces = self.interfaces if interfaces is None else interfaces
        # outlets = self.outlets if outlets is None else outlets
        local = {self.hostname: {'adapters': adapters, 'interfaces': interfaces, 'user': 'pi'}}

        return local

    def get_config_all(self):
        with open('/etc/ConsolePi/ConsolePi.conf', 'r') as config:
            for line in config:
                if line[0] != '#':
                    var = line.split("=")[0]
                    value = line.split('#')[0]
                    value = value.replace('{0}='.format(var), '')
                    value = value.split('#')[0].replace(' ', '')
                    value = value.replace('\t', '')
                    if '"' in value:
                        value = value.replace('"', '', 1)
                        value = value.split('"')[0]
                    
                    if 'true' in value.lower() or 'false' in value.lower():
                        value = True if 'true' in value.lower() else False
                    
                    if isinstance(value, str):
                        try:
                            value = int(value)
                        except ValueError:
                            pass
                    locals()[var] = value
        ret_data = locals()
        for key in ['self', 'config', 'line', 'var', 'value' 'ret_data']:
            if key in ret_data:
                del ret_data[key]

        return ret_data

    def detect_adapters(self, key=None):
        """Detect Locally Attached Adapters.

        Returns
        -------
        dict
            udev alias/symlink if defined/found as key or root device if not. 
            /dev/ is stripped: (ttyUSB0 | AP515).  Each device has it's attrs
            in a dict.
        """
        context = pyudev.Context()

        devs = {'by_name': {}, 'dup_ser': {}}
        
        usb_list = [dev.properties['DEVPATH'].split('/')[-1] for dev in context.list_devices(ID_BUS='usb', subsystem='tty')]
        pci_list = [dev.properties['DEVPATH'].split('/')[-1] for dev in context.list_devices(ID_BUS='pci', subsystem='tty')]
        root_dev_list = usb_list + pci_list
        for root_dev in root_dev_list:
            found = False
            for a in pyudev.Devices.from_name(context, 'tty', root_dev).properties['DEVLINKS'].split():
                if '/dev/serial/by-' not in a:
                    found = True
                    dev_name = a.replace('/dev/', '')
                    break
            if not found:
                dev_name = root_dev
            
            devs['by_name'][dev_name] = {}
            try:
                _ser = pyudev.Devices.from_name(context, 'tty', root_dev).properties['ID_SERIAL_SHORT']
            except KeyError:
                _ser = 'lame'
                self.error_msgs.append('The Adapter @ ' + root_dev + ' Lacks a serial #... lame!')
            for _dev in context.list_devices(subsystem='tty', DEVNAME='/dev/' + root_dev):
                devs['by_name'][dev_name]['id_path'] = _dev.properties['ID_PATH']
                devs['by_name'][dev_name]['id_ifnum'] = _dev.properties['ID_USB_INTERFACE_NUM']
                devs['by_name'][dev_name]['id_serial'] = _dev.get('ID_SERIAL_SHORT')
            for _dev in context.list_devices(subsystem='usb', ID_SERIAL_SHORT=_ser):
                devs['by_name'][dev_name]['id_prod'] = _dev.get('ID_MODEL_ID')
                devs['by_name'][dev_name]['id_model'] = _dev.get('ID_MODEL')
                devs['by_name'][dev_name]['id_vendorid'] = _dev.get('ID_VENDOR_ID')
                devs['by_name'][dev_name]['id_vendor'] = _dev.get('ID_VENDOR')
                devs['by_name'][dev_name]['root_dev'] = True if dev_name == root_dev else False

                if _ser in devs['dup_ser']:
                    devs['dup_ser'][_ser]['id_paths'].append(devs['by_name'][dev_name]['id_path'])
                    devs['dup_ser'][_ser]['id_ifnums'].append(devs['by_name'][dev_name]['id_ifnum'])
                else:
                    devs['dup_ser'][_ser] = {
                        'id_prod': devs['by_name'][dev_name]['id_prod'],
                        'id_model': devs['by_name'][dev_name]['id_model'],
                        'id_vendorid': devs['by_name'][dev_name]['id_vendorid'],
                        'id_vendor': devs['by_name'][dev_name]['id_vendor'],
                        'id_paths': [devs['by_name'][dev_name]['id_path']],
                        'id_ifnums': [devs['by_name'][dev_name]['id_ifnum']]
                        }
                        
        del_list = []
        for _ser in devs['dup_ser'] :
            if len(devs['dup_ser'][_ser]['id_paths']) == 1:
                del_list.append(_ser)

        if del_list:
            for i in del_list:
                del devs['dup_ser'][i]

        return devs if key is None else devs['by_name'][key.replace('/dev/', '')]    

    # TODO run get_local in blocking thread abort additional calls if thread already running
    # TODO assign defaults here if not found in ser2net instead of in consolepi-menu
    def get_adapters(self, do_print=None):
        if do_print is None:
            do_print = self.do_print
        log = self.log
        context = pyudev.Context()

        log.info('[GET ADAPTERS] Detecting Locally Attached Serial Adapters')
        if stdin.isatty() and do_print:
            self.spin.start('[GET ADAPTERS] Detecting Locally Attached Serial Adapters')

        # -- Detect Attached Serial Adapters and linked power outlets if defined --
        final_tty_list = []
        usb_list = [dev.properties['DEVPATH'].split('/')[-1] for dev in context.list_devices(ID_BUS='usb', subsystem='tty')]
        pci_list = [dev.properties['DEVPATH'].split('/')[-1] for dev in context.list_devices(ID_BUS='pci', subsystem='tty')]
        root_dev_list = usb_list + pci_list
        for root_dev in root_dev_list:
            found = False
            for a in pyudev.Devices.from_name(context, 'tty', root_dev).properties['DEVLINKS'].split():
                if '/dev/serial/by-' not in a:
                    found = True
                    final_tty_list.append(a)
                    break
            if not found:
                final_tty_list.append('/dev/' + root_dev)
        
        # get telnet port definition from ser2net.conf
        # and build adapters dict
        serial_list = []
        for tty_dev in final_tty_list:
            tty_port = 9999 # using 9999 as an indicator there was no def for the device.
            flow = 'n' # default if no value found in file
            # serial_list.append({tty_dev: {'port': tty_port}}) # PLACEHOLDER FOR REFACTOR with dev name as key
            # -- extract defined TELNET port and connection parameters from ser2net.conf --
            if os.path.isfile('/etc/ser2net.conf'):
                with open('/etc/ser2net.conf', 'r') as cfg:
                    for line in cfg:
                        if tty_dev in line:
                            line = line.split(':')
                            if '#' in line[0]:
                                continue
                            tty_port = int(line[0])
                            # --- ser2net config lines look like this ---
                            # ... 9600 NONE 1STOPBIT 8DATABITS XONXOFF LOCAL -RTSCTS
                            # ... 9600 8DATABITS NONE 1STOPBIT banner
                            connect_params = line[4]
                            connect_params.replace(',', ' ')
                            connect_params = connect_params.split()
                            for option in connect_params:
                                if option in VALID_BAUD:
                                    baud = int(option)
                                elif 'DATABITS' in option:
                                    dbits = int(option.replace('DATABITS', '')) # int 5 - 8
                                    if dbits < 5 or dbits > 8:
                                        if do_print:
                                            print('Invalid value for "data bits" found in ser2net.conf falling back to 8')
                                        log.error('Invalid Value for data bits found in ser2net.conf: {}'.format(option))
                                        dbits = 8
                                elif option in ['EVEN', 'ODD', 'NONE']:
                                    parity = option[0].lower() # converts to e o n
                                elif option in ['XONXOFF', 'RTSCTS']:
                                    if option == 'XONXOFF':
                                        flow = 'x'
                                    elif option == 'RTSCTS':
                                        flow = 'h'

                            log.info('[GET ADAPTERS] Found {0} TELNET port: {1} [{2} {3}{4}1, flow: {5}]'.format(
                                tty_dev.replace('/dev/', ''), tty_port, baud, dbits, parity.upper(), flow.upper()))
                            break
            else:   # No ser2net.conf file found
                msg = 'No ser2net.conf file found unable to extract port definition'
                log.error('[GET ADAPTERS] ' + msg)
                self.error_msgs.append(msg)
                serial_list.append({'dev': tty_dev, 'port': tty_port})

            if tty_port == 9999: # No ser2net definition found for this adapter - should not occur
                msg = 'No ser2net.conf definition found for {}'.format(tty_dev.replace('/dev/', ''))
                log.error('[GET ADAPTERS] ' + msg)
                self.error_msgs.append(msg)
                self.error_msgs.append('Use option \'c\' to change connection settings for ' + tty_dev.replace('/dev/', ''))
                serial_list.append({'dev': tty_dev, 'port': tty_port})
            else:
                serial_list.append({'dev': tty_dev, 'port': tty_port, 'baud': baud, 'dbits': dbits,
                        'parity': parity, 'flow': flow})
                            
        # if self.outlets:
        #     serial_list = self.map_serial2outlet(serial_list, self.outlets) ### TODO refresh kwarg to force pwr_get_outlets() line 200
        
        if stdin.isatty() and do_print:
            if len(serial_list) > 0:
                self.spin.succeed('[GET ADAPTERS] Detecting Locally Attached Serial Adapters\n\t' \
                    'Found {} Locally attached serial adapters'.format(len(serial_list))) #\GET ADAPTERS
            else:
                self.spin.warn('[GET ADAPTERS] Detecting Locally Attached Serial Adapters\n\tNo Locally attached serial adapters found')
        
        self.adapters = serial_list
        return serial_list

    # def format_dev(self, dev, with_path=True):
    #     dev = [dev] if not isinstance(dev, list) else dev
    #     ret_list = []
    #     for d in dev:
    #         if with_path:
    #             if '/dev/' not in d:
    #                 d = '/dev/{}'.format(d) 
    #         else:
    #             d = d.replace('/dev/', '')

    #         ret_list.append(d)
    #     return ret_list[0] if len(ret_list) == 1 else ret_list

    # TODO Refactor make more efficient
    def map_serial2outlet(self, serial_list, outlets):
        '''repr generates outlets linked to adapters in a dict keyed by the adapter

        adapter dict keyed by the adapter name (alias if defined)

        params:
            serial_list:list, list of discovered serial adapters
            outlets:dict, The outlet dict defined in power.json

        returns:
            dict: {adapter: {outlet_data}}
        '''
        log = self.log
        outlet_by_dev = {}
        for dev in serial_list:
            # print(dev['dev']) # -- DEBUG --
            if dev['dev'] not in outlet_by_dev:
                outlet_by_dev[dev['dev']] = []
            # -- get linked outlet details if defined --
            outlet_dict = None
            for o in outlets:
                outlet = outlets[o]
                if 'linked_devs' in outlet and outlet['linked_devs']:
                    if dev['dev'] in outlet['linked_devs']:
                        log.info('[PWR OUTLETS] Found Outlet {} linked to {}'.format(o, dev['dev'].replace('/dev/', '')))
                        address = outlet['address']
                        if outlet['type'].upper() == 'GPIO':
                            address = int(outlet['address'])
                        noff = outlet['noff'] if 'noff' in outlet else True
                        outlet_dict = {'key': o, 'type': outlet['type'], 'address': address, 'noff': noff, 'is_on': outlet['is_on'], 'grp_name': o}
                        outlet_by_dev[dev['dev']].append(outlet_dict)

            dev['outlet'] = outlet_dict

        self.outlet_by_dev = outlet_by_dev
        # return serial_list
        return outlet_by_dev

    def get_if_ips(self):
        log=self.log
        if_list = ni.interfaces()
        log.debug('[GET IFACES] interface list: {}'.format(if_list))
        if_data = {}
        for _if in if_list:
            if _if != 'lo':
                try:
                    if_data[_if] = {'ip': ni.ifaddresses(_if)[ni.AF_INET][0]['addr'], 'mac': ni.ifaddresses(_if)[ni.AF_LINK][0]['addr']}
                except KeyError:
                    log.info('[GET IFACES] No IP Found for {} skipping'.format(_if))
        log.debug('[GET IFACES] Completed Iface Data: {}'.format(if_data))
        return if_data

    def get_ip_list(self):
        ip_list = []
        if_ips = self.get_if_ips()
        for _iface in if_ips:
            ip_list.append(if_ips[_iface]['ip'])
        return ip_list

    def get_local_cloud_file(self, local_cloud_file=LOCAL_CLOUD_FILE):
        data = {}
        if os.path.isfile(local_cloud_file) and os.stat(local_cloud_file).st_size > 0:
            with open(local_cloud_file, mode='r') as cloud_file:
                data = json.load(cloud_file)
        return data

    def update_local_cloud_file(self, remote_consoles=None, current_remotes=None, local_cloud_file=LOCAL_CLOUD_FILE):
        '''Update local cloud cache (cloud.json)

        Verifies the newly discovered data is more current than what we already know and updates the local cloud.json file if so
        The Menu uses cloud.json to populate remote menu items

        params:
            remote_consoles: The newly discovered data (from Gdrive or mdns)
            current_remotes: The current remote data fetched from the local cloud cache (cloud.json)
                - func will retrieve this if not provided
            local_cloud_file The path to the local cloud file (global var cloud.json)

        return:
            remote_consoles: Dict, The resulting remote console dict representing what's deemed to be the most recent for each host
        '''
        # NEW gets current remotes from file and updates with new
        log = self.log
        if len(remote_consoles) > 0:
            if os.path.isfile(local_cloud_file):
                if current_remotes is None:
                    current_remotes = self.get_local_cloud_file()

        # update current_remotes dict with data passed to function
        # TODO # can refactor to check both when there is a conflict and use api to verify consoles, but I *think* logic below should work.
        if len(remote_consoles) > 0:
            if current_remotes is not None:
                for _ in current_remotes:
                    if _ not in remote_consoles:
                        if 'fail_cnt' in current_remotes[_] and current_remotes[_]['fail_cnt'] >=2:
                            pass
                        else:
                            remote_consoles[_] = current_remotes[_]
                    else:
                        # -- DEBUG --
                        log.debug('[CACHE UPD] \n--{}-- \n    remote rem_ip: {}\n    remote source: {}\n    remote upd_time: {}\n    cache rem_ip: {}\n    cache source: {}\n    cache upd_time: {}\n'.format(
                            _,
                            remote_consoles[_]['rem_ip'] if 'rem_ip' in remote_consoles[_] else None,
                            remote_consoles[_]['source'] if 'source' in remote_consoles[_] else None,
                            time.strftime('%a %x %I:%M:%S %p %Z', time.localtime(remote_consoles[_]['upd_time'])) if 'upd_time' in remote_consoles[_] else None,
                            current_remotes[_]['rem_ip'] if 'rem_ip' in current_remotes[_] else None, 
                            current_remotes[_]['source'] if 'source' in current_remotes[_] else None,
                            time.strftime('%a %x %I:%M:%S %p %Z', time.localtime(current_remotes[_]['upd_time'])) if 'upd_time' in current_remotes[_] else None,
                            ))
                        # -- END DEBUG --
                        # No Change Detected (data passed to function matches cache)
                        if remote_consoles[_] == current_remotes[_]:
                            log.info('[CACHE UPD] {} No Change in info detected'.format(_))
                        # only factor in existing data if source is not mdns
                        elif 'upd_time' in remote_consoles[_] or 'upd_time' in current_remotes[_]:
                            if 'upd_time' in remote_consoles[_] and 'upd_time' in current_remotes[_]:
                                if current_remotes[_]['upd_time'] > remote_consoles[_]['upd_time']:
                                    remote_consoles[_] = current_remotes[_]
                                    log.info('[CACHE UPD] {} Keeping existing data based on more current update time'.format(_))
                                else: 
                                    # -- fail_cnt persistence so Unreachable ConsolePi learned from Gdrive sync can still be flushed
                                    # -- after 3 failed connection attempts.
                                    if 'fail_cnt' not in remote_consoles[_] and 'fail_cnt' in current_remotes[_]:
                                        remote_consoles[_]['fail_cnt'] = current_remotes[_]['fail_cnt']
                                    log.info('[CACHE UPD] {} Updating data from {} based on more current update time'.format(_, remote_consoles[_]['source']))
                            elif 'upd_time' in current_remotes[_]:
                                    remote_consoles[_] = current_remotes[_] 
                                    log.info('[CACHE UPD] {} Keeping existing data based *existence* of update time which is lacking in this update from {}'.format(_, remote_consoles[_]['source']))
                                    
                        # -- Should be able to remove some of this logic now that a timestamp has beeen added along with a cloud update on serial adapter change --
                        # elif remote_consoles[_]['source'] != 'mdns' and 'source' in current_remotes[_] and current_remotes[_]['source'] == 'mdns':
                        #     if 'rem_ip' in current_remotes[_] and current_remotes[_]['rem_ip'] is not None:
                        #         # given all of the above it would appear the mdns entry is more current than the cloud entry
                        #         remote_consoles[_] = current_remotes[_]
                        #         log.info('[CACHE UPD] Keeping existing cache data for {}'.format(_))
                        # elif remote_consoles[_]['source'] != 'mdns':
                        #         if 'rem_ip' in current_remotes[_] and current_remotes[_]['rem_ip'] is not None:
                        #             # if we currently have a reachable ip assume whats in the cache is more valid
                        #             remote_consoles[_]['rem_ip'] = current_remotes[_]['rem_ip']

                        #             if len(current_remotes[_]['adapters']) > 0 and len(remote_consoles[_]['adapters']) == 0:
                        #                 log.info('[CACHE UPD] My Adapter data for {} is more current, keeping'.format(_))
                        #                 remote_consoles[_]['adapters'] = current_remotes[_]['adapters']
                        #                 log.debug('[CACHE UPD] !!! Keeping Adapter data from cache as none provided in data set !!!')
        
            with open(local_cloud_file, 'w') as cloud_file:
                cloud_file.write(json.dumps(remote_consoles, indent=4, sort_keys=True))
                set_perm(local_cloud_file)
        else:
            log.warning('[CACHE UPD] cache update called with no data passed, doing nothing')
        
        return remote_consoles

    def get_adapters_via_api(self, ip):
        log = self.log
        url = 'http://{}:5000/api/v1.0/adapters'.format(ip)

        headers = {
            'Accept': "*/*",
            'Cache-Control': "no-cache",
            'Host': "{}:5000".format(ip),
            'accept-encoding': "gzip, deflate",
            'Connection': "keep-alive",
            'cache-control': "no-cache"
            }

        try:
            response = requests.request("GET", url, headers=headers, timeout=2)
        except (OSError, TimeoutError) as e:
            log.error('[API RQST OUT] exception occured retrieving adapters via API for Remote ConsolePi {}\n{}'.format(ip, e))
            return False

        if response.ok:
            ret = json.loads(response.text)
            ret = ret['adapters']
            log.info('[API RQST OUT] Adapters retrieved via API for Remote ConsolePi {}'.format(ip))
            log.debug('[API RQST OUT] Response: \n{}'.format(json.dumps(ret, indent=4, sort_keys=True)))
        else:
            ret = response.status_code
            log.error('[API RQST OUT] Failed to retrieve adapters via API for Remote ConsolePi {}\n{}:{}'.format(ip, ret, response.text))
        return ret

    def api_reachable(self, remote_data: dict):
        '''Check Rechability & Fetch adapter data via API for remote ConsolePi

        params:
            remote_data:dict, The ConsolePi dictionary for the remote (from cache file)
        
        returns:
            tuple [0]: Bool, indicating if data is different than cache
                  [1]: dict, Updated ConsolePi dictionary for the remote
        '''
        rem_ip_list = []
        update = False

        if 'rem_ip' in remote_data and remote_data['rem_ip'] is not None:
            rem_ip_list.append(remote_data['rem_ip'])

        for _iface in remote_data['interfaces']:
            _ip = remote_data['interfaces'][_iface]['ip']
            if _ip not in rem_ip_list and _ip not in self.ip_list:
                rem_ip_list.append(_ip)

        for _ip in rem_ip_list:
            _adapters = self.get_adapters_via_api(_ip)
            if _adapters:
                if not isinstance(_adapters, int): # indicates an html error code was returned
                    if not remote_data['adapters'] == _adapters:
                        remote_data['adapters'] = _adapters
                        update = True
                # remote was reachable update rem_ip, even if returned bad status_code still reachable
                if 'rem_ip' not in remote_data or not remote_data['rem_ip'] == _ip:
                    remote_data['rem_ip'] = _ip
                    update = True
                break  # Stop Looping through interfaces we found a reachable one
            else:
                remote_data['rem_ip'] = None
        
        return (update, remote_data)
        
    
    def canbeint(self, _str):
        try: 
            int(_str)
            return True
        except ValueError:
            return False

    def gen_copy_key(self, rem_ip=None, rem_user=USER):
        hostname = self.hostname
        # generate local key file if it doesn't exist
        if not os.path.isfile(HOME + '/.ssh/id_rsa'):
            print('\n\nNo Local ssh cert found, generating...')
            bash_command('sudo -u {0} ssh-keygen -m pem -t rsa -C "{0}@{1}"'.format(rem_user, hostname))
        rem_list = []
        if rem_ip is not None and not isinstance(rem_ip, list):
            rem_list.append(rem_ip)
        else:
            rem_list = []
            for _ in sorted(self.remotes):
                if 'rem_ip' in self.remotes[_] and self.remotes[_]['rem_ip'] is not None:
                    rem_list.append(self.remotes[_]['rem_ip'])            
        # copy keys to remote(s)
        return_list = []
        for _rem in rem_list:
            print('\nAttempting to copy ssh cert to {}\n'.format(_rem))
            ret = bash_command('sudo -u {0} ssh-copy-id {0}@{1}'.format(rem_user, _rem))
            if ret is not None:
                return_list.append('{}: {}'.format(_rem, ret))
        return return_list

    def wait_for_threads(self, name='init', timeout=8):
        '''wait for parallel async threads to complete

        returns:
            bool: True if threads are still running indicating a timeout
                  False indicates no threads found ~ they have finished
        '''
        log = self.log
        start = time.time()
        do_log = False
        found = False    
        while self.power:
            found = False
            for t in threading.enumerate():
                if name in t.name:
                    found = do_log = True 
                    t.join(timeout - 1)

            if not found:
                if name == 'init':
                    self.pwr_init_complete = True
                if do_log:
                    log.info('[PWR {0} WAIT] Waiting for {0} Threads to Complete, elapsed time: {1}'.format(name.strip('_'), time.time() - start))
                break
            elif time.time() - start > timeout:
                log.error('[PWR INIT WAIT] Timeout Waiting for {} Threads to Complete, elapsed time: {}'.format(name.strip('_'), time.time() - start))
                break
        
        if not found:
            if self.power and self.pwr.outlet_data:
                # remove failed outlets from portions of the dict that are iterated over to build menu
                if self.pwr.outlet_data['failures']:
                    for o in self.pwr.outlet_data['failures']:
                        self.error_msgs.append(self.pwr.outlet_data['failures'][o]['error'])
                        if o in self.pwr.outlet_data['linked']:
                            del self.pwr.outlet_data['linked'][o]
                        if 'dli' in self.pwr.outlet_data and o in self.pwr.outlet_data['dli']:
                            del self.pwr.outlet_data['dli'][o]
                self.outlets = None if not self.pwr.outlet_data['linked'] else self.pwr.outlet_data['linked']
                self.outlet_failures = self.pwr.outlet_data['failures']                       
                self.dli_pwr = self.pwr.outlet_data['dli_power']
            else:
                self.outlet_failures = {}
                self.dli_pwr = {}

        return found

    def exec_auto_pwron(self, menu_dev):
        '''Launch auto_pwron in thread

        params:
            menu_dev:str, The tty dev user is connecting to
        '''
        print('Checking for and Powering on any outlets linked to {} in the background'.format(menu_dev.replace('/dev/', '')))
        # self.auto_pwron_thread(menu_dev) # swap to debug directly (disable thread)
        threading.Thread(target=self.auto_pwron_thread, args=(menu_dev,), name='auto_pwr_on_' + menu_dev.replace('/dev/', '')).start()
        self.log.debug('[AUTO PWRON] Active Threads: {}'.format(
            [t.name for t in threading.enumerate() if t.name != 'MainThread']
            ))

    def auto_pwron_thread(self, menu_dev):
        '''Ensure any outlets linked to device are powered on

        Called by consolepi_menu exec_menu function and remote_launcher (for sessions to remotes) 
        when a connection initiated with adapter.  Powers any linked outlets associated with the
        adapter on.

        params:
            menu_dev:str, The tty device user is connecting to.
        Returns:
            No Return - Updates class attributes
        '''
        # Outlet by dev None indicates it may still be updating
        # outlet_by_dev is dict after process runs (can be empty dict if no outlets defined)
        log = self.log
        if not self.pwr_init_complete:
            if not self.wait_for_threads('init'):
                if self.pwr.outlet_data:
                    self.outlet_by_dev = self.map_serial2outlet(self.adapters, self.pwr.outlet_data['linked'])
                    # self.local[self.hostname]['adapters'] = self.adapters
            else:
                self.error_msgs.append('Timeout Waiting for Power threads')
                log.error('Timeout Waiting for Power threads')
        # menu_dev = menu_dev.replace('/dev/', '') if menu_dev not in self.outlet_by_dev else menu_dev
        if self.outlet_by_dev is not None and menu_dev in self.outlet_by_dev:    # See Dictionary Reference for structure
            for outlet in self.outlet_by_dev[menu_dev]:
                _addr = outlet['address']

                # -- // DLI web power switch Auto Power On \\ --
                if outlet['type'].lower() == 'dli':
                    # host_short = _addr.split('.')[0] if '.' in _addr and not self.canbeint(_addr.split('.')[0]) else _addr
                    # is_on is a dict for dli outlets
                    # 'is_on': {<dli-port>: 'name': <dli-port-name>, 'state': <True|False>} ... where True = ON
                    # ports_to_pwr = []
                    for p in outlet['is_on']:
                        log.debug('[Auto PwrOn] Power ON {} Linked Outlet {}:{} p{}'.format(menu_dev, outlet['type'], _addr, p))
                        # self.spin.start('Ensuring linked outlet: [{}]:{} port: {}({}) is powered on'.format(
                            # outlet['type'], host_short, p, outlet['is_on'][p]['name']))
                        if not outlet['is_on'][p]['state']:   # This is just checking what's in the dict not querying the DLI
                            # ports_to_pwr.append(p)
                            r = self.pwr.pwr_toggle(outlet['type'], outlet['address'], desired_state=True, port=p)
                            if isinstance(r, bool):
                                if r:
                                    # self.spin.succeed()
                                    # start a thread to update outlet state in background
                                    threading.Thread(target=self.outlet_update, kwargs={'refresh': True, 'upd_linked': True}, name='auto_pwr_refresh_dli').start()
                                    # self.pwr.pwr_start_update_threads(upd_linked=True, t_name='refresh')
                                # else:
                                    # self.spin.fail()
                            else:
                                # self.spin.fail('Error operating linked outlet {} @ {} ({})'.format(
                                #     menu_dev.replace('/dev/', ''), outlet['address'], r))
                                log.warning('{} Error operating linked outlet @ {}'.format(menu_dev, outlet['address']))
                                self.error_msgs.append('Error operating linked outlet @ {}'.format(outlet['address']))
                        # else: # Outlet is already in powered on state
                        #     self.spin.succeed()
                # -- // GPIO & TASMOTA Auto Power On \\ --
                else:
                    log.debug('[Auto PwrOn] Power ON {} Linked Outlet {}:{}'.format(menu_dev, outlet['type'], _addr))
                    # msg = 'Ensuring linked outlet: {} ({}:{}) is powered on'.format(
                    #         outlet['grp_name'], outlet['type'], outlet['address'])
                    # self.spin.start(msg)
                    r = self.pwr.pwr_toggle(outlet['type'], outlet['address'], desired_state=True,
                        noff=outlet['noff'] if outlet['type'].upper() == 'GPIO' else True)
                    # TODO Below (first if) should never happen just a fail-safe after refactoring the returns from power.py Can eventually remove
                    if not isinstance(r, bool) and isinstance(r, int) and r <= 1: 
                        self.error_msgs.append('the return from {} {} was an int({})'.format(
                            outlet['type'], outlet['address'], r
                        ))
                    elif isinstance(r, int) and r > 1:  # return is an error
                        # self.spin.fail('{}\n{} {}'.format(
                        #     msg, self.log_sym_error, self.http_codes[r]))
                        r = False
                    else:   # return is bool which is what we expect
                        if r:
                            self.pwr.outlet_data['linked'][outlet['key']]['state'] = r
                            self.outlets = self.pwr.outlet_data['linked']
                            # self.spin.succeed()
                            # threading.Thread(target=config.pwr_get_outlets, name='auto_pwr_refresh_' + outlet['type']).start()
                            self.pwr.pwr_get_outlets(upd_linked=True)
                        else:
                            # self.spin.fail()
                            self.error_msgs.append('Error operating linked outlet @ {}'.format(outlet['address']))
                            log.warning('{} Error operating linked outlet @ {}'.format(menu_dev, outlet['address']))


def set_perm(file):
    gid = grp.getgrnam("consolepi").gr_gid
    if os.geteuid() == 0:
        os.chown(file, 0, gid)

# Get Individual Variables from Config
def get_config(var):
    with open(CONFIG_FILE, 'r') as cfg:
        for line in cfg:
            if var in line:
                var_out = line.replace('{0}='.format(var), '')
                var_out = var_out.split('#')[0]
                if '"' in var_out:
                    var_out = var_out.replace('"', '', 1)
                    var_out = var_out.split('"')
                    var_out = var_out[0]
                break

    if 'true' in var_out.lower() or 'false' in var_out.lower():
        var_out = True if 'true' in var_out.lower() else False

    return var_out

def error_handler(cmd, stderr):
    if stderr and 'FATAL: cannot lock /dev/' not in stderr:
        # Handle key change Error
        if 'WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!' in stderr:
            print(stderr.replace('ERROR: ', '').replace('/usr/bin/ssh-copy-id: ', ''))
            while True:
                try:
                    choice = input('\nDo you want to remove the old host key and re-attempt the connection (y/n)? ')
                    if choice.lower() in ['y', 'yes']:
                        _cmd = shlex.split(stderr.split('remove with:\r\n')[1].split('\r\n')[0].replace('ERROR:   ', ''))
                        subprocess.run(_cmd)
                        print('\n')
                        subprocess.run(cmd)
                        break
                    elif choice.lower() in ['n', 'no']:
                        break
                    else:
                        print("\n!!! Invalid selection {} please try again.\n".format(choice))
                except (KeyboardInterrupt, EOFError):
                    print('')
                    return 'Aborted last command based on user input'
                except ValueError:
                    print("\n!! Invalid selection {} please try again.\n".format(choice))
        elif 'All keys were skipped because they already exist on the remote system' in stderr:
            return 'skipped: keys already exist on the remote system'
        elif '/usr/bin/ssh-copy-id: INFO:' in stderr:
            pass # no need to re-display these
        else:
            return stderr   # return value that was passed in
    # Handle hung sessions always returncode=1 doesn't always present stderr
    elif cmd[0] == 'picocom':
        if kill_hung_session(cmd[1]):
            subprocess.run(cmd)
        else:
            return 'User Abort or Failure to kill existing session to {}'.format(cmd[1].replace('/dev/', ''))

def bash_command(cmd, do_print=False, eval_errors=True):
    # subprocess.run(['/bin/bash', '-c', cmd])
    response = subprocess.run(['/bin/bash', '-c', cmd], stderr=subprocess.PIPE)
    _stderr = response.stderr.decode('UTF-8')
    if do_print:
        print(_stderr)
    # print(response)
    # if response.returncode != 0:
    if eval_errors:
        if _stderr:
            return error_handler(getattr(response, 'args'), _stderr)

def is_valid_ipv4_address(address):
    try:
        socket.inet_pton(socket.AF_INET, address)
    except AttributeError:  # no inet_pton here, sorry
        try:
            socket.inet_aton(address)
        except socket.error:
            return False
        return address.count('.') == 3
    except socket.error:  # not a valid address
        return False

    return True


def get_dns_ips(dns_check_files=DNS_CHECK_FILES):
    dns_ips = []

    for file in dns_check_files:
        with open(file) as fp:
            for cnt, line in enumerate(fp):  # pylint: disable=unused-variable
                columns = line.split()
                if columns[0] == 'nameserver':
                    ip = columns[1:][0]
                    if is_valid_ipv4_address(ip):
                        if ip != '127.0.0.1':
                            dns_ips.append(ip)
    # -- only happens when the ConsolePi has no DNS will result in connection failure to cloud --
    if len(dns_ips) == 0:
        dns_ips.append('8.8.4.4')

    return dns_ips


def check_reachable(ip, port, timeout=2):
    # if url is passed check dns first otherwise dns resolution failure causes longer delay
    if '.com' in ip:
        test_set = [get_dns_ips()[0], ip]
        timeout += 3
    else:
        test_set = [ip]

    cnt = 0
    for _ip in test_set:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((_ip, 53 if cnt == 0 and len(test_set) > 1 else port ))
            reachable = True
        except (socket.error, TimeoutError):
            reachable = False
        sock.close()
        cnt += 1

        if not reachable:
            break
    return reachable

def user_input_bool(question):
    '''Ask User Y/N Question require Y/N answer

    Error and reprompt if user's response is not valid
    Appends '? (y/n): ' to question/prompt provided

    Params:
        question:str, The Question to ask
    Returns:
        answer:bool, Users Response yes=True
    '''
    try:
        answer = input(question + '? (y/n): ').lower().strip()
    except KeyboardInterrupt:
        return False
    while not(answer == "y" or answer == "yes" or \
              answer == "n" or answer == "no"):
        print("Input yes or no")
        answer = input(question + '? (y/n):').lower().strip()
    if answer[0] == "y":
        return True
    else:
        return False

def find_procs_by_name(name, dev):
    '''Return the pid of process matching name, where dev was referenced in the cmdline options

    Used by kill hung process

    Params: 
        name:str, name of process to find
        dev:str, dev which needs to be in the cmdline arguments for the process

    Returns:
        The pid of the matching process
    '''
    ppid = None
    for p in psutil.process_iter(attrs=["name", "cmdline"]):
        if name == p.info['name'] and dev in p.info['cmdline']:
            ppid = p.pid # if p.ppid() == 1 else p.ppid()
            break
    return ppid

def terminate_process(pid):
    '''send terminate, then kill if still alive to pid

    Used by kill_hung_sessions

    params: pid of process to be killed
    return: No Return
    '''
    p = psutil.Process(pid)
    x = 0
    while x < 2:
        p.terminate()
        if p.status() != 'Terminated':
            p.kill()
        else:
            break
        x += 1

def kill_hung_session(dev):
    '''Kill hung picocom session

    If picocom process still active and user is diconnected from SSH
    it makes the device unavailable.  When error_handler determines that is the case
    This function is called giving the user the option to kill it.
    '''
    ppid = find_procs_by_name('picocom', dev)
    retry = 0
    msg = '\n{} appears to be in use (may be a previous hung session).\nDo you want to Terminate the existing session'.format(dev.replace('/dev/', ''))
    if ppid is not None and user_input_bool(msg):
        while ppid is not None and retry < 3:
            print('An Existing session is already established to {}.  Terminating process {}'.format(dev.replace('/dev/', ''), ppid))
            try:
                terminate_process(ppid)
                time.sleep(3)
                ppid = find_procs_by_name('picocom', dev)
            except PermissionError:
                print('PermissionError: session is locked by user with higher priv. can not kill')
                break
            except psutil.AccessDenied:
                print('AccessDenied: Session is locked by user with higher priv. can not kill')
                break
            except psutil.NoSuchProcess:
                ppid = find_procs_by_name('picocom', dev)
            retry += 1
    return ppid is None

def get_serial_prompt(dev, commands=None, **kwargs):
    '''Attempt to get prompt from serial device

    Send 2 x cr to serial device and display any output
    returned from device.

    Used in rename function to help determine what the device is.
    '''
    dev = '/dev/' + dev if '/dev/' not in dev else dev
    ser = serial.Serial(dev, timeout=1, **kwargs)

    # before writing anything, ensure there is nothing in the buffer
    if ser.inWaiting() > 0:
        ser.flushInput()

    # send the commands:
    ser.write(b'\r')
    ser.write(b'\r')
    if commands:
        for cmd in commands:
            ser.write(bytes(cmd, 'UTF-8'))
    # read the response, guess a length that is more than the message
    msg = ser.read(2048)
    return msg.decode('UTF-8')

def json_print(obj):
    print(json.dumps(obj, indent=4, sort_keys=True))

def format_eof(file):
    cmd = 'sed -i -e :a -e {} {}'.format('\'/^\\n*$/{$d;N;};/\\n$/ba\'', file)
    return bash_command(cmd, eval_errors=False)

def append_to_file(file, line):
    '''Determine if last line of file includes a newline character
    write line provided on the next line

    params: 
        file: file to write to
        line: line to write
    '''
    # strip any blank lines from end of file and remove LF
    format_eof(file)

    # determine if last line in file has LF
    with open(file) as f:
        _lines = f.readlines()
        _last = _lines[-1]
    
    # prepend newline if last line of file lacks it to prevent appending to that line
    if '\n' not in _last:
        line = '\n{}'.format(line)

    with open(file, 'a+') as f:
        f.write(line)

# DEBUGGING Should not be called directly
if __name__ == '__main__':
    c = ConsolePi_data()
    c.exec_auto_pwron('/dev/2930F-Stage-Top')
    if not c.pwr_init_complete:
        from halo import Halo
        with Halo(text='Waiting for pwr init Threads to complete'):
            c.wait_for_threads()
            json_print(c.outlet_by_dev)
            # c.pwr._dli['labpower1.kabrew.com'].toggle([5, 6], toState=False)
    #     c.outlet_by_dev = c.map_serial2outlet(c.adapters, c.pwr.outlet_data['linked'])
    #     json_print(c.pwr.outlet_data)
    #     print('\n\n\nOutlet By Dev\n')
    #     json_print(c.outlet_by_dev)
    # json_print(c.adapters)
