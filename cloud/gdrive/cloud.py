#!/etc/ConsolePi/venv/bin/python3

from consolepi.common import ConsolePi_data
from consolepi.gdrive import GoogleDrive

config = ConsolePi_data(do_print=False)

def main():
    log = config.log
    # data = {config.hostname: {'adapters': config.get_adapters(), 'interfaces': config.get_if_ips(), 'user': config.USER}} # pylint: disable=maybe-no-member
    # data = {config.hostname: {'adapters': config.adapters, 'interfaces': config.interfaces, 'rem_ip': config.ip_w_gw, 'user': config.USER}} # pylint: disable=maybe-no-member
    data = config.local
    log.debug('[CLOUD TRIGGER (IP)]: Final Data set collected for {}: \n{}'.format(config.hostname, data))
    log.info('[CLOUD TRIGGER (IP)]: Cloud Update triggered by IP Update')
    if config.cloud_svc == 'gdrive':  # pylint: disable=maybe-no-member
        cloud = GoogleDrive(log)
    remote_consoles = cloud.update_files(data)

    # Send remotes learned from cloud file to local cache
    if remote_consoles and 'Gdrive-Error:' not in remote_consoles:
        config.update_local_cloud_file(remote_consoles)
    elif 'Gdrive-Error:' in remote_consoles:
        log.info('[CLOUD TRIGGER (IP)]: Cloud Update Failed {}'.format(remote_consoles))


if __name__ == '__main__':
    main()
