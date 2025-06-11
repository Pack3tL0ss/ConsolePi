#!/etc/ConsolePi/venv/bin/python3

# from consolepi import Response
from . import config, utils
from .exec import ConsolePiExec
from .local import Local
from .menu import Menu  # NoQA
from .power import Outlets
from .remotes import Remotes


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
        self.cpiexec = ConsolePiExec(self.pwr, self.local, self.menu)
        if not bypass_remotes:
            self.remotes = Remotes(self.local, self.cpiexec, bypass_cloud=bypass_cloud)

        # TODO Move to menu launch and prompt user
        # verify TELNET is installed and install if not if hosts of type TELNET are defined.
        if config.hosts:
            utils.verify_telnet_installed(config.hosts)
