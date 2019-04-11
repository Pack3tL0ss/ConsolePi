#!./../venv/bin/python

# import os
# os.chdir('/etc/ConsolePi/cloud/gdrive')
# Import the necessary packages
import logging
from consolemenu import *
from consolemenu.items import *
import csv
import sys
import json

# sys.path.insert(0, '../cloud/gdrive')
# print(sys.path)
# from include.utils import get_config
config_file = '/etc/ConsolePi/ConsolePi.conf'
log_file = '/var/log/ConsolePi/cloud.log'
local_cloud_file = '/etc/ConsolePi/ConsolePi.cloud.csv'


# Get Variables from Config
def get_config(var):
    with open(config_file, 'r') as cfg:
        for line in cfg:
            if var in line:
                var_out = line.replace('{0}='.format(var), '')
                var_out = var_out.replace('"'.format(var), '', 1)
                var_out = var_out.split('"')
                var_out = var_out[0]
                break

    if var_out == 'true' or var_out == 'false':
        var_out = True if var_out == 'true' else False

    return var_out

# -- GLOBALS --
DEBUG = get_config('debug')
CLOUD_SVC = get_config('cloud_svc')

# Logging
LOG_FILE = log_file
log = logging.getLogger(__name__)
log.setLevel(logging.INFO if not DEBUG else logging.DEBUG)
handler = logging.FileHandler(LOG_FILE)
handler.setLevel(logging.INFO if not DEBUG else logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)


def get_serial_ports():
    this = serial.tools.list_ports.grep('.*ttyUSB[0-9]*', include_links=True)
    tty_list = {}
    tty_alias_list = {}
    for x in this:
        _device_path = x.device_path.split('/')
        if x.device.replace('/dev/', '') != _device_path[len(_device_path)-1]:
            tty_alias_list[x.device_path] = x.device
        else:
            tty_list[x.device_path] = x.device

    final_tty_list = []
    for k in tty_list:
        if k in tty_alias_list:
            final_tty_list.append(tty_alias_list[k])
        else:
            final_tty_list.append(tty_list[k])

    # get telnet port deffinitions from ser2net.conf
    # and build adapters dict
    serial_list = []
    if os.path.isfile('/etc/ser2net.conf'):
        for tty_dev in final_tty_list:
            with open('/etc/ser2net.conf', 'r') as cfg:
                for line in cfg:
                    if tty_dev in line:
                        tty_port = line.split(':')
                        tty_port = tty_port[0]
                        log.info('get_serial_ports: found {} {}'.format(tty_dev, tty_port))
                        break
                    else:
                        tty_port = 7000
            serial_list.append({'dev': tty_dev, 'port': tty_port})
            if tty_port == 7000:
                log.error('No ser2net.conf deffinition found for {}'.format(tty_dev))
                print('No ser2net.conf deffinition found for {}'.format(tty_dev))
    else:
        log.error('No ser2net.conf file found unable to extract port deffinitions')
        print('No ser2net.conf file found unable to extract port deffinitions')

    return serial_list


def get_remote_ports():
    remote_cmd_list = []
    data = {}
    with open(local_cloud_file, mode='r') as csv_file:
        csv_reader = csv.reader(csv_file)
        line_count = 0
        for row in csv_reader:
            if len(row[0]) > 0:
                hostname = row[0]
                row.pop(0)
                host_data = (', '.join(row))
                data[hostname] = json.loads(host_data)
                print(row[1])
                print(type(row[1]))
                # hostname = row[0]
                # ip = row[1]
                # user = row[2]
                # device = row[3]
                # port = row[4]
                remote_cmd_list.append('ssh -t {0}@{1} picocom {2}'.format(row[2], row[1], row[3]))
            line_count += 1
        print('Processed {0} lines.'.format(line_count))
        return data


def create_menu(data):
    # Create the menu
    menu = ConsoleMenu("ConsolePi Menu", "")

    # Create some items

    # MenuItem is the base class for all items, it doesn't do anything when selected
    menu_item = MenuItem("ConsolePi Menu")

    # A FunctionItem runs a Python function when selected
    for host in data:
        cnt = 0
        for adapter in data[host]['adapters']:
            rem_console_item = CommandItem('Connect to {0} on {1}'.format(
                data[host]['adapters'][cnt]['dev'].replace('/dev/', ''), host),
                'ssh -t {0}@{1} picocom {2}'.format(
                    data[host]['user'], data[host]['interfaces']['wlan0'], data[host]['adapters'][cnt]['dev']))
            # rem_console_item = CommandItem('Connect to {0} on {1}'.format(
            #     data[host]['adapters'][cnt]['dev'].replace('/dev/', ''), host),
            #     'echo "ssh -t {0}@{1} picocom {2}" >> c:/users/wellswa/cloud.log'.format(
            #         data[host]['user'], data[host]['interfaces']['wlan0'], data[host]['adapters'][cnt]['dev'], log_file))
            menu.append_item(rem_console_item)
            cnt += 1
    # A CommandItem runs a console command
    command_item = CommandItem("Run a console command",  "touch hello.txt")

    # A SelectionMenu constructs a menu from a list of strings
    selection_menu = SelectionMenu([300, 1200, 9600, 19200, 57600, 115200])

    # A SubmenuItem lets you add a menu (the selection_menu above, for example)
    # as a submenu of another menu
    con_menu = ConsoleMenu("Connection Settings", "")
    connection_menu = MenuItem("ConsolePi Connection Settings")
    submenu_item = SubmenuItem("Configure Connection Settings", connection_menu, menu)
    baud_menu = SubmenuItem("Baud", selection_menu, connection_menu)
    con_menu.append_item(baud_menu)

    # Once we're done creating them, we just add the items to the menu
    # menu.append_item(menu_item)
    # menu.append_item(function_item)
    menu.append_item(command_item)
    menu.append_item(submenu_item)

    # Finally, we call show to show the menu and allow the user to interact
    menu.show()
data = get_remote_ports()
create_menu(data)
