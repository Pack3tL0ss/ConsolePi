#!/etc/ConsolePi/venv/bin/python3

"""
This script is called by dnsmasq after DHCP operation or after TFTP Xfer.

When Triggered by DHCP:
    logs data provided by dnsmasq including the Vendor Class String.

When Triggered by TFTP:
    Adjusts the dnsmasq configuration (for ordered ZTP)
    Process any post CLI commands against the device.

    Portions of this script adapted from the Aruba Networks Automation
    Teams work @ https://github.com/aruba/aruba-switch-ansible
"""
import sys
import os
import json
import paramiko
import time
import re
import in_place
import socket

sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import utils, log, config # type: ignore # NoQA

ZTP_CLI_DEFAULT_TIMEOUT = config.static.get('ZTP_CLI_DEFAULT_TIMEOUT', 75)
ZTP_CLI_LOGIN_MAX_WAIT = config.static.get('ZTP_CLI_LOGIN_MAX_WAIT', 60)
lease_file = '/var/lib/misc/dnsmasq.leases'
ztp_opts_conf = '/etc/ConsolePi/dnsmasq.d/wired-dhcp/ztp-opts/ztp-opts.conf'
ztp_hosts_conf = '/etc/ConsolePi/dnsmasq.d/wired-dhcp/ztp-hosts/ztp-hosts.conf'
ZTP_CLI_FILE = config.static.get('ZTP_CLI_FILE', '/etc/ConsolePi/ztp/.ztpcli')
match = [m for m in config.cfg_yml.get('ZTP', {}).get('ordered_ztp', {})]
ztp_lease_time = '2m'

# -- DEBUG STUFF
DEBUG = False
if DEBUG:
    log.setLevel(10)  # 10 = logging.DEBUG

    env = ''
    for k, v in os.environ.items():
        if 'DNS' in k:
            env += f"{k}: {v}\n"
    if env:
        log.debug(f"Environment:\n{env}")
        log.debug(f"Arguments:\n{', '.join(sys.argv[1:])}")
# --

# dhcp args: add aa:bb:cc:dd:ee:ff 10.33.0.151
# tftp args: tftp 12261 10.33.0.113 /srv/tftp/6200_1.cfg
add_del = sys.argv[1]       # the word tftp when tftp
mac_bytes = sys.argv[2]     # bytes sent when tftp
ip = sys.argv[3]
cfg_file = None
if len(sys.argv) > 4:
    cfg_file = sys.argv[4]  # file sent via tftp

# Available from environ when called by dhcp
iface = os.environ.get('DNSMASQ_INTERFACE')
vendor = os.environ.get('DNSMASQ_VENDOR_CLASS')


