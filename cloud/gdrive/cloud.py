#!/etc/ConsolePi/venv/bin/python3

from consolepi.common import ConsolePi_data
from consolepi.gdrive import GoogleDrive

config = ConsolePi_data(do_print=False)

def main():
    log = config.log
    data = config.local
    log.debug('[CLOUD TRIGGER (IP)]: Final Data set collected for {}: \n{}'.format(config.hostname, data))
    log.info('[CLOUD TRIGGER (IP)]: Cloud Update triggered by IP Update')
    if config.cloud_svc == 'gdrive':  # pylint: disable=maybe-no-member
        cloud = GoogleDrive(log)
    remote_consoles = cloud.update_files(data)

    # Send remotes learned from cloud file to local cache
    if len(remote_consoles) > 0:
        config.update_local_cloud_file(remote_consoles)


if __name__ == '__main__':
    main()
