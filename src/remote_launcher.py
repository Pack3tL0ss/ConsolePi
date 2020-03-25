#!/etc/ConsolePi/venv/bin/python3

'''
argv1 is the process menu currently uses picocom
argv2 is the device
'''

import psutil
import sys
import subprocess
from time import sleep
sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import config, utils  # NoQA
from consolepi.consolepi import ConsolePi  # NoQA
cpi = ConsolePi(bypass_remotes=True)
# from consolepi.common import user_input_bool
# from consolepi.common import ConsolePi_data

# config = ConsolePi_data(do_print=False)


def find_procs_by_name(name, dev):
    "Return a list of processes matching 'name'."
    ppid = None
    for p in psutil.process_iter(attrs=["name", "cmdline"]):
        if name == p.info['name'] and dev in p.info['cmdline']:
            ppid = p.pid if p.ppid() == 1 else p.ppid()
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
        _cmd = sys.argv[1:]
        ppid = find_procs_by_name(sys.argv[1], sys.argv[2])
        retry = 0
        msg = f"\n{sys.argv[2].replace('/dev/', '')} appears to be in use (may be a previous hung session)."
        msg += '\nDo you want to Terminate the existing session'
        if ppid is not None and utils.user_input_bool(msg):
            while ppid is not None and retry < 3:
                print('Terminating Existing Session...')
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
                cpi.cpiexec.exec_auto_pwron(sys.argv[2])
            subprocess.run(_cmd)
