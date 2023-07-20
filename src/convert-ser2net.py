#!/etc/ConsolePi/venv/bin/python3

import sys
from pathlib import Path
import shutil
from rich import print
from rich.prompt import Confirm
from datetime import datetime
from typing import List

sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import config  # type: ignore # NoQA

DEF_V4_FILE = Path("/etc/ConsolePi/src/ser2net.yaml")
V3_FILE = Path("/etc/ser2net.conf")
BAK_DIR = Path("/etc/ConsolePi/bak")
DEF_PROMPT = f"""
[green]--------------------[/] [cyan]ser2net[/] [bright_red]v3[/] to [green3]v4[/] conversion utility [green]--------------------[/]
This utility will parse the [cyan]ser2net[/] v3 configuration file [cyan italic]{V3_FILE.name}[/]
and create a ConsolePi compatible ser2net v4 config [cyan italic]ser2net.yaml[/].

If ser2net v4 is installed the v3 config will be moved to {BAK_DIR}.
"""


class Convert:
    def __init__(self):
        self.v4_file: Path = self.get_v4_config_name()

    def __call__(self):
        if "-y" in " ".join(sys.argv[1:]).lower() or self.confirm():
            _ = self.check_v4_config()
            v4_lines = self.gather_config_data()
            if self.v4_file.exists() and self.v4_file.read_text() == v4_lines:
                print(f'  [magenta]-[/] Process resulted in no change in {self.v4_file.name} content.  Existing v4 config left as is.')
            else:
                print(f'  [magenta]-[/] Writing converted config to {self.v4_file}')
                self.v4_file.write_text(v4_lines)
                self.backup_v3_config()
            print()
        else:
            print("[bright_red]Aborted.")

    def get_v4_config_name(self) -> Path:
        new_file = Path("/etc/ser2net.yaml")
        if not new_file.exists() and Path("/etc/ser2net.yml").exists():
            new_file = Path("/etc/ser2net.yml")

        return new_file

    def check_v4_config(self) -> bool:
        if self.v4_file.exists():
            if "ConsolePi" not in self.v4_file.read_text().splitlines()[2]:
                now = datetime.now()
                _bak_file = BAK_DIR / f'{self.v4_file.name}.{now.strftime("%F_%H%M")}'
                print(f'  [magenta]-[/] Backing up existing non ConsolePi version of [cyan]{self.v4_file}[/] to [cyan]{_bak_file}[/].')
                shutil.move(self.v4_file, _bak_file)
                do_ser2net = True
                print("  [magenta]-[/] Preparing default ConsolePi ser2net v4 base config.")
            else:
                print(f'  [magenta]-[/] Found existing ConsolePi compatible version of [cyan]{self.v4_file}[reset].')
                do_ser2net = False
        else:
            do_ser2net = True
            print("  [magenta]-[/] Preparing default ConsolePi ser2net v4 base config.")

        return do_ser2net

    def backup_v3_config(self):
        if int("".join(config.ser2net_ver.split(".")[0])) > 3:
            if not self.v4_file.exists:
                print(f'  [dark_orange3][blink]!![/blink] WARNING[/]: ser2net v4 Configuration ({self.v4_file}) not found.  Keeping ser2net v3 file ({V3_FILE}) in place')
            else:
                now = datetime.now()
                _bak_file = BAK_DIR / f'{V3_FILE.name}.{now.strftime("%F_%H%M")}'
                print(f"  [magenta]-[/] ser2net [cyan]v{config.ser2net_ver}[/] installed.  Backing up v3 config {V3_FILE.name} to {_bak_file}")
                shutil.move(V3_FILE, _bak_file)
        else:
            print(f"  [magenta]-[/] ser2net [cyan]v{config.ser2net_ver}[/] installed.  Keeping v3 config {V3_FILE} in place.")

    def gather_config_data(self) -> str:
        v3_aliases = {k: v for k, v in config.ser2net_conf.items() if not k.startswith("_") and 7000 < v.get('port', 0) <= 7999}
        if self.v4_file.exists():
            v4_config: List[str] = self.v4_file.read_text().splitlines(keepends=True)
            v4_config_dict = config.get_ser2netv4(self.v4_file)
            v4_aliases = {k: v for k, v in v4_config_dict.items() if not k.startswith("_") and 7000 < v.get('port', 0) <= 7999}
        else:
            v4_config: List[str] = DEF_V4_FILE.read_text().splitlines(keepends=True)
            v4_aliases = {}

        v4_user_lines = [v["v4line"] for k, v in v3_aliases.items() if k not in v4_aliases.keys()]

        # Gather any trace-file references from v3 config and ensure they are defined in v4 config.
        if "trace-" in "".join(v4_user_lines):
            trace_lines = [line.strip().split(":")[-1].strip() for line in v4_user_lines if "trace-" in line]
            new_defs = [ref.lstrip("*") for ref in trace_lines if ref.startswith("*")]  # trace-file defs referenced in old config
            if new_defs:
                existing_defs, get_next_empty, insert_idx = [], False, 19
                for idx, line in enumerate(v4_config):
                    if "define: &" in line and "banner" not in line and "/" in line:
                        existing_defs += [line.split("&")[-1].split()[0]]  # define: &trace3 /var/log/ser2net/trace3...
                    elif get_next_empty:
                        if not line.strip() or not line.strip().startswith("define:"):
                            get_next_empty = False
                            insert_idx = idx
                    elif "# TRACEFILE DEFINITIONS" in line.strip():
                        get_next_empty = True
                    else:
                        continue

                missing_defs = [ref for ref in new_defs if ref not in existing_defs]
                if missing_defs:
                    missing_lines = [line for line in config.ser2net_conf.get("_v4_tracefiles", "").splitlines() for d in missing_defs if not line.startswith("#") and f'define: &{d}' in line]
                    if missing_lines:
                        print(f"  [magenta]-[/] Adding trace-file definition{'s' if len(missing_defs) > 1 else ''} [cyan]{'[/], [cyan]'.join(missing_defs)}[/] referenced in v3 config.")
                        v4_config.insert(insert_idx, "\n".join(missing_lines) + "\n")

        if v4_user_lines:
            new_cnt = len([line for line in v4_user_lines if line.startswith("connection:")])
            print(f"  [magenta]-[/] Adding {new_cnt} alias definitions converted from {config.ser2net_file}")
            v4_config += v4_user_lines
            if len(v3_aliases) != new_cnt:
                print(f"  [magenta]-[/] {len(v3_aliases) - new_cnt} aliases found in ser2net v3 config were skipped as they are already defined in the existing v4 config.")
        elif v3_aliases and v4_aliases:
            print(f'  [dark_orange3][blink]!![/blink] WARNING[/]: All {len(v3_aliases)} alias definitions found in the ser2net v3 config were ignored as they are already defined in the existing v4 config.')
        else:
            print(f'  [dark_orange3][blink]!![/blink] WARNING[/]: No User defined aliases found in {V3_FILE.name}.')

        return "".join(v4_config)

    @staticmethod
    def confirm(prompt: str = None) -> bool:
        prompt = prompt or DEF_PROMPT
        print(DEF_PROMPT)
        choice = Confirm.ask("Proceed?")
        print(f"[green]{'':-^77}[/]\n")

        return choice


if __name__ == "__main__":
    if shutil.os.getuid() != 0:
        print("[bright_red]Error:[/] Must be run as root.  Launch with [cyan]consolepi-convert[/].")
        sys.exit(1)
    elif not Path("/etc/ser2net.conf").exists():
        print("[bright_red]Error:[/] No v3 config found ([cyan]/etc/ser2net.conf[/]).")
        sys.exit(1)
    else:
        convert = Convert()
        convert()
