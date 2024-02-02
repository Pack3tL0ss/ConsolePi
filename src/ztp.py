#!/etc/ConsolePi/venv/bin/python3

"""
This script is called by consolepi-ztp.  It generates the configuration files based on
ZTP configuration in ConsolePi.yaml and configures dnsmasq for ZTP.
"""

import os
import sys
import yaml
import json
from jinja2 import Environment, FileSystemLoader
sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import utils, config  # type: ignore # NoQA
from consolepi.local import Local  # type: ignore # NoQA
parser_dir = config.static.get('PARSER_DIR', '/etc/ConsolePi/ztp/custom-parsers')
sys.path.insert(1, parser_dir)

try:
    from parsers import Parsers # type: ignore
    custom_parsers = True
except ImportError:
    custom_parsers = False

local = Local()
ztp_iface = 'eth0'  # TODO dynamically determine wired interface for non rpi
ztp_lease_time = config.ovrd.get('ztp_lease_time', '2m')
ztp_dir = config.static.get('ZTP_DIR', '/etc/ConsolePi/ztp')  # j2 tamplates and var files
ztp_main_conf = "/etc/ConsolePi/dnsmasq.d/wired-dhcp/ztp.conf"
eth_main_conf = "/etc/ConsolePi/dnsmasq.d/wired-dhcp/wired-dhcp.conf"
ztp_opts_conf = '/etc/ConsolePi/dnsmasq.d/wired-dhcp/ztp-opts/ztp-opts.conf'
ztp_hosts_conf = '/etc/ConsolePi/dnsmasq.d/wired-dhcp/ztp-hosts/ztp-hosts.conf'
ZTP_CLI_FILE = config.static.get('ZTP_CLI_FILE', '/etc/ConsolePi/ztp/.ztpcli')

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
    def __init__(self, ztp_conf: dict, mac: utils.Mac = None, vc_idx: int = 1, prep_dhcp: bool = True):
        self.main_lines = []
        self.host_lines = []
        self.opt_lines = []
        self.ok = True
        self.prep_dhcp = prep_dhcp
        self.error = ''
        self.mac = mac
        self.conf = ztp_conf
        self.conf_pretty = ''.join([f"\t{k}: {v}\n" for k, v in self.conf.items()])
        self.vendor_class = ztp_conf.get('vendor_class')
        self.image = ztp_conf.get('image')
        self.tmplt = self._get_template()
        self.var_file = self._get_var_file()
        self.vc_idx = vc_idx
        if not self.ok:
            print(f"!! {self.error}")
        else:
            self.data = self._get_config_data()
            if self.mac:
                if self.mac.ok:
                    self.cfg_file_name = f"{mac.clean}.cfg"
                else:
                    # if we are not prepping dhcp a valid MAC is not required
                    if not self.prep_dhcp:
                        self.cfg_file_name = f"{mac.orig}.cfg"
                    else:
                        self.error = mac.error
                        self.ok = False
            elif self.vendor_class:
                self.cfg_file_name = f"{self.vendor_class}_{vc_idx}.cfg"
            else:
                print('This should never happen')

            if self.prep_dhcp:
                self.gen_dhcp_lines()

            msg = f"+ Generating config {self.cfg_file_name}"
            print(f"{msg}{'' if self.prep_dhcp else ' (omitted from DHCP/ZTP Orchestration based on config)'}")
            print(f"  Template: {os.path.basename(self.tmplt)}")
            print(f"  Variables: {os.path.basename(self.var_file)}")
            self.generate_template()

    def _get_template(self):
        '''Determine what jinja2 template to use to generate the config.

        Template filename can be provided in config if not provided look for template
        named <mac-address>.j2

        Returns:
            str: Full path to j2 template.
        '''
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
        '''Determine variable file to use to generate the config.

        Variables can be provided (in the order we look for them):
            1. in the config for the device
            2. via a file named <mac address>.yaml
            3. matching the template name with .yaml extension
            4. in a common variables.yaml file
                a. by mac-address
                b. by key matching the template name


        when using ordered ztp variable file based on template name should have
        _# appended where # corresponds to the order for that model.  i.e. 6200F_1.yaml, 6200F_2.yaml
        given the template is 6200F.j2

        Returns:
            str: Full path to yaml variable file.
        '''
        variables = self.conf.get('variables')
        mac = self.mac
        if variables and utils.valid_file(f"{ztp_dir}/{variables}"):
            return f"{ztp_dir}/{variables}"
        elif mac and utils.valid_file(f"{ztp_dir}/{mac.clean}.yaml"):
            return f'{ztp_dir}/{mac.clean}.yaml'
        elif self.tmplt and utils.valid_file(f"{self.tmplt.rstrip('.j2')}.yaml"):
            return f"{self.tmplt.rstrip('.j2')}.yaml"
        elif mac and utils.valid_file(f'{ztp_dir}/variables.yaml'):
            return f'{ztp_dir}/variables.yaml'
        else:
            self.ok = False
            if self.error and 'No Template Found' in self.error:
                self.error = "[ZTP Entry Skipped!!] No Template or Variables Found for Entry with " \
                             f"the following config:\n{self.conf_pretty}\n"
            else:
                self.error += f"[ZTP Entry Skipped!!] No Variables Found for:\n{self.conf_pretty}\n"

    def _get_config_data(self):
        '''Generate/Return the dict (variable to value mappings) for jinja2 template conversion.

        '''
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
        mac = self.mac if not self.conf.get('oobm') else self.mac.oobm
        if mac:
            tag = mac.tag
            self.host_lines.append(f"{mac.cols},{tag},,{ztp_lease_time},set:{tag}\n")
            self.opt_lines.append(f'tag:{tag},option:bootfile-name,"{self.cfg_file_name}"\n')

        elif self.vendor_class:
            tag = self.vendor_class
            self.main_lines.append(f'dhcp-vendorclass=set:{self.vendor_class},{self.vendor_class}\n')
            if self.vc_idx == 1:
                self.opt_lines.append(f"tag:{tag},tag:!cfg_sent,option:bootfile-name,{self.cfg_file_name}\n")
            else:
                self.opt_lines.append(f"# tag:{tag},tag:!cfg_sent,option:bootfile-name,{self.cfg_file_name}\n")

        if self.image:
            self.opt_lines.insert(0, f"tag:{tag},tag:!img_sent,vendor:,145,{self.image}\n")

    def generate_template(self):
        '''Generate configuration files based on j2 templates and provided variables
        '''
        env = Environment(loader=FileSystemLoader(os.path.dirname(self.tmplt)), trim_blocks=True, lstrip_blocks=True)
        template = env.get_template(os.path.basename(self.tmplt))

        with open(f"/srv/tftp/{self.cfg_file_name}", "w") as output:
            output.write(template.render(self.data))


