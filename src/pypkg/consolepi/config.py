#!/etc/ConsolePi/venv/bin/python3
import os
import yaml
import json

from consolepi import utils, log
LOG_FILE = '/var/log/ConsolePi/consolepi.log'

# overridable defaults (via OVERRIDES section of ConsolePi.yaml)
DEFAULT_BAUD = 9600
DEFAULT_DBITS = 8
DEFAULT_PARITY = 'n'
DEFAULT_FLOW = 'n'
DEFAULT_SBITS = 1
DEFAULT_REMOTE_TIMEOUT = 3
DEFAULT_DLI_TIMEOUT = 7
DEFAULT_SO_TIMEOUT = 3  # smart outlets
DEFAULT_CYCLE_TIME = 3


class Config():
    '''Config object contains all statically defined variables and data from config files.'''

    def __init__(self):
        self.static = self.get_config_all('/etc/ConsolePi/.static.yaml', {})
        self.FALLBACK_USER = self.static.get('FALLBACK_USER', 'pi')
        self.REM_LAUNCH = self.static.get('REM_LAUNCH', '/etc/ConsolePi/src/remote_launcher.py')
        self.cfg_yml = self.get_config_all(yaml_cfg=self.static.get('CONFIG_FILE_YAML'),
                                           legacy_cfg=self.static.get('CONFIG_FILE'))
        self.cfg = self.cfg_yml.get('CONFIG')
        self.ztp = self.cfg_yml.get('ZTP', {})
        self.ovrd = self.cfg_yml.get('OVERRIDES', {})
        self.do_overrides()
        self.debug = self.cfg.get('debug', False)
        self.cloud = self.cfg.get('cloud', False)
        self.cloud_svc = self.cfg.get('cloud_svc', 'gdrive')
        try:
            self.loc_user = os.getlogin()
        except Exception:
            self.loc_user = os.getenv('SUDO_USER', os.getenv('USER'))

        self.linked_exists = False  # updated in get_outlets_from_file()
        self.picocom_ver = utils.get_picocom_ver()
        self.ser2net_conf = self.get_ser2net()
        self.hosts = self.get_hosts()
        self.power = self.cfg.get('power', False)
        self.outlets = {} if not self.power else self.get_outlets_from_file()
        self.remotes = self.get_remotes_from_file()
        self.remote_update = self.get_remotes_from_file
        self.root = True if os.geteuid() == 0 else False

    def get_remotes_from_file(self):
        return self.get_json_file(self.static.get('LOCAL_CLOUD_FILE'))

    def get_config_all(self, yaml_cfg=None, legacy_cfg=None):
        '''Parse bash style cfg vars from cfg file convert to class attributes.'''
        # prefer yaml file for all config items if it exists
        do_legacy = True
        if yaml_cfg and utils.valid_file(yaml_cfg):
            yml = self.get_yaml_file(yaml_cfg)
            cfg = yml.get('CONFIG', yml)
            if cfg:
                do_legacy = False
                for k in cfg:
                    if cfg[k] in ['true', 'false']:
                        cfg[k] = True if cfg[k] == 'true' else False
                if 'CONSOLEPI_VER' not in yml:
                    yml['CONFIG'] = cfg
        else:
            cfg = {}
            if utils.valid_file(legacy_cfg):
                with open(legacy_cfg, 'r') as config:
                    for line in config:
                        if not line.startswith('#'):
                            var = line.split("=")[0]
                            value = line.split('#')[0]
                            value = value.replace('{0}='.format(var), '')
                            value = value.split('#')[0].strip()

                            if value in ['true', 'false']:
                                cfg[var] = bool(value.replace('false', ''))
                            else:
                                cfg[var] = value.replace('"', '')

        return yml if not do_legacy else {'CONFIG': cfg}

    def do_overrides(self):
        '''Process Globals that can be overriden by values in ConsolePi.yaml
        '''
        ovrd = self.ovrd if self.ovrd else {}
        for k in ovrd:
            if ovrd[k] in ['true', 'false']:
                ovrd[k] = True if ovrd[k] == 'true' else False
        self.ovrd = ovrd
        self.default_baud = ovrd.get('default_baud', DEFAULT_BAUD)
        self.default_dbits = ovrd.get('default_dbits', DEFAULT_DBITS)
        self.default_parity = ovrd.get('default_parity', DEFAULT_PARITY)
        self.default_flow = ovrd.get('default_flow', DEFAULT_FLOW)
        self.default_sbits = ovrd.get('default_sbits', DEFAULT_SBITS)
        self.cloud_pull_only = ovrd.get('cloud_pull_only', False)
        self.compact_mode = ovrd.get('compact_mode', False)
        self.remote_timeout = int(ovrd.get('remote_timeout', DEFAULT_REMOTE_TIMEOUT))
        self.dli_timeout = int(ovrd.get('dli_timeout', DEFAULT_DLI_TIMEOUT))
        self.so_timeout = int(ovrd.get('smartoutlet_timeout', DEFAULT_SO_TIMEOUT))
        self.cycle_time = int(ovrd.get('cycle_time', DEFAULT_CYCLE_TIME))

    def get_outlets_from_file(self):
        '''Get outlets defined in config

        returns:
            dict: with following keys (all values are dicts)
                linked: linked outlets from config (linked to serial adapters- auto pwr-on)
                dli_power: dict any dlis in config have all ports represented here
                failures: failure to connect to any outlets will result in an entry here
                    outlet_name: failure description
        '''
        outlet_data = self.cfg_yml.get('POWER')
        if not outlet_data:  # fallback to legacy json config
            outlet_data = self.get_json_file(self.static.get('POWER_FILE'))

        if not outlet_data:
            if self.power:
                log.show('Power Function Disabled - Configuration Not Found')
                self.power = False
            self.outlet_types = []
            return outlet_data

        types = []
        by_dev = {}
        for k in outlet_data:
            if outlet_data[k].get('linked_devs'):
                outlet_data[k]['linked_devs'] = utils.format_dev(outlet_data[k]['linked_devs'],
                                                                 hosts=self.hosts, with_path=True)
                self.linked_exists = True
                for dev in outlet_data[k]['linked_devs']:
                    _type = outlet_data[k].get('type').lower()
                    if _type == 'dli':
                        _this = [f"{k}:{[int(p) for p in utils.listify(outlet_data[k]['linked_devs'][dev])]}"]
                    elif _type == 'esphome':
                        _linked = utils.listify(outlet_data[k]['linked_devs'][dev])
                        _this = [f'{k}:{[p for p in _linked]}']
                    else:
                        _this = [k]
                    by_dev[dev] = _this if dev not in by_dev else by_dev[dev] + _this
            else:
                outlet_data[k]['linked_devs'] = []

            if outlet_data[k]["type"].lower() not in types:
                types.append(outlet_data[k]["type"].lower())

            if outlet_data[k]['type'].upper() == 'GPIO' and isinstance(outlet_data[k].get('address'), str) \
                    and outlet_data[k]['address'].isdigit():
                outlet_data[k]['address'] = int(outlet_data[k]['address'])

        self.outlet_types = types
        outlet_data = {
            'defined': outlet_data,
            'linked': by_dev,
            'dli_power': {},
            'failures': {}
            }

        return outlet_data

    def get_json_file(self, json_file):
        '''Return dict from json file.'''
        if os.path.isfile(json_file) and os.stat(json_file).st_size > 0:
            with open(json_file) as f:
                try:
                    return json.load(f)
                except ValueError as e:
                    log.warning(f'Unable to load configuration from {json_file}\n\t{e}', show=True)

    def get_yaml_file(self, yaml_file):
        '''Return dict from yaml file.'''
        if os.path.isfile(yaml_file) and os.stat(yaml_file).st_size > 0:
            with open(yaml_file) as f:
                try:
                    # return yaml.load(f, Loader=yaml.BaseLoader)
                    return yaml.load(f, Loader=yaml.FullLoader)
                except ValueError as e:
                    log.warning(f'Unable to load configuration from {yaml_file}\n\t{e}', show=True)

    def get_hosts(self):
        '''Parse user defined hosts.json for inclusion in menu

        returns dict with formatted keys prepending /host/
        '''
        # utils = self.utils
        hosts = self.cfg_yml.get('HOSTS')
        if not hosts:  # fallback to legacy json config
            hosts = self.get_json_file(self.static.get('REM_HOSTS_FILE'))
            if not hosts:
                return {}

        # generate remote command used in menu
        for h in hosts:
            if hosts[h].get('method').lower() == 'ssh':
                port = 22 if ':' not in hosts[h]['address'] else hosts[h]['address'].split(':')[1]
                _user_str = '' if not hosts[h].get('username') else f'{hosts[h].get("username")}@'
                hosts[h]['cmd'] = f"sudo -u {self.loc_user} ssh -t {_user_str}{hosts[h]['address'].split(':')[0]} -p {port}"
            elif hosts[h].get('method').lower() == 'telnet':
                port = 23 if ':' not in hosts[h]['address'] else hosts[h]['address'].split(':')[1]
                _user_str = '' if not hosts[h].get('username') else f'-l {hosts[h].get("username")}'
                hosts[h]['cmd'] = f"sudo -u {self.loc_user} telnet {_user_str} {hosts[h]['address'].split(':')[0]} {port}"

        groups = [hosts[h].get('group', 'user-defined') for h in hosts]
        host_dict = {'main': {}, 'rshell': {}}

        for g in utils.unique(groups):
            host_dict['main'][g] = {f'/host/{h.split("/")[-1]}': hosts[h] for h in hosts
                                    if hosts[h].get('show_in_main', False) and hosts[h].get('group', 'user-defined') == g}
            if not host_dict['main'][g]:
                del host_dict['main'][g]
            host_dict['rshell'][g] = {f'/host/{h.split("/")[-1]}': hosts[h] for h in hosts
                                      if not hosts[h].get('show_in_main', False) and hosts[h].get('group', 'user-defined') == g}
            if not host_dict['rshell'][g]:
                del host_dict['rshell'][g]

        host_dict['_methods'] = utils.unique([hosts[h]['method'] for h in hosts])
        host_dict['_host_list'] = [f'/host/{h.split("/")[-1]}' for h in hosts]

        return host_dict

    def get_ser2net(self):
        '''Parse ser2net.conf to extract connection info for serial adapters

        retruns 2 level dict (empty dict if ser2net.conf not found or empty):
            {
                <adapter name or alias>: {
                    "baud": <baud>,
                    "dbits": <data bits>,
                    "flow": "<flow control>",
                    "parity": "<parity>",
                    "sbits": <stop bits>,
                    "port": <telnet port (ser2net),
                    "logfile": None or logfile if defined in ser2net.conf
                    "cmd": picocom command string used in menu
                    "line": The line from ser2net.conf
                }
            }
        '''
        ########################################################
        # --- ser2net (3.x) config lines look like this ---
        # ... 9600 NONE 1STOPBIT 8DATABITS XONXOFF LOCAL -RTSCTS
        # ... 9600 8DATABITS NONE 1STOPBIT banner
        ########################################################
        # utils = self.utils
        if not utils.valid_file(self.static.get('SER2NET_FILE')):
            log.warning('No ser2net.conf file found unable to extract port definition', show=True)
            return {}

        ser2net_conf = {}
        trace_files = {}
        with open(self.static['SER2NET_FILE']) as cfg:
            for line in cfg:
                if 'TRACEFILE:' in line:
                    line = line.split(':')
                    trace_files[line[1]] = line[2]
                    continue
                elif not line[0].isdigit():
                    continue
                _line = line.strip('\n')
                line = line.split(':')
                tty_port = int(line[0])
                tty_dev = line[3]

                # Reset defaults
                # baud is used to determine parsing failure
                dbits = 8
                parity = 'n'
                flow = 'n'
                sbits = 1
                logfile = None
                log_ptr = None

                connect_params = line[4].replace(',', ' ').split()
                for option in connect_params:
                    if option in self.static.get('VALID_BAUD',
                                                 ['300', '1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200']):
                        baud = int(option)
                    elif 'DATABITS' in option:
                        dbits = int(option.replace('DATABITS', ''))  # int 5 - 8
                        if dbits < 5 or dbits > 8:
                            log.warning(
                                f'{tty_dev}: Invalid value for "data bits" found in ser2net.conf falling back to 8',
                                show=True)
                            dbits = 8
                    elif option in ['EVEN', 'ODD', 'NONE']:
                        parity = option[0].lower()  # converts to e o n used by picocom
                    elif option == 'XONXOFF':
                        flow = 'x'
                    elif option == 'RTSCTS':
                        flow = 'h'
                    elif 'STOPBIT' in option:   # Not used by picocom
                        sbits = int(option[0]) if option[0].isdigit else 1
                    elif 'tb=' in option or 'tr=' in option or 'tw=' in option:
                        log_ptr = option
                        logfile = option.split('=')[1]

                # Use baud to determine if options were parsed correctly
                if baud is None:
                    log.warning(f'{tty_dev} found in ser2net but unable to parse baud falling back to {self.default_baud}',
                                show=True)
                    baud = self.default_baud

                # parse TRACEFILE defined in ser2net.conf
                cmd_base = f'picocom {tty_dev} --baud {baud} --flow {flow} --databits {dbits} --parity {parity}'
                if self.picocom_ver > 1:  # picocom ver 1.x in Stretch doesn't support "--stopbits"
                    cmd_base = cmd_base + f' --stopbits {sbits}'
                if logfile:
                    logfile = trace_files[logfile]
                    logfile = logfile.replace('\\p', str(tty_port)).replace('\\d', tty_dev.split('/')[-1])
                    logfile = logfile.replace('\\s', f'{baud}_{dbits}{parity.upper()}{sbits}')
                    logfile = logfile.split('\\')[0] + '-{{timestamp}}.log'  # + time.strftime('%H.%M.log')
                    cmd = cmd_base + f' --logfile {logfile}'
                    utils.do_shell_cmd(f"mkdir -p {'/'.join(logfile.split('/')[0:-1])}")
                    utils.set_perm('/'.join(logfile.split('/')[0:-1]))
                else:
                    cmd = cmd_base

                # update dict with values for this device
                ser2net_conf[tty_dev] = {
                    'port': tty_port,
                    'baud': baud,
                    'dbits': dbits,
                    'parity': parity,
                    'flow': flow,
                    'sbits': sbits,
                    'logfile': logfile,
                    'log_ptr': log_ptr,
                    'cmd': cmd,
                    'line': _line
                    }

        return ser2net_conf
