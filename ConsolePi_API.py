#!venv/bin/python3

from waitress import serve
from flask import Flask, jsonify
from consolepi.common import ConsolePi_data

app = Flask(__name__)
config = ConsolePi_data(do_print=False)
log = config.log

@app.route('/api/v1.0/adapters', methods=['GET'])
def get_adapters():
    return jsonify({'adapters': config.adapters})

@app.route('/api/v1.0/remcache', methods=['GET'])
def get_cache():
    return jsonify({'remotes': config.remotes})

@app.route('/api/v1.0/ifaces', methods=['GET'])
def get_ifaces():
    return jsonify({'interfaces': config.interfaces})

@app.route('/api/v1.0/details', methods=['GET'])
def get_details():
    return jsonify(config.local)

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000)
