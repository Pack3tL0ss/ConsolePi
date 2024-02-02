#!/etc/ConsolePi/venv/bin/python

'''
ConsolePi API

Used for remote discovery.  When ConsolePis discover each other
this allows any of them to display options for all discovered
ConsolePis in consolepi-menu (you can connect to serail devices
attached to the remotes).

mdns and gdrive provide discovery/sync mechanisms, the API is used
to ensure the remote is reachable and that the data is current.
'''
import sys

import setproctitle
import uvicorn  # NoQA
from rich.traceback import install

sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import config, log  # type: ignore # NoQA
from consolepi.consolepi import ConsolePi  # type: ignore # NoQA
from fastapi import FastAPI  # NoQA
# from pydantic import BaseModel  # NoQA
from time import time  # NoQA
from starlette.requests import Request  # NoQA

install(show_locals=True)

setproctitle.setproctitle("consolepi-api")


cpi = ConsolePi()
cpiexec = cpi.cpiexec
local = cpi.local
if config.power:
    if not cpiexec.wait_for_threads():
        OUTLETS = cpi.pwr.data if cpi.pwr.data else None
else:
    OUTLETS = None
user = local.user
last_update = int(time())
udev_last_update = int(time())


# class Adapters(BaseModel):
#     adapters: dict

#     class Config:
#         schema_extra = {
#             'example': [{
#                 "adapters": {
#                     "/dev/FT232R-dev": {
#                         "udev": {
#                             "by_path": "/dev/serial/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.3.1.3:1.0-port0",
#                             "by_id": "/dev/serial/by-id/pci-FTDI_FT232R_USB_UART_AC012WBO-if00-port0",
#                             "root_dev": "false",
#                             "devname": "/dev/ttyUSB5",
#                             "devpath": "/devices/platform/scb/fd500000.pcie/pci0000:00/.../ttyUSB5/tty/ttyUSB5",
#                             "id_bus": "pci",
#                             "id_model": "FT232R_USB_UART",
#                             "id_model_from_database": "FT232 Serial (UART) IC",
#                             "id_model_id": "6001",
#                             "id_path": "platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.3.1.3:1.0",
#                             "id_pci_class_from_database": "Serial bus controller",
#                             "id_pci_subclass_from_database": "USB controller",
#                             "id_serial": "FTDI_FT232R_USB_UART_AB123456",
#                             "id_serial_short": "AB123456",
#                             "id_type": "generic",
#                             "id_usb_driver": "ftdi_sio",
#                             "id_usb_interfaces": ":ffffff:",
#                             "id_ifnum": "00",
#                             "id_vendor": "FTDI",
#                             "id_vendor_from_database": "Future Technology Devices International, Ltd",
#                             "id_vendor_id": "0403",
#                             "subsystem": "tty",
#                             "time_since_init": "2:09:35.455413 as of 03/29/20 01:03:48 AM CDT"
#                         },
#                         "outlets": [],
#                         "config": {
#                             "port": 7013,
#                             "baud": 9600,
#                             "dbits": 8,
#                             "parity": "n",
#                             "flow": "n",
#                             "sbits": 1,
#                             "logfile": "null",
#                             "log_ptr": 'null',
#                             "cmd": "picocom /dev/FT232R-dev --baud 9600 --flow n --databits 8 --parity n --stopbits 1",
#                             "line": "7013:telnet:0:/dev/FT232R-dev:9600 8DATABITS NONE 1STOPBIT  banner "
#                         }
#                     }
#                 }
#             }]
#         }


app = FastAPI(title='ConsolePi.API',
              docs_url='/api/docs',
              redoc_url="/api/redoc",
              openapi_url='/api/openapi/openapi.json'
              )


def log_request(request: Request, route: str):
    log.info('[NEW API RQST IN] {} Requesting -- {} -- Data via API'.format(request.client.host, route))


#  -- Haven't yet cracked the code on properly updating swagger-ui with examples and schema --
# @app.get('/api/v1.0/adapters', responses={200: {'model': Adapters}})
@app.get('/api/v1.0/adapters')
async def adapters(request: Request, refresh: bool = False):
    global last_update
    time_upd = True if int(time()) - last_update > 20 else False
    log_request(request, f'adapters Update based on Time {time_upd}, Update based on query param {refresh}')
    # if data has been refreshed in the last 20 seconds trust it is valid
    # prevents multiple simul calls to get_adapters after mdns_refresh and
    # subsequent API calls from all other ConsolePi on the network
    if refresh or int(time()) - last_update > 20:
        config.ser2net_conf = config.get_ser2net()
        local.adapters = local.build_adapter_dict(refresh=True)
        last_update = int(time())
    return {'adapters': local.adapters}


@app.get('/api/v1.0/adapters/udev/{adapter}')
async def udev(request: Request, adapter: str = None):
    log_request(request, f'fetching udev details for {adapter}')
    return {adapter: local.udev_adapters.get(f'/dev/{adapter}')}


@app.get('/api/v1.0/remotes')
def remotes(request: Request):
    log_request(request, 'remotes')
    return {'remotes': config.get_remotes_from_file()}


@app.get('/api/v1.0/interfaces')
def get_ifaces(request: Request):
    log_request(request, 'ifaces')
    local.interfaces = local.get_if_info()
    return {'interfaces': local.interfaces}

# removing due to fastapi issue #894, outlets method was not being used for anything currently so disabling for now
# @app.get('/api/v1.0/outlets')
# def get_outlets(request: Request, outlets=OUTLETS):
#     log_request(request, 'outlets')
#     # -- Collect Outlet Details remove sensitive data --
#     if outlets:
#         outlets = cpi.pwr.pwr_get_outlets()
#         cpiexec.wait_for_threads()
#         if outlets and 'defined' in outlets:
#             outlets['defined'] = {p: {k: v for k, v in outlets['defined'][p].items()
#                                   if k not in ['username', 'password']} for p in outlets['defined']}

#     return outlets


@app.get('/api/v1.0/details')
def get_details(request: Request):
    log_request(request, 'details')
    global last_update
    if int(time()) - last_update > 20:
        local.data = local.build_local_dict(refresh=True)
        last_update = int(time())
    return local.data


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.api_port, log_level="info")
