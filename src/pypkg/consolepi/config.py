#!/etc/ConsolePi/venv/bin/python3


import json
import logging
import os
import yaml

# Global values overriden if variable (lowercase) by the same name exists in ConsolePi.conf
# i.e. default_baud=115200 will override DEFAULT_BAUD below
DEFAULT_BAUD = 9600
DEFAULT_DBITS = 8
DEFAULT_PARITY = 'n'
DEFAULT_FLOW = 'n'


class Config():
    '''Config object contains all statically defined variables and data from config files.'''

    def __init__(self, cpi):
        print(__name__)
        self.cpi = cpi
        self.utils = cpi.utils
        self.static = self.get_config_all('/etc/ConsolePi/.static.yaml')
        self.FALLBACK_USER = self.static.get('FALLBACK_USER', 'pi')
        self.REM_LAUNCH = self.static.get('REM_LAUNCH', '/etc/ConsolePi/src/remote_launcher.py')
        self.cfg_yml = self.get_config_all(self.static.get('CONFIG_FILE_YAML'))
        self.cfg = self.cfg_yml.get('CONFIG')
        self.log = self.get_logger()

        self.ser2net_conf = self.get_ser2net()
        self.hosts = self.get_hosts()
        self.outlets = self.get_outlets_from_file()
        self.remotes = self.get_json_file(self.static.get('LOCAL_CLOUD_FILE'))
        self.power = self.cfg.get('power')
        self.root = True if os.geteuid() == 0 else False

        try:
            self.loc_user = os.getlogin()
        except Exception:
            self.loc_user = os.getenv('SUDO_USER', os.getenv('USER'))

    def get_logger(self):
        '''Return custom log object.'''
        fmtStr = "%(asctime)s [%(module)s:%(funcName)s:%(lineno)d:%(process)d][%(levelname)s]: %(message)s"
        dateStr = "%m/%d/%Y %I:%M:%S %p"
        logging.basicConfig(filename=self.static.get('LOG_FILE'),
                            # level=logging.DEBUG if self.debug else logging.INFO,
                            level=logging.DEBUG if self.cfg['debug'] else logging.INFO,
                            format=fmtStr,
                            datefmt=dateStr)
        return logging.getLogger('ConsolePi')

    def log_and_show(self, msg, logit=True, showit=True, log=None):
        cpi = self.cpi
        if logit:
            log = self.log.info if log is None else log
            log(msg)

        if showit:
            msg = msg.replace('\t', '').split('\n')

            [cpi.error_msgs.append(f'{m.split("]")[1].strip() if "]" in m else m}')
                for m in msg
                if (']' in m and m.split(']')[1].strip() not in cpi.error_msgs)
                or ']' not in m and m not in cpi.error_msgs]
            # [cpi.error_msgs.append(m) for m in msg if m not in cpi.error_msgs]

    def get_config_all(self, yaml_cfg=None, legacy_cfg=None):
        '''Parse bash style cfg vars from cfg file convert to class attributes.'''
        utils = self.utils
        # prefer yaml file for all config items if it exists
        legacy_cfg = True  # init
        if yaml_cfg and utils.valid_file(yaml_cfg):
            yml = self.get_yaml_file(yaml_cfg)
            cfg = yml.get('CONFIG', yml)
            if cfg:
                legacy_cfg = False
                for k in cfg:
                    if cfg[k] in ['true', 'false']:
                        cfg[k] = True if cfg[k] == 'true' else False
                yml['CONFIG'] = cfg

        if legacy_cfg:
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
                                cfg[var] = bool(value)
                            else:
                                cfg[var] = value

        if cfg:
            # Process Globals that can be overriden by values in ConsolePi.conf
            self.default_baud = cfg.get('default_baud', DEFAULT_BAUD)
            self.default_dbits = cfg.get('default_dbits', DEFAULT_DBITS)
            self.default_parity = cfg.get('default_parity', DEFAULT_PARITY)
            self.default_flow = cfg.get('default_flow', DEFAULT_FLOW)

            return yml if not legacy_cfg else {'CONFIG': cfg}

    def get_outlets_from_file(self):
        '''Get outlets defined in power.json

        returns:
            dict: with following keys (all values are dicts)
                linked: linked outlets from power.json (linked to serial adapters- auto pwr-on)
                dli_power: dict any dlis in power.json have all ports represented here
                failures: failure to connect to any outlets will result in an entry here
                    outlet_name: failure description
        '''
        utils = self.utils
        outlet_data = self.cfg_yml.get('POWER')
        if not outlet_data:  # fallback to legacy json config
            outlet_data = self.get_json_file(self.static.get('POWER_FILE'))

        if not outlet_data:
            return outlet_data

        types = []
        by_dev = {}
        for k in outlet_data:
            if outlet_data[k].get('linked_devs'):
                outlet_data[k]['linked_devs'] = utils.format_dev(outlet_data[k]['linked_devs'],
                                                                 hosts=self.hosts, with_path=True)
                self.linked_exists = True
                for dev in outlet_data[k]['linked_devs']:
                    _this = [k] if outlet_data[k].get('type').lower() != 'dli' \
                        else [f"{k}:{[int(p) for p in outlet_data[k]['linked_devs'][dev]]}"]
                    by_dev[dev] = _this if dev not in by_dev else by_dev[dev] + _this
            else:
                outlet_data[k]['linked_devs'] = []

            if outlet_data[k]["type"].lower() not in types:
                types.append(outlet_data[k]["type"].lower())

            if outlet_data[k]['type'].upper() == 'GPIO' and outlet_data[k].get('address', 'error').isdigit():
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
                    self.log_and_show(f'Unable to load configuration from {json_file}\n\t{e}', log=self.log.warning)

    def get_yaml_file(self, yaml_file):
        '''Return dict from yaml file.'''
        if os.path.isfile(yaml_file) and os.stat(yaml_file).st_size > 0:
            with open(yaml_file) as f:
                try:
                    return yaml.load(f, Loader=yaml.BaseLoader)
                except ValueError as e:
                    self.log_and_show(f'Unable to load configuration from {yaml_file}\n\t{e}', log=self.log.warning)

    def get_hosts(self):
        '''Parse user defined hosts.json for inclusion in menu

        returns dict with formatted keys prepending /host/
        '''
        utils = self.utils
        hosts = self.cfg_yml.get('HOSTS')
        if not hosts:  # fallback to legacy json config
            hosts = self.get_json_file(self.static.get('REM_HOSTS_FILE'))
            if not hosts:
                return None

        # generate remote command used in menu
        for h in hosts:
            if hosts[h].get('method').lower() == 'ssh':
                port = 22 if ':' not in hosts[h]['address'] else hosts[h]['address'].split(':')[1]
                _user_str = '' if not hosts[h].get('username') else f'{hosts[h].get("username")}@'
                hosts[h]['cmd'] = f"ssh -t {_user_str}{hosts[h]['address'].split(':')[0]} -p {port}"
            elif hosts[h].get('method').lower() == 'telnet':
                port = 23 if ':' not in hosts[h]['address'] else hosts[h]['address'].split(':')[1]
                _user_str = '' if not hosts[h].get('username') else f'-l {hosts[h].get("username")}'
                hosts[h]['cmd'] = f"telnet {_user_str} {hosts[h]['address'].split(':')[0]} {port}"

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
                }
            }
        '''
        ########################################################
        # --- ser2net (3.x) config lines look like this ---
        # ... 9600 NONE 1STOPBIT 8DATABITS XONXOFF LOCAL -RTSCTS
        # ... 9600 8DATABITS NONE 1STOPBIT banner
        ########################################################
        utils = self.utils
        if not utils.valid_file(self.static.get('SER2NET_FILE')):
            self.log_and_show('No ser2net.conf file found unable to extract port definition', log=self.log.warning)
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

                connect_params = line[4].replace(',', ' ').split()
                for option in connect_params:
                    if option in self.static.get('VALID_BAUD',
                                                 ['300', '1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200']):
                        baud = int(option)
                    elif 'DATABITS' in option:
                        dbits = int(option.replace('DATABITS', ''))  # int 5 - 8
                        if dbits < 5 or dbits > 8:
                            self.log_and_show(
                                f'{tty_dev}: Invalid value for "data bits" found in ser2net.conf falling back to 8'
                                )
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
                        logfile = option.split('=')[1]

                # Use baud to determine if options were parsed correctly
                if baud is None:
                    self.log_and_show(f'{tty_dev} found in ser2net but unable to parse baud falling back to {self.default_baud}')
                    baud = self.default_baud

                # parse TRACEFILE defined in ser2net.conf
                cmd_base = f'picocom {tty_dev} --baud {baud} --flow {flow} --databits {dbits} --parity {parity}'
                if utils.get_picocom_ver() > 1:  # picocom ver 1.x in Stretch doesn't support "--stopbits"
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
                    'cmd': cmd
                    }

        return ser2net_conf


if __name__ == '__main__':
    config = Config()
    print(json.dumps(config.ser2net_conf, indent=4, sort_keys=True))
    # print(json.dumps(config.remotes, indent=4, sort_keys=True))
    # print(json.dumps(config.outlets, indent=4, sort_keys=True))
    # print(json.dumps(config.hosts, indent=4, sort_keys=True))
    # print(json.dumps(config.cfg, indent=4, sort_keys=True))
