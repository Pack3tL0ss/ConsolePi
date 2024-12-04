#!/etc/ConsolePi/venv/bin/python3

import pyudev
import socket
import netifaces as ni
import os
import time
from pathlib import Path
from consolepi import utils, log, config  # type: ignore


class Local():
    ''' Class to collect and manage ConsolePis local attributes '''

    def __init__(self):
        self.default_baud = config.default_baud
        self.api_port = config.api_port
        self.udev_adapters = self.detect_adapters()
        self.adapters = self.build_adapter_dict()
        self.hostname = socket.gethostname()
        self.cpuserial = self.get_cpu_serial()
        self.interfaces = self.get_if_info()
        self.ip_list = self.get_ip_list()
        self.data = self.build_local_dict()
        self.user = config.loc_user
        self.loc_home = os.path.expanduser(f'~{self.user}')

    def build_local_dict(self, rem_ip=None, refresh=False):
        '''Display representation of all local data in combined dict.'''
        if refresh:
            self.adapters = self.build_adapter_dict(refresh=True)
            self.interfaces = self.get_if_info()
        _ip_w_gw = self.interfaces['_ip_w_gw']
        rem_ip = _ip_w_gw if rem_ip is None else rem_ip
        local = {
            self.hostname: {
                'cpuserial': self.cpuserial,
                'adapters': self.adapters,
                'interfaces': self.interfaces,
                'rem_ip': rem_ip,
                'api_port': self.api_port,
                'user': config.cfg.get('rem_user', 'pi')
            }
        }
        return local

    # TODO pyudev.Devices.time_since_initialized is datetime timedelta dt.now() - dev.time_since_initialized.  Include init_time as attribute of adapter object
    def detect_adapters(self, key=None):
        """Detect Locally Attached Adapters.

        Returns
        -------
        dict
            udev alias/symlink if defined/found as key or root device if not.
            /dev/ is stripped: (ttyUSB0 | AP515).  Each device has it's attrs
            in a dict.
        """
        if key is not None:
            key = '/dev/' + key.split('/')[-1]  # key can be provided with or without /dev/ prefix

        context = pyudev.Context()

        devs = {'_dup_ser': {}}
        usb_list = [dev.properties['DEVPATH'].split('/')[-1] for dev in context.list_devices(ID_BUS='usb', subsystem='tty')]
        pci_list = [dev.properties['DEVPATH'].split('/')[-1] for dev in context.list_devices(ID_BUS='pci', subsystem='tty')]
        i2c_list = [dev.properties['DEVPATH'].split('/')[-1] for dev in context.list_devices(ID_BUS='i2c', subsystem='tty')]
        ama_list = [dev.replace('/dev/', '') for dev in config.cfg_yml.get('TTYAMA', {})]
        root_dev_list = usb_list + pci_list + i2c_list + ama_list

        for root_dev in root_dev_list:
            # determine if the device already has a udev alias & collect available path options for use on lame adapters
            dev_name = by_path = by_id = None
            try:
                _dev = pyudev.Devices.from_name(context, 'tty', root_dev)
            except pyudev._errors.DeviceNotFoundByNameError:
                log.error(f'pyudev Ubable to find {root_dev}')
                continue  # TODO Catching error as have seen it in consolepi-mdnsreg not sure if continue is appropriate
            _devlinks = _dev.get('DEVLINKS', '').split()
            if not _devlinks:   # skip occurs on non rpi and ttyAMA
                if not root_dev.startswith('ttyAMA'):
                    continue
            else:
                for _d in _devlinks:
                    if '/dev/serial' not in _d:
                        dev_name = _d.replace('/dev/', '')
                    elif '/dev/serial/by-path/' in _d:
                        by_path = _d
                    elif '/dev/serial/by-id/' in _d:
                        by_id = _d

            dev_name = f'/dev/{root_dev}' if not dev_name else f'/dev/{dev_name}'
            devs[dev_name] = {'by_path': by_path, 'by_id': by_id}
            devs[dev_name]['root_dev'] = True if dev_name == f'/dev/{root_dev}' else False

            # Gather all available properties from device  # TODO investigate use of pyudev.Device.time_since_initialized
            _props = {p.lower() if p != 'ID_USB_INTERFACE_NUM' else 'id_ifnum': _dev.properties[p]
                      for p in _dev.properties}
            devs[dev_name] = {**devs[dev_name], **_props}

            # -- no need for remaining logic on ttyAMA adapters (local UART)
            if 'ttyAMA' in root_dev:
                # TODO clean up logic this is copy paste from below
                # clean up some redundant or less useful properties
                rm_list = ['devlinks', 'id_mm_candidate', 'id_model_enc', 'id_path_tag', 'tags', 'major', 'minor',
                           'usec_initialized', 'id_vendor_enc', 'id_pci_interface_from_database', 'id_revision']

                devs[dev_name] = {k: v for k, v in devs[dev_name].items() if k not in rm_list}

                continue

            # with some multi-port adapters the model_id and vendor_id need to be pulled from higher in stack
            this_dev = _dev
            while '0x' in this_dev.properties.get('ID_MODEL_ID', '0x') and hasattr(this_dev, 'parent'):
                this_dev = this_dev.parent

            # -- Collect path for mapping to specific USB port
            # TODO clean this up not efficient could combine search for ID_MODEL_ID and devpath
            lame_devpath = this_dev.attributes.get('devpath')
            if lame_devpath and isinstance(lame_devpath, bytes):
                lame_devpath = lame_devpath.decode('UTF-8')
            else:
                for p in _dev.ancestors:
                    if 'devpath' in p.attributes.available_attributes:
                        lame_devpath = p.attributes.get('devpath')
                        if lame_devpath and isinstance(lame_devpath, bytes):
                            lame_devpath = lame_devpath.decode('UTF-8')
                            break

            devs[dev_name]['lame_devpath'] = lame_devpath

            fallback_ser = this_dev.properties.get('ID_SERIAL_SHORT')
            devs[dev_name]['id_model_id'] = this_dev.properties['ID_MODEL_ID']
            devs[dev_name]['id_vendor_id'] = this_dev.properties['ID_VENDOR_ID']
            devs[dev_name]['time_since_init'] = f'{_dev.properties.device.time_since_initialized} ' \
                                                f"as of {time.strftime('%x %I:%M:%S %p %Z', time.localtime(time.time()))}"

            # clean up some redundant or less useful properties
            rm_list = ['devlinks', 'id_mm_candidate', 'id_model_enc', 'id_path_tag', 'tags', 'major', 'minor',
                       'usec_initialized', 'id_vendor_enc', 'id_pci_interface_from_database', 'id_revision']

            devs[dev_name] = {k: v for k, v in devs[dev_name].items() if k not in rm_list}

            # --- // Handle Multi-Port adapters that use same serial for all interfaces \\ ---
            # Capture the dict in dup_ser it's later del if no additional devices present with the same serial
            # Capture path and ifnum for any subsequent devs if ser is already in the dup_ser dict
            _ser = devs[dev_name]['id_serial_short'] = _dev.get('ID_SERIAL_SHORT', fallback_ser)
            if _ser not in devs['_dup_ser']:
                devs['_dup_ser'][_ser] = {'id_paths': [], 'id_ifnums': []}

            devs['_dup_ser'][_ser]['id_paths'].append(devs[dev_name]['id_path'])
            devs['_dup_ser'][_ser]['id_ifnums'].append(devs[dev_name]['id_ifnum'])

        # --- // Clean up detection of Multi-Port adapters that use same serial for all interfaces \\ ---
        # all dev serial #s are added to dup_ser as they are discovered
        # remove any serial #s that only appeared once.
        del_list = [_ser for _ser in devs['_dup_ser'] if len(devs['_dup_ser'][_ser]['id_paths']) == 1]
        for i in del_list:
            del devs['_dup_ser'][i]

        return devs if key is None else devs[key]

    def default_ser_config(self, tty_dev, tty_port=0):
        '''Return default serial parameters when no match found in ser2net'''
        return {
            'port': tty_port,
            'baud': self.default_baud,
            'dbits': 8,
            'parity': 'n',
            'flow': 'n',
            'sbits': 1,
            'logfile': None,
            'cmd': f'picocom {tty_dev} --baud {self.default_baud}'
        }

    def build_adapter_dict(self, refresh=False):
        '''Create final adapter dict from udev ser2net and outlet dicts.'''
        if refresh or not hasattr(self, 'udev_adapters'):
            self.udev_adapters = self.detect_adapters()
        udev = {a: self.udev_adapters[a] for a in self.udev_adapters if a != '_dup_ser'}
        linked = [] if not config.outlets else config.outlets['linked']
        ser2net = {} if not config.ser2net_conf else config.ser2net_conf

        adapters = {}
        for a in udev:
            adapters[a] = {'udev': udev[a],
                           'outlets': [] if a not in linked else linked[a],
                           'config': self.default_ser_config(a) if a not in ser2net else ser2net[a]
                           }

        if refresh:
            self.adapters = adapters
            self.data = self.build_local_dict()

        return adapters

    def get_cpu_serial(self):
        res = utils.do_shell_cmd("/bin/cat /proc/cpuinfo | grep Serial | awk '{print $3}'", return_stdout=True)
        if res[0] > 0:
            log.warning('Unable to get unique identifier for this pi (cpuserial)', show=True)
            return 0
        elif res[1]:
            return res[1]
        else:  # for non rpi use machine-id if file exists
            machine_id_file = Path("/etc/machine-id")
            if machine_id_file.exists():
                return machine_id_file.read_text().strip()
            else:
                return 0

    def get_if_info(self):
        '''Build and return dict with interface info.'''
        if_list = [i for i in ni.interfaces() if i != 'lo' and 'docker' not in i]
        if_w_gw = ni.gateways()['default'].get(ni.AF_INET, {1: None})[1]
        if_data = {_if: {'ip': ni.ifaddresses(_if).get(ni.AF_INET, {0: {}})[0].get('addr'),
                         'mac': ni.ifaddresses(_if).get(ni.AF_LINK, {0: {}})[0].get('addr'),
                         'isgw': True if _if == if_w_gw else False} for _if in if_list
                   if ni.ifaddresses(_if).get(ni.AF_INET, {0: {}})[0].get('addr')
                   }

        if_data['_ip_w_gw'] = if_data.get(if_w_gw, {'ip': None})['ip']
        log.debugv('[GET IFACES] Completed Iface Data: {}'.format(if_data))
        return if_data

    def get_ip_list(self):
        return [
            ni.ifaddresses(i).get(ni.AF_INET, {0: {}})[0].get('addr')
            for i in ni.interfaces()
            if i != 'lo' and 'docker' not in i and 'ifb' not in i and ni.ifaddresses(i).get(ni.AF_INET, {0: {}})[0].get('addr')
        ]


if __name__ == '__main__':
    pass
