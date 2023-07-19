#!/etc/ConsolePi/venv/bin/python3

'''
argv1 is the process menu currently uses picocom
argv2 is the device
'''
# imports in try/except in case user aborts after ssh session established
try:
    import psutil
    import sys
    import subprocess
    import time
    sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
    from consolepi import config, utils  # type: ignore # NoQA
    from consolepi.consolepi import ConsolePi  # type: ignore # NoQA
    cpi = ConsolePi(bypass_remotes=True)
except (KeyboardInterrupt, EOFError):
    print("Operation Aborted")
    exit(0)


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


def check_hung_process(cmd: str, device: str) -> int:
    ppid = find_procs_by_name(cmd, device)
    retry = 0
    msg = f"\n{_device.replace('/dev/', '')} appears to be in use (may be a previous hung session)."
    msg += '\nDo you want to Terminate the existing session'
    if ppid is not None and utils.user_input_bool(msg):
        while ppid is not None and retry < 3:
            print('Terminating Existing Session...')
            try:
                terminate_process(ppid)
                time.sleep(3)
                ppid = find_procs_by_name(cmd, device)
            except PermissionError:
                print('This appears to be a locally established session, if you want to kill that do it yourself')
                break
            except psutil.AccessDenied:
                print('This appears to be a locally established session, session will not be terminated')
                break
            except psutil.NoSuchProcess:
                ppid = find_procs_by_name(cmd, device)
            retry += 1

    return ppid


if __name__ == '__main__':
    # Allow user to ssh to configured port which using ForceCommand and specifying only the device they want to connect to
    if len(sys.argv) == 2 and "picocom" not in sys.argv[1]:
        _device = f'/dev/{sys.argv[1].replace("/dev/", "")}'
        adapter_data = cpi.local.adapters.get(_device)
        if not adapter_data:
            print(f'{_device.replace("/dev/", "")} Not found on system... Refreshing local adapters.')
            cpi.local.build_adapter_dict(refresh=True)
            adapter_data = cpi.local.adapters.get(_device)

        if adapter_data:
            print(f'Establishing Connection to {_device.replace("/dev/", "")}...')
            _cmd = adapter_data["config"]["cmd"].replace("{{timestamp}}", time.strftime("%F_%H.%M")).split()
        else:
            print(f'{_device.replace("/dev/", "")} Not found on system... Exiting.')
            sys.exit(1)
    # Sent from menu on remote full command is sent
    elif len(sys.argv) >= 3:
        _cmd = sys.argv[1:]
        _device = f'/dev/{sys.argv[2].replace("/dev/", "")}'

    ppid = check_hung_process(_cmd[0], _device)

    if ppid is None:
        # if power feature enabled and adapter linked - ensure outlet is on
        # TODO try/except block here
        if config.power:
            cpi.cpiexec.exec_auto_pwron(_device)
        subprocess.run(_cmd)
