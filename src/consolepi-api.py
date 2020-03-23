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
sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import config, log  # NoQA
from consolepi.consolepi import ConsolePi  # NoQA
from fastapi import FastAPI  # NoQA
from time import time  # NoQA
from starlette.requests import Request  # NoQA
import uvicorn  # NoQA


cpi = ConsolePi()
cpiexec = cpi.cpiexec
local = cpi.local
if config.power:
    if not cpiexec.wait_for_threads():
        outlets = cpi.pwr.data if cpi.pwr.data else None
else:
    outlets = None
user = local.user  # pylint: disable=maybe-no-member
last_update = int(time())
udev_last_update = int(time())

app = FastAPI(title='ConsolePi.API',
              docs_url='/api/docs',
              redoc_url="/api/redoc",
              openapi_url='/api/openapi/openapi.json'
              )


def log_request(request: Request, route: str):
    log.info('[NEW API RQST IN] {} Requesting -- {} -- Data via API'.format(request.client.host, route))


@app.get('/api/v1.0/adapters')
async def adapters(request: Request, refresh: bool = False):
    global last_update
    time_upd = True if int(time()) - last_update > 20 else False
    log_request(request, f'adapters Update based on Time {time_upd}, Update based on query param {refresh}')
    # if data has been refreshed in the last 20 seconds trust it is valid
    # prevents multiple simul calls to get_adapters after mdns_refresh and
    # subsequent API calls from all other ConsolePi on the network
    if refresh or int(time()) - last_update > 20:
        config.ser2net_conf = config.get_ser2net() if refresh else config.ser2net_conf
        local.adapters = local.build_adapter_dict(refresh=True)
        last_update = int(time())
    return {'adapters': local.adapters}


@app.get('/api/v1.0/remotes')
def remotes(request: Request):
    log_request(request, 'remotes')
    return {'remotes': config.get_remotes_from_file()}


@app.get('/api/v1.0/interfaces')
def get_ifaces(request: Request):
    log_request(request, 'ifaces')
    local.interfaces = local.get_if_info()
    # ifaces = {k: v for k, v in local.interfaces.items() if not k.startswith('_')}
    return {'interfaces': local.interfaces}


@app.get('/api/v1.0/outlets')
def get_outlets(request: Request, outlets=outlets):
    log_request(request, 'outlets')
    # -- Collect Outlet Details remove sensitive data --
    if outlets:
        outlets = cpi.pwr.pwr_get_outlets()
        cpiexec.wait_for_threads()
        if outlets and 'defined' in outlets:
            for grp in outlets['defined']:
                for x in ['username', 'password']:
                    if x in outlets['defined'][grp]:
                        del outlets['defined'][grp][x]
    return outlets


@app.get('/api/v1.0/details')
def get_details(request: Request):
    log_request(request, 'details')
    global last_update
    if int(time()) - last_update > 20:
        local.data = local.build_local_dict(refresh=True)
        last_update = int(time())
    return local.data


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")
