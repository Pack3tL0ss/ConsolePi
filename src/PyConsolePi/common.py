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
from .power import Outlets

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


class ConsolePi_data(Outlets):

    def __init__(self, log_file=CLOUD_LOG_FILE, do_print=True):
        super().__init__(POWER_FILE)
        config = self.get_config_all()
        for key, value in config.items():
            if type(value) == str:
                exec('self.{} = "{}"'.format(key, value))
            else:
                exec('self.{} = {}'.format(key, value))
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
        self.do_print = do_print
        self.log_file = log_file
        cpi_log = ConsolePi_Log(log_file=log_file, do_print=do_print, debug=self.debug) # pylint: disable=maybe-no-member
        self.log = cpi_log.log
        self.plog = cpi_log.plog
        self.hostname = socket.gethostname()
        self.error_msgs = []
        self.outlet_by_dev = None # defined in get_local --> map_serial2outlet
        self.outlet_failures = {}
        self.power = self.outlets = False
        if self.power: # pylint: disable=access-member-before-definition
            if os.path.isfile(POWER_FILE):
                self.outlet_update()
            else:
                self.log.warning('Powrer Outlet Control is enabled but no power.json defined - Disabling')
                self.error_msgs.append('Powrer Outlet Control is enabled but no power.json defined - Disabling')    
        self.adapters = self.get_local(do_print=do_print)
        self.interfaces = self.get_if_ips()
        self.local = {self.hostname: {'adapters': self.adapters, 'interfaces': self.interfaces, 'user': 'pi'}}
        self.remotes = self.get_local_cloud_file()
        if stdin.isatty():
            self.rows, self.cols = self.get_tty_size()
        self.display_con_settings = False
        self.root = True if os.geteuid() == 0 else False

    def get_tty_size(self):
        size = subprocess.run(['stty', 'size'], stdout=subprocess.PIPE)
        rows, cols = size.stdout.decode('UTF-8').split()
        return int(rows), int(cols)

    def outlet_update(self, upd_linked=False, refresh=False):
        '''
        Called by init and consolepi-menu refresh
        '''
        if self.power:
            if not hasattr(self, 'outlets') or refresh:
                _outlets = self.get_outlets(upd_linked=upd_linked, failures=self.outlet_failures)
                self.outlets = _outlets['linked']
                self.outlet_failures = _outlets['failures']
                self.dli_pwr = _outlets['dli_power']


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
        for key in ['self', 'config', 'line', 'var', 'value']:
            ret_data.pop(key)
        return ret_data

    # TODO run get_local in blocking thread abort additional calls if thread already running
    def get_local(self, do_print=True):
        log = self.log
        # plog = self.plog
        context = pyudev.Context()

        # plog('Detecting Locally Attached Serial Adapters')
        log.info('[GET ADAPTERS] Detecting Locally Attached Serial Adapters')
        if stdin.isatty():
            self.spin.start('[GET ADAPTERS] Detecting Locally Attached Serial Adapters')

        # -- Detect Attached Serial Adapters and linked power outlets if defined --
        final_tty_list = []
        for device in context.list_devices(subsystem='tty', ID_BUS='usb'):
            found = False
            for _ in device['DEVLINKS'].split():
                if '/dev/serial/by-' not in _:
                    found = True
                    final_tty_list.append(_)
                    break
            if not found:
                final_tty_list.append(device['DEVNAME'])
        
        # get telnet port definition from ser2net.conf
        # and build adapters dict
        serial_list = []
        for tty_dev in final_tty_list:
            tty_port = 9999 # using 9999 as an indicator there was no def for the device.
            flow = 'n' # default if no value found in file
            # -- extract defined TELNET port and connection parameters from ser2net.conf --
            if os.path.isfile('/etc/ser2net.conf'):
                with open('/etc/ser2net.conf', 'r') as cfg:
                    for line in cfg:
                        if tty_dev in line:
                            line = line.split(':')
                            if '#' in line[0]:
                                continue
                            tty_port = int(line[0])
                            # 9600 NONE 1STOPBIT 8DATABITS XONXOFF LOCAL -RTSCTS
                            # 9600 8DATABITS NONE 1STOPBIT banner
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
            else:
                msg = '[GET ADAPTERS] No ser2net.conf file found unable to extract port definition'
                log.error(msg)
                self.error_msgs.append(msg)
                # log.error('No ser2net.conf file found unable to extract port definition')
                # if do_print:
                #     print('No ser2net.conf file found unable to extract port definition')

            if tty_port == 9999:
                msg = '[GET ADAPTERS] No ser2net.conf definition found for {}'.format(tty_dev)
                log.error(msg)
                self.error_msgs.append(msg)
                self.display_con_settings = True
                # log.error('[GET ADAPTERS] No ser2net.conf definition found for {}'.format(tty_dev))
                # serial_list.append({'dev': tty_dev, 'port': tty_port})
                # if do_print:
                #     print('No ser2net.conf definition found for {}'.format(tty_dev))
            else:
                serial_list.append({'dev': tty_dev, 'port': tty_port, 'baud': baud, 'dbits': dbits,
                        'parity': parity, 'flow': flow})       
        if self.power and os.path.isfile(POWER_FILE):  # pylint: disable=maybe-no-member
            if self.outlets:
                serial_list = self.map_serial2outlet(serial_list, self.outlets) ### TODO refresh kwarg to force get_outlets() line 200
        
        if stdin.isatty():
            if len(serial_list) > 0:
                self.spin.succeed('[GET ADAPTERS] Detecting Locally Attached Serial Adapters\n\t' \
                    'Found {} Locally attached serial adapters'.format(len(serial_list))) #\GET ADAPTERS
            else:
                self.spin.warn('[GET ADAPTERS] Detecting Locally Attached Serial Adapters\n\tNo Locally attached serial adapters found')
        
        return serial_list

    # TODO Refactor make more efficient
    def map_serial2outlet(self, serial_list, outlets):
        log = self.log
        # print('Fetching Power Outlet Data')
        outlet_by_dev = {}
        for dev in serial_list:
            if dev['dev'] not in outlet_by_dev:
                outlet_by_dev[dev['dev']] = []
            # -- get linked outlet details if defined --
            outlet_dict = None
            for o in outlets:
                outlet = outlets[o]
                if 'linked_devs' in outlet and outlet['linked_devs']:
                    if dev['dev'] in outlet['linked_devs']:
                        log.info('[PWR OUTLETS] Found Outlet {} linked to {}'.format(o, dev['dev']))
                        address = outlet['address']
                        if outlet['type'].upper() == 'GPIO':
                            address = int(outlet['address'])
                        noff = outlet['noff'] if 'noff' in outlet else True
                        outlet_dict = {'type': outlet['type'], 'address': address, 'noff': noff, 'is_on': outlet['is_on'], 'grp_name': o}
                        # TODO This should only keep 1 outlet per adapter in the adapters dict, refactor as below to allow list of outlets or dict with grp as key
                        # this_outlet_dict = {'type': outlet['type'], 'address': address, 'noff': noff, 'is_on': outlet['is_on'], 'grp_name': o}
                        # if outlet_dict is None:
                        #     outlet_dict = this_outlet_dict
                        # else:
                        #     outlet_dict[o] = this_outlet_dict
                        # outlet_by_dev[dev['dev']].append(outlet_dict)
                        outlet_by_dev[dev['dev']].append(outlet_dict)
                        # break

            dev['outlet'] = outlet_dict

        self.outlet_by_dev = outlet_by_dev
        return serial_list

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
        # NEW gets current remotes from file and updates with new
        log = self.log
        if len(remote_consoles) > 0:
            if os.path.isfile(local_cloud_file):
                if current_remotes is None:
                    current_remotes = self.get_local_cloud_file()
                # os.remove(local_cloud_file)

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
                                        remote_consoles[_]['fail_cnt'] = {self.hostname: current_remotes[_]['fail_cnt']}
                                    log.info('[CACHE UPD] {} Updating data from {} based on more current update time'.format(_, remote_consoles[_]['source']))
                            elif 'upd_time' in current_remotes[_]:
                                    remote_consoles[_] = current_remotes[_] 
                                    log.info('[CACHE UPD] {} Keeping existing data based *existence* of update time which is lacking in this update from {}'.format(_, remote_consoles[_]['source']))
                                    
                        # -- Should be able to remove some of this logic now that a timestamp has beeen added along with a cloud update on serial adapter change --
                        elif remote_consoles[_]['source'] != 'mdns' and 'source' in current_remotes[_] and current_remotes[_]['source'] == 'mdns':
                            if 'rem_ip' in current_remotes[_] and current_remotes[_]['rem_ip'] is not None:
                                # given all of the above it would appear the mdns entry is more current than the cloud entry
                                remote_consoles[_] = current_remotes[_]
                                log.info('[CACHE UPD] Keeping existing cache data for {}'.format(_))
                        elif remote_consoles[_]['source'] != 'mdns':
                                if 'rem_ip' in current_remotes[_] and current_remotes[_]['rem_ip'] is not None:
                                    # if we currently have a reachable ip assume whats in the cache is more valid
                                    remote_consoles[_]['rem_ip'] = current_remotes[_]['rem_ip']

                                    if len(current_remotes[_]['adapters']) > 0 and len(remote_consoles[_]['adapters']) == 0:
                                        log.info('[CACHE UPD] My Adapter data for {} is more current, keeping'.format(_))
                                        remote_consoles[_]['adapters'] = current_remotes[_]['adapters']
                                        log.debug('[CACHE UPD] !!! Keeping Adapter data from cache as none provided in data set !!!')
        
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

        response = requests.request("GET", url, headers=headers)

        if response.ok:
            ret = json.loads(response.text)
            ret = ret['adapters']
            log.info('[API RQST OUT] Adapters retrieved via API for Remote ConsolePi {}'.format(ip))
            log.debug('[API RQST OUT] Response: \n{}'.format(json.dumps(ret, indent=4, sort_keys=True)))
        else:
            ret = response.status_code
            log.error('[API RQST OUT] Failed to retrieve adapters via API for Remote ConsolePi {}\n{}:{}'.format(ip, ret, response.text))
        return ret
    
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
            bash_command('ssh-keygen -m pem -t rsa -C "{0}@{1}"'.format(rem_user, hostname))
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
            ret = bash_command('ssh-copy-id {0}@{1}'.format(rem_user, _rem))
            if ret is not None:
                return_list.append('{}: {}'.format(_rem, ret))
        return return_list

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

def key_change_detector(cmd, stderr):
    if 'WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!' in stderr:
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
    else:
        return stderr   # return value that was passed in


def bash_command(cmd, do_print=False):
    # subprocess.run(['/bin/bash', '-c', cmd])
    response = subprocess.run(['/bin/bash', '-c', cmd], stderr=subprocess.PIPE)
    _stderr = response.stderr.decode('UTF-8')
    if do_print:
        print(_stderr)
    # print(response)
    # if response.returncode != 0:
    if _stderr:
        return key_change_detector(getattr(response, 'args'), _stderr)

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
    "Return a list of processes matching 'name'."
    ppid = None
    for p in psutil.process_iter(attrs=["name", "cmdline"]):
        if name == p.info['name'] and dev in p.info['cmdline']:
            ppid = p.pid if p.ppid() == 1 else p.ppid()
    return ppid

def terminate_process(pid):
    p = psutil.Process(pid)
    x = 0
    while x < 2:
        p.terminate()
        if p.status() != 'Terminated':
            p.kill()
        else:
            break
        x += 1