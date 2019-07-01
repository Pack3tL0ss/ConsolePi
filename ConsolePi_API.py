#!venv/bin/python3

import socket
from waitress import serve
from flask import Flask, jsonify
from consolepi.common import ConsolePi_Log
from consolepi.common import get_local
from consolepi.common import get_if_ips
from consolepi.common import get_local_cloud_file

app = Flask(__name__)
CPI_LOG = ConsolePi_Log(do_print=False)
log = CPI_LOG.log
# adapters = get_local(log)
LOCAL_CLOUD_FILE = '/etc/ConsolePi/cloud.data'

@app.route('/api/v1.0/adapters', methods=['GET'])
def get_adapters():
    return jsonify({'adapters': get_local(cpi_log=CPI_LOG, do_print=False)})

@app.route('/api/v1.0/remcache', methods=['GET'])
def get_cache():
    return jsonify({'remotes': get_local_cloud_file(LOCAL_CLOUD_FILE)})

@app.route('/api/v1.0/ifaces', methods=['GET'])
def get_ifaces():
    return jsonify({'interfaces': get_if_ips(log)})

@app.route('/api/v1.0/details', methods=['GET'])
def get_details():
    return jsonify({socket.gethostname(): {'adapters': get_local(cpi_log=CPI_LOG, do_print=False), 'interfaces': get_if_ips(log), 'user': 'pi'}})

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000)
