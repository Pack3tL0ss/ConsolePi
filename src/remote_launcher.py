#!/etc/ConsolePi/venv/bin/python3

import psutil
import sys
import subprocess
from time import sleep
from consolepi.common import user_input_bool
from consolepi.common import ConsolePi_data
from consolepi.power import Outlets

config = ConsolePi_data(do_print=False)
power = Outlets()

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
                    sleep(1)
                    ppid = find_procs_by_name(sys.argv[1], sys.argv[2])
                except PermissionError:
                    print('This appears to be a locally established session, if you want to kill that do it yourself')
                    break
                except psutil.AccessDenied:
                    print('This appears to be a locally established session, session will not be terminated')
                    break
        
        if ppid is None:
            # if power feature enabled and adapter linked - ensure outlet is on
            if config.power:  # pylint: disable=maybe-no-member
                for dev in config.local[config.hostname]['adapters']:
                    if dev['dev'] == sys.argv[2]:
                        outlet = None if 'outlet' not in dev else dev['outlet']
                        if outlet is not None and isinstance(outlet['is_on'], int) and outlet['is_on'] <= 1:
                            desired_state = 'on' if outlet['noff'] else 'off' # TODO Move noff logic to power.py
                            print('Ensuring ' + sys.argv[2] + ' is Powered On')
                            r = power.do_toggle(outlet['type'], outlet['address'], desired_state=desired_state)
                            if isinstance(r, int) and r > 1:
                                print('Error operating linked outlet @ {}'.format(outlet['address']))
                                config.log.warning('[REMOTE LAUNCHER] {} Error operating linked outlet @ {}'.format(sys.argv[2], outlet['address']))
                        break
            # -- // Connect \\ --
            subprocess.run(_cmd)