#!/etc/ConsolePi/venv/bin/python3

"""
    -- dev testing file currently --
    This file currently only logs
    Eventually this file may be used for ztp trigger or oobm switch discovery for the menu
"""

import os
import sys
import yaml
# import string
# import json
from jinja2 import Environment, FileSystemLoader
sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import utils, log, config, requests  # NoQA
from consolepi.local import Local  # NoQA
parser_dir = config.static.get('PARSER_DIR', '/etc/ConsolePi/ztp-custom-parsers')
sys.path.insert(1, parser_dir)

try:
    from parsers import Parsers
    custom_parsers = True
except ImportError:
    custom_parsers = False

local = Local()
ztp_iface = 'eth0'
ztp_lease_time = config.ovrd.get('ztp_lease_time', '2m')
if config.cfg_yml.get('ZTP'):
    config.do_ztp = True
    config.ztp = config.cfg_yml['ZTP']
else:
    config.do_ztp = False
    config.ztp = {}

ztp_dir = config.static.get('ZTP_DIR', '/etc/ConsolePi/ztp')  # j2 tamplates and var files
ztp_main_conf = "/etc/ConsolePi/dnsmasq.d/wired-dhcp/ztp.conf"
eth_main_conf = "/etc/ConsolePi/dnsmasq.d/wired-dhcp/wired-dhcp.conf"
ztp_opts_conf = '/etc/ConsolePi/dnsmasq.d/wired-dhcp/ztp-opts/ztp-opts.conf'
ztp_hosts_conf = '/etc/ConsolePi/dnsmasq.d/wired-dhcp/ztp-hosts/ztp-hosts.conf'

ztp_main_lines = [
                    "enable-tftp\n",
                    "tftp-root=/srv/tftp\n"
                    f"dhcp-option=option:tftp-server,\"{local.interfaces[ztp_iface]['ip']}\"\n",
                    "dhcp-optsdir=/etc/ConsolePi/dnsmasq.d/wired-dhcp/ztp-opts\n"
                    "dhcp-hostsdir=/etc/ConsolePi/dnsmasq.d/wired-dhcp/ztp-hosts\n"
]


if custom_parsers:
    class CustomParsers(Parsers):
        def __init__(self, data):
            super().__init__(data)


class Ztp:
    def __init__(self, ztp_conf: dict, mac: utils.Mac = None, vc_idx: int = 1):
        self.main_lines = []
        self.host_lines = []
        self.opt_lines = []
        self.ok = True
        self.error = ''
        self.mac = mac
        self.conf = ztp_conf
        self.conf_pretty = ''.join([f"\t{k}: {v}\n" for k, v in self.conf.items()])
        self.vendor_class = ztp_conf.get('vendor_class')
        self.tmplt = self._get_template()
        self.var_file = self._get_var_file()
        self.vc_idx = vc_idx
        if not self.ok:
            print(f"!! {self.error}")
        else:
            self.data = self._get_config_data()
            if self.mac:
                self.cfg_file_name = f"{mac.clean}.cfg"
                if not self.mac.ok:
                    self.error = mac.error
                    self.ok = False
            elif self.vendor_class:
                self.cfg_file_name = f"{self.vendor_class}_{vc_idx}.cfg"
            else:
                print('This should never happen')
            self.gen_dhcp_lines()
            print(f"+ Generating Template {self.cfg_file_name}")
            self.generate_template()

    def _get_template(self):
        tmplt = self.conf.get('template', '').rstrip('.j2')
        mac = self.mac
        # template is defined in config
        if tmplt and utils.valid_file(f"{ztp_dir}/{tmplt}.j2"):
            return f"{ztp_dir}/{tmplt}.j2"
        # template is not defined look for <mac>.j2 file for template
        elif mac and utils.valid_file(f"{ztp_dir}/{mac.clean}.j2"):
            return f"{ztp_dir}/{mac.clean}.j2"
        else:
            self.ok = False
            self.error += f"[ZTP Entry Skipped!!] No Template Found for:\n{self.conf_pretty}\n"

    def _get_var_file(self):
        variables = self.conf.get('variables')
        mac = self.mac
        if variables and utils.valid_file(f"{ztp_dir}/{variables}"):
            return f"{ztp_dir}/{variables}"
        elif mac and utils.valid_file(f"{ztp_dir}/{mac.clean}.yaml"):
            return f'{ztp_dir}/{mac.clean}.yaml'
        elif mac and utils.valid_file(f'{ztp_dir}/variables.yaml'):
            return f'{ztp_dir}/variables.yaml'
        else:
            self.ok = False
            if self.error and 'No Template Found' in self.error:
                self.error = "[ZTP Entry Skipped!!] No Template or Variables Found for Entry with " \
                             f"the following config:\n{self.conf_pretty}\n"
                pass
            else:
                self.error += f"[ZTP Entry Skipped!!] No Variables Found for:\n{self.conf_pretty}\n"

    def _get_config_data(self):
        config_data = yaml.load(open(self.var_file), Loader=yaml.SafeLoader)
        mac = self.mac
        if 'variables.yaml' in self.var_file:
            config_data = config_data.get(mac.clean) if config_data.get(mac.clean) else \
                          config_data.get(os.path.basename(self.tmplt).rstrip('.j2'))
        elif 'config' in config_data:
            config_data = config_data['config']

        if custom_parsers:
            _data = CustomParsers(config_data)
            if _data.ok:
                config_data = _data.out
            else:
                self.error = _data.error

        return config_data

    def gen_dhcp_lines(self):
        '''Generate dnsmasq/dhcp configuration lines
        '''
        mac = self.mac
        if mac:
            # ztp_hosts_lines.append(f"{mac.cols},{mac.tag},{_ip_pfx}.{_ip_sfx},{ztp_lease_time},set:{mac.tag}\n")
            _mac = mac.cols if not self.conf.get('oobm') else mac.oobm.cols
            self.host_lines.append(f"{_mac},{mac.tag},,{ztp_lease_time},set:{mac.tag}\n")
            self.opt_lines.append(f'tag:{mac.tag},option:bootfile-name,"{self.cfg_file_name}"\n')

        elif self.vendor_class:
            self.main_lines.append(f'dhcp-vendorclass=set:{self.vendor_class},{self.vendor_class}\n')
            if self.vc_idx == 1:
                self.opt_lines.append(f"tag:{self.vendor_class},tag:!sent,option:bootfile-name,{self.cfg_file_name}\n")
            else:
                self.opt_lines.append(f"# tag:{self.vendor_class},tag:!sent,option:bootfile-name,{self.cfg_file_name}\n")

    def generate_template(self):
        '''Generate configuration files based on j2 templates and provided variables
        '''
        env = Environment(loader=FileSystemLoader(os.path.dirname(self.tmplt)), trim_blocks=True, lstrip_blocks=True)
        template = env.get_template(os.path.basename(self.tmplt))

        with open(f"/srv/tftp/{self.cfg_file_name}", "w") as output:
            output.write(template.render(self.data))