class ConsolePiZtp(Ztp):
    def __init__(self, prep_dhcp=True):
        self.prep_dhcp = prep_dhcp
        self.ztp_main_lines = ztp_main_lines
        self.ztp_host_lines = []
        self.ztp_opt_lines = []
        self.ztp_clifile_data = {}
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
            self.ztp_main_lines.insert(0, line[0])
        else:
            print("!! Error occured getting dhcp-range from wired-dhcp.conf lease-time will not be updated for ZTP")

        for _file, _lines in zip(
            [ztp_main_conf, ztp_hosts_conf, ztp_opts_conf],
            [self.ztp_main_lines, self.ztp_host_lines, utils.unique(self.ztp_opt_lines)]
        ):
            with open(_file, "w") as f:
                f.writelines(_lines)

            # assign file to consolepi group and makes group writable.  Makes troubleshooting easier
            utils.set_perm(_file, other='r')

    def dhcp_append(self, ztp: Ztp):
        if self.prep_dhcp:
            self.ztp_main_lines = utils.unique(self.ztp_main_lines + ztp.main_lines)
            self.ztp_host_lines += ztp.host_lines
            self.ztp_opt_lines += ztp.opt_lines

        if hasattr(ztp, 'cfg_file_name'):
            self.ztp_clifile_data[ztp.cfg_file_name] = ztp.conf

    def run(self):
        msg = 'Resetting ZTP Configuration Based On Config' if self.prep_dhcp else \
            'Generating Configuration based on Templates Only (No DHCP Prep for ZTP)'
        print(f"{'-' * int(len(msg))}\n{msg}\n  cfg output dir: /srv/tftp\n{'-' * int(len(msg))}")

        for key in config.ztp:
            if 'ordered' not in key:
                # -- Generate Templates for defined MACs in ztp config --
                mac = utils.Mac(key)
                if mac.ok:
                    ztp = Ztp(config.ztp[key], mac=mac)
                    # if self.prep_dhcp:
                    self.dhcp_append(ztp)
                else:
                    ztp_ok = True
                    for _key in ["template", "variables", "no_dhcp"]:
                        if _key not in config.ztp[key]:
                            ztp_ok = False
                            print(f'The ztp configuration {key} does not appear to be a valid MAC ... skipping')
                            break

                    # generate config without configuring associated ztp rule
                    if ztp_ok:
                        mac = utils.Mac(key)
                        ztp = Ztp(config.ztp[key], mac=mac, prep_dhcp=False)
                        self.dhcp_append(ztp)

            else:
                # -- Generate Templates for ordered_ztp based on fuzzy match of vendor class --
                for vendor_class in config.ztp.get('ordered', {}):
                    idx = 1
                    print(f"\n -- Configuring vendor class *{vendor_class}* for Ordered ZTP -- ")
                    for _ztp in config.ztp['ordered'][vendor_class]:
                        _ztp['vendor_class'] = vendor_class
                        ztp = Ztp(_ztp, vc_idx=idx)
                        # if self.prep_dhcp:
                        self.dhcp_append(ztp)
                        idx += 1

        if self.prep_dhcp:
            # -- re-order ztp_opt_lines so all image file entries are at top --
            self.ztp_opt_lines = [_line for _line in self.ztp_opt_lines if 'img_sent' in _line] + \
                [_line for _line in self.ztp_opt_lines if 'img_sent' not in _line]
            print("+ Creating DHCP Configuration for ZTP")
            self.configure_dhcp_files()

        # Always Update .ztpcli even if not updating DHCP
        if self.ztp_clifile_data:
            print("+ Stashing cfg_file to param mappings for cli operations\n")
            with open(ZTP_CLI_FILE, "w") as fb:
                fb.writelines(json.dumps(self.ztp_clifile_data))


if __name__ == '__main__':
    if not config.ztp:
        print('ZTP is not configured in ConsolePi.yaml')
        print('refer to GitHub for more details')
        sys.exit(1)
    else:
        _prep_dhcp = False if len(sys.argv) > 1 and sys.argv[1] == 'nodhcp' else True
        ConsolePiZtp(prep_dhcp=_prep_dhcp)
