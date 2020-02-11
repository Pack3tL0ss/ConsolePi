#!/etc/ConsolePi/venv/bin/python3

from consolepi.config import Config  # NoQA
from consolepi.local import Local  # NoQA
from consolepi.remotes import Remotes  # NoQA
from consolepi.udevrename import Rename  # NoQA
from consolepi.consolepi import ConsolePi  # NoQA

# def get_yaml_file(yaml_file):
#     '''Return dict from yaml file.'''
#     if os.path.isfile(yaml_file) and os.stat(yaml_file).st_size > 0:
#         with open(yaml_file) as f:
#             try:
#                 return yaml.load(f, Loader=yaml.BaseLoader)
#             except ValueError as e:
#                 print(f'Unable to load configuration from {yaml_file}\n\t{e}')


# class ConsolePiLogger():
#     def __init__(self, log_file):
#         self.LOG_FILE = log_file

#     def get_logger(self):
#         '''Return custom log object.'''
#         fmtStr = "%(asctime)s [%(module)s:%(funcName)s:%(lineno)d:%(process)d][%(levelname)s]: %(message)s"
#         dateStr = "%m/%d/%Y %I:%M:%S %p"
#         logging.basicConfig(filename=self.LOG_FILE,
#                             # level=logging.DEBUG if self.debug else logging.INFO,
#                             level=logging.DEBUG if self.cfg['debug'] else logging.INFO,
#                             format=fmtStr,
#                             datefmt=dateStr)
#         return logging.getLogger('ConsolePi')

#     def log_and_show(self, msg, logit=True, showit=True, log=None):
#         cpi = self.cpi
#         if logit:
#             log = self.log.info if log is None else log
#             log(msg)

#         if showit:
#             msg = msg.replace('\t', '').split('\n')
#             [cpi.error_msgs.append(m) for m in msg if m not in cpi.error_msgs]


# static = get_yaml_file('/etc/ConsolePi/.static.yaml')
# log = ConsolePiLogger(static.get('LOG_FILE'))
