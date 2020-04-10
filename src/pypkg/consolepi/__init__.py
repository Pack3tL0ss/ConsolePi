#!/etc/ConsolePi/venv/bin/python3

import json
import logging
import requests  # NoQA
from consolepi.utils import Utils  # NoQA

LOG_FILE = '/var/log/ConsolePi/consolepi.log'


class Response():
    def __init__(self, ok: bool, output=None, error=None, status_code=None, state=None, do_json=False,  **kwargs):
        self.ok = ok
        self.text = output
        self.error = error
        self.state = state
        self.status_code = status_code
        self.json = None if not do_json else json.dumps(output)


class ConsolePiLog:

    def __init__(self, log_file, debug=False):
        self.error_msgs = []
        self.DEBUG = debug
        self.verbose = False
        self.log_file = log_file
        self._log = self.get_logger()
        self.name = self._log.name

    def get_logger(self):
        '''Return custom log object.'''
        # fmtStr = "%(asctime)s [%(module)s:%(funcName)s:%(lineno)d:%(process)d][%(levelname)s]: %(message)s"
        fmtStr = "%(asctime)s [%(process)d][%(levelname)s]: %(message)s"
        dateStr = "%m/%d/%Y %I:%M:%S %p"
        logging.basicConfig(filename=self.log_file,
                            level=logging.DEBUG if self.DEBUG else logging.INFO,
                            format=fmtStr,
                            datefmt=dateStr)
        return logging.getLogger('ConsolePi')

    def log_print(self, msgs, log=False, show=True, level='info', *args, **kwargs):
        msgs = [msgs] if not isinstance(msgs, list) else msgs
        _msgs = []
        _logged = []
        for i in msgs:
            if log and i not in _logged:
                getattr(self._log, level)(i)
                _logged.append(i)
            if '\n' in i:
                _msgs += i.replace('\t', '').replace('\r', '').split('\n')
            elif i.startswith('[') and ']' in i:
                _msgs.append(i.split(']', 1)[1].replace('\t', '').replace('\r', ''))
            else:
                _msgs.append(i.replace('\t', '').replace('\r', '').strip())

        msgs = []
        [msgs.append(i) for i in _msgs
            if i and i not in msgs and i not in self.error_msgs]

        if show:
            self.error_msgs += msgs

    def show(self, msgs, log=False, show=True, *args, **kwargs):
        self.log_print(msgs, show=show, log=log, *args, **kwargs)

    def debug(self, msgs, log=True, show=False, *args, **kwargs):
        self.log_print(msgs, log=log, show=show, level='debug', *args, **kwargs)

    # -- more verbose debugging - primarily to get json dumps
    # -- set verbose_debug: true in OVERRIDES to enable
    def debugv(self, msgs, log=True, show=False, *args, **kwargs):
        if self.DEBUG and self.verbose:
            self.log_print(msgs, log=log, show=show, level='debug', *args, **kwargs)

    def info(self, msgs, log=True, show=False, *args, **kwargs):
        self.log_print(msgs, log=log, show=show, *args, **kwargs)

    def warning(self, msgs, log=True, show=False, *args, **kwargs):
        self.log_print(msgs, log=log, show=show, level='warning', *args, **kwargs)

    def error(self, msgs, log=True, show=False, *args, **kwargs):
        self.log_print(msgs, log=log, show=show, level='error', *args, **kwargs)

    def exception(self, msgs, log=True, show=False, *args, **kwargs):
        self.log_print(msgs, log=log, show=show, level='exception', *args, **kwargs)

    def critical(self, msgs, log=True, show=False, *args, **kwargs):
        self.log_print(msgs, log=log, show=show, level='critical', *args, **kwargs)

    def fatal(self, msgs, log=True, show=False, *args, **kwargs):
        self.log_print(msgs, log=log, show=show, level='fatal', *args, **kwargs)

    def setLevel(self, level):
        getattr(self._log, 'setLevel')(level)


utils = Utils()

log = ConsolePiLog(LOG_FILE)

from consolepi.config import Config  # NoQA

config = Config()  # NoQA
if config.debug:
    log.setLevel(logging.DEBUG)

if config.ovrd.get('verbose_debug'):
    log.verbose = True
