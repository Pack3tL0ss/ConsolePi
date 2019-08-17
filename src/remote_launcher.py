#!/etc/ConsolePi/venv/bin/python3

import psutil
import sys
import subprocess
from time import sleep

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

if len(sys.argv) >= 3:
    # _cmd = (' '.join(sys.argv[1:]))
    _cmd = sys.argv[1:]
    ppid = find_procs_by_name(sys.argv[1], sys.argv[2])
    retry = 0
    while ppid is not None and retry < 3:
        print('An Existing session is already established to {}.  Terminating that session'.format(sys.argv[2].replace('/dev/', '')))
        terminate_process(ppid)
        sleep(1)
        ppid = find_procs_by_name(sys.argv[1], sys.argv[2])
    
    subprocess.run(_cmd)