class ConsolePiZtp(Ztp):
    def __init__(self):
        self.ztp_main_lines = ztp_main_lines
        self.ztp_host_lines = []
        self.ztp_opt_lines = []
        self.run()

    def configure_dhcp_files(self):
        for _dir in [os.path.dirname(ztp_opts_conf), os.path.dirname(ztp_hosts_conf)]:
            if not os.path.isdir(_dir):
                os.mkdir(_dir)
                utils.set_perm(_dir, user='rwx', group='rwx', other='rx')

        # -- get dhcp-range= line from wired-dhcp.conf and override it in ztp.conf with shorter lease time for ztp
        with open('/etc/ConsolePi/dnsmasq.d/wired-dhcp/wired-dhcp.conf') as f:
            dhcp_main_lines = f.readlines()

        line = [
                f"{','.join(_line.split(',')[0:-1])},{ztp_lease_time}\n" for _line in dhcp_main_lines
                if _line.strip().startswith('dhcp-range=')
                ]
        if line and len(line) == 1:
            ztp_main_lines.insert(0, line[0])
        else:
            print("!! Error occured getting dhcp-range from wired-dhcp.conf lease-time will not be updated for ZTP")

        for _file, _lines in zip(
                [ztp_main_conf, ztp_hosts_conf, ztp_opts_conf],
                [self.ztp_main_lines, self.ztp_host_lines, self.ztp_opt_lines]
                ):
            with open(_file, "w") as f:
                f.writelines(_lines)

    def dhcp_append(self, ztp: Ztp):
        self.ztp_main_lines = utils.unique(self.ztp_main_lines + ztp.main_lines)
        self.ztp_host_lines += ztp.host_lines
        self.ztp_opt_lines += ztp.opt_lines

    def run(self):
        print(f"{'-' * 43}\nResetting ZTP Configuration Based On Config\n{'-' * 43}")
        for key in config.ztp:
            if 'ordered' not in key:
                # -- Generate Templates for defined MACs in ztp config --
                mac = utils.Mac(key)
                if mac.ok:
                    ztp = Ztp(config.ztp[key], mac=mac)
                    self.dhcp_append(ztp)
                else:
                    print(f'The ztp configuration {key} does not appear to be a valid MAC ... skipping')
            else:
                # -- Generate Templates for ordered_ztp based on fuzzy match of vendor class --
                for vendor_class in config.ztp.get('ordered', {}):
                    idx = 1
                    print(f"\n -- Configuring vendor class *{vendor_class}* for Ordered ZTP -- ")
                    for _ztp in config.ztp['ordered'][vendor_class]:
                        _ztp['vendor_class'] = vendor_class
                        ztp = Ztp(_ztp, vc_idx=idx)
                        self.dhcp_append(ztp)
                        idx += 1

        print("+ Creating DHCP Configuration for ZTP\n")
        self.configure_dhcp_files()


if __name__ == '__main__':
    if not config.do_ztp:
        print('ZTP is not Enabled in Config.')
        print('refer to GitHub for more details')
    else:
        # if not config.cfg.get('wired_dhcp', False):
        #     pass  # TODO prompt to enable wired_dhcp
        # if utils.do_shell_cmd('systemctl is_active tftpd-hpa'):
        #     pass  # TODO diable tftpd-hpe
        ConsolePiZtp()
