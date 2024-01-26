#!/etc/ConsolePi/venv/bin/python3

import sys

sys.path.insert(0, "/etc/ConsolePi/src/pypkg")
from consolepi import config, log, utils  # type: ignore # NoQA
from consolepi.consolepi import ConsolePi  # type: ignore # NoQA
from consolepi.gdrive import GoogleDrive  # type: ignore # NoQA


def main():
    cpi = ConsolePi()
    cloud_svc = config.cfg.get("cloud_svc", "error")
    local = cpi.local
    remotes = cpi.remotes
    cpiexec = cpi.cpiexec
    log.info("[CLOUD TRIGGER (IP)]: Cloud Update triggered by IP Update")
    CLOUD_CREDS_FILE = config.static.get("CLOUD_CREDS_FILE", "/etc/ConsolePi/cloud/gdrive/.credentials/credentials.json")
    if not utils.is_reachable("www.googleapis.com", 443):
        log.error(f"Not Updating {cloud_svc} due to connection failure")
        sys.exit(1)
    if not utils.valid_file(CLOUD_CREDS_FILE):
        log.error("Credentials file not found or invalid")
        sys.exit(1)

    # -- // Get details from Google Drive - once populated will skip \\ --
    if cloud_svc == "gdrive" and remotes.cloud is None:
        remotes.cloud = GoogleDrive(hostname=local.hostname)

    if cpiexec.wait_for_threads(thread_type="remotes") and (config.power and cpiexec.wait_for_threads(name="_toggle_refresh")):
        log.error("IP Change Cloud Update Trigger: TimeOut Waiting for Threads to Complete")

    remote_consoles = remotes.cloud.update_files(local.data)
    if remote_consoles and "Gdrive-Error:" in remote_consoles:
        log.error(remote_consoles)
    else:
        for r in remote_consoles:
            # -- Convert Any Remotes with old API schema to new API schema --
            if isinstance(remote_consoles[r].get("adapters", {}), list):
                remote_consoles[r]["adapters"] = remotes.convert_adapters(remote_consoles[r]["adapters"])
                log.warning(f"Adapter data for {r} retrieved from cloud in old API format... Converted")
        if len(remote_consoles) > 0:
            remotes.update_local_cloud_file(remote_consoles)

# TODO cmd line args when called from Network Dispatcher to bypass remotes (when updating on VPN down)
# Also can probably always bypass outlets
if __name__ == "__main__":
    main()
