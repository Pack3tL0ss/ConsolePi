#!/etc/ConsolePi/venv/bin/python3

import os
import yaml
from consolepi import log, config, utils  # type: ignore


class Rename():
    def __init__(self, menu):
        self.menu = menu
        self.udev_pending = False
        self.baud = config.default_baud
        self.data_bits = config.default_dbits
        self.parity = config.default_parity
        self.flow = config.default_flow
        self.sbits = config.default_sbits
        self.parity_pretty = {'o': 'Odd', 'e': 'Even', 'n': 'No'}
        self.flow_pretty = {'x': 'Xon/Xoff', 'h': 'RTS/CTS', 'n': 'No'}
        self.rules_file = config.static.get('RULES_FILE', '/etc/udev/rules.d/10-ConsolePi.rules')
        self.ttyama_rules_file = config.static.get('TTYAMA_RULES_FILE', '/etc/udev/rules.d/11-ConsolePi-ttyama.rules')
        self.ser2net_file = config.static.get('SER2NET_FILE', '/etc/ser2net.conf')  # TODO Not Used Remove once verified all refs switched to config.ser2net_file
        self.reserved_names = ['ttyUSB', 'ttyACM', 'ttyAMA', 'ttySC']

    # --- // START MONSTER RENAME FUNCTION \\ --- # TODO maybe break this up a bit
    def do_rename_adapter(self, from_name):
        '''Rename USB to Serial Adapter

        Creates new or edits existing udev rules and ser2net conf
        for USB to serial adapters detected by the system.

        params:
        from_name(str): Devices current name passed in from rename_menu()

        returns:
        None type if no error, or Error (str) if Error occurred
        '''
        from_name = from_name.replace('/dev/', '')
        local = self.cpi.local
        c = {
            'green': '\033[1;32m',  # Bold with normal ForeGround
            'red': '\033[1;31m',
            'norm': '\033[0m',  # Reset to Normal
        }
        c_from_name = '{}{}{}'.format(c['red'], from_name, c['norm'])
        error = False
        use_def = True

        try:
            to_name = None
            while not to_name:
                print(" Press 'enter' to keep the same name and change baud/parity/...")
                to_name = input(f' [rename {c_from_name}]: Provide desired name: ')
                print("")
                to_name = to_name or from_name
            to_name = to_name.replace('/dev/', '')  # strip /dev/ if they thought they needed to include it
            # it's ok to essentialy rename with same name (to chg baud etc.), but not OK to rename to a name that is already
            # in use by another adapter
            # TODO collect not connected adapters as well to avoid dups
            if from_name != to_name and f"/dev/{to_name}" in local.adapters:
                return f"There is already an adapter using alias {to_name}"

            for _name in self.reserved_names:
                if to_name.startswith(_name):
                    return f"You can't start the alias with {_name}.  Matches system root device prefix"

            if ' ' in to_name or ':' in to_name or '(' in to_name or ')' in to_name:
                print('\033[1;33m!!\033[0m Spaces, Colons and parentheses are not allowed by the associated config files.\n'
                      '\033[1;33m!!\033[0m Swapping with valid characters\n')
                to_name = to_name.replace(' ', '_').replace('(', '_').replace(')', '_')  # not allowed in udev
                to_name = to_name.replace(':', '-')  # replace any colons with - as it's the field delim in ser2net

        except (KeyboardInterrupt, EOFError):
            return 'Rename Aborted based on User Input'

        c_to_name = f'{c["green"]}{to_name}{c["norm"]}'
        log_c_to_name = "".join(["{{green}}", to_name, "{{norm}}"])

        go, con_only = True, False
        if from_name == to_name:
            log.show(f"Keeping {log_c_to_name}. Changing connection settings Only.")
            con_only = True
            use_def = False
        elif utils.user_input_bool(' Please Confirm Rename {} --> {}'.format(c_from_name, c_to_name)) is False:
            go = False

        if go:
            for i in local.adapters:
                if i == f'/dev/{from_name}':
                    break
            _dev = local.adapters[i].get('config')  # type: ignore # dict
            # -- these values are always safe, values set by config.py if not extracted from ser2net.conf
            baud = _dev['baud']
            dbits = _dev['dbits']
            flow = _dev['flow']
            sbits = _dev['sbits']
            parity = _dev['parity']
            word = 'keep existing'
            for _name in self.reserved_names:
                if from_name.startswith(_name):
                    word = 'Use default'

            # -- // Ask user if they want to update connection settings \\ --
            if not con_only:
                use_def = utils.user_input_bool(' {} connection values [{} {}{}1 Flow: {}]'.format(
                    word, baud, dbits, parity.upper(), self.flow_pretty[flow]))

            if not use_def:
                self.con_menu(rename=True, con_dict={'baud': baud, 'data_bits': dbits, 'parity': parity,
                                                     'flow': flow, 'sbits': sbits})
                baud = self.baud
                parity = self.parity
                dbits = self.data_bits
                parity = self.parity
                flow = self.flow
                sbits = self.sbits

            # restore defaults back to class attribute if we flipped them when we called con_menu
            # TODO believe this was an old hack, and can be removed
            if hasattr(self, 'con_dict') and self.con_dict:
                self.baud = self.con_dict['baud']
                self.data_bits = self.con_dict['data_bits']
                self.parity = self.con_dict['parity']
                self.flow = self.con_dict['flow']
                self.sbits = self.con_dict['sbits']
                self.con_dict = None

            if word == 'Use default':  # see above word is set if from_name matches a root_dev pfx
                devs = local.detect_adapters()
                if f'/dev/{from_name}' in devs:
                    _tty = devs[f'/dev/{from_name}']
                    id_prod = _tty.get('id_model_id')
                    id_model = _tty.get('id_model')  # NoQA pylint: disable=unused-variable
                    id_vendorid = _tty.get('id_vendor_id')
                    id_vendor = _tty.get('id_vendor')  # NoQA pylint: disable=unused-variable
                    id_serial = _tty.get('id_serial_short')
                    id_ifnum = _tty.get('id_ifnum')
                    id_path = _tty.get('id_path')  # NoQA pylint: disable=unused-variable
                    lame_devpath = _tty.get('lame_devpath')
                    root_dev = _tty.get('root_dev')  # NoQA pylint: disable=unused-variable
                else:
                    return 'ERROR: Adapter no longer found'

                # -- // ADAPTERS WITH ALL ATTRIBUTES AND GPIO UART (TTYAMA) \\ --
                if id_prod and id_serial and id_vendorid:
                    if id_serial not in devs['_dup_ser']:
                        udev_line = (
                            'ATTRS{{idVendor}}=="{}", ATTRS{{idProduct}}=="{}", ATTRS{{serial}}=="{}", SYMLINK+="{}"'.format(id_vendorid, id_prod, id_serial, to_name)
                        )

                        error = None
                        while not error:
                            error = self.add_to_udev(udev_line, '# END BYSERIAL-DEVS')
                            error = self.do_ser2net_line(from_name=from_name, to_name=to_name, baud=baud, dbits=dbits,
                                                         parity=parity, flow=flow)
                            break

                    # -- // MULTI-PORT ADAPTERS WITH COMMON SERIAL (different ifnums) \\ --
                    else:
                        # SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6011", ATTRS{serial}=="FT4XXXXP", GOTO="FTXXXXP"  # NoQA
                        udev_line = (
                            'ATTRS{{idVendor}}=="{0}", ATTRS{{idProduct}}=="{1}", ATTRS{{serial}}=="{2}", GOTO="{2}"'.format(id_vendorid, id_prod, id_serial)
                        )

                        error = None
                        while not error:
                            error = self.add_to_udev(udev_line, '# END BYPORT-POINTERS')
                            # ENV{ID_USB_INTERFACE_NUM}=="00", SYMLINK+="FT4232H_port1", GOTO="END"
                            udev_line = ('ENV{{ID_USB_INTERFACE_NUM}}=="{}", SYMLINK+="{}"'.format(id_ifnum, to_name))
                            error = self.add_to_udev(udev_line, '# END BYPORT-DEVS', label=id_serial)
                            error = self.do_ser2net_line(from_name=from_name, to_name=to_name, baud=baud, dbits=dbits,
                                                         parity=parity, flow=flow)
                            break

                else:
                    if f'/dev/{from_name}' in devs:
                        devname = devs[f'/dev/{from_name}'].get('devname', '')
                        # -- // local ttyAMA adapters \\ --
                        if 'ttyAMA' in devname:
                            udev_line = ('KERNEL=="{}", SYMLINK+="{}"'.format(devname.replace('/dev/', ''), to_name))

                            # Testing simplification not using separate file for ttyAMA
                            error = None
                            while not error:
                                error = self.add_to_udev(udev_line, '# END TTYAMA-DEVS')
                                error = self.do_ser2net_line(from_name=from_name, to_name=to_name, baud=baud, dbits=dbits,
                                                             parity=parity, flow=flow)
                                break
                        else:
                            # -- // LAME ADAPTERS NO SERIAL NUM (map usb port) \\ --
                            log.warning('[ADD ADAPTER] Lame adapter missing key detail: idVendor={}, idProduct={}, serial#={}'.format(  # NoQA
                                        id_vendorid, id_prod, id_serial))
                            print('\n\n This Device Does not present a serial # (LAME!).  So the adapter itself can\'t be '
                                  'uniquely identified.\n There are 2 options for naming this device:')

                            mlines = [
                                '1. Map it to the USB port it\'s plugged in to'
                                '\n\tAnytime a {} {} tty device is plugged into the port it\n\tis currently plugged into it will '
                                'adopt the {} alias'.format(
                                    _tty['id_vendor_from_database'], _tty['id_model_from_database'], to_name),
                                '2. Map it by vedor ({0}) and model ({1}) alone.'
                                '\n\tThis will only work if this is the only {0} {1} adapter you plan to plug in'.format(
                                    _tty['id_vendor_from_database'], _tty['id_model_from_database'])
                                # 'Temporary mapping' \
                                # '\n\tnaming will only persist during this menu session\n'
                            ]
                            print(self.menu.format_subhead(mlines))
                            print('\n b. back (abort rename)\n')
                            valid_ch = {
                                '1': 'by_path',
                                '2': 'by_id'
                            }
                            valid = False
                            ch = ''
                            while not valid:
                                print(' Please Select an option')
                                ch = self.wait_for_input()
                                if ch.lower == 'b':
                                    log.show(f'Rename {from_name} --> {to_name} Aborted')
                                    return
                                elif ch.lower in valid_ch:
                                    valid = True
                                else:
                                    print('invalid choice {} Try Again.'.format(ch.orig))

                            udev_line = None
                            if valid_ch[ch.lower] == 'temp':
                                error = True
                                print('The Temporary rename feature is not yet implemented')
                            elif valid_ch[ch.lower] == 'by_path':
                                udev_line = (
                                    'ATTRS{{idVendor}}=="{0}", ATTRS{{idProduct}}=="{1}", GOTO="{0}_{1}"'.format(  # NoQA
                                        id_vendorid, id_prod), 'ATTRS{{devpath}}=="{}", ENV{{ID_USB_INTERFACE_NUM}}=="{}", '\
                                                               'SYMLINK+="{}"'.format(lame_devpath, id_ifnum, to_name),
                                )
                            elif valid_ch[ch.lower] == 'by_id':
                                udev_line = (
                                    'SUBSYSTEM=="tty", ATTRS{{idVendor}}=="{0}", ATTRS{{idProduct}}=="{1}", GOTO="{0}_{1}"'.format(  # NoQA
                                        id_vendorid, id_prod),
                                    'ENV{{ID_USB_INTERFACE_NUM}}=="{}", SYMLINK+="{}", GOTO="END"'.format(id_ifnum, to_name)  # NoQA
                                )
                            else:
                                error = ['Unable to add udev rule adapter missing details', 'idVendor={}, idProduct={}, serial#={}'.format(  # NoQA
                                    id_vendorid, id_prod, id_serial)]

                            while udev_line:
                                error = self.add_to_udev(udev_line[0], '# END BYPATH-POINTERS')
                                error = self.add_to_udev(udev_line[1], '# END BYPATH-DEVS', label='{}_{}'.format(id_vendorid, id_prod))  # NoQA
                                error = self.do_ser2net_line(from_name=from_name, to_name=to_name, baud=baud, dbits=dbits,
                                                             parity=parity, flow=flow)
                                break
                    else:
                        log.error(f'Device {from_name} No Longer Found', show=True)

            # TODO simplify once ser2net existing verified
            else:   # renaming previously named port.
                # -- // local ttyAMA adapters \\ --
                devname = local.adapters[f'/dev/{from_name}']['udev'].get('devname', '')
                rules_file = self.rules_file if 'ttyAMA' not in devname else self.ttyama_rules_file

                cmd = 'sudo sed -i "s/{0}{3}/{1}{3}/g" {2} && grep -q "{1}{3}" {2} && [ $(grep -c "{0}{3}" {2}) -eq 0 ]'.format(
                    from_name,
                    to_name,
                    rules_file,
                    ''
                )
                error = utils.do_shell_cmd(cmd, shell=True)
                if not error:
                    error = self.do_ser2net_line(from_name=from_name, to_name=to_name, baud=baud, dbits=dbits,
                                                 parity=parity, flow=flow)
                else:
                    return [error.split('\n'), 'Failed to change {} --> {} in {}'.format(from_name, to_name, config.ser2net_file)]

            if error:
                log.error(error, show=True)
            else:
                # Update adapter variables with new_name
                local.adapters[f'/dev/{to_name}'] = local.adapters[f'/dev/{from_name}']
                local.adapters[f'/dev/{to_name}']['config']['port'] = config.ser2net_conf[f'/dev/{to_name}'].get('port', 0)
                local.adapters[f'/dev/{to_name}']['config']['cmd'] = config.ser2net_conf[f'/dev/{to_name}'].get('cmd')
                local.adapters[f'/dev/{to_name}']['config']['line'] = config.ser2net_conf[f'/dev/{to_name}'].get('line')
                local.adapters[f'/dev/{to_name}']['config']['log'] = config.ser2net_conf[f'/dev/{to_name}'].get('log')
                local.adapters[f'/dev/{to_name}']['config']['log_ptr'] = config.ser2net_conf[f'/dev/{to_name}'].get('log_ptr')
                _config_dict = local.adapters[f'/dev/{to_name}']['config']
                if not use_def:  # overwrite con settings if they were changed
                    updates = {
                        'baud': baud,
                        'dbits': dbits,
                        'flow': flow,
                        'parity': parity,
                        'sbits': sbits,
                    }
                    local.adapters[f'/dev/{to_name}']['config'] = {**_config_dict, **updates}

                if from_name != to_name:  # facilitates changing con settings without actually renaming
                    del local.adapters[f'/dev/{from_name}']

                self.udev_pending = True    # toggle for exit function if they exit directly from rename memu

                # update first item in first section of menu_body menu uses it to determine if section is a continuation
                try:
                    self.cur_menu.body_in[0][0] = self.cur_menu.body_in[0][0].replace(from_name, to_name)
                    if self.menu.body_in is not None:  # Can be none when called via rename directly
                        self.menu.body_in[0][0] = self.menu.body_in[0][0].replace(from_name, to_name)
                except Exception as e:
                    log.exception(f"[DEV NOTE menu_body update after rename caused exception.\n{e}", show=False)

        else:
            return 'Aborted based on user input'
    # --- // END MONSTER RENAME METHOD \\ ---

    def do_ser2net_line(self, from_name: str = None, to_name: str = None, baud: int = None,
                        dbits: int = None, parity: str = None,
                        flow: str = None, sbits: int = None):
        '''Process Adapter Configuration Changes in ser2net.conf.

        Keyword Arguments:
            from_name {str} -- The Adapters existing name/alias (default: {None})
            to_name {str} -- The Adapters new name/alias (default: {None})
            baud {int} -- Adapter baud (default: {self.baud})
            dbits {int} -- Adapter databits (default: {self.data_bits})
            parity {str} -- Adapter Parity (default: {self.parity})
            flow {str} -- Adapter flow (default: {self.flow})
            sbits {int} -- Adapter stop bits (default: {self.sbits})

        Returns:
            {str|None} -- Returns error text if an error occurs or None if no issues.
        '''
        # TODO add rename support for ser2net.yaml (v4)
        # don't add the new entry to ser2net if one already exists for the alias
        if from_name != to_name and config.ser2net_conf.get(f"/dev/{to_name}"):
            log.info(f"ser2net: {to_name} already mapped to port {config.ser2net_conf[f'/dev/{to_name}'].get('port')}", show=True)
            return

        ser2net_parity = {
            'n': 'NONE',
            'e': 'EVEN',
            'o': 'ODD'
        }
        ser2net_flow = {
            'n': '',
            'x': ' XONXOFF',
            'h': ' RTSCTS'
        }
        baud = self.baud if not baud else baud
        dbits = self.data_bits if not dbits else dbits
        parity = self.parity if not parity else parity
        flow = self.flow if not flow else flow
        sbits = self.sbits if not sbits else sbits
        log_ptr = ''

        cur_line = config.ser2net_conf.get(f'/dev/{from_name}', {}).get('line')
        # TODO shouldn't  this include /dev/ttyAMA ??? the on-board ttl?
        if cur_line and '/dev/ttyUSB' not in cur_line and '/dev/ttyACM' not in cur_line and '/dev/ttySC' not in cur_line:
            new_entry = False
            if config.ser2net_file.suffix in [".yaml", ".yml"]:
                next_port = int(yaml.safe_load(cur_line.replace(": *", ": REF_"))["connection"].get("accepter").split(",")[-1])
            else:
                next_port = cur_line.split(':')[0]  # Renaming existing
            log_ptr = config.ser2net_conf[f'/dev/{from_name}'].get('log_ptr')
            if not log_ptr:
                log_ptr = ''
        else:
            new_entry = True
            if utils.valid_file(config.ser2net_file):
                ports = [v['port'] for k, v in config.ser2net_conf.items() if not k.startswith("_") and 7000 < v.get('port', 0) <= 7999]
                next_port = 7001 if not ports else int(max(ports)) + 1
            else:
                next_port = 7001
                error = utils.do_shell_cmd(f'sudo cp {config.ser2net_file} /etc/', handle_errors=False)
                if error:
                    log.error(f'Rename Menu Error while attempting to cp ser2net.conf from src {error}', show=True)
                    return error  # error added to display in calling method

        if config.ser2net_file.suffix in [".yaml", ".yml"]:
            ser2net_line = f"""connection: &{to_name}
  accepter: telnet(rfc2217),tcp,{next_port}
  connector: serialdev,/dev/{to_name},{baud}{parity}{dbits}{sbits},local{'' if flow == 'n' else ',' + ser2net_flow[flow].lower()}
  enable: on
  options:
    banner: *banner
    kickolduser: true
    telnet-brk-on-sync: true
"""
            # if flow != "n":
            #     ser2net_line = ser2net_line.rstrip("\n")
            #     ser2net_line = f'{ser2net_line},\n            {ser2net_flow[flow].lower()}\n'
        else:
            ser2net_line = (
                '{telnet_port}:telnet:0:/dev/{alias}:{baud} {dbits}DATABITS {parity} {sbits}STOPBIT {flow} banner {log_ptr}'.format(
                    telnet_port=next_port,
                    alias=to_name,
                    baud=baud,
                    dbits=dbits,
                    sbits=sbits,
                    parity=ser2net_parity[parity],
                    flow=ser2net_flow[flow],
                    log_ptr=log_ptr
                )
            )

        # -- // Append to ser2net config \\ --
        if new_entry:
            error = utils.append_to_file(config.ser2net_file, ser2net_line)
        # -- // Rename Existing Definition in ser2net.conf \\ --
        # -- for devices with existing definitions cur_line is the existing line
        elif config.ser2net_file.suffix in [".yaml", ".yml"]:
            # sudo sed -i 's|^connection: &delme1$|connection: \&test1|g'  /etc/ser2net.yaml
            # sudo sed -i 's|^  connector: serialdev,/dev/orange1|  connector: serialdev,/dev/delme1|g'  /etc/ser2net.yaml
            if not cur_line:
                return f'cur_line has no value.  Leaving {config.ser2net_file} unchanged.'
            connection_line = cur_line.splitlines()[0]
            connector_line = [line for line in cur_line.splitlines() if "connector:" in line and f'/dev/{from_name},' in line.replace("\\/", "/")]
            if connector_line:
                if len(connector_line) > 1:
                    error = f'Found {len(connector_line)} lines in {config.ser2net_file} with /dev/{from_name} defined.  Expected 1.  Aborting'
                elif "connection:" not in connection_line:
                    error = f'Unexpected connection line {connection_line} extracted for /dev/{from_name} from {config.ser2net_file}'
                else:
                    new_connection_line = connection_line.replace(f'&{from_name}', f'\&{to_name}')  # NoQA
                    connector_line = connector_line[0]
                    new_connector_line = connector_line.replace(f"/dev/{from_name},", f"/dev/{to_name},")
                    expected_complete_connector_line = f"  connector: serialdev,/dev/{to_name},{baud}{parity}{dbits}{sbits},local{'' if flow == 'n' else ',' + ser2net_flow[flow].lower()}"
                    if new_connector_line != expected_complete_connector_line:
                        if "local" in new_connector_line:
                            new_connector_line = expected_complete_connector_line
                        else:
                            return f'rename requires all serial settings be on the same line i.e. {expected_complete_connector_line}.'
                    cmds = [
                        f"sudo sed -i 's|^{connection_line}$|{new_connection_line}|g'  {config.ser2net_file}",
                        f"sudo sed -i 's|^{connector_line}$|{new_connector_line}|g'  {config.ser2net_file}"
                    ]
                    for cmd in cmds:
                        error = utils.do_shell_cmd(cmd, shell=True)
                        if error:
                            break
        else:
            ser2net_line = ser2net_line.strip().replace('/', r'\/')
            cur_line = cur_line.replace('/', r'\/')
            cmd = "sudo sed -i 's/^{}$/{}/'  {}".format(
                cur_line, ser2net_line, config.ser2net_file
            )
            error = utils.do_shell_cmd(cmd, shell=True)

        if not error:
            config.ser2net_conf = config.get_ser2net()
        else:
            return error

    def add_to_udev(self, udev_line: str, section_marker: str, label: str = None):
        '''Add or edit udev rules file with new symlink after adapter rename.

        Arguments:
            udev_line {str} -- The properly formatted udev line being added to the file
            section_marker {str} -- Match text used to determine where to place the line


        Keyword Arguments:
            label {str} -- The rules file GOTO label used in some scenarios
                           (i.e. multi-port 1 serial) (default: {None})

        Returns:
            {str|None} -- Returns error string if an error occurs
        '''
        found = ser_label_exists = get_next = update_file = alias_found = False  # NoQA
        # alias_name = udev_line.split("SYMLINK+=")[1].split(",")[0].replace('"', "")  # TODO WIP add log when alias is already associated with diff serial
        goto = line = cmd = ''  # init
        rules_file = self.rules_file  # if 'ttyAMA' not in udev_line else self.ttyama_rules_file  Testing 1 rules file
        if utils.valid_file(rules_file):
            with open(rules_file) as x:
                for line in x:
                    # temporary for those that have the original file
                    if 'ID_SERIAL' in line and 'IMPORT' not in line:
                        _old = 'ENV{ID_SERIAL}=="", GOTO="BYPATH-POINTERS"'
                        _new = 'ENV{ID_SERIAL_SHORT}=="", IMPORT{builtin}="path_id", GOTO="BYPATH-POINTERS"'
                        cmd = "sudo sed -i 's/{}/{}/' {}".format(_old, _new, rules_file)
                        update_file = True

                    # No longer including SUBSYSTEM in formatted udev line, redundant given logic @ top of rules file
                    if line.replace('SUBSYSTEM=="tty", ', '').strip() == udev_line.strip():
                        return  # Line is already in file Nothing to do.
                    # elif f'SYMLINK+="{alias_name}",' in line:
                    #     alias_found = True  # NoQA
                        # log.warning(f'{rules_file.split("/")[-1]} already contains an {alias_name} alias\nExisting alias {udev_line}', show=True)
                    if get_next:
                        goto = line
                        get_next = False
                    if section_marker.replace(' END', '') in line:
                        get_next = True
                    elif section_marker in line:
                        found = True
                    elif label and 'LABEL="{}"'.format(label) in line:
                        ser_label_exists = True

                last_line = line
            if update_file:
                error = utils.do_shell_cmd(cmd)
                if error:
                    log.show(error)

            goto = goto.split('GOTO=')[1].replace('"', '').strip() if 'GOTO=' in goto else None
            if goto is None:
                goto = last_line.strip().replace('LABEL=', '').replace('"', '') if 'LABEL=' in last_line else None
        else:
            error = utils.do_shell_cmd(f'sudo cp /etc/ConsolePi/src/{os.path.basename(rules_file)} /etc/udev/rules.d/')
            # TODO switch to pathlib.Path('path...').copy(src, dst)
            found = True
            goto = 'END'

        if goto and 'GOTO=' not in udev_line:
            udev_line = '{}, GOTO="{}"'.format(udev_line, goto)

        if label and not ser_label_exists:
            udev_line = 'LABEL="{}"\\n{}'.format(label, udev_line)

        # -- // UPDATE RULES FILE WITH FORMATTED LINE \\ --
        if found:
            udev_line = '{}\\n{}'.format(udev_line, section_marker)
            cmd = "sudo sed -i 's/{}/{}/' {}".format(section_marker, udev_line, rules_file)
            error = utils.do_shell_cmd(cmd, handle_errors=False)
            if error:
                return error
        else:  # Not Using new 10-ConsolePi.rules template just append to file
            if section_marker == '# END BYSERIAL-DEVS':
                return utils.append_to_file(rules_file, udev_line)
            else:  # if not by serial device the new template is required
                return 'Unable to Add Line, please use the new 10.ConsolePi.rules found in src dir and\n' \
                    'add you\'re current rules to the BYSERIAL-DEVS section.'

    def trigger_udev(self):
        '''reload/trigger udev (udevadm)

        Returns:
            No return unless there is an error.
            Returns {str} if an error occurs.
        '''
        cmd = 'sudo udevadm control --reload && sudo udevadm trigger && systemctl is-active ser2net >/dev/null 2>&1'\
              '&& sudo systemctl stop ser2net && sleep 1 && sudo systemctl start ser2net'
        error = utils.spinner('Triggering reload of udev & ser2net due to name change',
                              utils.do_shell_cmd, cmd, shell=True)
        if not error:
            self.udev_pending = False
        else:
            log.show('Failed to reload udev rules, you may need to rectify manually for adapter names to display correctly')
            log.show(f'Check /var/log/syslog for errors, the rules file ({self.rules_file}) and reattempt {cmd} manually')
            log.show(error)
