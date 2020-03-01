#!/etc/ConsolePi/venv/bin/python3

import re
from halo import Halo


class Rename():
    def __init__(self):
        print(__name__)
        self.udev_pending = False
        self.baud = self.cpi.config.default_baud
        self.data_bits = self.cpi.config.default_dbits
        self.parity = self.cpi.config.default_parity
        self.flow = self.cpi.config.default_flow
        self.parity_pretty = {'o': 'Odd', 'e': 'Even', 'n': 'No'}
        self.flow_pretty = {'x': 'Xon/Xoff', 'h': 'RTS/CTS', 'n': 'No'}

# --- // START MONSTER RENAME FUNCTION \\ --- # TODO maybe break this up a bit
    def do_rename_adapter(self, from_name):
        '''Rename USB to Serial Adapter

        Creates new or edits existing udev rules and ser2net conf
        for USB to serial adapters detected by the system.

        params:
        from_name(str): Devices current name passed in from rename_menu()

        returns:
        None type if no error, or Error (str) if Error occured
        '''
        from_name = from_name.replace('/dev/', '')
        local = self.cpi.local
        config = self.cpi.config
        utils = self.cpi.utils
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
                to_name = input(' [rename {}]: Provide desired name: '.format(c_from_name))
            to_name = to_name.replace('/dev/', '')  # strip /dev/ if they thought they needed to include it
            to_name = to_name.replace(' ', '_')  # replace any spaces with _ as not allowed (udev rule symlink)
        except (KeyboardInterrupt, EOFError):
            return 'Rename Aborted based on User Input'
        c_to_name = '{}{}{}'.format(c['green'], to_name, c['norm'])

        if utils.user_input_bool(' Please Confirm Rename {} --> {}'.format(c_from_name, c_to_name)):
            for i in local.adapters:
                if i == '/dev/{}'.format(from_name):
                    break
            _dev = local.adapters[i].get('config')  # dict
            baud = _dev['baud']
            dbits = _dev['dbits']
            flow = _dev['flow']
            parity = _dev['parity']
            word = 'Use default' if 'ttyUSB' in from_name or 'ttyACM' in from_name else 'Keep existing'

            # -- // Ask user if they want to update connection settings \\ --
            use_def = utils.user_input_bool(' {} connection values [{} {}{}1 Flow: {}]'.format(
                word, baud, dbits, parity.upper(), self.flow_pretty[flow]))
            if not use_def:
                self.con_menu(rename=True, con_dict={'baud': baud, 'data_bits': dbits, 'parity': parity, 'flow': flow})
                baud = self.baud
                parity = self.parity
                dbits = self.data_bits
                parity = self.parity
                flow = self.flow
            # if not use_def:
            #     con_settings = self.con_menu(rename=True)
            #     print(con_settings)

            # restore defaults back to class attribute if we flipped them when we called con_menu
            if hasattr(self, 'con_dict') and self.con_dict:
                self.baud = self.con_dict['baud']
                self.data_bits = self.con_dict['data_bits']
                self.parity = self.con_dict['parity']
                self.flow = self.con_dict['flow']
                self.con_dict = None

            if 'ttyUSB' in from_name or 'ttyACM' in from_name:
                devs = local.detect_adapters()
                if f'/dev/{from_name}' in devs:
                    _tty = devs[from_name]
                    id_prod = _tty['id_model_id']
                    id_model = _tty['id_model']  # NoQA pylint: disable=unused-variable
                    id_vendorid = _tty['id_vendor_id']
                    id_vendor = _tty['id_vendor']  # NoQA pylint: disable=unused-variable
                    id_serial = _tty['id_serial_short']
                    id_ifnum = _tty['id_ifnum']
                    id_path = _tty['id_path']
                    root_dev = _tty['root_dev']
                else:
                    return 'ERROR: Adapter no longer found'

                if not root_dev:
                    return 'Did you really create an alias with "ttyUSB" or "ttyACM" in it (same as root devices)?\n\t' \
                           'Rename failed cause you\'re silly'

                # -- // ADAPTERS WITH ALL ATTRIBUTES \\ --
                if id_prod and id_serial and id_vendorid:
                    if id_serial not in devs['_dup_ser']:
                        udev_line = ('SUBSYSTEM=="tty", ATTRS{{idVendor}}=="{}", ATTRS{{idProduct}}=="{}", '
                                     'ATTRS{{serial}}=="{}", SYMLINK+="{}"'.format(
                                        id_vendorid, id_prod, id_serial, to_name))

                        error = None
                        while not error:
                            error = self.add_to_udev(udev_line, '# END BYSERIAL-DEVS')
                            error = self.do_ser2net_line(to_name=to_name, baud=baud, dbits=dbits, parity=parity, flow=flow)
                            break

                    # -- // MULTI-PORT ADAPTERS WITH COMMON SERIAL (different ifnums) \\ --
                    else:
                        # SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6011", ATTRS{serial}=="FT4213OP", GOTO="FT4213OP"  # NoQA
                        udev_line = ('SUBSYSTEM=="tty", ATTRS{{idVendor}}=="{0}", ATTRS{{idProduct}}=="{1}", '
                                     'ATTRS{{serial}}=="{2}", GOTO="{2}"'.format(
                                      id_vendorid, id_prod, id_serial))

                        error = None
                        while not error:
                            error = self.add_to_udev(udev_line, '# END BYPORT-POINTERS')
                            # ENV{ID_USB_INTERFACE_NUM}=="00", SYMLINK+="FT4232H_port1", GOTO="END"
                            udev_line = ('ENV{{ID_USB_INTERFACE_NUM}}=="{}", SYMLINK+="{}"'.format(
                                    id_ifnum, to_name))
                            error = self.add_to_udev(udev_line, '# END BYPORT-DEVS', label=id_serial)
                            error = self.do_ser2net_line(to_name=to_name, baud=baud, dbits=dbits, parity=parity, flow=flow)
                            break

                # -- // LAME ADAPTERS NO SERIAL NUM (map usb port) \\ --
                else:
                    config.log.warning('[ADD ADAPTER] Lame adapter missing key detail: idVendor={}, idProduct={}, serial#={}'.format(  # NoQA
                                id_vendorid, id_prod, id_serial))
                    print('\n\n This Device Does not present a serial # (LAME!).  So the adapter itself can\'t be uniquely '
                          'identified.\n There are 2 options for naming this device:')

                    mlines = [
                        'Map it to the USB port it\'s plugged in to'
                        '\n\tAnytime a {} {} tty device is plugged into the port it\n\tis currently plugged into it will adopt '
                        'the {} alias'.format(
                            _tty['id_vendor_from_database'], _tty['id_model_from_database'], to_name),
                        'Map it by vedor ({0}) and model ({1}) alone.'
                        '\n\tThis will only work if this is the only {0} {1} adapter you plan to plug in'.format(
                            _tty['id_vendor_from_database'], _tty['id_model_from_database'])
                        # 'Temporary mapping' \
                        # '\n\tnaming will only persist during this menu session\n'
                    ]
                    self.menu_formatting('body', text=mlines)
                    print('\n b. back (abort rename)\n')
                    valid_ch = {
                        '1': 'by_path',
                        '2': 'by_id'
                    }
                    valid = False
                    while not valid:
                        print(' Please Select an option')
                        ch = self.wait_for_input(lower=True)
                        if ch == 'b':
                            return
                        elif ch in valid_ch:
                            # _path = valid_ch[ch]
                            valid = True
                        else:
                            print('invalid choice {} Try Again.'.format(ch))

                    udev_line = None
                    if valid_ch[ch] == 'temp':
                        error = True
                        print('The Temporary rename feature is not yet implemented')
                        pass  # by not setting an error the name will be updated below
                    elif valid_ch[ch] == 'by_path':
                        udev_line = (
                            'SUBSYSTEM=="tty", ATTRS{{idVendor}}=="{0}", ATTRS{{idProduct}}=="{1}", GOTO="{0}_{1}"'.format(
                                id_vendorid, id_prod), 'ENV{{ID_PATH}}=="{}", SYMLINK+="{}"'.format(id_path, to_name),
                        )
                    elif valid_ch[ch] == 'by_id':
                        udev_line = (
                            'SUBSYSTEM=="tty", ATTRS{{idVendor}}=="{0}", ATTRS{{idProduct}}=="{1}", GOTO="{0}_{1}"'.format(
                                id_vendorid, id_prod),
                            'ENV{{ID_USB_INTERFACE_NUM}}=="{}", SYMLINK+="{}", GOTO="END"'.format(_tty['id_ifnum'], to_name)
                        )
                    else:
                        error = ['Unable to add udev rule adapter missing details', 'idVendor={}, idProduct={}, serial#={}'.format(  # NoQA
                            id_vendorid, id_prod, id_serial)]

                    while udev_line:
                        error = self.add_to_udev(udev_line[0], '# END BYPATH-POINTERS')
                        error = self.add_to_udev(udev_line[1], '# END BYPATH-DEVS', label='{}_{}'.format(id_vendorid, id_prod))
                        error = self.do_ser2net_line(to_name=to_name, baud=baud, dbits=dbits, parity=parity, flow=flow)
                        break

            # TODO simplify once ser2net existing verified
            else:   # renaming previously named port.
                rules_file = config.static.get('RULES_FILE', '/etc/udev/rules.d/10-ConsolePi.rules')
                ser2net_file = config.static.get('SER2NET_FILE', '/etc/ser2net.conf')
                # cmd = 'sudo sed -i "s/{0}/{1}/g" {2} && grep -q "{1}" {2} && [ $(grep -c "{0}" {2}) -eq 0 ]'.format(  # NoQA
                #     from_name,
                #     to_name,
                #     rules_file
                #     )
                cmd = 'sudo sed -i "s/{0}{3}/{1}{3}/g" {2} && grep -q "{1}{3}" {2} && [ $(grep -c "{0}{3}" {2}) -eq 0 ]'.format(
                    from_name,
                    to_name,
                    rules_file,
                    ''
                    )
                # error = bash_command(cmd)
                error = utils.do_shell_cmd(cmd)
                if not error:
                    error = self.do_ser2net_line(to_name=to_name, baud=baud, dbits=dbits, parity=parity, flow=flow,
                                                 existing=True, match_txt='{}:'.format(from_name))
                if error:
                    return [error.split('\n'), 'Failed to change {} --> {} in {}'.format(from_name, to_name, ser2net_file)]

            if not error:
                # Update adapter variables with new_name
                local.adapters[f'/dev/{to_name}'] = local.adapters[f'/dev/{from_name}']
                _config_dict = local.adapters[f'/dev/{to_name}']['config']
                if not use_def:  # overwrite con settings if they were changed
                    updates = {
                        'baud': baud,
                        'dbits': dbits,
                        'flow': flow,
                        'parity': parity
                        }
                    local.adapters[f'/dev/{to_name}']['config'] = {**_config_dict, **updates}
                if from_name != to_name:  # facilitates changing con settings without actually renaming
                    del local.adapters[f'/dev/{from_name}']
                self.udev_pending = True    # toggle for exit function if they exit directly from rename memu

        else:
            return 'Aborted based on user input'
