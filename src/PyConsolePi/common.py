import logging
import netifaces as ni
import os
import pwd
import grp
import json
import socket
import subprocess
import threading
import requests
import time
from pathlib import Path
import pyudev
from .power import Outlets

# Common Static Global Variables
DNS_CHECK_FILES = ['/etc/resolv.conf', '/run/dnsmasq/resolv.conf']
CONFIG_FILE = '/etc/ConsolePi/ConsolePi.conf'
LOCAL_CLOUD_FILE = '/etc/ConsolePi/cloud.data'
CLOUD_LOG_FILE = '/var/log/ConsolePi/cloud.log'
USER = 'pi' # currently not used, user pi is hardcoded using another user may have unpredictable results as it hasn't been tested
HOME = str(Path.home())
POWER_FILE = '/etc/ConsolePi/power.json'
VALID_BAUD = ['300', '1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200']

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
            msg = '{}: {}'.format(level.upper(), msg) if level != 'info' else msg
            print(msg, end=end)


class ConsolePi_data:

    def __init__(self, log_file=CLOUD_LOG_FILE, do_print=True):
        config = self.get_config_all()
        for key, value in config.items():
            if type(value) == str:
                exec('self.{} = "{}"'.format(key, value))
            elif type(value) == bool:
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
        self.adapters = self.get_local(do_print=do_print)
        self.interfaces = self.get_if_ips()
        # self.outlets = Outlets().outlet_data
        self.local = {self.hostname: {'adapters': self.adapters, 'interfaces': self.interfaces, 'user': 'pi'}}
        self.remotes = self.get_local_cloud_file()
    
    def get_config_all(self):
        with open('/etc/ConsolePi/ConsolePi.conf', 'r') as config:
            for line in config:
                if 'ConsolePi Configuration File ver' not in line:
                    var = line.split("=")[0]
                    value = line.split('#')[0]
                    value = value.replace('{0}='.format(var), '')
                    value = value.split('#')[0]
                    if '"' in value:
                        value = value.replace('"', '', 1)
                        value = value.split('"')
                        value = value[0]
                    
                    if 'true' in value.lower() or 'false' in value.lower():
                        value = True if 'true' in value.lower() else False
                        
                    locals()[var] = value
        ret_data = locals()
        ret_data.pop('config')
        ret_data.pop('line')
        return ret_data

    def get_local(self, do_print=True):   
        log = self.log
        # plog = self.plog
        context = pyudev.Context()

        # if os.path.isfile(POWER_FILE):
        #     with open(POWER_FILE, 'r') as power_file:
        #         outlet_data = json.load(power_file)

        # plog('Detecting Locally Attached Serial Adapters')
        log.info('[GET ADAPTERS]: Detecting Locally Attached Serial Adapters')

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
        if os.path.isfile('/etc/ser2net.conf'):
            for tty_dev in final_tty_list:
                # -- Set Default Connection Params overwritten if found in ser2net.conf --
                baud = 9600
                dbits = 8
                parity = 'n'
                flow = 'n'
                # -- extract defined TELNET port and connection parameters from ser2net.conf --
                with open('/etc/ser2net.conf', 'r') as cfg:
                    for line in cfg:
                        if tty_dev in line:
                            line = line.split(':')
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
                                        print('Invalid value for "data bits" found in ser2net.conf falling back to 8')
                                        log.error('Invalid Value for data bits found in ser2net.conf: {}'.format(option))
                                        # dbits is pre-set for default of 8
                                elif option in ['EVEN', 'ODD', 'NONE']:
                                    parity = option[0].lower() # EVEN ODD NONE
                                elif option in ['XONXOFF', 'RTSCTS']:
                                    if option == 'XONXOFF':
                                        flow = 'x'
                                    elif option == 'RTSCTS':
                                        flow = 'h'

                            log.info('[GET ADAPTERS]: Found {0} TELNET port: {1} [{2} {3}{4}1, flow: {5}]'.format(
                                tty_dev.replace('/dev/', ''), tty_port, baud, dbits, parity.upper(), flow.upper()))
                            break
                        else:
                            tty_port = 9999  # this is error - placeholder value Telnet port is not currently used

                serial_list.append({'dev': tty_dev, 'port': tty_port, 'baud': baud, 'dbits': dbits,
                                    'parity': parity, 'flow': flow})

                if tty_port == 9999:
                    log.error('No ser2net.conf definition found for {}'.format(tty_dev))
                    print('No ser2net.conf definition found for {}'.format(tty_dev))

        else:
            log.error('No ser2net.conf file found unable to extract port definition')
            print('No ser2net.conf file found unable to extract port definition')
        
        if self.power and os.path.isfile(POWER_FILE):  # pylint: disable=maybe-no-member
            serial_list = self.get_outlet_data(serial_list)

        return serial_list

    # TODO Refactor make more efficient
    def get_outlet_data(self, serial_list):
        log = self.log
        outlet_data = Outlets().get_outlets()
        # print('Fetching Power Outlet Data')
        for dev in serial_list:
            # -- get linked outlet details if defined --
            outlet_dict = None
            for o in outlet_data:
                outlet = outlet_data[o]
                if outlet['linked']:
                    if dev['dev'] in outlet['linked_devs']:
                        log.info('[PWR OUTLETS]: Found Outlet {} linked to {}'.format(o, dev['dev']))
                        noff = True # default value
                        address = outlet['address']
                        if outlet['type'].upper() == 'GPIO':
                            address = int(outlet['address'])
                            if 'noff' in outlet:
                                noff = outlet['noff']
                        outlet_dict = {'type': outlet['type'], 'address': address, 'noff': noff, 'is_on': outlet['is_on']}
                        break
            dev['outlet'] = outlet_dict

        return serial_list


    def get_if_ips(self):
        log=self.log
        if_list = ni.interfaces()
        log.debug('[GET IFACES]: interface list: {}'.format(if_list))
        if_data = {}
        for _if in if_list:
            if _if != 'lo':
                try:
                    if_data[_if] = {'ip': ni.ifaddresses(_if)[ni.AF_INET][0]['addr'], 'mac': ni.ifaddresses(_if)[ni.AF_LINK][0]['addr']}
                except KeyError:
                    log.info('No IP Found for {} skipping'.format(_if))
        log.debug('[GET IFACES]: Completed Iface Data: {}'.format(if_data))
        return if_data

    def get_ip_list(self):
        ip_list = []
        if_ips = self.get_if_ips()
        for _iface in if_ips:
            ip_list.append(if_ips[_iface]['ip'])
        return ip_list

    def get_local_cloud_file(self, local_cloud_file=LOCAL_CLOUD_FILE):
        data = {}
        if os.path.isfile(local_cloud_file):
            with open(local_cloud_file, mode='r') as cloud_file:
                data = json.load(cloud_file)
        return data

    def update_local_cloud_file(self, remote_consoles=None, current_remotes=None, local_cloud_file=LOCAL_CLOUD_FILE):
        # NEW gets current remotes from file and updates with new
        log = self.log
        if remote_consoles is not None and len(remote_consoles) > 0:
            if os.path.isfile(local_cloud_file):
                if current_remotes is None:
                    current_remotes = self.get_local_cloud_file()
                os.remove(local_cloud_file)

            # update current_remotes dict with data passed to function
            # TODO # can refactor to check both when there is a conflict and use api to verify consoles, but I *think* logic below should work.
            if current_remotes is not None:
                for _ in current_remotes:
                    if _ not in remote_consoles:
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
                        # -- /DEBUG --
                        # only factor in existing data if source is not mdns
                        if 'upd_time' in remote_consoles[_] or 'upd_time' in current_remotes[_]:
                            if 'upd_time' in remote_consoles[_] and 'upd_time' in current_remotes[_]:
                                if current_remotes[_]['upd_time'] > remote_consoles[_]['upd_time']:
                                    remote_consoles[_] = current_remotes[_]
                                    log.info('[CACHE UPD] {} Keeping existing data based on more current update time'.format(_))
                                else: 
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
        
            with open(local_cloud_file, 'a') as new_file:
                new_file.write(json.dumps(remote_consoles, indent=4, sort_keys=True))
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
            log.info('[API] Adapters retrieved via API for Remote ConsolePi {}'.format(ip))
            log.debug('[API] Response: \n{}'.format(json.dumps(ret, indent=4, sort_keys=True)))
        else:
            ret = response.status_code
            log.error('[API] Failed to retrieve adapters via API for Remote ConsolePi {}\n{}:{}'.format(ip, ret, response.text))
        return ret

def set_perm(file):
    gid = grp.getgrnam("consolepi").gr_gid
    os.chown(file, 0, gid)

# Get Variables from Config
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

def bash_command(cmd):
    subprocess.run(['/bin/bash', '-c', cmd])


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

def gen_copy_key(rem_ip, rem_user='pi', hostname=None, copy=False):
    if hostname is None:
        hostname = socket.gethostname()
    if not os.path.isfile(HOME + '/.ssh/id_rsa'):
        print('\n\nNo Local ssh cert found, generating...')
        bash_command('ssh-keygen -m pem -t rsa -C "{0}@{1}"'.format(rem_user, hostname))
        copy = True
    if copy:
        print('\nAttempting to copy ssh cert to {}\n'.format(rem_ip))
        bash_command('ssh-copy-id {0}@{1}'.format(rem_user, rem_ip))
