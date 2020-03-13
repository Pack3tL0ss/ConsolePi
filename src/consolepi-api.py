#!/etc/ConsolePi/venv/bin/python

'''
ConsolePi API

Used for remote discovery.  When ConsolePis discover each other
this allows any of them to display options for all discovered
ConsolePis in consolepi-menu (you can connect to serail devices
attached to the remotes).

mdns and gdrive provide discovery/sync mechanisms, when the payload
is to large for mdns the API is leveraged to gather the missing details.
'''
from fastapi import FastAPI
from time import time
from consolepi.common import ConsolePi_data
from starlette.requests import Request
import uvicorn

config = ConsolePi_data(do_print=False)
if config.power:
    if not config.wait_for_threads():
        outlets = config.pwr.outlet_data if config.pwr.outlet_data else None
else:
    outlets = None
log = config.log
user = config.USER  # pylint: disable=maybe-no-member
last_update = int(time())

app = FastAPI(title='ConsolePi.API',
              docs_url='/api/docs',
              redoc_url="/api/redoc",
              openapi_url='/api/openapi/openapi.json'
              )


def log_request(request: Request, route: str):
    log.info('[NEW API RQST IN] {} Requesting -- {} -- Data via API'.format(request.client.host, route))


@app.get('/api/v1.0/adapters')
def adapters(request: Request):
    log_request(request, 'adapters')
    # if data has been refreshed in the last 20 seconds trust it is valid
    # prevents multiple simul calls to get_adapters after mdns_refresh and
    # subsequent API calls from all other ConsolePi on the network
    global last_update
    if int(time()) - last_update > 20:
        adapters = config.get_adapters(do_print=False)
        last_update = int(time())
        return {'adapters': adapters}
    else:
        return {'adapters': config.adapters}


@app.get('/api/v1.0/remotes')
def remotes(request: Request):
    log_request(request, 'remotes')
    remotes = config.get_local_cloud_file()
    return {'remotes': remotes}


@app.get('/api/v1.0/interfaces')
def get_ifaces(request: Request):
    log_request(request, 'ifaces')
    ifaces = config.get_if_ips()
    return {'interfaces': ifaces}


@app.get('/api/v1.0/outlets')
def get_outlets(request: Request, outlets=outlets):
    log_request(request, 'outlets')
    # -- Collect Outlet Details remove sensitive data --
    if outlets:
        outlets = config.pwr.pwr_get_outlets()
        if outlets and 'linked' in outlets:
            for grp in outlets['linked']:
                for x in ['username', 'password']:
                    if x in outlets['linked'][grp]:
                        del outlets['linked'][grp][x]
    return outlets


@app.get('/api/v1.0/details')
def get_details(request: Request):
    log_request(request, 'details')
    return {config.hostname: {'adapters': config.get_adapters(), 'interfaces': config.get_if_ips(), 'user': user}}

# @app.get("/api/v1.0/{item_id}")
# def read_item(self, item_id: int, q: str = None):
#     return {"item_id": item_id, "q": q}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")
