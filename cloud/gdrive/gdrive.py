#!/etc/ConsolePi/venv/bin/python3

import os
import logging
import json
import socket
# import getpass
# import configparser
import netifaces as ni
import serial.tools.list_ports

from googleapiclient import discovery
import pickle
import os.path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from include.utils import get_config

# -- GLOBALS --
DEBUG = get_config('debug')
CLOUD_SVC = get_config('cloud_svc')

# Logging
LOG_FILE = '/var/log/ConsolePi/cloud.log'
log = logging.getLogger(__name__)
log.setLevel(logging.INFO if not DEBUG else logging.DEBUG)
handler = logging.FileHandler(LOG_FILE)
handler.setLevel(logging.INFO if not DEBUG else logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive.metadata']
APPLICATION_NAME = 'ConsolePi'
TIMEOUT = 3   # socket timeout in seconds (for clustered/cloud setup)

# Change current working directory
# os.chdir('/home/pi/ConsolePi_Cluster/')
os.chdir('/etc/ConsolePi/cloud/{}}/'.format(CLOUD_SVC))


# Google sheets API credentials - used to update config on Google Drive
def get_credentials():
    log.debug('-->get_credentials()')
    """
    Get credentials for google drive sheets
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('.credentials/token.pickle'):
        with open('.credentials/token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                '.credentials/credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('.credentials/token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds


# Google Drive Get File ID from File Name
def get_file_id(credentials):
    """
    Gets file id for ConsolePi.csv file on Google Drice
    Params: credentials object
    """
    credentials = get_credentials()
    # http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', credentials=credentials)

    results = service.files().list(
        pageSize=10, fields="nextPageToken, files(id, name)", q="name='ConsolePi.csv'").execute()
    items = results.get('files', [])
    if not items:
        print('No files found.')
    else:
        for item in items:
            if item['name'] == 'ConsolePi.csv':
                return item['id']


# Create spreadsheet to store data if not found (get_file_id returns None)
def create_sheet(service):
    print('ConsolePi.csv not found on Gdrive. Creating ConsolePi.csv')
    spreadsheet = {
        'properties': {
            'title': 'ConsolePi.csv'
        }
    }
    spreadsheet = service.spreadsheets().create(body=spreadsheet,
                                                fields='spreadsheetId').execute()
    return '{0}'.format(spreadsheet.get('spreadsheetId'))


def update_files(data):
    log.debug('-->update_files({})'.format(data))
    # Google Sheets params
    credentials = get_credentials()
    service = discovery.build('sheets', 'v4', credentials=credentials)
    spreadsheet_id = get_file_id(credentials)

    # If no spreadsheet_id sheet doesn't exist - create sheet
    if not spreadsheet_id:
        spreadsheet_id = create_sheet(service)
        log.debug('spreadsheet_id *new* sheet: ' + spreadsheet_id)
    else:
        log.debug('spreadsheet_id *existing* sheet: ' + spreadsheet_id)

    value_input_option = 'USER_ENTERED'

    # init remote_consoles dict, any entries in config not matching this ConsolePis hostname are added as remote ConsolePis
    remote_consoles = {}
    cnt = 1
    for k in data:
        found = False
        value_range_body = {
            "values": [
                [
                    k,
                    json.dumps(data[k])
                ]
            ]
        }

        # find out if this ConsolePi already has a row use that row in range
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range='A:B').execute()
        # TODO add exception catcher for HttpError 503 service currently unreachable with retries
        if result.get('values') is not None:
            x = 1
            for row in result.get('values'):
                # print(row[0])
                if socket.gethostname() in row:
                    cnt = x
                    found = True
                else:
                    remote_consoles[row[0]] = json.loads(row[1])
                x += 1
            log.debug('remote_ConsolePis Discovered from sheet: {0}, Count: {1}'.format(
                json.dumps(remote_consoles) if len(remote_consoles) > 0 else 'None', str(len(remote_consoles))))
        range_ = 'a' + str(cnt) + ':b' + str(cnt)

        if found:
            log.info('Updating ' + str(k) + ' data found on row ' + str(cnt) + ' of Google Drive config')
            request = service.spreadsheets().values().update(spreadsheetId=spreadsheet_id, range=range_,
                                                             valueInputOption=value_input_option, body=value_range_body)
        else:
            print('Updating Google Drive Config with ' + k + ' data')
            request = service.spreadsheets().values().append(spreadsheetId=spreadsheet_id, range=range_,
                                                             valueInputOption=value_input_option, body=value_range_body)
        request.execute()
        resize_cols(service, spreadsheet_id)
        cnt += 1
    return remote_consoles


# check remote ConsolePi is reachable
def check_reachable(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)
    try:
        sock.connect((ip, port))
        reachable = True
    except (socket.error, TimeoutError):
        # print('ERROR: %s is not reachable' % hostname)
        reachable = False
    sock.close()
    return reachable


# Auto Resize gdrive columns to match content
def resize_cols(service, spreadsheet_id):
    body = {"requests": [
        {
          "autoResizeDimensions": {
            "dimensions": {
              "sheetId": 0,
              "dimension": "COLUMNS",
              "startIndex": 0,
              "endIndex": 2
                }
            }
        }
      ]
    }
    response = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=body).execute()
    log.debug('resize_cols response: {}'.format(response))
    # print(response)


# if the device has a row in the cloud config, but it is not reachable delete that row
def del_row(dev_name):
    log.debug('{0} found in Drive Config, but not reachable... Deleting from Cloud Config'.format(dev_name))
    print('{0} found in Drive Config, but not reachable... Deleting from Cloud Config'.format(dev_name))
    found = False
    # find out if this ConsolePi already has a row use that row in range
    # -- TODO call get_credentials once and pass result to other functions
    credentials = get_credentials()
    service = discovery.build('sheets', 'v4', credentials=credentials)
    spreadsheet_id = get_file_id(credentials)
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range='A:A').execute()
    log.debug(result)
    if result.get('values') is not None:
        x = 0
        for row in result.get('values'):
            # print(row[0])
            if dev_name in row:
                found = True
                break
            else:
                x += 1

    if found:
        request = service.spreadsheets().get(spreadsheetId=spreadsheet_id, ranges=[],
                                             includeGridData=False)
        response = request.execute()
        # print(response)
        # sheet_id = response['sheets'][0]['properties']['sheetId']
        # print('sheet_id: {}'.format(sheet_id))
        requests = [{
                "deleteDimension": {
                    "range": {
                      "dimension": "ROWS",
                      "startIndex": x,
                      "endIndex": x+1
                    }
                  }
                }
        ]

        body = {
            'requests': requests
        }
        # print(body)
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body).execute()
        log.debug('del_row response: {}'.format(response))
        # print(response)


def get_if_ips():
    if_list = ni.interfaces()
    log.debug('interface list: {}'.format(if_list))
    ip_list = {}
    pos = 0
    for _if in if_list:
        if _if != 'lo':
            try:
                ip_list[if_list[pos]] = ni.ifaddresses(_if)[ni.AF_INET][0]['addr']
            except KeyError:
                log.info('No IP Found for {} skipping'.format(_if))
        pos += 1
    return ip_list


def get_serial_ports():
    this = serial.tools.list_ports.grep('.*ttyUSB[0-9]*', include_links=True)
    tty_list = {}
    tty_alias_list = {}
    for x in this:
        _device_path = x.device_path.split('/')
        if x.device.replace('/dev/', '') != _device_path[len(_device_path)-1]:
            tty_alias_list[x.device_path] = x.device
        else:
            tty_list[x.device_path] = x.device

    final_tty_list = []
    for k in tty_list:
        if k in tty_alias_list:
            final_tty_list.append(tty_alias_list[k])
        else:
            final_tty_list.append(tty_list[k])

    # get telnet port deffinitions from ser2net.conf
    # and build adapters dict
    serial_list = []
    if os.path.isfile('/etc/ser2net.conf'):
        for tty_dev in final_tty_list:
            with open('/etc/ser2net.conf', 'r') as cfg:
                for line in cfg:
                    if tty_dev in line:
                        tty_port = line.split(':')
                        tty_port = tty_port[0]
                        log.info('get_serial_ports: found {} {}'.format(tty_dev, tty_port))
                        break
                    else:
                        tty_port = 7000
            serial_list.append({'dev': tty_dev, 'port': tty_port})
            if tty_port == 7000:
                log.error('No ser2net.conf deffinition found for {}'.format(tty_dev))
                print('No ser2net.conf deffinition found for {}'.format(tty_dev))
    else:
        log.error('No ser2net.conf file found unable to extract port deffinitions')
        print('No ser2net.conf file found unable to extract port deffinitions')

    return serial_list


def main():
    hostname = socket.gethostname()
    if_ips = get_if_ips()
    print('  Detecting Local Adapters')
    tty_list = get_serial_ports()
    data = {hostname: {'user': 'pi'}}
    data[hostname]['adapters'] = tty_list
    data[hostname]['interfaces'] = if_ips
    log.info('Final Data set collected for {}: {}'.format(hostname, data))
    local_cloud_file = '/etc/ConsolePi/ConsolePi.cloud'
    new_cloud_file = '/etc/ConsolePi/cloud.data'
    print('  Updating Local Adapters and Retrieving Remote Adapters from Cloud Config')
    remote_consoles = update_files(data)

    # Remove local cloud file if it exists, re-create based on current data and reachability
    if os.path.isfile(local_cloud_file):
        os.remove(local_cloud_file)
    ip = None
    if len(remote_consoles) > 0:
        for remote_dev in remote_consoles:

            # -- Check each interface (ip) for remote_consoles, stop and write to local if reachable
            is_reachable = False
            for interface in remote_consoles[remote_dev]['interfaces']:
                ip = remote_consoles[remote_dev]['interfaces'][interface]
                if ip not in if_ips.values():
                    is_reachable = check_reachable(ip, 22)
                    if is_reachable:
                        break
            if is_reachable:
                with open(local_cloud_file, 'a') as cloud_file:
                    for adapter in remote_consoles[remote_dev]['adapters']:
                        cloud_file.write('{0},{1},{2},{3},{4}\n'.format(remote_dev, ip, remote_consoles[remote_dev]['user'],
                                                                        adapter['dev'], adapter['port']))
                        log.info('{0} is reachable. Adding {1} as remote connection option to local consolepi-menu'.format(
                            remote_dev, adapter['dev']))
            else:
                del_row(remote_dev)
                remote_consoles.pop(remote_dev)
        # Write All Remotes to local file
        if os.path.isfile(new_cloud_file):
            os.remove(new_cloud_file)
        with open(new_cloud_file, 'a') as new_file:
            new_file.write(json.dumps(remote_consoles))


if __name__ == '__main__':
    main()