class Cli:
    """Class to execute CLI commands on device after configuration has been sent.
    """
    def __init__(self, ip: str = None, cli_method: str = 'ssh', cli_user: str = None, cli_pass: str = None,
                 cli_timeout: int = ZTP_CLI_DEFAULT_TIMEOUT, cmd_list: list = None, **kwargs):
        # TELNET not supported for now... cli_method currently ignored
        self.fail_msg = ''
        self.ip = ip
        self.cmd_list = cmd_list
        if not cli_user or cli_pass is None or not cmd_list:
            log.info(f"No CLI Operations Performed on {ip} Missing/incomplete cli configuration")
        else:
            paramiko_ssh_connection_args = {'hostname': ip, 'port': 22, 'look_for_keys': False,
                                            'username': cli_user, 'password': cli_pass, 'timeout': cli_timeout}

            # Login
            self.ssh_client = paramiko.SSHClient()
            # Default AutoAdd as Policy
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.run(paramiko_ssh_connection_args)

    def fail_json(self, **kwargs):
        self.fail_msg = {k: v for k, v in kwargs.items()}

    def execute_command(self, command_list):
        """
        Execute command and returns output
        :param command_list: list of commands
        :return: output of show command
        """
        prompt = re.compile(r'\r\n' + re.escape(self.prompt.replace('#', '')) + '.*# ')
        hostname = re.compile(r'^ho[^ ]*')

        # NoQA RFC 1123 Compliant Regex (See https://stackoverflow.com/questions/106179/regular-expression-to-match-dns-hostname-or-ip-address)
        validhostname = re.compile(r'^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])$')  # NoQA

        # Clear Buffer
        self.out_channel()

        cli_output = []
        for command in command_list:
            # Check if command wants to change hostname and if so it will also change the prompt regex
            if hostname.search(command):
                new_hostname = command.split(" ")[-1]
                if validhostname.search(new_hostname):
                    self.prompt = new_hostname + "#"
                    prompt = re.compile(r'\r\n' + re.escape(new_hostname) + '.*# ')
                else:
                    self.fail_json(
                        msg='To be compliant with RFC 1123, the hostname must contain only letters, '
                            'numbers and hyphens, and must not start or end with a hyphen. Can not change Hostname!')

            if command.startswith('SLEEP'):
                _ = os.system(command.lower())
            else:
                self.in_channel(command)
                count = 0
                text = ''
                fail = True
                while count < 45:
                    time.sleep(2)
                    curr_text = self.out_channel()
                    text += curr_text
                    if prompt.search(curr_text):
                        fail = False
                        break
                    count += 1
                if fail:
                    self.fail_json(msg='Unable to read CLI Output in given Time')
                # Reformat text
                text = text.replace('\r', '').rstrip('\n')
                # Delete command and end prompt from output
                text_lines = text.split('\n')[1:-1]
                cli_output.append('\n'.join(text_lines))

        return cli_output

    def get_prompt(self):
        """
        Additional needed Setup for Connection
        """
        # Set prompt
        count = 0
        fail = True
        self.in_channel("")
        while count < 45:
            time.sleep(2)
            curr_text = self.out_channel()
            if '#' in curr_text:
                fail = False
                break
            count += 1
        if fail:
            self.fail_json(msg='Unable to read CLI Output in given Time')

        # Set prompt
        count = 0
        self.in_channel("")
        # Regex for ANSI escape chars and prompt
        text = ''
        fail = True
        while count < 45:
            time.sleep(2)
            curr_text = self.out_channel()
            text += curr_text.replace('\r', '')
            if '#' in curr_text:
                fail = False
                break
            count += 1

        if fail:
            self.fail_json(msg='Unable to read CLI Output in given Time for prompt')

        self.prompt = text.strip('\n').replace(' ', '')

    def out_channel(self):
        """
        Clear Buffer/Read from Shell
        :return: Read lines
        """
        recv = ""
        # Loop while shell is able to recv data
        while self.shell_chanel.recv_ready():
            recv = self.shell_chanel.recv(65535)
            if not recv:
                self.fail_json(msg='Chanel gives no data. Chanel is closed by Switch.')
            recv = recv.decode('utf-8', 'ignore')
        return recv

    def in_channel(self, cmd):
        """
        Sends cli command to Shell
        :param cmd: the command itself
        """
        cmd = cmd.rstrip()
        cmd += '\n'
        cmd = cmd.encode('ascii', 'ignore')
        self.shell_chanel.sendall(cmd)

    def logout(self):
        """
        Logout from Switch
        :return:
        """
        self.in_channel('end')
        self.in_channel('exit')
        self.shell_chanel.close()
        self.ssh_client.close()

    def run(self, connection_args):
        '''Establish Connection to device and run CLI commands provided via ztp config

        Args:
            connection_args (dict): Arguments passed to paramiko to establish connection
        '''
        result = dict(
            changed=False,
            cli_output=[],
            message=''
        )
        _start_time = time.time()
        while True:
            try:
                go = False
                # Connect to Switch via SSH
                self.ssh_client.connect(**connection_args)
                self.prompt = ''
                # SSH Command execution not allowed, therefore using the following paramiko functionality
                self.shell_chanel = self.ssh_client.invoke_shell()
                self.shell_chanel.settimeout(8)
                # AOS-CX specific
                self.get_prompt()
                go = True
                break
            except socket.timeout:
                log.error(f'ZTP CLI Operations Failed, TimeOut Connecting to {self.ip}')
            except paramiko.ssh_exception.NoValidConnectionsError as e:
                log.error(f'ZTP CLI Operations Failed, {e}')
            except paramiko.ssh_exception.AuthenticationException:
                log.error('ZTP CLI Operations Failed, CLI Authentication Failed verify creds in config')

            if time.time() - _start_time >= ZTP_CLI_LOGIN_MAX_WAIT:
                break  # Give Up
            else:
                time.sleep(10)

        if go:
            try:
                result['cli_output'] = self.execute_command(self.cmd_list)
                result['changed'] = True
                if self.fail_msg:
                    result['message'] += self.fail_msg.get('msg')
            finally:
                self.logout()

            # Format log entries and exit
            _res = " -- // Command Results \\ -- \n"
            _cmds = [c for c in self.cmd_list if 'SLEEP' not in c]
            for cmd, out in zip(_cmds, result['cli_output']):
                if "progress:" in out and f"progress: {out.count('progress:')}/{out.count('progress:')}" in out:
                    out = out.split("progress:")[0] + f"progress: {out.count('progress:')}/{out.count('progress:')}"
                _res += "{}:{} {}\n".format(cmd, '\n' if '\n' in out else '', out)
            _res += " --------------------------- \n"
            _res += ''.join([f"{k}: {v}\n" for k, v in result.items() if k != "cli_output" and v])
            log.info(f"Post ZTP CLI Operational Result for {ip}:\n{_res}")


