#!/etc/ConsolePi/venv/bin/python3

import sys
sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import log  # NoQA
from consolepi.consolepi import ConsolePi  # NoQA


def main():
    cpi = ConsolePi()
    log.info('[CLOUD TRIGGER (IP)]: Cloud Update triggered by IP Update')
    cpi.remotes.refresh()


if __name__ == '__main__':
    main()
