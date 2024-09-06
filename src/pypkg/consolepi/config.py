#!/etc/ConsolePi/venv/bin/python3
from __future__ import annotations
import os
from typing import Any, Dict
import yaml
import json
import shutil
from pathlib import Path

from consolepi import utils, log  # type: ignore
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
DEFAULT_API_PORT = 5000


class RemoteTimeout:
    def __init__(self, default: int = DEFAULT_REMOTE_TIMEOUT) -> None:
        self.default: int = default

    def add_host(self, host: str, timeout: int):
        setattr(self, host, timeout)

    def __getattr__(self, name: str) -> int:
        name = name.split("(")[0]  # provided hostname(ip-address) from remotes.get_adapters_via_api()
        if name in self.__dict__.keys():
            return getattr(self, name)
        else:
            return self.default


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
        self.picocom_ver = utils.get_picocom_ver()
        self.ser2net_ver = utils.get_ser2net_ver()
        if utils.valid_file("/etc/ser2net.yaml"):
            self.ser2net_file = Path("/etc/ser2net.yaml")
            self.ser2net_conf = self.get_ser2netv4()
        elif utils.valid_file("/etc/ser2net.conf"):
            self.ser2net_file = Path("/etc/ser2net.conf")
            self.ser2net_conf = self.get_ser2netv3()
        else:
            self.ser2net_file = None
            self.ser2net_conf = {}
            log.warning("No ser2net configuration found to extract serial port settings from, using defaults", show=True)

        self.debug = self.cfg.get('debug', False)
        self.cloud = self.cfg.get('cloud', False)
        self.cloud_svc = self.cfg.get('cloud_svc', 'gdrive')
        try:
            self.loc_user = os.getlogin()
        except Exception:
            self.loc_user = os.getenv('SUDO_USER', os.getenv('USER'))

        self.linked_exists = False  # updated in get_outlets_from_file()
        self.hosts = self.get_hosts()
        self.power = self.cfg.get('power', False)
        self.do_dli_menu = None  # updated in get_outlets_from_file()
        self.outlet_groups = {}  # updated in get_outlets_from_file()
        self.outlets = {} if not self.power else self.get_outlets_from_file()
        self.remotes = self.get_remotes_from_file()
        self.remote_update = self.get_remotes_from_file
        self.root = True if os.geteuid() == 0 else False

    def verify_ser2net_file(self):
        """Validate and update ser2net file.

        This is necessary after Instantiation as user could
        convert/remove old .conf file.  Which would cause
        and exception.
        """
        if self.ser2net_file.exists():
            return self.ser2net_file
        elif utils.valid_file("/etc/ser2net.yaml"):
            self.ser2net_file = Path("/etc/ser2net.yaml")
        elif utils.valid_file("/etc/ser2net.conf"):
            self.ser2net_file = Path("/etc/ser2net.conf")
        else:
            self.ser2net_file = None

        return self.ser2net_file

    def get_remotes_from_file(self):
        return self.get_json_file(self.static.get('LOCAL_CLOUD_FILE'))

    def get_config_all(self, yaml_cfg=None, legacy_cfg=None):
        '''Parse bash style cfg vars from cfg file convert to class attributes.'''
        # prefer yaml file for all config items if it exists
        do_legacy = True
        yml = {}
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
                        if line.strip() and not line.startswith('#'):
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
        if ovrd.get("remote_timeout"):
            if isinstance(ovrd["remote_timeout"], dict):  # New config style allowing per host timeout override
                self.remote_timeout = RemoteTimeout()
                for k, v in ovrd["remote_timeout"].items():
                    self.remote_timeout.add_host(k, int(v))
            else:
                self.remote_timeout = RemoteTimeout(int(ovrd["remote_timeout"]))  # Old config style they overrode the default for all remotes
        else:
            self.remote_timeout = RemoteTimeout()  # Default
        self.dli_timeout = int(ovrd.get('dli_timeout', DEFAULT_DLI_TIMEOUT))
        self.so_timeout = int(ovrd.get('smartoutlet_timeout', DEFAULT_SO_TIMEOUT))
        self.cycle_time = int(ovrd.get('cycle_time', DEFAULT_CYCLE_TIME))
        self.api_port = int(ovrd.get("api_port", DEFAULT_API_PORT))
        self.hide_legend = ovrd.get("hide_legend", False)
        # Additional override settings not needed by the python files
        # ovpn_share:  Share VPN connection when wired_dhcp enabled with hotspot connected devices

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
        by_dev: Dict[str, Any] = {}
        for k in outlet_data:
            if k == "OUTLET-GROUPS":
                self.outlet_groups = outlet_data[k]
                continue
            _type = outlet_data[k].get('type').lower()
            relays = [] if _type != "esphome" else utils.listify(outlet_data[k].get('relays', k))
            linked = outlet_data[k].get('linked_devs', {})

            if linked:
                outlet_data[k]['linked_devs'] = utils.format_dev(outlet_data[k]['linked_devs'],
                                                                 hosts=self.hosts, outlet_groups=self.outlet_groups, with_path=True)
                self.linked_exists = True
                for dev in outlet_data[k]['linked_devs']:
                    if _type == 'dli':
                        self.do_dli_menu = True
                        _this = [f"{k}:{[int(p) for p in utils.listify(outlet_data[k]['linked_devs'][dev])]}"]
                    elif _type == 'esphome':
                        _linked = utils.listify(outlet_data[k]['linked_devs'][dev])
                        _this = [f'{k}:{[p for p in _linked]}']
                    else:
                        _this = [k]
                    by_dev[dev] = _this if dev not in by_dev else by_dev[dev] + _this
            else:
                outlet_data[k]['linked_devs'] = {}

            if outlet_data[k]["type"].lower() not in types:
                types.append(outlet_data[k]["type"].lower())

            if outlet_data[k]['type'].upper() == 'GPIO' and isinstance(outlet_data[k].get('address'), str) \
                    and outlet_data[k]['address'].isdigit():
                outlet_data[k]['address'] = int(outlet_data[k]['address'])

            # This block determines if we should show dli_menu / if any esphome outlets match criteria to show
            # in dli menu (anytime it has exactly 8 outlets, if it has > 1 relay and not all are linked)
            if not self.do_dli_menu and _type == "esphome" and len(relays) > 1:
                if len(relays) == 8 or not linked:
                    self.do_dli_menu = True
                elif [r for r in relays if f"'{r}'" not in str(linked)]:
                    self.do_dli_menu = True

        self.outlet_types = types
        outlet_data = {
            'defined': {k: v for k, v in outlet_data.items() if k != "OUTLET-GROUPS"},
            'linked': by_dev,
            'dli_power': {},
            'esp_power': {},
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
                    return yaml.load(f, Loader=yaml.SafeLoader)
                except ValueError as e:
                    log.warning(f'Unable to load configuration from {yaml_file}\n\t{e}', show=True)

    def get_hosts(self):
        '''Parse user defined hosts for inclusion in menu

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
            hosts[h]["method"] = hosts[h].get('method', 'ssh').lower()
            if hosts[h]["method"] == 'ssh':  # method defaults to ssh if not provided
                port = 22 if ':' not in hosts[h]['address'] else hosts[h]['address'].split(':')[1]
                _user_str = '' if not hosts[h].get('username') else f'{hosts[h].get("username")}@'
                key_file = None
                if hosts[h].get("key") and self.loc_user is not None:
                    if utils.valid_file(f"/home/{self.loc_user}/.ssh/{hosts[h]['key']}"):
                        user_key = Path(f"/home/{self.loc_user}/.ssh/{hosts[h]['key']}")
                        if utils.valid_file(f"/etc/ConsolePi/.ssh/{hosts[h]['key']}"):
                            mstr_key = Path(f"/etc/ConsolePi/.ssh/{hosts[h]['key']}")
                            if mstr_key.stat().st_mtime > user_key.stat().st_mtime:
                                shutil.copy(mstr_key, user_key)
                                shutil.chown(user_key, user=self.loc_user, group=self.loc_user)
                                user_key.chmod(0o600)
                                log.info(f"{hosts[h]['key']} Updated from ConsolePi global .ssh key_dir to "
                                         f"{str(user_key.parent)} for use with {h}...", show=True)
                        key_file = str(user_key)
                    elif utils.valid_file(hosts[h]['key']):
                        key_file = hosts[h]['key']
                    elif utils.valid_file(f"/etc/ConsolePi/.ssh/{hosts[h]['key']}"):
                        user_ssh_dir = Path(f"/home/{self.loc_user}/.ssh/")
                        if user_ssh_dir.is_dir():
                            shutil.copy(f"/etc/ConsolePi/.ssh/{hosts[h]['key']}", user_ssh_dir)
                            user_key = Path(f"{user_ssh_dir}/{hosts[h]['key']}")
                            shutil.chown(user_key, user=self.loc_user, group=self.loc_user)
                            user_key.chmod(0o600)
                            log.info(f"{hosts[h]['key']} imported from ConsolePi global .ssh key_dir to "
                                     f"{str(user_ssh_dir)} for use with {h}...", show=True)
                            key_file = str(user_key)
                hosts[h]['cmd'] = (
                    f"sudo -u {self.loc_user} ssh{' ' if not key_file else f' -i {key_file} '}" f"-t {_user_str}{hosts[h]['address'].split(':')[0]} -p {port}"
                )
                # hosts[h]['cmd'] = f"sudo -u {self.loc_user} ssh -t {_user_str}{hosts[h]['address'].split(':')[0]} -p {port}"
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

        host_dict['_methods'] = utils.unique([hosts[h].get('method', 'ssh') for h in hosts])
        host_dict['_host_list'] = [f'/host/{h.split("/")[-1]}' for h in hosts]

        return host_dict

    def get_ser2net(self):
        self.verify_ser2net_file()
        return self.get_ser2netv4() if self.ser2net_file.suffix in [".yaml", ".yml"] else self.get_ser2netv3()

    @staticmethod
    def get_v4_line(tty_dev: str, *, port: int, baud: int, parity: str, dbits: int, sbits: int, flow: str, logfile: str | Path, log_ptr: str, **kwargs) -> str:
        ser2net_flow = {
            'n': '',
            'x': ' XONXOFF',
            'h': ' RTSCTS'
        }
        ser2netv4_line = f"""connection: &{tty_dev.replace("/dev/", "")}
  accepter: telnet(rfc2217),tcp,{port}
  connector: serialdev,{tty_dev},{baud}{parity}{dbits}{sbits},local{'' if flow == 'n' else ',' + ser2net_flow[flow].lower()}
  enable: on
  options:
    banner: *banner
    kickolduser: true
    telnet-brk-on-sync: true
"""
        if logfile and log_ptr:
            log_type = log_ptr.split("=")[0]
            log_alias = "".join(log_ptr.split("=")[1:])
            pointers = {
                "tr": "trace-read",
                "tw": "trace-write",
                "tb": "trace-both",
            }
            ser2netv4_line = f'{ser2netv4_line}    {pointers[log_type]}: *{log_alias}\n'
        return ser2netv4_line

    def get_ser2netv3(self):
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
        if self.ser2net_ver and int(self.ser2net_ver[0]) == 4:
            log.warning("You are running ser2net v4 which uses /etc/ser2net.yaml for it's config.  However the v3 config /etc/ser2net.conf was found.", show=True)
            log.warning("The menu will continue to use ser2net.conf if present in case ser2net config has not been migrated.", show=True)
            log.warning("/etc/ser2net.yaml will be used to extract serial settings once /etc/ser2net.conf is removed", show=True)

        ser2net_conf = {}
        trace_files = {}
        cfg = self.ser2net_file.read_text()
        for line in cfg.splitlines():
            if line.lstrip().startswith("#"):
                continue
            elif not line.strip():
                continue
            elif 'TRACEFILE:' in line:
                line = line.split(':')
                trace_files[line[1]] = "".join(line[2:])
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
            baud = None
            for option in connect_params:
                if option in self.static.get(
                    'VALID_BAUD',
                    ['300', '1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200']
                ):
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
                'line': _line,
            }
            ser2net_conf[tty_dev]['v4line'] = self.get_v4_line(tty_dev, **ser2net_conf[tty_dev])
            if trace_files:
                _v4_tracefiles = [f'define: &{k} {v}' for k, v in trace_files.items()]
                ser2net_conf["_v4_tracefiles"] = "# TRACEFILE DEFINITIONS\n" + "\n".join(_v4_tracefiles)

        return ser2net_conf

    def get_ser2netv4(self, file: Path = None) -> Dict:
        """Parse ser2net.yaml (ser2net 4.x) to extract connection info for serial adapters

        Args:
            ser_dict (dict, optional): Used to convert ser2netv3 to v4. Defaults to None.

        retruns 2 level dict (empty dict if ser2net.yaml not found or empty):
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
                    "line": The config lines from ser2net.yaml
                }
            }
        """
        ########################################################
        # --- ser2net (4.x) config lines look like this ---
        # connection: &con0096
        #   accepter: telnet(rfc2217),tcp,2000
        #   connector: serialdev,/dev/ttyS0,9600n81,local
        #   enable: on
        #   options:
        #     banner: *banner
        #     kickolduser: true
        #     telnet-brk-on-sync: true
        ########################################################
        ser2net_conf = {}
        if file is None and self.ser2net_file is None:
            return {}

        raw = self.ser2net_file.read_text() if not file else file.read_text()
        raw_mod = "\n".join([line if not line.startswith("connection") else f"{line.split('&')[-1]}:" for line in raw.splitlines()])
        banner = [line for line in raw.splitlines() if line.startswith("define: &banner")]
        banner = None if not banner else banner[-1].replace("define: &banner", "").lstrip()
        try:
            ser_dict = yaml.safe_load(raw_mod)
        except Exception as e:
            log.error(f"Error ({e.__class__.__name__}) occured parsing {file or self.ser2net_file}, verify file contents.", show=True)
            log.exception(e)
            return {}

        for k, v in ser_dict.items():
            if not isinstance(v, dict):
                continue
            if "accepter" not in v or "connector" not in v:
                continue
            if "serialdev" not in v["connector"]:
                log.info(f"skipping ser2net config for {v['connector']} as it is not a serialdev")
                continue

            con_dict = {f"connection: &{k}": v}
            tty_port = v["accepter"].split(",")[-1]
            tty_port = 0 if not tty_port.isdigit() else int(tty_port)
            _connector = v["connector"]
            _connector_list = [part.strip() for part in _connector.split(",")]
            tty_dev = _connector_list[1]
            _baud_str = _connector_list[2].rstrip() if " " not in _connector_list[2].rstrip() else _connector_list[2].split(" ")[0]
            _parity_options = "neoms"  # None Even Odd Mark Space
            parity = [x for x in list(_parity_options) if x in _baud_str]
            if not parity:
                log.warning(f"unable to extract parity from {_baud_str} for {_connector} defaulting to 'n'")
                parity = "n"
            else:
                parity = parity[0]
            baud = _baud_str[0:_baud_str.index(parity)]
            if not baud.isdigit():
                log.warning(f"parse error extracting baud ({baud}) from ser2net.yaml for {_connector}, defaulting to {self.default_baud}", show=True)
                baud = self.default_baud
            else:
                baud = int(baud)

            if parity in ["m", "s"]:
                parity = "n"
                log.warning(f"Setting parity to none for {_connector} when launched via menu. picocom does not support 'm'ark or 's'pace", show=True)
            # parity = _connector_list[2][-3]
            if "rtscts" in str(_connector_list).lower():
                flow = "h"
            elif "xonxoff" in str(_connector_list).lower():  # TODO need to verify this is the format ser2net.yaml accepts, documentation doesn't mention what the options are
                flow = "x"
            else:
                flow = "n"
            dbits = int(_baud_str[-2])
            sbits = int(_baud_str[-1])
            if sbits not in range(1, 3):
                log.warning(f"parse error of config error stop bit ({sbits}) extracted from ser2net.yaml for {_connector}, is invalid defaulting to 1", show=True)
                sbits = 1
            if dbits < 5 or dbits > 8:
                log.warning(
                    f'{tty_dev}: Invalid value for "data bits" found in ser2net.conf falling back to 8',
                    show=True)
                dbits = 8
            if "options" in v:
                keys = [k for k in v["options"].keys() if k.startswith("trace")]
                # picocom just has the simple log option ser2net allows multiple with various options use trace-both if specified
                # it's the closest to what picocom will do.  otherwise simply base it on whatever the first trace entry is.
                if keys:
                    _log_key = "trace-both" if len(keys) > 1 and "trace-both" in keys else keys[0]
                logfile = log_ptr = None if not keys else v["options"][_log_key]

            # parse TRACEFILE defined in ser2net.yaml se we can pass a similar log file format to picocom when launched from menu
            cmd_base = f'picocom {tty_dev} --baud {baud} --flow {flow} --databits {dbits} --parity {parity}'
            if self.picocom_ver > 1:  # picocom ver 1.x in Stretch doesn't support "--stopbits"
                cmd_base = cmd_base + f' --stopbits {sbits}'
            if logfile:
                logfile = logfile.replace('\\p', str(tty_port)).replace('\\d', tty_dev.split('/')[-1])
                logfile = logfile.replace('\\s', f'{baud}_{dbits}{parity.upper()}{sbits}')
                logfile = logfile.split('\\')[0] + '-{{timestamp}}.log'  # + menu will convert totime.strftime('%H.%M.log') when session is launched
                cmd = cmd_base + f' --logfile {logfile}'
                if not Path(logfile).parent.is_dir():
                    Path(logfile).parent.mkdir()
                    utils.set_perm(str(Path(logfile).parent))
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
                'line': f'{list(con_dict.keys())[0]}\n{"".join(line if "banner:" not in line else line.replace(f"banner: {banner}", "banner: *banner") for idx, line in enumerate(yaml.safe_dump(con_dict, indent=2).splitlines(keepends=True)) if idx > 0)}'
            }

        return ser2net_conf
