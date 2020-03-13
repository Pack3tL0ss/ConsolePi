#!/etc/ConsolePi/venv/bin/python3

from consolepi import Response
from consolepi import utils, config
from consolepi.remotes import Remotes
from consolepi.local import Local
from consolepi.power import Outlets
from consolepi.exec import ConsolePiExec
from consolepi.menu import Menu  # NoQA


class ConsolePi():
    def __init__(self, bypass_remotes=False):
        self.response = Response
        self.menu = Menu()
        self.local = Local()
        if config.cfg.get('power'):
            self.pwr_init_complete = False
            self.pwr = Outlets()
        else:
            self.pwr_init_complete = True
            self.pwr = None
        self.cpiexec = ConsolePiExec(config, self.pwr, self.local, self.menu)
        if not bypass_remotes:
            self.remotes = Remotes(self.local, self.cpiexec)

        # TODO Move to menu launch and prompt user
        # verify TELNET is installed and install if not if hosts of type TELNET are defined.
        if config.hosts:
            utils.verify_telnet_installed(config.hosts)
