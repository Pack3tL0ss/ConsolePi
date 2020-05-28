#!/etc/ConsolePi/venv/bin/python3

import sys

sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import config  # NoQA

cfg = {**config.cfg, **{"comment": "START OF OVERRIDES"},  **config.ovrd}


def get_config(cfg=cfg):
    '''get ConsolePi configuration from ConsolePi

    ConsolePi config.py will use ConsolePi.yaml if exists, ConsolePi.json if it doesn't

    Keyword Arguments:
        cfg {str} -- "static" or "bash" static gets static system vars from .static.yaml
                     "bash" or the default will get user config from ConsolePi.yaml or
                     ConsolePi.json (default: {cfg})

    Output is bash formatted var=value file for use as a source in bash scripts
    '''
    for k, v in cfg.items():
        if isinstance(v, str):
            if v.isdigit() and '.' not in v:
                print(f'{k}={v}')
            else:
                print(f'{k}="{v}"')
        elif isinstance(v, list):
            v = ' '.join(v)
            print(f'{k}=({v})')
        elif isinstance(v, bool):
            v = 'true' if v else 'false'
            print(f'{k}={v}')
        else:
            print(f'{k}={v}')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'bash':
            get_config(cfg)
        elif sys.argv[1] == 'static':
            get_config(config.static)
        else:
            print(f'Invalid Argument {sys.argv[1]}')
    else:
        get_config()