def get_mac(ip):
    '''Get the mac address for the device based on ip provided by dnsmasq (triggered by tftp xfer).

    Args:
        ip (str): IP address provided by dnsmasq as argument when it triggers this script after tftp xfer.

    Returns:
        str or None: MAC address associated with IP from dhcp lease file
    '''
    with open(lease_file) as f:
        mac = None
        lines = f.readlines()
        for line in lines:
            if ip in line:
                mac = line.split(' ')[1]
        if not mac:
            if len(sys.argv) > 5:
                mac = sys.argv[5]  # debug option for testing add mac as 5th arg doesn't have to be in lease file
        return mac


def _write_to_file(fp, current: list, new: list):
    new = utils.unique(new)
    if 'ztp-opts' in fp.name:   # Overwrite the existing file contents
        for line_num, line in enumerate(new):
            fp.write(line)
    else:                       # Append to existing file for ztp-hosts.conf
        for line_num, line in enumerate(new):
            if line not in current:
                fp.write(line)
            else:
                log.info(f"Skipping write for content on line {line_num} ({line[0:20]}...) as the line already exists")


def next_ztp(filename, mac):
    '''Transition dnsmasq configuration to next config file when using ordered ZTP mechanism.

    Args:
        filename (str): Full path of filename just sent via tftp.  Provided by dnsmasq as argument.
        mac (Mac object): mac object with various attributes for the MAC address of the device that requested/rcvd the config.
    '''
    _from = os.path.basename(filename)
    _to = None  # init
    if _from.endswith('.cfg'):
        set_tag = "cfg_sent"
        _cfg_mac = utils.Mac(_from.rstrip('.cfg'))
        if _cfg_mac.ok and mac.clean not in [_cfg_mac.clean, _cfg_mac.oobm.clean]:
            _to = f"{_from.split('_')[0]}_{int(_from.rstrip('.cfg').split('_')[-1]) + 1}.cfg"
    else:
        set_tag = "img_sent"

    host_lines = []
    opts_lines = []

    if not os.path.isfile(ztp_opts_conf):
        log.warning(f"{ztp_opts_conf} not found. Noting to do.")
    else:
        if _to and not os.path.isfile(f"{os.path.dirname(filename)}/{_to}"):
            log.info(f"No More Files for {_from.split('_')[0]}")
        with in_place.InPlace(ztp_opts_conf) as fp:
            line_num = 1
            cur_opts_lines = fp.readlines()
            for line in cur_opts_lines:
                if _from in line:
                    if mac.ok:
                        opts_lines.append(
                            f"# {mac.cols}|{ip} Sent {_from}"
                            f"{' Success' if ztp_ok else 'WARN file size != xfer total check switch and logs'}\n"
                            )

                        if set_tag == "cfg_sent" and not line.startswith("#"):
                            opts_lines.append(f"# SENT # {line}")
                            opts_lines.append(f"# -- Retry Line for {_from.rstrip('.cfg')} Based On mac {mac.cols} --\n")
                            opts_lines.append(f'tag:{mac.tag},option:bootfile-name,"{_from}"\n')
                            log.info(f"Disabled {_from} on line {line_num} of {os.path.basename(ztp_opts_conf)}")
                            log.info(f"Retry Entry Created for {_from.rstrip('.cfg')} | {mac.cols} | {ip}")
                        else:
                            opts_lines.append(line)

                        host_lines.append(f"{mac.cols},{mac.tag},,{ztp_lease_time},set:{mac.tag},set:{set_tag}\n")
                    else:
                        print(f'Unable to write Retry Lines for previously updated device.  Mac {mac.orig} appears invalid')
                        log.warning(
                            f"Unable to Create Retry Entry for {_from.rstrip('.cfg')} @ {ip}, "
                            f"Invalid MAC address --> {mac.cols}"
                            )

                elif _to and _to in line:
                    if not line.startswith('#'):
                        log.warning(f'Expected {_to} option line to be commented out @ this point.  It was not.')
                    opts_lines.append(line.lstrip('#').lstrip())
                    log.info(f"Enabled {_to} on line {line_num} of {os.path.basename(ztp_opts_conf)}")
                else:
                    opts_lines.append(line)
                line_num += 1

            _write_to_file(fp, cur_opts_lines, opts_lines)

        if host_lines:
            with open(ztp_hosts_conf, 'a+') as fp:
                fp.seek(0)
                cur_host_lines = fp.readlines()
                _write_to_file(fp, cur_host_lines, host_lines)

                if set_tag.startswith('cfg'):
                    log.info(f"Retry Entries Written to file for {_from.rstrip('.cfg')} | {mac.cols} | {ip}")
                else:
                    log.info(f"{mac.cols} tagged as img_sent to prevent re-send of {_from}")


