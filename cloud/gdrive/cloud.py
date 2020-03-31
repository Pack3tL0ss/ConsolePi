#!/etc/ConsolePi/venv/bin/python3

import sys
sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import config, log  # NoQA
from consolepi.consolepi import ConsolePi  # NoQA
from consolepi.gdrive import GoogleDrive # NoQA


def main():
    cpi = ConsolePi()
    cloud_svc = config.cfg.get("cloud_svc", "error")
    local = cpi.local
    remotes = cpi.remotes
    cpiexec = cpi.cpiexec
    log.info('[CLOUD TRIGGER (IP)]: Cloud Update triggered by IP Update')

    # -- // Get details from Google Drive - once populated will skip \\ --
    if not remotes.local_only:
        if cloud_svc == "gdrive" and remotes.cloud is None:
            remotes.cloud = GoogleDrive(hostname=local.hostname)

        if cpiexec.wait_for_threads(thread_type="remotes") and (
           config.power and cpiexec.wait_for_threads(name="_toggle_refresh")):
            log.error('IP Change Cloud Update Trigger: TimeOut Waiting for Threads to Complete')

        remote_consoles = remotes.cloud.update_files(local.data)
        if "Gdrive-Error:" in remote_consoles:
            log.error(remote_consoles)
    else:
        log.error(f"Not Updating {cloud_svc} due to connection failure")


if __name__ == '__main__':
    main()
