#!/etc/ConsolePi/venv/bin/python3

"""
    -- dev testing file currently --
    This file currently only logs
    Eventually this file may be used for ztp trigger or oobm switch discovery for the menu
"""
import sys
import in_place
sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import utils, log, config # NoQA
import sys  # NoQA
import os  # NoQA


lease_file = '/var/lib/misc/dnsmasq.leases'
# ztp_conf = '/etc/ConsolePi/dnsmasq.d/wired-dhcp/ztp.conf'
ztp_opts_conf = '/etc/ConsolePi/dnsmasq.d/wired-dhcp/ztp-opts/ztp-opts.conf'
ztp_hosts_conf = '/etc/ConsolePi/dnsmasq.d/wired-dhcp/ztp-hosts/ztp-hosts.conf'
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


def get_mac(ip):
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


def next_ztp(filename, mac):
    _from = os.path.basename(filename)
    if _from.endswith('.cfg'):
        set_tag = "cfg_sent"
        _to = f"{_from.split('_')[0]}_{int(_from.rstrip('.cfg').split('_')[-1]) + 1}.cfg"
    else:
        set_tag = "img_sent"
        _to = None

    host_lines = []

    if not os.path.isfile(ztp_opts_conf):
        log.warning(f"{ztp_opts_conf} not found. Noting to do.")
    else:
        if _to and not os.path.isfile(f"{os.path.dirname(filename)}/{_to}"):
            log.info(f"No More Files for {_from.split('_')[0]}")
        with in_place.InPlace(ztp_opts_conf) as fp:
            line_num = 1
            for line in fp:
                if _from in line:
                    if mac.ok:
                        fp.write(
                                f"# {mac.cols}|{ip} Sent {_from}"
                                f"{' Success' if ztp_ok else 'WARN file size != xfer total check switch and logs'}\n"
                                )
                        fp.write(f"# -- Retry Line for {_from.rstrip('.cfg')} Based On mac {mac.cols} --\n")
                        fp.write(f'tag:{mac.tag},option:bootfile-name,"{_from}"\n')
                        host_lines.append(f"{mac.cols},{mac.tag},,{ztp_lease_time},set:{mac.tag},set:{set_tag}\n")
                    else:
                        print(f'Unable to write Retry Lines for previously updated device.  Mac {mac.orig} appears invalid')

                    fp.write(f"# SENT # {line}")
                    log.info(f"Disabled {_from} on line {line_num} of {os.path.basename(ztp_opts_conf)}")
                    log.info(f"Retry Entries Created for {_from.rstrip('.cfg')} | {mac.cols} | {ip}")
                elif _to and _to in line:
                    if not line.startswith('#'):
                        log.warning(f'Expected {_to} option line to be commented out @ this point.  It was not.')
                    fp.write(line.lstrip('#').lstrip())
                    log.info(f"Enabled {_to} on line {line_num} of {os.path.basename(ztp_opts_conf)}")
                else:
                    fp.write(line)
                line_num += 1

        if host_lines:
            with open(ztp_hosts_conf, 'a') as fp:
                fp.writelines(host_lines)
                if set_tag.startswith('cfg'):
                    log.info(f"Retry Entries Written to file for {_from.rstrip('.cfg')} | {mac.cols} | {ip}")
                else:
                    log.info(f"{mac.cols} tagged as img_sent to prevent re-send of {_from}")


if add_del != "tftp":
    log.info(f'[DHCP LEASE] DHCP Client Connected ({add_del}): iface: {iface}, mac: {mac_bytes}, ip: {ip}, vendor: {vendor}')
    ztp = False
else:
    ztp = True
    file_size = os.stat(cfg_file).st_size
    ztp_ok = True if int(mac_bytes) == file_size else False
    mac = utils.Mac(get_mac(ip))
    log.info(f"[ZTP - TFTP XFR] {os.path.basename(cfg_file)} sent to {ip}|{mac.cols}{' Success' if ztp_ok else ''}")
    _res = utils.do_shell_cmd(f"wall 'consolepi-ztp: {os.path.basename(cfg_file)} sent to "
                              f"{ip}|{mac.cols}{' Success' if ztp_ok else ' WARNING xfr != file size'}'")
    if not ztp_ok:
        log.warning(f"File Size {file_size} and Xfr Total ({mac_bytes}) don't match")

    # If cfg file was sent transition to next (N/A for image file)
    # TODO !img_sent tag to prevent second image xfer after reboot
    # if cfg_file.endswith('.cfg'):
    next_ztp(cfg_file, mac)

    # -- Some old log only stuff, may use for post deployment actions --
    if vendor and 'ConsolePi' in vendor:
        log.info(f'A ConsolePi has connected to {iface}')
    elif vendor and iface and 'eth' in iface:
        for _ in match:
            if _ in vendor:
                if utils.is_reachable(ip, 22):
                    log.info('{} is reachable via ssh @ {}'.format(_, ip))
                elif utils.is_reachable(ip, 23):
                    log.info('{} is reachable via telnet @ {}'.format(_, ip))
