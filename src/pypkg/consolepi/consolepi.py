#!/etc/ConsolePi/venv/bin/python3

# import threading
# import time
# import os
# import json
# import subprocess
from consolepi import Response
from consolepi import config
# from consolepi.config import Config
# from consolepi.utils import Utils
from consolepi import utils
from consolepi.remotes import Remotes
# from consolepi.udevrename import Rename
from consolepi.local import Local
# from collections import namedtuple
from consolepi.power import Outlets
from consolepi.exec import ConsolePiExec
from consolepi.menu import Menu  # NoQA


class ConsolePi():
    def __init__(self, bypass_remotes=False):
        self.response = Response
        self.utils = utils
        self.config = config
        self.error_msgs = config.error_msgs
        self.log = self.config.log
        self.plog = self.config.plog
        self.menu = Menu(self.config)
        self.local = Local(self.config)
        if self.config.cfg.get('power'):
            self.pwr_init_complete = False
            self.pwr = Outlets(self.config)
        else:
            self.pwr_init_complete = True
            self.pwr = None
        self.cpiexec = ConsolePiExec(config, self.pwr, self.local, self.menu)
        if not bypass_remotes:
            self.remotes = Remotes(self.config, self.local, self.cpiexec)
        # verify TELNET is installed and install if not if hosts of type TELNET are defined.
        # TODO Move to menu launch and prompt user
        if self.config.hosts:
            self.utils.verify_telnet_installed(self.config.hosts)
