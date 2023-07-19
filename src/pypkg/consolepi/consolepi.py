#!/etc/ConsolePi/venv/bin/python3

# from consolepi import Response
from consolepi import utils
from consolepi import config
from consolepi.remotes import Remotes
from consolepi.local import Local
from consolepi.power import Outlets
from consolepi.exec import ConsolePiExec
from consolepi.menu import Menu  # NoQA


class ConsolePi():
    def __init__(self, bypass_remotes: bool = False, bypass_outlets: bool = False, bypass_cloud: bool = False):
        self.menu = Menu("main_menu")
        self.local = Local()
        if not bypass_outlets and config.cfg.get('power'):
            self.pwr_init_complete = False
            self.pwr = Outlets()
        else:
            self.pwr_init_complete = True
            self.pwr = None
        self.cpiexec = ConsolePiExec(config, self.pwr, self.local, self.menu)
        if not bypass_remotes:
            self.remotes = Remotes(self.local, self.cpiexec, bypass_cloud=bypass_cloud)

        # TODO Move to menu launch and prompt user
        # verify TELNET is installed and install if not if hosts of type TELNET are defined.
        if config.hosts:
            utils.verify_telnet_installed(config.hosts)
