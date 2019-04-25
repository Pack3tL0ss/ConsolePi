#!/etc/ConsolePi/venv/bin/python3

from socket import gethostname
from consolepi.common import get_config
from consolepi.common import get_if_ips
from consolepi.common import get_local
from consolepi.common import update_local_cloud_file
from consolepi.common import ConsolePi_Log
from consolepi.gdrive import GoogleDrive

DEBUG = get_config('debug')
CLOUD_SVC = get_config('cloud_svc').lower()
LOG_FILE = '/var/log/ConsolePi/cloud.log'
LOCAL_CLOUD_FILE = '/etc/ConsolePi/cloud.data'


def main():
    cpi_log = ConsolePi_Log(debug=DEBUG, log_file=LOG_FILE)
    log = cpi_log.log
    hostname = gethostname()
    if_ips = get_if_ips(log)
    tty_list = get_local(log)
    data = {hostname: {'user': 'pi'}}
    data[hostname]['adapters'] = tty_list
    data[hostname]['interfaces'] = if_ips
    log.debug('Final Data set collected for {}: {}'.format(hostname, data))
    log.info('Cloud Update triggered by IP update')
    if CLOUD_SVC == 'gdrive':
        cloud = GoogleDrive(log)
    remote_consoles = cloud.update_files(data)

    # NEW Python Menu: Write All Remotes to local file
    if len(remote_consoles) > 0:
        update_local_cloud_file(LOCAL_CLOUD_FILE, remote_consoles)


if __name__ == '__main__':
    main()
