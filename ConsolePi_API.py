#!venv/bin/python3

from waitress import serve
from flask import Flask, jsonify, request
from consolepi.common import ConsolePi_data

app = Flask(__name__)
config = ConsolePi_data(do_print=False)
outlets = config.outlets
log = config.log
user = config.USER # pylint: disable=maybe-no-member

def log_request(route):
    log.info('[API RQST IN] {} Requesting -- {} -- Data via API'.format(request.remote_addr, route))

@app.route('/api/v1.0/adapters', methods=['GET'])
def get_adapters():
    log_request('adapters')
    return jsonify({'adapters': config.get_local(do_print=False)})

@app.route('/api/v1.0/remotes', methods=['GET'])
def get_cache():
    log_request('remcache')
    return jsonify({'remotes': config.get_local_cloud_file()})

@app.route('/api/v1.0/interfaces', methods=['GET'])
def get_ifaces():
    log_request('ifaces')
    return jsonify({'interfaces': config.get_if_ips()})

@app.route('/api/v1.0/outlets', methods=['GET'])
def get_outlets():
    log_request('outlets')
    return jsonify(config.get_outlets())

@app.route('/api/v1.0/details', methods=['GET'])
def get_details():
    log_request('details')
    return jsonify({config.hostname: {'adapters': config.get_local(), 'interfaces': config.get_if_ips(), 'user': user}})

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000)
