#!/etc/ConsolePi/venv/bin/python3

import json
import sys
# import threading
sys.path.insert(0, '/etc/ConsolePi/src/pypkg')

from consolepi import log # NoQA
from consolepi.consolepi import ConsolePi # NoQA
# from consolepi import threading  # NoQA
# from consolepi.power.outlets import Outlets  # NoQA

cpi = ConsolePi(bypass_remotes=True)
# cpi = ConsolePi()
pwr = cpi.pwr
# utils = cpi.utils
# threading.Thread(target=utils.set_perm, args=['/home/pi/testfile'], name='common_import_test').start()
# outlet_data = cpi.config.outlets
print(pwr.do_esphome_cmd("outlet1.kabrew.com", "outlet1", 'cycle'))
sys.exit(0)

pwr.pwr_start_update_threads()
if cpi.cpiexec.wait_for_threads():
    print('Threads Timed Out')
    sys.exit(1)
else:
    outlets = pwr.data
    print(pwr.do_esphome_cmd("outlet1.kabrew.com", "outlet1", True))

if len(sys.argv) >= 2:
    if len(sys.argv) == 2:
        print(json.dumps(getattr(pwr, sys.argv[1]), indent=4, sort_keys=True))
    else:
        func = getattr(pwr, sys.argv[1])
        print(sys.argv[2:])
        func(*sys.argv[2:])
        # upd = pwr.pwr_get_outlets(upd_linked=True)
        # print(json.dumps(upd, indent=4, sort_keys=True))
else:
    pass
    # print(json.dumps(outlets, indent=4, sort_keys=True))
    # print(outlets['defined']['labpower1']['linked_devs'])

# for t in threading.enumerate():
#     print(t.name)
for e in log.error_msgs:
    print(e)
