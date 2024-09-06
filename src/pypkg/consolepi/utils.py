#!/etc/ConsolePi/venv/bin/python3

from __future__ import annotations

import string
import subprocess
import shlex
from subprocess import TimeoutExpired
import time
import psutil
import os
import sys
import stat
import grp
import json
import threading
import socket
from io import StringIO
from halo import Halo
from typing import List, Dict

try:
    loc_user = os.getlogin()
except Exception:
    loc_user = os.getenv("SUDO_USER", os.getenv("USER"))


class Convert:
    def __init__(self, mac):
        self.orig = mac
        if not mac:
            mac = '0'
        self.clean = ''.join([c for c in list(mac) if c in string.hexdigits])
        self.ok = True if len(self.clean) == 12 else False
        self.cols = ':'.join(self.clean[i:i + 2] for i in range(0, 12, 2))
        self.dashes = '-'.join(self.clean[i:i + 2] for i in range(0, 12, 2))
        self.dots = '.'.join(self.clean[i:i + 4] for i in range(0, 12, 4))
        self.tag = f"ztp-{self.clean[-4:]}"
        self.dec = int(self.clean, 16) if self.ok else 0


class Mac(Convert):
    def __init__(self, mac):
        super().__init__(mac)
        oobm = hex(self.dec + 1).lstrip('0x')
        self.oobm = Convert(oobm)


