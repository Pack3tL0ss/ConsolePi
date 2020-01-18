#!/etc/ConsolePi/venv/bin/python3

import json
import sys
import os
from halo import Halo
from consolepi.common import (ConsolePi_data, set_perm)

config = ConsolePi_data(do_print=False)
local_cloud_file = config.LOCAL_CLOUD_FILE # pylint: disable=maybe-no-member
spin = Halo(spinner='dots')

spin.start('Gathering ConsolePi Data')
hostname = config.hostname
adapters = config.adapters
interfaces = config.interfaces
outlets = config.pwr.outlet_data
remotes = config.remotes
details = config.local_data_repr()
details['remotes'] = remotes
spin.stop()

if len(sys.argv) > 1:
    if sys.argv[1] == 'adapters':
        print(json.dumps(adapters, indent=4, sort_keys=True))
    elif sys.argv[1] == 'interfaces':
        print(json.dumps(interfaces, indent=4, sort_keys=True))
    elif sys.argv[1] == 'outlets':
        if not config.pwr_init_complete:
            config.wait_for_threads()
            outlets = config.pwr.outlet_data
        print(json.dumps(outlets, indent=4, sort_keys=True))
    elif sys.argv[1] == 'remotes':
        if len(sys.argv) == 2:
            print(json.dumps(remotes, indent=4, sort_keys=True))
        elif len(sys.argv) == 4:
            if sys.argv[2] == 'del':
                if sys.argv[3] in remotes:
                    print('Removing ' + sys.argv[3] + ' from local cloud cache')
                    remotes.pop(sys.argv[3])
                    config.update_local_cloud_file(remote_consoles=remotes, current_remotes=remotes)
                    print('Remotes remaining in local cache')
                    print(json.dumps(remotes, indent=4, sort_keys=True))
                    print('{} Removed from local cache'.format(sys.argv[3]))
    elif sys.argv[1] == 'local':
        print(json.dumps(details, indent=4, sort_keys=True))
    else:
        try:
            print('\nRemote Cache data for {}:\n{}'.format(sys.argv[1], json.dumps(details['remotes'][sys.argv[1]], indent=4, sort_keys=True)))
        except KeyError:
            print(json.dumps(details, indent=4, sort_keys=True))
            print('!!!  {} Not Found entire data set above   !!!'.format(sys.argv[1]))
else:
    print(json.dumps(details, indent=4, sort_keys=True))
