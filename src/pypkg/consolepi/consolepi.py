#!/etc/ConsolePi/venv/bin/python3

import threading
import time
import os
import json
import subprocess
from consolepi.power import Outlets
from consolepi import Config
from consolepi.remotes import Remotes
from consolepi.utils import Utils
# from consolepi.udevrename import Rename
from consolepi.local import Local
from collections import namedtuple


def Response(ok, text, code=None):
    res = namedtuple('Response', 'ok text code')
    return res(ok, text, code)


# TODO bypass_remotes no longer implemented re-implement or remove
class ConsolePi():
    def __init__(self, bypass_remote=False):
        self.error_msgs = []
        self.response = Response
        self.utils = Utils()
        self.config = Config(self)
        self.log = self.config.log
        self.local = Local(self)
        self.remotes = Remotes(self)
        # used to signal the need to retry connection if autopwr for ssh/telnet sessions (allow bootup)
        # changed in auto_pwron_thread
        self.autopwr_wait = False
        if self.config.cfg.get('power'):
            self.pwr_init_complete = False
            self.pwr = Outlets(self)
        else:
            self.pwr_init_complete = True

        # self.rename = Rename(self)
        # verify TELNET is installed and install if not if hosts of type TELNET are defined.
        # TODO Move to menu launch and prompt user
        if self.config.hosts:
            self.utils.verify_telnet_installed(self.config.hosts)

    def con_menu_response(self, ok, baud, dbits, parity, flow, sbits=1, error=None):
        res = namedtuple('Response', 'baud dbits parity flow sbits error')
        return res(ok, baud, dbits, parity, flow, sbits, error)

    def exec_auto_pwron(self, pwr_key):
        '''Launch auto_pwron in thread

        params:
            menu_dev:str, The tty dev user is connecting to
        '''
        pwr_key_pretty = pwr_key.replace('/dev/', '').replace('/host/', '')
        if pwr_key in self.config.outlets['linked']:  # verify against config here as pwr may not be completely init
            _msg = f"Ensuring {pwr_key_pretty} Linked Outlets ({' '.join(self.config.outlets['linked'][pwr_key])}) " \
                   "are Powered \033[1;32mON\033[0m"
            _dots = '-' * (len(_msg) + 4)
            _msg = f"\n{_dots}\n  {_msg}  \n{_dots}\n"  # TODO send to formatter in menu ... __init__
            print(_msg)
            threading.Thread(target=self.auto_pwron_thread, args=(pwr_key,),
                             name='auto_pwr_on_' + pwr_key_pretty).start()
            self.log.debug('[AUTO PWRON] Active Threads: {}'.format(
                [t.name for t in threading.enumerate() if t.name != 'MainThread']
                ))

    # TODO just get the outlet from the dict, and pass to power module function let it determine type etc
    def auto_pwron_thread(self, pwr_key):
        '''Ensure any outlets linked to device are powered on

        Called by consolepi_menu exec_menu function and remote_launcher (for sessions to remotes)
        when a connection initiated with adapter.  Powers any linked outlets associated with the
        adapter on.

        params:
            menu_dev:str, The tty device user is connecting to.
        Returns:
            No Return - Updates class attributes
        '''
        # config = self.config
        log = self.log
        if not self.pwr_init_complete:
            if self.wait_for_threads('init'):
                return

        outlets = self.pwr.data
        if 'linked' not in outlets:
            _msg = 'Error linked key not found in outlet dict\nUnable to perform auto power on'
            self.config.log_and_show(_msg, log=log.error)
            return

        if not outlets['linked'].get(pwr_key):
            return

        # -- // Perform Auto Power On (if not already on) \\ --
        for o in outlets['linked'][pwr_key]:
            outlet = outlets['defined'].get(o.split(':')[0])
            ports = [] if ':' not in o else json.loads(o.split(':')[1])
            _addr = outlet['address']

            # -- // DLI web power switch Auto Power On \\ --
            if outlet['type'].lower() == 'dli':
                for p in ports:
                    log.debug(f"[Auto PwrOn] Power ON {pwr_key} Linked Outlet {outlet['type']}:{_addr} p{p}")
                    if not outlet['is_on'][p]['state']:   # This is just checking what's in the dict not querying the DLI
                        r = self.pwr.pwr_toggle(outlet['type'], _addr, desired_state=True, port=p)
                        if isinstance(r, bool):
                            if r:
                                threading.Thread(target=self.outlet_update, kwargs={'refresh': True,
                                                 'upd_linked': True}, name='auto_pwr_refresh_dli').start()
                                self.autopwr_wait = True
                        else:
                            self.config.log_and_show(f"{pwr_key} Error operating linked outlet @ {o}", log=log.warning)

            # -- // GPIO & TASMOTA Auto Power On \\ --
            else:
                log.debug(f"[Auto PwrOn] Power ON {pwr_key} Linked Outlet {outlet['type']}:{_addr}")
                r = self.pwr.pwr_toggle(outlet['type'], _addr, desired_state=True,
                                        noff=outlet.get('noff', True) if outlet['type'].upper() == 'GPIO' else True)
                if isinstance(r, int) and r > 1:  # return is an error
                    r = False
                else:   # return is bool which is what we expect
                    if r:
                        self.pwr.data['defined'][o]['state'] = r
                        self.autopwr_wait = True
                        # self.pwr.pwr_get_outlets(upd_linked=True)
                    else:
                        self.config.log_and_show(f"Error operating linked outlet {o}:{outlet['address']}", log=log.warning)

    def exec_shell_cmd(self, cmd):
        '''Determine if cmd is valid shell cmd and execute if so.

        Command will execute as the local user unless the user used sudo -u

        Arguments:
            cmd {str} -- Input provided by user

        Returns:
            True|None -- Return True if cmd was determined to be a bash cmd
        '''
        s = subprocess
        c = cmd.replace('-u', '').replace('sudo', '').strip()
        p = 'PATH=$PATH:/etc/ConsolePi/src/consolepi-commands && '
        r = s.run(f'{p}which {c.split()[0]}', shell=True, capture_output=True)
        if r.returncode == 0:
            try:
                if 'sudo ' not in cmd:
                    cmd = f'sudo -u {self.local.user} bash -c "{p}{cmd}"'
                elif 'sudo -u ' not in cmd:
                    cmd = cmd.replace('sudo ', '')
                subprocess.run(cmd, shell=True)
            except (KeyboardInterrupt, EOFError):
                pass
            print('')
            input('Press Enter to Continue... ')
            return True

    def wait_for_threads(self, name='init', timeout=10, thread_type='power'):
        '''wait for parallel async threads to complete

        returns:
            bool: True if threads are still running indicating a timeout
                  None indicates no threads found ~ they have finished
        '''
        log = self.config.log
        start = time.time()
        do_log = False
        found = False
        while True:
            found = False
            for t in threading.enumerate():
                if name in t.name:
                    found = do_log = True
                    t.join(timeout - 1)

            if not found:
                if name == 'init' and thread_type == 'power':
                    if not self.pwr.data.get('dli_power'):
                        self.pwr.dli_exists = False
                    self.pwr_init_complete = True
                if do_log:
                    log.info('[{0} {1} WAIT] {0} Threads have Completed, elapsed time: {2}'.format(
                        name.strip('_').upper(), thread_type.upper(), time.time() - start))
                break
            elif time.time() - start > timeout:
                self.config.log_and_show('[{0} {1} WAIT] Timeout Waiting for {0} Threads to Complete, elapsed time: {2}'.format(
                    name.strip('_').upper(), thread_type.upper(), time.time() - start), log=log.error)
                return True

    def launch_shell(self):
        iam = self.config.loc_user
        os.system('sudo -u {0} echo PS1=\\"\\\033[1\;36mconsolepi-menu\\\033[0m:\\\w\\\$ \\" >/tmp/prompt && '  # NoQA
            'echo alias consolepi-menu=\\"exit\\" >>/tmp/prompt &&'
            'echo PATH=$PATH:/etc/ConsolePi/src/consolepi-commands >>/tmp/prompt && '
            'alias consolepi-menu=\\"exit\\" >>/tmp/prompt && '
            'echo "launching local shell, \'exit\' to return to menu" &&'
            'sudo -u {0} bash -rcfile /tmp/prompt ; rm /tmp/prompt'.format(iam))

    def outlet_update(self, upd_linked=False, refresh=False, key='defined', outlets=None):
        '''
        Called by consolepi-menu refresh
        '''
        config = self.config
        pwr = self.pwr
        log = self.log
        if config.power:
            outlets = pwr.data if outlets is None else outlets
            if not self.pwr_init_complete or refresh:
                _outlets = pwr.pwr_get_outlets(
                    outlet_data=outlets.get('defined', {}),
                    upd_linked=upd_linked,
                    failures=outlets.get('failures', {})
                    )
                pwr.data = _outlets
            else:
                _outlets = outlets

            if key in _outlets:
                return _outlets[key]
            else:
                msg = f'Invalid key ({key}) passed to outlet_update. Returning "defined"'
                log.error(msg)
                self.error_msgs.append(msg)
                return _outlets['defined']

    def gen_copy_key(self, rem_data=None):
        '''Generate public ssh key and distribute to remote ConsolePis

        Keyword Arguments:
            rem_data {tuple or list of tuples} -- each tuple should have 3 items
            0: hostname of remote, 1: rem_ip, 3: rem_user    (default: {None})

        Returns:
            {list} -- list of any errors reported, could be informational
        '''
        hostname = self.local.hostname
        loc_user = self.local.user
        loc_home = self.local.loc_home
        utils = self.utils

        # generate local key file if it doesn't exist
        if not os.path.isfile(loc_home + '/.ssh/id_rsa'):
            print('\n\nNo Local ssh cert found, generating...\n')
            utils.do_shell_cmd(f'sudo -u {loc_user} ssh-keygen -m pem -t rsa -C "{loc_user}@{hostname}"')

        # copy keys to remote(s)
        if not isinstance(rem_data, list):
            rem_data = [rem_data]
        return_list = []
        for _rem in rem_data:
            rem, rem_ip, rem_user = _rem
            print('\nAttempting to copy ssh cert to {}\n'.format(rem))
            ret = utils.do_shell_cmd(f'sudo -u {loc_user} ssh-copy-id {rem_user}@{rem_ip}', timeout=360)
            if ret is not None:
                return_list.append('{}: {}'.format(rem, ret))
        return return_list

    def show_adapter_details(self, adapters):
        for a in adapters:
            print(f' --- Details For {a.replace("/dev/", "")} --- ')
            for k in sorted(adapters[a]['udev'].keys()):
                print(f'{k}: {adapters[a]["udev"][k]}')
            print('')

        input('\nPress Any Key To Continue\n')


if __name__ == '__main__':
    cpi = ConsolePi()
    cpi.utils.json_print(cpi.local)
