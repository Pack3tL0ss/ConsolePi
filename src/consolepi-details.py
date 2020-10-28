#!/etc/ConsolePi/venv/bin/python3

import sys
import subprocess

sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import config, utils, log  # type: ignore # NoQA
from consolepi.consolepi import ConsolePi  # type: ignore # NoQA


cpi = ConsolePi()
local = cpi.local
hostname = local.hostname
adapters = local.adapters
interfaces = local.interfaces
remotes = cpi.remotes.data
details = local.data
dump = {'local': details, 'remotes': config.remotes}


def jprint(data):
    utils.json_print(data)
    if isinstance(data, dict):
        if len(data) > 1:
            _keys = [k.replace("/dev/", "") for k in data.keys()]
            _len = len(_keys)
            print(f"\n--\n{_keys}\nTotal: {_len}\n--")


def get_outlets():
    if not config.outlets:
        cpi.cpiexec.pwr_init_complete = True
    if config.outlets and not cpi.cpiexec.pwr_init_complete:
        utils.spinner('Waiting for Power Threads To Complete', cpi.cpiexec.wait_for_threads)
        if cpi.pwr:
            return cpi.pwr.data


if config.remotes:
    for r in config.remotes:
        if r not in cpi.remotes.data:
            dump['remotes'][r]['!! WARNING !!'] = 'This Device is Currently Unreachable'

if len(sys.argv) > 1:
    if sys.argv[1] == 'adapters':
        jprint(adapters)
    elif sys.argv[1] == 'interfaces':
        jprint(interfaces)
    elif sys.argv[1] == 'outlets':
        jprint(get_outlets())
    elif sys.argv[1] == 'hosts':
        _ = subprocess.run("sed -n '/HOSTS:/,/^ *$/p' /etc/ConsolePi/ConsolePi.yaml | more", shell=True)
        print(f"Total: {len(config.hosts.get('_host_list', []))}")
    elif sys.argv[1] == 'remotes':
        if len(sys.argv) == 2:
            jprint(remotes)
        elif len(sys.argv) == 4:
            if sys.argv[2] == 'del':
                if sys.argv[3] in remotes:
                    print('Removing ' + sys.argv[3] + ' from local cloud cache')
                    remotes.pop(sys.argv[3])
                    cpi.remotes.update_local_cloud_file(remote_consoles=remotes, current_remotes=remotes)
                    print('Remotes remaining in local cache')
                    jprint(remotes)
                    print('{} Removed from local cache'.format(sys.argv[3]))
                else:
                    print(f'!! {sys.argv[3]} Not Found in Local Cache')
    elif sys.argv[1] == 'local':
        jprint(details)
    else:
        try:
            print(f'\nRemote Cache data for {sys.argv[1]}:')
            jprint(remotes[sys.argv[1]])
        except KeyError:
            dump['outlets'] = get_outlets()
            jprint(dump)
            print('!!!  {} Not Found entire data set above   !!!'.format(sys.argv[1]))

else:
    dump['outlets'] = get_outlets()
    jprint(dump)

if log.error_msgs:
    print('!! ', end='')
    print('\n!! '.join(log.error_msgs))

if config.outlets and not cpi.cpiexec.pwr_init_complete:
    utils.spinner('Exiting... Waiting for Power Threads To Complete', cpi.cpiexec.wait_for_threads)
