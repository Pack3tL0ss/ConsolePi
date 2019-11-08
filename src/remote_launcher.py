#!/etc/ConsolePi/venv/bin/python3

import psutil
import sys
import subprocess
from time import sleep
from consolepi.common import user_input_bool
from consolepi.common import ConsolePi_data
# from consolepi.power import Outlets

config = ConsolePi_data(do_print=False)
# power = Outlets()

def find_procs_by_name(name, dev):
    "Return a list of processes matching 'name'."
    ppid = None
    for p in psutil.process_iter(attrs=["name", "cmdline"]):
        if name == p.info['name'] and dev in p.info['cmdline']:
            ppid = p.ppid()
    return ppid

def terminate_process(pid):
    p = psutil.Process(pid)
    x = 0
    while x < 2:
        p.terminate()
        if p.status() != 'Terminated':
            p.kill()
        else:
            break
        x += 1

if __name__ == '__main__':
    if len(sys.argv) >= 3:
        # _cmd = (' '.join(sys.argv[1:]))
        _cmd = sys.argv[1:]
        ppid = find_procs_by_name(sys.argv[1], sys.argv[2])
        retry = 0
        msg = '\n{} appears to be in use (may be a previous hung session).\nDo you want to Terminate the existing session'.format(sys.argv[2].replace('/dev/', ''))
        if ppid is not None and user_input_bool(msg):
            while ppid is not None and retry < 3:
                print('An Existing session is already established to {}.  Terminating that session'.format(sys.argv[2].replace('/dev/', '')))
                try:
                    terminate_process(ppid)
                    sleep(3)
                    ppid = find_procs_by_name(sys.argv[1], sys.argv[2])
                except PermissionError:
                    print('This appears to be a locally established session, if you want to kill that do it yourself')
                    break
                except psutil.AccessDenied:
                    print('This appears to be a locally established session, session will not be terminated')
                    break
                except psutil.NoSuchProcess:
                    ppid = find_procs_by_name(sys.argv[1], sys.argv[2])
                retry += 1
        
        if ppid is None:
            # if power feature enabled and adapter linked - ensure outlet is on
            if config.power:  # pylint: disable=maybe-no-member
                try:
                    for dev in config.local[config.hostname]['adapters']:
                        print(dev['dev'], sys.argv[2])
                        if dev['dev'] == sys.argv[2]:
                            outlet = None if 'outlet' not in dev else dev['outlet']
                            if outlet is not None:
                                desired_state = 'on'
                                # -- // DLI Auto Power On \\ --
                                if outlet['type'] == 'dli':
                                    fail = False
                                    for p in outlet['is_on']:
                                        name = outlet['is_on'][p]['name']
                                        print('Ensuring {0} mapped port ({1}: {2}) on dli {3} is Powered On'.format(
                                            sys.argv[2], p, name, outlet['address']))
                                        if not outlet['is_on'][p]['state']:
                                            r = config.pwr_toggle(outlet['type'], outlet['address'], desired_state=desired_state, port=p)
                                            if not r or not isinstance(r, bool):
                                                fail = True
                                        else:
                                            fail = None
                                    if fail:
                                        print('Error returned from dli {}'.format(outlet['address']))
                                        config.log.warning('[REMOTE LAUNCHER] {0} Error operating linked {1} {2}'.format(
                                            sys.argv[2], outlet['type'], outlet['address']))
                                # -- // GPIO & TASMOTA Auto Power On \\ --
                                else:
                                    print('Ensuring ' + sys.argv[2] + ' is Powered On')
                                    r = config.pwr_toggle(outlet['type'], outlet['address'], desired_state=desired_state,
                                        noff=outlet['noff'] if outlet['type'].upper() == 'GPIO' else True)
                                    if not r:
                                        print('Error operating linked outlet @ {}'.format(outlet['address']))
                                        config.log.warning('[REMOTE LAUNCHER] {} Error operating linked outlet @ {}'.format(sys.argv[2], outlet['address']))
                            else:
                                print('Linked Outlet @ {} returned an error during menu load. Skipping...'.format(outlet['address']))

                            break
                except Exception as e:
                    config.log.error('[REMOTE LAUNCHER] an Exception occured during Auto Power On\n{}'.format(e))
            # -- // Connect \\ --
            subprocess.run(_cmd)