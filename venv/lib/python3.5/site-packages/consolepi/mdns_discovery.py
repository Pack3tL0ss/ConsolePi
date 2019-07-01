#!/etc/ConsolePi/venv/bin/python3 

""" Test File was never implemented mdns_browse seems to be the right way about it """

import logging
import sys
import json
from consolepi.common import update_local_cloud_file
from consolepi.common import get_config
import threading
import socket

from zeroconf import Zeroconf

TYPE = '_consolepi._tcp.local.'
NAME = 'ConsolePi'      
LOCAL_CLOUD_FILE = '/etc/ConsolePi/cloud.data'
DEBUG = get_config('debug')
HOSTNAME = socket.gethostname()

def discover_remotes_mdns(do_thread=False):
    zeroconf = Zeroconf()

    try:
        properties = zeroconf.get_service_info(TYPE, NAME + '.' + TYPE).properties
        for _ in properties:
            print('{}: {}'.format(_, properties[_]))
        hostname = properties[b'hostname'].decode("utf-8")
        user = properties[b'user'].decode("utf-8")
        interfaces = json.loads(properties[b'interfaces'].decode("utf-8"))
        adapters = json.loads(properties[b'adapters'].decode("utf-8"))
        data = {hostname: {'interfaces': interfaces, 'adapters': adapters, 'user': user}}

        print(data)
        if do_thread:
            threading.Thread(target=update_local_cloud_file, args=(LOCAL_CLOUD_FILE, data), name='avahi_local_cache_update').start()
        else:
            print('no thread')
            x = update_local_cloud_file(LOCAL_CLOUD_FILE, data)
    except AttributeError:
        pass
    finally:
        zeroconf.close()

    # return data

if __name__ == '__main__':
    print(discover_remotes_mdns(do_thread=True))