class Utils:
    def __init__(self):
        self.Mac = Mac

    def user_input_bool(self, question):
        """Ask User Y/N Question require Y/N answer

        Error and reprompt if user's response is not valid
        Appends '? (y/n): ' to question/prompt provided

        Params:
            question:str, The Question to ask
        Returns:
            answer:bool, Users Response yes=True
        """
        valid_answer = ["yes", "y", "no", "n"]
        try:
            answer = input(question + "? (y/n): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("")  # prevents header printing on same line when in debug
            return False
        while answer.lower() not in valid_answer:
            if answer != "":
                print(
                    f" \033[1;33m!!\033[0m Invalid Response '{answer}' Valid Responses: {valid_answer}"
                )
            answer = input(question + "? (y/n): ").strip()
        if answer[0].lower() == "y":
            return True
        else:
            return False

    def kill_hung_session(self, dev):
        """Kill hung picocom session

        If picocom process still active and user is diconnected from SSH
        it makes the device unavailable.  When error_handler determines that is the case
        This function is called giving the user the option to kill it.
        """

        def find_procs_by_name(name, dev):
            """Return the pid of process matching name, where dev was referenced in the cmdline options

            Params:
                name:str, name of process to find
                dev:str, dev which needs to be in the cmdline arguments for the process

            Returns:
                The pid of the matching process
            """
            ppid = None
            for p in psutil.process_iter(attrs=["name", "cmdline"]):
                if name == p.info["name"] and dev in p.info["cmdline"]:
                    ppid = p.pid  # if p.ppid() == 1 else p.ppid()
                    break
            return ppid

        def terminate_process(pid):
            """send terminate, then kill if still alive to pid

            params: pid of process to be killed
            """
            p = psutil.Process(pid)
            for x in range(0, 2):
                p.terminate()
                if p.status() != "Terminated":
                    p.kill()
                else:
                    break

        ppid = find_procs_by_name("picocom", dev)
        retry = 0
        msg = "\n{} appears to be in use (may be a previous hung session).\nDo you want to Terminate the existing session".format(
            dev.replace("/dev/", "")
        )
        if ppid is not None and self.user_input_bool(msg):
            while ppid is not None and retry < 3:
                print(
                    "An Existing session is already established to {}.  Terminating process {}".format(
                        dev.replace("/dev/", ""), ppid
                    )
                )
                try:
                    terminate_process(ppid)
                    time.sleep(3)
                    ppid = find_procs_by_name("picocom", dev)
                except PermissionError:
                    print(
                        "PermissionError: session is locked by user with higher priv. can not kill"
                    )
                    break
                except psutil.AccessDenied:
                    print(
                        "AccessDenied: Session is locked by user with higher priv. can not kill"
                    )
                    break
                except psutil.NoSuchProcess:
                    ppid = find_procs_by_name("picocom", dev)
                retry += 1
        return ppid is None

    def error_handler(self, cmd, stderr, user=loc_user):
        # TODO rather than running the command return something to the calling function instructing it to retry
        # with new cmd
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
        if stderr and "FATAL: cannot lock /dev/" not in stderr:
            # -- // KEY CHANGE ERROR \\ --
            if "WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!" in stderr:
                print(
                    "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
                    "@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @\n"
                    "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
                    "IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!\n"
                    "Someone could be eavesdropping on you right now (man-in-the-middle attack)!\n"
                    "It is also possible that a host key has just been changed."
                )
                while True:
                    choice = ''
                    try:
                        choice = input(
                            "\nDo you want to remove the old host key and re-attempt the connection (y/n)? "
                        )
                        if choice.lower() in ["y", "yes"]:
                            _cmd = shlex.split(
                                stderr.replace("\r", "")
                                .split("remove with:\n")[1]
                                .split("\n")[0]
                                .replace("ERROR:   ", "")
                            )  # NoQA
                            _cmd = shlex.split("sudo -u {}".format(user)) + _cmd
                            subprocess.run(_cmd)
                            print("\n")
                            subprocess.run(cmd)
                            break
                        elif choice.lower() in ["n", "no"]:
                            break
                        else:
                            print(
                                "\n!!! Invalid selection {} please try again.\n".format(
                                    choice
                                )
                            )
                    except (KeyboardInterrupt, EOFError):
                        print("")
                        return "Aborted last command based on user input"
                    except ValueError:
                        print(
                            "\n!! Invalid selection {} please try again.\n".format(
                                choice
                            )
                        )
            elif (
                "All keys were skipped because they already exist on the remote system"
                in stderr
            ):
                return "Skipped - key already exists"

            elif "/usr/bin/ssh-copy-id: INFO:" in stderr:
                if "sh: 1:" in stderr:
                    return "".join(stderr.split("sh: 1:")[1:]).strip()
                else:
                    if '\n' in stderr:
                        stderr = stderr.replace('\r', '')
                        return "".join([line for line in stderr.split('\n')
                                        if not line.startswith('/usr/bin/ssh-copy-id: INFO:')
                                        ]).strip()

            # -- // SSH CIPHER SUITE ERRORS \\ --
            elif "no matching cipher found. Their offer:" in stderr:
                print("Connection Error: {}\n".format(stderr))
                cipher = stderr.split("offer:")[1].strip().split(",")
                aes_cipher = [c for c in cipher if "aes" in c]
                if aes_cipher:
                    cipher = aes_cipher[-1]
                else:
                    cipher = cipher[-1]
                cmd += ["-o", f"ciphers={cipher}"]

                print(f"Reattempting Connection using cipher {cipher}")
                # r = subprocess.run(cmd)
                # if r.returncode:
                #     time.sleep(3)
                #     return "Error on Retry Attempt"  # TODO better way... handle banners... paramiko?
                s = subprocess
                with s.Popen(cmd, stderr=s.PIPE, bufsize=1, universal_newlines=True) as p, StringIO() as buf1:
                    for line in p.stderr:
                        print(line, end="")
                        if not line.startswith('/usr/bin/ssh-copy-id: INFO:'):
                            buf1.write(line)

                    return buf1.getvalue()

            # TODO handle invalid Key Exchange -o KexAlgorithms=...
            else:
                return stderr  # return value that was passed in

        # Handle hung sessions always returncode=1 doesn't always present stderr
        elif cmd[0] == "picocom":
            if self.kill_hung_session(cmd[1]):
                subprocess.run(cmd)
            else:
                return "User Abort or Failure to kill existing session to {}".format(
                    cmd[1].replace("/dev/", "")
                )

    def shell_output_cleaner(self, output):
        strip_words = ["/usr/bin/ssh-copy-id: "]
        return "".join(
            [x.replace(i, "") for x in self.listify(output) for i in strip_words]
        )

    def do_shell_cmd(
        self,
        cmd,
        do_print=False,
        handle_errors=True,
        return_stdout=False,
        tee_stderr=False,
        timeout=5,
        shell=False,
        **kwargs,
    ):
        """Runs shell cmd (i.e. ssh) returns stderr if any by default

        Arguments:
            cmd {str|list} -- commands/args sent to subprocess

        Keyword Arguments:
            do_print {bool} -- Print stderr after cmd completes (default: {False})
            handle_errors {bool} -- Send stderr to error_handler (default: {True})
            return_stdout {bool} -- run with shell and return tuple returncode, stdout, stderr (default: {False})
            tee_stderr {bool} -- stderr is displayed and captured (default: {False})
            timeout {int} -- subprocess timeout (default: {5})
            shell {bool} -- run cmd as shell (default: {True})

        Returns:
            {str|tuple} -- By default there is no return unless there is an error.
            return_stdout=True will return tuple returncode, stdout, stderr
        """
        if return_stdout:
            res = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                **kwargs,
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        elif shell:
            res = subprocess.run(
                cmd,
                shell=True,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                **kwargs,
            )
            if res.stderr:
                return (
                    res.stderr
                    if not handle_errors
                    else self.error_handler(cmd, res.stderr)
                )

        else:
            if isinstance(cmd, str):
                cmd = shlex.split(cmd)

            if tee_stderr:
                s = subprocess
                start_time = time.time()
                with s.Popen(
                    cmd, stderr=s.PIPE, bufsize=1, universal_newlines=True, **kwargs
                ) as p, StringIO() as buf1, StringIO() as buf2:
                    for line in p.stderr:
                        print(line, end="")
                        # handles login banners which are returned via stderr
                        if time.time() - start_time < timeout + 5:
                            buf1.write(line)
                        else:
                            buf2.write(line)

                    early_error = buf1.getvalue()
                    late_error = buf2.getvalue()

                # if connections lasted 20 secs past timeout assume the early stuff was innocuous
                if time.time() - start_time > timeout + 10:
                    error = late_error
                else:
                    error = early_error

                if handle_errors and error and p.returncode != 0:
                    error = self.error_handler(cmd, error)
                else:
                    error = None
                return error
            else:
                proc = subprocess.Popen(
                    cmd, stderr=subprocess.PIPE, universal_newlines=True, **kwargs
                )

                try:
                    err = proc.communicate(timeout=timeout)[1]
                    if err is not None and do_print:
                        print(self.shell_output_cleaner(err), file=sys.stdout)
                    # if proc.returncode != 0 and handle_errors:
                    if err and handle_errors:
                        err = self.error_handler(cmd, err)

                    proc.wait()
                    return err
                except (TimeoutExpired, TimeoutError):
                    return "Timed Out.  Host is likely unreachable."

    def check_install_apt_pkg(self, pkg: str, verify_cmd=None):
        verify_cmd = "which {}".format(pkg) if verify_cmd is None else verify_cmd

        def verify(verify_cmd):
            if isinstance(verify_cmd, str):
                verify_cmd = shlex.split(verify_cmd)
            r = subprocess.run(
                verify_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE
            )
            return r.returncode == 0

        if not verify(verify_cmd):
            resp = subprocess.run(
                ["/bin/bash", "-c", "apt install -y {}".format(pkg)],
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            if resp != 0:
                if verify(verify_cmd):
                    return (0, "{} Install Success".format(pkg))
        else:
            return (0, "Already Installed")

        return (
            resp.returncode,
            resp.stdout.decode("UTF-8")
            if resp.returncode == 0
            else resp.stderr.decode("UTF-8"),
        )

    def set_perm(self, file, user: str = None, group: str = None, other: str = None):
        _modes = {
            'user': {    # -- user and group set by default for our purposes --
                'r': 0,  # stat.S_IRUSR,
                'w': 0,  # stat.S_IWUSR,
                'x': stat.S_IXUSR
            },
            'group': {
                'r': 0,  # stat.S_IRGRP,
                'w': 0,  # stat.S_IWGRP,
                'x': stat.S_IXGRP
            },
            'other': {
                'r': stat.S_IROTH,
                'w': stat.S_IWOTH,
                'x': stat.S_IXOTH
            }
        }
        # -- by default set group ownership to consolepi and rw for user and group
        gid = grp.getgrnam("consolepi").gr_gid
        if os.geteuid() == 0:
            os.chown(file, 0, gid)
            _perms = stat.S_IWGRP + stat.S_IRGRP + stat.S_IWUSR + stat.S_IRUSR
            for k, v in [('user', user), ('group', group), ('other', other)]:
                if v:
                    # remove _perms added by this helper func by default if provided
                    if k and (k == 'user' or k == 'group'):
                        v = v.replace('r', '').replace('w', '')
                    for _m in list(v.lower()):
                        if not (_m == 'x' and os.path.isdir(file)):
                            # print(f"Add {k}: {_m}")
                            _perms += _modes[k][_m]

            # set x for all when dir (allow cd to the dir)
            if os.path.isdir(file):
                # print("add x for all")
                _perms += stat.S_IXUSR + stat.S_IXGRP + stat.S_IXOTH

            # if other and 'r' in other:
            #     _perms += stat.S_IROTH
            os.chmod(file, (_perms))

    def json_print(self, obj):
        print(json.dumps(obj, indent=4, sort_keys=True))

    def format_eof(self, file):
        cmd = "sed -i -e :a -e {} {}".format("'/^\\n*$/{$d;N;};/\\n$/ba'", file)
        return self.do_shell_cmd(cmd, handle_errors=False)

    def append_to_file(self, file, line):
        """Determine if last line of file includes a newline character
        write line provided on the next line

        params:
            file: file to write to
            line: line to write

        Returns:
            str if an error occurs otherwise Nothing
        """
        # strip any blank lines from end of file and remove LF
        self.format_eof(file)

        try:
            # determine if last line in file has LF
            with open(file) as f:
                _lines = f.readlines()
                _last = _lines[-1]

            # Make sure blank line will be placed at EOF and
            # prepend newline if last line of file lacks it to prevent appending to that line
            line = f"{line}\n" if not line.endswith("\n") else line
            line = f"\n{line}" if not _last.endswith("\n") else line

            with open(file, "a+") as f:
                f.write(line)
        except Exception as e:
            return e

    def get_picocom_ver(self):
        """return version of picocom"""
        x = subprocess.run(
            "which picocom >/dev/null && picocom  --help | head -1 | cut -dv -f2",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )
        x = x.stdout.decode("UTF-8").strip()
        if not x:
            # print("\nConsolePi Menu Requires picocom which doesn't appear to be installed")
            # print("Install with 'sudo apt install picocom'")
            # sys.exit(1)
            return 0
        else:
            return float(x)

    def get_ser2net_ver(self) -> str | None:
        """return version of ser2net"""
        x = subprocess.run(
            "which ser2net >/dev/null && ser2net -v | cut -d' ' -f3",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )
        x = x.stdout.decode("UTF-8").strip()

        return "" if not x else x

    def verify_telnet_installed(self, host_dict):
        """Install TELNET pkg if not already and TELNET hosts are defined

        params: host_dict.  The dict with manually defined host details
        return: True if not needed by any defined hosts, or is installed.
            returns are not currently used.
        """

        def telnet_install_thread(host_dict=host_dict):
            if "telnet" not in host_dict["_methods"]:
                return True

            r = self.check_install_apt_pkg("telnet")
            if r[0] != 0:
                # apt seems to return an error even when success
                r = subprocess.run(["which", "telnet"], capture_output=True).returncode
                if r != 0:
                    return False
            else:
                return True

        threading.Thread(
            target=telnet_install_thread, name="telnet_install_verify"
        ).start()

    def get_tty_size(self):
        size = subprocess.run(["stty", "size"], stdout=subprocess.PIPE)
        rows, cols = size.stdout.decode("UTF-8").split()
        return int(rows), int(cols)

    # TODO check if using kwarg sort added to fix re-order of error_msgs
    def unique(self, _list, sort=False):
        out = []
        [out.append(i) for i in _list if i not in out and i is not None]
        return out if not sort else sorted(out)

    def is_reachable(self, host, port, timeout=3, silent=False):
        s = socket.socket()
        try:
            s.settimeout(timeout)
            s.connect((host, port))
            _reachable = True
        except Exception as e:
            if not silent:
                print("something's wrong with %s:%d. Exception is %s" % (host, port, e))
            _reachable = False
        finally:
            s.close()
        return _reachable

    def format_dev(self, dev, hosts=None, outlet_groups: List[str] = None, udev=None, with_path=False) -> Dict[str, int | List[int]]:
        """Properly format devs found in user created JSON

        Args:
            dev (str | List[str]): An individual device or list of devices to be formatted (i.e. '/dev/idf_switch_1)
            hosts (dict, optional): Manually defined hosts from config. Defaults to None.
            outlet_groups (List[str], optional): Outlet Groups defined in the config. Defaults to None.
            udev (_type_, optional): _description_. Defaults to None.
            with_path (bool, optional): Strips any prefix if False adds /dev/, /host/, /group/ if True. Defaults to False.

        Returns:
            Dict[str, int | List[int]]: Linked Devices dictionary
        """
        if udev and not hosts:  # TODO don't think udev is ever passed to this func
            data = udev
            pfx = "/dev/"
            pfx_else = "/host/"
            print("DEBUG HIT HERE REMOVE THIS")
        else:
            data = hosts.get("_host_list", [])
            pfx = "/host/"
            pfx_else = "/dev/"

        dev = [dev] if not isinstance(dev, (list, dict)) else dev
        # dev_out = {}
        if with_path:
            if isinstance(dev, list):
                # d1 = [pfx + d for d in dev if '/' not in d and pfx + d in data]
                d_out = [
                    f"{f'{pfx}{d}' if f'{pfx}{d}' in data else None or f'/group/{d}' if d in outlet_groups else None or f'{pfx_else}{d}'}"
                    for d in dev
                    if "/" not in d
                ]
            elif isinstance(dev, dict):
                ...
                d_out = {
                    f"{f'{pfx}{d}' if f'{pfx}{d}' in data else None or f'/group/{d}' if d in outlet_groups else None or f'{pfx_else}{d}'}": dev[d]
                    for d in dev
                    if "/" not in d
                }
            else:
                d_out = None
            # for d in dev:
            #     if '/' not in d:
            #         _pfx = pfx if pfx + d in data else pfx_else
            #         if isinstance(dev, list):  # dli represented by dict dev: port or port list
            #             dev[dev.index(d)] = _pfx + d
            #         else:
            #             dev_out[_pfx + d] = dev[d]
            return d_out
        else:  # return dev list with prefixes stripped
            return (
                [d.split("/")[-1] for d in dev]
                if isinstance(dev, list)
                else {d.split("/")[-1]: dev[d] for d in dev}
            )

    def valid_file(self, filepath):
        return os.path.isfile(filepath) and os.stat(filepath).st_size > 0

    def listify(self, var):
        if var is None:
            return []
        else:
            return var if isinstance(var, list) else [var]

    def get_host_short(self, host):
        """Extract hostname from fqdn

        Arguments:
            host {str} -- hostname. If ip address is provided it's returned as is

        Returns:
            str -- host_short (lab1.example.com becomes lab1)
        """
        return (
            host.split(".")[0]
            if "." in host and not host.split(".")[0].isdigit()
            else host
        )

    def spinner(self, spin_txt, function, *args, **kwargs):
        spinner = kwargs.get("spinner", "dots")
        if sys.stdin.isatty():
            with Halo(text=spin_txt, spinner=spinner):
                return function(*args, **kwargs)
