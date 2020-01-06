#!venv/bin/python3

from waitress import serve
from flask import Flask, jsonify, request
from consolepi.common import ConsolePi_data
from time import time

app = Flask(__name__)
config = ConsolePi_data(do_print=False)
# outlets = config.outlets
log = config.log
user = config.USER # pylint: disable=maybe-no-member
last_update = int(time())

def log_request(route):
    log.info('[API RQST IN] {} Requesting -- {} -- Data via API'.format(request.remote_addr, route))

@app.route('/api/v1.0/adapters', methods=['GET'])
def get_adapters():
    log_request('adapters')
    global last_update
    # if data has been refreshed in the last 20 seconds trust it is valid
    # prevents multiple simul calls to get_local after mdns_refresh and
    # subsequent API calls from all other ConsolePi on the network
    if int(time()) - last_update > 20:
        last_update = int(time())
        return jsonify({'adapters': config.get_adapters(do_print=False)})
    else:
        return jsonify({'adapters': config.adapters})

@app.route('/api/v1.0/remotes', methods=['GET'])
def get_cache():
    log_request('remotes')
    return jsonify({'remotes': config.get_local_cloud_file()})

@app.route('/api/v1.0/interfaces', methods=['GET'])
def get_ifaces():
    log_request('ifaces')
    return jsonify({'interfaces': config.get_if_ips()})

@app.route('/api/v1.0/outlets', methods=['GET'])
def get_outlets():
    log_request('outlets')
    # -- Collect Outlet Details remove sensitive data --
    outlets = config.pwr.pwr_get_outlets()
    if outlets and 'linked' in outlets:
        for grp in outlets['linked']:
            for x in ['username', 'password']:
                if x in outlets['linked'][grp]:
                    del outlets['linked'][grp][x]
    return jsonify(outlets)

@app.route('/api/v1.0/details', methods=['GET'])
def get_details():
    log_request('details')
    return jsonify({config.hostname: {'adapters': config.get_adapters(), 'interfaces': config.get_if_ips(), 'user': user}})

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000)