if __name__ == "__main__":
    if add_del != "tftp":  # -- // Triggerd By DHCP \\ --
        log.info(f'[DHCP LEASE] DHCP Client Connected ({add_del}): iface: {iface}, mac: {mac_bytes}, ip: {ip}, vendor: {vendor}')
        ztp = False

        # -- Simply logging if another ConsolePi has connected directly to this one --
        if vendor and 'ConsolePi' in vendor:
            log.info(f'A ConsolePi has connected to {iface}')

    else:  # -- // Triggerd By TFTP XFER \\ --
        ztp = True
        file_size = os.stat(cfg_file).st_size
        ztp_ok = True if int(mac_bytes) == file_size else False
        mac = utils.Mac(get_mac(ip))
        log.info(f"[ZTP - TFTP XFR] {os.path.basename(cfg_file)} sent to {ip}|{mac.cols}{' Success' if ztp_ok else ''}")
        _res = utils.do_shell_cmd(f"wall 'consolepi-ztp: {os.path.basename(cfg_file)} sent to "
                                  f"{ip}|{mac.cols}{' Success' if ztp_ok else ' WARNING xfr != file size'}'")
        if not ztp_ok:
            log.warning(f"File Size {file_size} and Xfr Total ({mac_bytes}) don't match")

        # If cfg file was sent transition to next cfg (ordered).
        # if img sent adjust adjust dnsmasq to prevent needless resend of img.
        next_ztp(cfg_file, mac)
        if config.ztp and cfg_file.endswith('.cfg'):
            # load stashed dict from file. keys are ztp.py generated cfg files names, mapped to dict of ztp settings from config.
            if not utils.valid_file(ZTP_CLI_FILE):
                log.warning(f'Skipping ZTP Post CLI for {ip} {ZTP_CLI_FILE} not found/invalid')
            else:
                with open(ZTP_CLI_FILE) as fb:
                    cfg_dict = json.loads(''.join(fb.readlines()))
                cfg_file_name = os.path.basename(cfg_file)
                if cfg_file_name in cfg_dict:
                    cli_ok = True
                    cfg_dict[cfg_file_name]['ip'] = ip
                    if 'cli_post' in cfg_dict[cfg_file_name]:
                        cfg_dict[cfg_file_name]['cmd_list'] = cfg_dict[cfg_file_name]['cli_post']
                        del cfg_dict[cfg_file_name]['cli_post']

                    log.debug(f"Dict from .ztpcli: {cfg_dict[cfg_file_name]}")

                    # -- // PERFORM Post ZTP CLI Based Operations via SSH \\ --
                    if cli_ok:
                        log.info(f"Start post ZTP CLI: {cfg_dict[cfg_file_name]['cmd_list']}")
                        cli = Cli(**cfg_dict[cfg_file_name])
