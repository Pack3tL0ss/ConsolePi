#!/etc/ConsolePi/venv/bin/python3

import threading
import time
import os
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


class ConsolePi():
    def __init__(self):
        print(__name__)
        self.error_msgs = []
        self.response = Response
        self.utils = Utils()
        self.config = Config(self)
        self.log = self.config.log
        self.local = Local(self)
        self.remotes = Remotes(self)
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

    def exec_auto_pwron(self, menu_dev):
        '''Launch auto_pwron in thread

        params:
            menu_dev:str, The tty dev user is connecting to
        '''
        print('Checking for and Powering on any outlets linked to {} in the background'.format(menu_dev.replace('/dev/', '')))
        # self.auto_pwron_thread(menu_dev) # swap to debug directly (disable thread)
        threading.Thread(target=self.auto_pwron_thread, args=(menu_dev,),
                         name='auto_pwr_on_' + menu_dev.replace('/dev/', '')).start()
        self.log.debug('[AUTO PWRON] Active Threads: {}'.format(
            [t.name for t in threading.enumerate() if t.name != 'MainThread']
            ))

    # TODO just get the outlet from the dict, and pass to power module function let it determine type etc
    def auto_pwron_thread(self, menu_dev):
        '''Ensure any outlets linked to device are powered on

        Called by consolepi_menu exec_menu function and remote_launcher (for sessions to remotes)
        when a connection initiated with adapter.  Powers any linked outlets associated with the
        adapter on.

        params:
            menu_dev:str, The tty device user is connecting to.
        Returns:
            No Return - Updates class attributes
        '''
        config = self.config
        log = self.log
        if not self.pwr_init_complete:
            if not self.wait_for_threads('init'):
                self.config.log_and_show('Timeout Waiting for Power threads', log=log.error)
        for adapter in config.outlets.get('linked', []):
            outlet = self.pwr.data.get(adapter)  # TODO need split logic for ports with new schema
            if not outlet:
                continue

            _addr = outlet['address']

            # -- // DLI web power switch Auto Power On \\ --
            if outlet['type'].lower() == 'dli':
                for p in outlet['is_on']:
                    log.debug('[Auto PwrOn] Power ON {} Linked Outlet {}:{} p{}'.format(menu_dev, outlet['type'], _addr, p))
                    if not outlet['is_on'][p]['state']:   # This is just checking what's in the dict not querying the DLI
                        r = self.pwr.pwr_toggle(outlet['type'], outlet['address'], desired_state=True, port=p)
                        if isinstance(r, bool):
                            if r:
                                threading.Thread(target=self.outlet_update, kwargs={'refresh': True,
                                                 'upd_linked': True}, name='auto_pwr_refresh_dli').start()
                        else:
                            log.warning('{} Error operating linked outlet @ {}'.format(menu_dev, outlet['address']))
                            self.error_msgs.append('Error operating linked outlet @ {}'.format(outlet['address']))

            # -- // GPIO & TASMOTA Auto Power On \\ --
            else:
                log.debug('[Auto PwrOn] Power ON {} Linked Outlet {}:{}'.format(menu_dev, outlet['type'], _addr))
                r = self.pwr.pwr_toggle(outlet['type'], outlet['address'], desired_state=True,
                                        noff=outlet['noff'] if outlet['type'].upper() == 'GPIO' else True)
                # TODO Below (first if) should never happen fail-safe after refactoring the returns from power.py
                # Can eventually remove
                if not isinstance(r, bool) and isinstance(r, int) and r <= 1:
                    self.error_msgs.append('the return from {} {} was an int({})'.format(
                        outlet['type'], outlet['address'], r
                    ))
                elif isinstance(r, int) and r > 1:  # return is an error
                    r = False
                else:   # return is bool which is what we expect
                    if r:
                        self.pwr.outlet_data['linked'][outlet['key']]['state'] = r
                        self.outlets = self.pwr.outlet_data['linked']
                        self.pwr.pwr_get_outlets(upd_linked=True)
                    else:
                        self.error_msgs.append('Error operating linked outlet @ {}'.format(outlet['address']))
                        log.warning('{} Error operating linked outlet @ {}'.format(menu_dev, outlet['address']))

    def wait_for_threads(self, name='init', timeout=8, thread_type='power'):
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
                    self.pwr_init_complete = True
                if do_log:
                    log.info('[{0} {1} WAIT] {0} Threads have Completed, elapsed time: {2}'.format(
                        name.strip('_').upper(), thread_type.upper(), time.time() - start))
                break
            elif time.time() - start > timeout:
                log.error('[{0} {1} WAIT] Timeout Waiting for {0} Threads to Complete, elapsed time: {2}'.format(
                    name.strip('_').upper(), thread_type.upper(), time.time() - start))
                return True

    def launch_shell(self):
        iam = self.config.loc_user
        # pylint:disable=anomalous-backslash-in-string
        os.system('sudo -u {0} echo PS1=\\"consolepi-menu:\\\w\\\$ \\" >/tmp/prompt && '  # NoQA
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
        loc_home = os.getenv('HOME')
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
    # cmd = 'sudo -u pi ssh -t pi@10.0.30.111'
    # p, e = cpi.do_shell_cmd(cmd)
    # p.stderr
    # print('\n\n')
    # e
    cpi.utils.json_print(cpi.local)
    # print(cpi.cfg_yml['CONFIG'].get('cloud'))