# --- // END MONSTER RENAME FUNCTION \\ ---

    def do_ser2net_line(self, to_name=None, baud=None, dbits=None, parity=None,
                        flow=None, existing=False, match_txt=None):
        '''Process Adapter Configuration Changes in ser2net.conf.

        Keyword Arguments:
            to_name {str} -- The Adapters new name/alias (default: {None})
            baud {int} -- Adapter baud (default: {self.baud})
            dbits {int} -- Adapter databits (default: {self.data_bits})
            parity {str} -- Adapter Parity (default: {self.parity})
            flow {str} -- Adapter flow (default: {self.flow})
            existing {bool} -- False(default): Adapter currently has no symlink (root dev), True: Renaming existing symlink
            match_txt {str} --  Used for existing adapters to find the line with the previous symlink entry (default: {None})

        Returns:
            {str|None} -- Returns error text if an error occurs or None if no issues.
        '''
        cpi = self.cpi
        config = cpi.config
        utils = cpi.utils
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
        parity = ser2net_parity[parity]
        flow = ser2net_flow[flow]
        # TODO Now have ser2net config stored in dict, use it vs. parsing file again
        ser2net_file = config.static.get('SER2NET_FILE')
        if utils.valid_file(ser2net_file):
            if not existing:
                ports = [re.findall(r'^(7[0-9]{3}):telnet', line) for line in open(ser2net_file)
                         if line.startswith('7')]
                if ports:
                    next_port = int(max(ports)[0]) + 1
                else:
                    next_port = '7001'
            else:
                ports = [line.split(':')[0] for line in open(ser2net_file)
                         if line.startswith('7') and match_txt in line]
                if len(ports) > 1:
                    cpi.error_msgs.append('multilple lines found in ser2net matching {}'.format(match_txt))
                    cpi.error_msgs.append('Update Failed, verify {}'.format(ser2net_file))
                    return
                else:
                    next_port = ports[0]  # it's the existing port in this case
        else:
            # res = bash_command('sudo cp /etc/ConsolePi/src/ser2net.conf /etc/', eval_errors=False)
            res = utils.do_shell_cmd('sudo cp /etc/ConsolePi/src/ser2net.conf /etc/', handle_errors=False)
            next_port = '7001'  # added here looks like flawed logic below
            if res:
                return res
            else:  # TODO this logic looks flawed
                next_port = '7001'

        ser2net_line = ('{telnet_port}:telnet:0:/dev/{alias}:{baud} {dbits}DATABITS {parity} 1STOPBIT {flow} banner'.format(
                        telnet_port=next_port,
                        alias=to_name,
                        baud=baud,
                        dbits=dbits,
                        parity=parity,
                        flow=flow))

        if not existing:
            utils.append_to_file(ser2net_file, ser2net_line)  # pylint: disable=maybe-no-member
        else:
            ser2net_line = ser2net_line.replace('/', r'\/')
            cmd = "sudo sed -i 's/.*{}.*/{}/'  {}".format(
                        match_txt, ser2net_line, ser2net_file)  # pylint: disable=maybe-no-member

            # return bash_command(cmd)
            return utils.do_shell_cmd(cmd)

    def add_to_udev(self, udev_line, section_marker, label=None):
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
        cpi = self.cpi
        config = cpi.config
        utils = cpi.utils
        found = ser_label_exists = get_next = update_file = False  # init
        goto = ''  # init
        rules_file = config.serial.get('RULES_FILE')
        if utils.valid_file(rules_file):   # pylint: disable=maybe-no-member
            with open(rules_file) as x:  # pylint: disable=maybe-no-member
                for line in x:
                    # temporary for those that have the original file
                    if 'ID_SERIAL' in line and 'IMPORT' not in line:
                        _old = 'ENV{ID_SERIAL}=="", GOTO="BYPATH-POINTERS"'
                        _new = 'ENV{ID_SERIAL_SHORT}=="", IMPORT{builtin}="path_id", GOTO="BYPATH-POINTERS"'
                        cmd = "sed -i 's/{}/{}/' {}".format(_old, _new, rules_file)  # pylint: disable=maybe-no-member
                        update_file = True
                    if line.strip() == udev_line.strip():
                        return  # Line is already in file Nothing to do.
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
                    cpi.error_msgs.append(error)

            goto = goto.split('GOTO=')[1].replace('"', '').strip() if 'GOTO=' in goto else None
            if goto is None:
                goto = last_line.strip().replace('LABEL=', '').replace('"', '') if 'LABEL=' in last_line else None
        else:
            error = utils.do_shell_cmd('sudo cp /etc/ConsolePi/src/10-ConsolePi.rules /etc/udev/rules.d/')
            found = True
            goto = 'END'

        if goto and 'GOTO=' not in udev_line:
            udev_line = '{}, GOTO="{}"'.format(udev_line, goto)

        if label and not ser_label_exists:
            udev_line = 'LABEL="{}"\\n{}'.format(label, udev_line)

        # -- // UPDATE RULES FILE WITH FORMATTED LINE \\ --
        if found:
            udev_line = '{}\\n{}'.format(udev_line, section_marker)
            cmd = "sed -i 's/{}/{}/' {}".format(section_marker, udev_line, rules_file)
            error = utils.do_shell_cmd(cmd, eval_errors=False)
            if error:
                return error
        else:  # Not Using new 10-ConsolePi.rules template just append to file
            if section_marker == '# END BYSERIAL-DEVS':
                utils.append_to_file(rules_file, udev_line)  # pylint: disable=maybe-no-member
            else:  # if not by serial device the new template is required
                return 'Unable to Add Line, please use the new 10.ConsolePi.rules found in src dir and\n' \
                    'add you\'re current rules to the BYSERIAL-DEVS section.'

    def trigger_udev(self):
        utils = self.cpi.utils
        cmd = 'sudo udevadm control --reload && sudo udevadm trigger && sudo systemctl stop ser2net && sleep 1 && sudo systemctl start ser2net '  # NoQA
        with Halo(text='Triggering reload of udev do to name change', spinner='dots1'):
            # error = bash_command(cmd)
            error = utils.do_shell_cmd(cmd)
        if not error:
            self.udev_pending = False
        else:
            return error
