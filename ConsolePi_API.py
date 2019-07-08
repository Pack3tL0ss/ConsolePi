#!venv/bin/python3

from waitress import serve
from flask import Flask, jsonify
from consolepi.common import ConsolePi_data

app = Flask(__name__)
config = ConsolePi_data(do_print=False)
log = config.log

@app.route('/api/v1.0/adapters', methods=['GET'])
def get_adapters():
    return jsonify({'adapters': config.get_local(do_print=False)})

@app.route('/api/v1.0/remcache', methods=['GET'])
def get_cache():
    return jsonify({'remotes': config.get_local_cloud_file()})

@app.route('/api/v1.0/ifaces', methods=['GET'])
def get_ifaces():
    return jsonify({'interfaces': config.get_if_ips()})

@app.route('/api/v1.0/details', methods=['GET'])
def get_details():
    return jsonify({config.hostname: {'adapters': config.get_local(), 'interfaces': config.get_if_ips(), 'user': config.local['user']}})

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000)
