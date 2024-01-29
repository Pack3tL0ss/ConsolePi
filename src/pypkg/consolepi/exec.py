#!/etc/ConsolePi/venv/bin/python3

import threading
import time
import os
import json
import subprocess
import shlex
from halo import Halo

from consolepi import utils, log, config

# TODO byobu to menu launch new sessions in new tab by default figure out best way to provide split options i.e. 11 split h 14 create new-window and launch 11 on top 14 on bottom
# Command to launch menu in byobu: byobu new-session -n menu consolepi-menu
# command to launch new window
# byobu new-window -n r1-6100-oobm "bash -c 'echo -e $pre_msg \n;stty size; ssh -t garagepi /etc/ConsolePi/src/remote_launcher.py picocom /dev/r1-6100-oobm-sw -b 115200'"
# or byobu new-window -n name 'ssh -t garagepi /etc/ConsolePi/src/remote_launcher.py picocom /dev/r1-6100-oobm-sw -b 115200'
# # temp byobu launch testing
# menu_actions['by'] = {
#     "cmd": "sudo -u wade byobu new-window -n r1-6100-oobm-sw 'sudo -u wade ssh -t garagepi /etc/ConsolePi/src/remote_launcher.py picocom /dev/r1-6100-oobm-sw -b 115200'",
#     "pre_msg": "Connecting To r1-6100-oobm-sw on GaragePi..."

class ConsolePiExec:
    def __init__(self, config, pwr, local, menu):
        self.pwr = pwr
        self.local = local
        self.menu = menu
        self.pwr_init_complete = False
        self.autopwr_wait = False
        self.spin = Halo(spinner="dots")

    def exec_auto_pwron(self, pwr_key):
        """Launch auto_pwron in thread

        params:
            menu_dev:str, The tty dev user is connecting to
        """
        pwr_key_pretty = pwr_key.replace("/dev/", "").replace("/host/", "")
        if (
            pwr_key in config.outlets["linked"]
        ):  # verify against config here as pwr may not be completely init
            _msg = (
                f"Ensuring {pwr_key_pretty} Linked Outlets ({' '.join(config.outlets['linked'][pwr_key])}) "
                "are Powered \033[1;32mON\033[0m"
            )
            _dots = "-" * (len(_msg) + 4)
            _msg = (
                f"\n{_dots}\n  {_msg}  \n{_dots}\n"  # TODO send to formatter in menu ... __init__
            )
            print(_msg)
            threading.Thread(
                target=self.auto_pwron_thread,
                args=(pwr_key,),
                name="auto_pwr_on_" + pwr_key_pretty,
            ).start()
            log.debug(
                "[AUTO PWRON] Active Threads: {}".format(
                    [t.name for t in threading.enumerate() if t.name != "MainThread"]
                )
            )

    # TODO just get the outlet from the dict, and pass to power module function let it determine type etc
    def auto_pwron_thread(self, pwr_key):
        """Ensure any outlets linked to device are powered on

        Called by consolepi_menu exec_menu function and remote_launcher (for sessions to remotes)
        when a connection initiated with adapter.  Powers any linked outlets associated with the
        adapter on.

        params:
            menu_dev:str, The tty device user is connecting to.
        Returns:
            No Return - Updates class attributes
        """
        if self.wait_for_threads("init"):
            return

        outlets = self.pwr.data
        if "linked" not in outlets:
            _msg = "Error linked key not found in outlet dict\nUnable to perform auto power on"
            log.show(_msg, show=True)
            return

        if not outlets["linked"].get(pwr_key):
            return

        # -- // Perform Auto Power On (if not already on) \\ --
        for o in outlets["linked"][pwr_key]:
            outlet = outlets["defined"].get(o.split(":")[0])
            if outlet:
                ports = [] if ":" not in o else json.loads(o.replace("'", '"').split(":")[1])
                _addr = outlet["address"]
            else:
                log.error(
                    f"Skipping Auto Power On {pwr_key} for {o}. Unable to pull outlet details from defined outlets.",
                    show=True,
                )
                log.debugv(f"Outlet Dict:\n{json.dumps(outlets)}")
                continue

            # -- // DLI web power switch Auto Power On \\ --
            #
            # TODO combine all ports from same pwr_key and sent to pwr_toggle once
            # TODO Update outlet if return is OK, then run refresh in the background to validate
            # TODO Add class attribute to cpi_menu ~ cpi_menu.new_data = "power", "main", etc
            #      Then in wait_for_input run loop to check for updates and re-display menu
            # TODO power_menu and dli_menu wait_for_threads auto power ... check cpiexec.autopwr_wait first
            #
            if outlet["type"].lower() == "dli":
                for p in ports:
                    log.debug(
                        f"[Auto PwrOn] Power ON {pwr_key} Linked Outlet {outlet['type']}:{_addr} p{p}"
                    )

                    if not outlet["is_on"][p][
                        "state"
                    ]:  # This is just checking what's in the dict not querying the DLI
                        r = self.pwr.pwr_toggle(outlet["type"], _addr, desired_state=True, port=p)
                        if isinstance(r, bool):
                            if r:
                                threading.Thread(
                                    target=self.outlet_update,
                                    kwargs={"refresh": True, "upd_linked": True},
                                    name="auto_pwr_refresh_dli",
                                ).start()
                                self.autopwr_wait = True
                        else:
                            log.warning(
                                f"{pwr_key} Error operating linked outlet @ {o}",
                                show=True,
                            )

            # -- // esphome Auto Power On \\ --
            elif outlet["type"].lower() == "esphome":
                for p in ports:
                    log.debug(
                        f"[Auto PwrOn] Power ON {pwr_key} Linked Outlet {outlet['type']}:{_addr} p{p}"
                    )
                    if not outlet["is_on"][p]["state"]:  # This is just checking what's in the dict
                        r = self.pwr.pwr_toggle(outlet["type"], _addr, desired_state=True, port=p)
                        if isinstance(r, bool):
                            self.pwr.data["defined"][o.split(":")[0]]["is_on"][p]["state"] = r
                        else:
                            log.show(r)
                            log.warning(
                                f"{pwr_key} Error operating linked outlet @ {o}",
                                show=True,
                            )

            # -- // GPIO & TASMOTA Auto Power On \\ --
            else:
                log.debug(f"[Auto PwrOn] Power ON {pwr_key} Linked Outlet {outlet['type']}:{_addr}")
                r = self.pwr.pwr_toggle(
                    outlet["type"],
                    _addr,
                    desired_state=True,
                    noff=outlet.get("noff", True) if outlet["type"].upper() == "GPIO" else True,
                )
                if isinstance(r, int) and r > 1:  # return is an error
                    r = False
                else:  # return is bool which is what we expect
                    if r:
                        self.pwr.data["defined"][o]["state"] = r
                        self.autopwr_wait = True
                        # self.pwr.pwr_get_outlets(upd_linked=True)
                    else:
                        # self.config.log_and_show(f"Error operating linked outlet {o}:{outlet['address']}", log=log.warning)
                        log.show(
                            f"Error operating linked outlet {o}:{outlet['address']}",
                            show=True,
                        )

    def exec_shell_cmd(self, cmd):
        """Determine if cmd is valid shell cmd and execute if so.

        Command will execute as the local user unless the user prefixed the
        cmd with sudo -u

        Arguments:
            cmd {str} -- Input provided by user

        Returns:
            True|None -- Return True if cmd was determined to be a bash cmd
        """
        s = subprocess
        c = cmd.replace("-u", "").replace("sudo", "").strip()
        p = "PATH=$PATH:/etc/ConsolePi/src/consolepi-commands && "
        # TODO if shutil.which(c.split()[0]):
        r = s.run(f"{p}which {c.split()[0]}", shell=True, stderr=s.PIPE, stdout=s.PIPE)
        if r.returncode == 0:
            try:
                if "sudo " not in cmd:
                    cmd = f'sudo -u {config.loc_user} bash -c "{p}{cmd}"'
                elif "sudo -u " not in cmd:
                    cmd = cmd.replace("sudo ", "")
                subprocess.run(cmd, shell=True)
                print("")
                input("Press Enter to Continue... ")
            except (KeyboardInterrupt, EOFError):
                log.show("Operation Aborted")
                print("")  # prevents header and prompt on same line in debug

            return True

    def wait_for_threads(self, name="init", timeout=10, thread_type="power"):
        """wait for parallel async threads to complete

        returns:
            bool: True if threads are still running indicating a timeout
                  None indicates no threads found ~ they have finished
        """
        start = time.perf_counter()
        do_log = False
        found = False
        while True:
            found = False
            for t in threading.enumerate():
                if name in t.name:
                    found = do_log = True
                    t.join(timeout - 1)

            if not found:
                if name == "init" and thread_type == "power":
                    if self.pwr and not self.pwr.data or not self.pwr.data.get("dli_power"):
                        self.pwr.dli_exists = False
                    self.pwr_init_complete = True
                if do_log:
                    log.info(
                        "[{0} {1} WAIT] {0} Threads have Completed, elapsed time: {2}".format(
                            name.strip("_").upper(),
                            thread_type.upper(),
                            round(time.perf_counter() - start, 2),
                        )
                    )
                break
            elif time.perf_counter() - start > timeout:
                log.error(
                    "[{0} {1} WAIT] Timeout Waiting for {0} Threads to Complete, elapsed time: {2}".format(
                        name.strip("_").upper(),
                        thread_type.upper(),
                        round(time.perf_counter() - start, 2),
                    ),
                    show=True,
                )
                return True

    # TODO REMOVE - Deprecated
    def launch_shell(self):
        iam = config.loc_user
        os.system(
            'sudo -u {0} echo PS1=\\"\\\033[1\;36mconsolepi-menu\\\033[0m:\\\w\\\$ \\" >/tmp/prompt && '  # NoQA
            'echo alias consolepi-menu=\\"exit\\" >>/tmp/prompt &&'
            "echo PATH=$PATH:/etc/ConsolePi/src/consolepi-commands >>/tmp/prompt && "
            'alias consolepi-menu=\\"exit\\" >>/tmp/prompt && '
            "echo \"launching local shell, 'exit' to return to menu\" &&"
            "sudo -u {0} bash -rcfile /tmp/prompt ; rm /tmp/prompt".format(iam)
        )

    def outlet_update(self, upd_linked=False, refresh=False, key="defined", outlets=None):
        """
        Called by consolepi-menu refresh and exec_auto_pwron (to update outlets in menu)
        """
        pwr = self.pwr
        if config.power:
            outlets = pwr.data if outlets is None else outlets
            if not self.pwr_init_complete or refresh:
                _outlets = pwr.pwr_get_outlets(
                    outlet_data=outlets.get("defined", {}),
                    upd_linked=upd_linked,
                    failures=outlets.get("failures", {}),
                )
                pwr.data = _outlets
            else:
                _outlets = outlets

            if key in _outlets:
                return _outlets[key]
            else:
                msg = f'Invalid key ({key}) passed to outlet_update. Returning "defined"'
                log.error(msg, show=True)
                return _outlets["defined"]

    def gen_copy_key(self, rem_data=None):
        """Generate public ssh key and distribute to remote ConsolePis

        Keyword Arguments:
            rem_data {tuple or list of tuples} -- each tuple should have 3 items
            0: hostname of remote, 1: rem_ip, 3: rem_user    (default: {None})

        Returns:
            {list} -- list of any errors reported, could be informational
        """
        hostname = self.local.hostname
        loc_user = self.local.user
        loc_home = self.local.loc_home

        # -- generate local key file if it doesn't exist
        # TODO pathlib
        if not os.path.isfile(loc_home + "/.ssh/id_rsa"):
            print("\nNo Local ssh cert found, generating...\n")
            utils.do_shell_cmd(
                f'sudo -u {loc_user} ssh-keygen -m pem -t rsa -C "{loc_user}@{hostname}"',
                timeout=360,
            )

        # -- copy keys to remote(s)
        if not isinstance(rem_data, list):
            rem_data = [rem_data]
        return_list = []
        for _rem in rem_data:
            rem, rem_ip, rem_user = _rem
            print(
                self.menu.format_line(
                    "{{magenta}}Attempting to copy ssh cert to " + rem + "{{norm}}"
                ).text
            )
            if not utils.is_reachable(rem_ip, 22, timeout=5, silent=True):
                return_list.append(f"{rem}: is not reachable... Skipped")
            else:
                ret = utils.do_shell_cmd(
                    f"sudo -u {loc_user} ssh-copy-id {rem_user}@{rem_ip}", timeout=60  # 360
                )
                if ret is not None:
                    return_list.append("{}: {}".format(rem, ret))
        return return_list

    def show_adapter_details(self, adapters):
        for a in adapters:
            print(f' --- Details For {a.replace("/dev/", "")} --- ')
            for k in sorted(adapters[a]["udev"].keys()):
                print(f'{k}: {adapters[a]["udev"][k]}')
            print("")
            # this_ser2net = config.ser2net_conf.get(a, {})
            # print(f"ser2net config: {this_ser2net.get('line', '!! Not Found !!')}")
            print(f'ser2net config: {adapters[a]["config"].get("line", "Not Defined")}')

        input("\nPress Enter To Continue\n")

    # ------ // EXECUTE MENU SELECTIONS \\ ------ #
    def menu_exec(self, choice, menu_actions, calling_menu="main_menu"):
        """Execute Menu Selection.  This method needs to be overhauled.

        The ConsolePiAction object defined but not used in __init__ is part of the plan for overhaul
        menu will build instance of the object for each selection. That will be used to determine what
        action to perform and what to do after etc.
        """
        pwr = self.pwr

        if not config.debug and calling_menu not in ["dli_menu", "power_menu"]:
            os.system("clear")

        if not choice.lower or choice.lower in menu_actions and menu_actions[choice.lower] is None:
            # They just hit return with no input
            (
                self.menu.rows,
                self.menu.cols,
            ) = utils.get_tty_size()  # re-calc tty size in case they've adjusted the window
            return

        else:
            ch = choice.lower
            try:  # Invalid Selection, Keyboard Interupt
                if isinstance(menu_actions[ch], dict):
                    if menu_actions[ch].get("cmd"):
                        # TimeStamp for picocom session log file if defined
                        menu_actions[ch]["cmd"] = menu_actions[ch]["cmd"].replace(
                            "{{timestamp}}", time.strftime("%F_%H.%M")
                        )

                        # -- // AUTO POWER ON LINKED OUTLETS \\ --
                        if config.power and "pwr_key" in menu_actions[ch]:
                            self.exec_auto_pwron(menu_actions[ch]["pwr_key"])

                        # -- // Print pre-connect messsage if provided \\ --
                        if menu_actions[ch].get("pre_msg"):
                            print(menu_actions[ch]["pre_msg"])
                            c = menu_actions[ch].get("cmd")
                            if (
                                calling_menu != "rename_menu"
                                and "/dev/" in c
                                or "telnet" in c.lower()
                            ):
                                print(self.menu.tty)

                        # --// execute the command \\--
                        try:
                            _error = None
                            if "exec_kwargs" in menu_actions[ch]:
                                c = menu_actions[ch]["cmd"]
                                _error = utils.do_shell_cmd(c, **menu_actions[ch]["exec_kwargs"])
                                if _error and self.autopwr_wait:
                                    # TODO simplify this after moving to action object
                                    _h = None
                                    _method = "ssh -t" if "ssh" in c else "telnet"
                                    if "ssh" in _method:
                                        _h = c.split(f"{_method} ")[1].split(" -p")[0].split("@")[1]
                                        _p = int(c.split("-p ")[1])
                                    elif _method == "telnet":
                                        c_list = c.split()
                                        _h = c_list[-2]
                                        _p = int(c_list[-1])

                                    def wait_for_boot():
                                        while True:
                                            try:
                                                if utils.is_reachable(_h, _p, silent=True):
                                                    break
                                                else:
                                                    time.sleep(3)
                                            except (KeyboardInterrupt, EOFError):
                                                self.autopwr_wait = False
                                                log.show("Connection Aborted")
                                                break

                                    if _h:
                                        print(
                                            "\nInitial Attempt Failed, but host is linked to an outlet that was"
                                        )
                                        print("off. Host may still be booting\n")
                                        utils.spinner(
                                            f"Waiting for {_h} to boot, CTRL-C to Abort",
                                            wait_for_boot,
                                        )
                                        if self.autopwr_wait:
                                            _error = utils.do_shell_cmd(
                                                c, **menu_actions[ch]["exec_kwargs"]
                                            )
                                            self.autopwr_wait = False
                            else:
                                c = shlex.split(menu_actions[ch]["cmd"])
                                result = subprocess.run(c, stderr=subprocess.PIPE)
                                _stderr = result.stderr.decode("UTF-8")
                                if _stderr or result.returncode == 1:
                                    _error = utils.error_handler(c, _stderr)

                            if _error:
                                log.show(_error)

                            # -- // resize the terminal to handle serial connections that jack the terminal size \\ --
                            if (
                                "picocom" in menu_actions[ch]["cmd"]
                                or "telnet" in menu_actions[ch]["cmd"]
                            ):
                                os.system("/etc/ConsolePi/src/consolepi-commands/resize >/dev/null")

                        except (KeyboardInterrupt, EOFError):
                            log.show("Aborted last command based on user input")

                    elif "function" in menu_actions[ch]:
                        args = menu_actions[ch]["args"] if "args" in menu_actions[ch] else []
                        kwargs = menu_actions[ch]["kwargs"] if "kwargs" in menu_actions[ch] else {}
                        confirmed, spin_text, name = self.confirm_and_spin(
                            menu_actions[ch], *args, **kwargs
                        )
                        if confirmed:
                            # update kwargs with name from confirm_and_spin method
                            if menu_actions[ch]["function"].__name__ == "pwr_rename":
                                kwargs["name"] = name

                            # // -- CALL THE FUNCTION \\--
                            if spin_text:  # start spinner if spin_text set by confirm_and_spin
                                with Halo(text=spin_text, spinner="dots2"):
                                    response = menu_actions[ch]["function"](*args, **kwargs)
                            else:  # no spinner
                                response = menu_actions[ch]["function"](*args, **kwargs)

                            # --// Power Menus \\--
                            if calling_menu in ["power_menu", "dli_menu"]:
                                if menu_actions[ch]["function"].__name__ == "pwr_all":
                                    with Halo(text="Refreshing Outlet States", spinner="dots"):
                                        self.outlet_update(
                                            refresh=True, upd_linked=True
                                        )  # TODO can I move this to Outlets Class
                                else:
                                    _grp = menu_actions[ch]["key"]
                                    _type = menu_actions[ch]["args"][0]
                                    _addr = menu_actions[ch]["args"][1]
                                    # --// EVAL responses for dli outlets \\--
                                    if _type == "dli":
                                        host_short = utils.get_host_short(_addr)
                                        _port = menu_actions[ch]["kwargs"]["port"]
                                        # --// Operations performed on ALL outlets \\--
                                        if isinstance(response, bool) and _port is not None:
                                            if (
                                                menu_actions[ch]["function"].__name__
                                                == "pwr_toggle"
                                            ):
                                                self.spin.start(
                                                    "Request Sent, Refreshing Outlet States"
                                                )
                                                # threading.Thread(target=self.get_dli_outlets,
                                                # kwargs={'upd_linked': True, 'refresh': True}, name='pwr_toggle_refresh').start()
                                                upd_linked = (
                                                    True if calling_menu == "power_menu" else False
                                                )  # else dli_menu
                                                threading.Thread(
                                                    target=self.outlet_update,
                                                    kwargs={
                                                        "upd_linked": upd_linked,
                                                        "refresh": True,
                                                    },
                                                    name="pwr_toggle_refresh",
                                                ).start()
                                                if _grp in pwr.data["defined"]:
                                                    pwr.data["defined"][_grp]["is_on"][_port][
                                                        "state"
                                                    ] = response
                                                elif _port != "all":
                                                    pwr.data["dli_power"][_addr][_port][
                                                        "state"
                                                    ] = response
                                                else:  # dli toggle all
                                                    for t in threading.enumerate():
                                                        if t.name == "pwr_toggle_refresh":
                                                            t.join()  # if refresh thread is running join ~
                                                            # wait for it to complete.
                                                            # TODO Don't think this works or below
                                                            # wouldn't have been necessary.

                                                            # toggle all returns True (ON) or False (OFF) if command
                                                            # successfully sent.  In reality the ports
                                                            # may not be in the  state yet, but dli is working it.
                                                            # Update menu items to reflect end state
                                                            for p in pwr.data["dli_power"][_addr]:
                                                                pwr.data["dli_power"][_addr][p][
                                                                    "state"
                                                                ] = response
                                                            break
                                                self.spin.stop()
                                            # Cycle operation returns False if outlet is off, only valid on powered outlets
                                            elif (
                                                menu_actions[ch]["function"].__name__ == "pwr_cycle"
                                                and not response
                                            ):
                                                log.show(
                                                    f"{host_short} Port {_port} is Off.  Cycle is not valid"
                                                )
                                            elif (
                                                menu_actions[ch]["function"].__name__
                                                == "pwr_rename"
                                            ):
                                                if response:
                                                    _name = pwr._dli[_addr].name(_port)
                                                    if _grp in pwr.data.get("defined", {}):
                                                        pwr.data["defined"][_grp]["is_on"][_port][
                                                            "name"
                                                        ] = _name
                                                    else:
                                                        threading.Thread(
                                                            target=self.outlet_update,
                                                            kwargs={
                                                                "upd_linked": True,
                                                                "refresh": True,
                                                            },
                                                            name="pwr_rename_refresh",
                                                        ).start()
                                                    pwr.data["dli_power"][_addr][_port][
                                                        "name"
                                                    ] = _name
                                        # --// str responses are errors append to error_msgs \\--
                                        # TODO refactor response to use new cpi.response(...)
                                        elif isinstance(response, str) and _port is not None:
                                            log.show(response)
                                        # --// Can Remove After Refactoring all responses to bool or str \\--
                                        elif isinstance(response, int):
                                            if (
                                                menu_actions[ch]["function"].__name__ == "pwr_cycle"
                                                and _port == "all"
                                            ):
                                                if response != 200:
                                                    log.show(
                                                        "Error Response Returned {}".format(
                                                            response
                                                        )
                                                    )
                                            # This is a catch as for the most part I've tried to refactor so the pwr library
                                            # returns port state on success (True/False)
                                            else:
                                                if response in [200, 204]:
                                                    log.show(
                                                        "DEV NOTE: check pwr library ret=200 or 204"
                                                    )
                                                else:
                                                    _action = menu_actions[ch]["function"].__name__
                                                    log.show(
                                                        f"Error returned from dli {host_short} when "
                                                        f"attempting to {_action} port {_port}"
                                                    )
                                    # --// EVAL responses for espHome outlets \\--
                                    elif _type == "esphome":
                                        host_short = utils.get_host_short(_addr)
                                        _port = menu_actions[ch]["kwargs"]["port"]
                                        # --// Operations performed on ALL outlets \\--
                                        if isinstance(response, bool) and _port is not None:
                                            pwr.data["defined"][_grp]["is_on"][_port][
                                                "state"
                                            ] = response
                                            if (
                                                menu_actions[ch]["function"].__name__ == "pwr_cycle"
                                                and not response
                                            ):
                                                _msg = (
                                                    f"{_grp}({host_short})"
                                                    if _grp != host_short
                                                    else f"{_grp}"
                                                )
                                                if _msg != _port:
                                                    _msg = f"{_msg} Port {_port} is Off. Cycle is not valid"
                                                else:
                                                    _msg = f"{_msg} is Off. Cycle is not valid"
                                                log.show(_msg)
                                        elif isinstance(response, str) and _port is not None:
                                            log.show(response)

                                    # --// EVAL responses for GPIO and tasmota outlets \\--
                                    else:
                                        if menu_actions[ch]["function"].__name__ == "pwr_toggle":
                                            if _grp in pwr.data.get("defined", {}):
                                                if isinstance(response, bool):
                                                    pwr.data["defined"][_grp]["is_on"] = response
                                                else:
                                                    pwr.data["defined"][_grp]["errors"] = response
                                        elif (
                                            menu_actions[ch]["function"].__name__ == "pwr_cycle"
                                            and not response
                                        ):
                                            log.show(
                                                "Cycle is not valid for Outlets in the off state"
                                            )
                                        elif menu_actions[ch]["function"].__name__ == "pwr_rename":
                                            log.show(
                                                "rename not yet implemented for {} outlets".format(
                                                    _type
                                                )
                                            )
                            elif calling_menu in ["key_menu", "rename_menu"]:
                                if response:
                                    log.show(response)
                        else:  # not confirmed
                            log.show("Operation Aborted by User")
                elif menu_actions[ch].__name__ in ["power_menu", "dli_menu"]:
                    menu_actions[ch](calling_menu=calling_menu)
                else:  # the selection is a function / coroutine
                    # TODO may need to add inspect.iscoroutinefunction(func) if any of the options are async
                    menu_actions[ch]()
            except KeyError as e:
                if len(choice.orig) <= 2 or not self.exec_shell_cmd(choice.orig):
                    log.show(f"Invalid selection {e}, please try again.")
            except (KeyboardInterrupt, EOFError):
                log.show("Operation Aborted")
                print("")  # prevents header and prompt on same line in debug
        return True

    def confirm_and_spin(self, action_dict: dict, *args, **kwargs):
        """
        called by menu_exec.
        Collects user Confirmation if operation warrants it (Powering off or cycle outlets)
        and Generates appropriate spinner text

        returns tuple
            0: Bool False indicates user abort otherwise True should be returned
            1: str spinner_text used in menu_exec while function runs
            3: str name (for rename operation)
        """
        pwr = self.pwr
        menu = self.menu
        _func = action_dict["function"].__name__
        _off_str = "{{red}}OFF{{norm}}"
        _on_str = "{{green}}ON{{norm}}"
        _cycle_str = "{{red}}C{{green}}Y{{red}}C{{green}}L{{red}}E{{norm}}"
        _type = _addr = None
        to_state = kwargs.get("desired_state")
        if _func in ["pwr_toggle", "pwr_cycle", "pwr_rename"]:
            _type = args[0].lower()
            _addr = args[1]
            _grp = action_dict["key"]
            if _type == "dli":
                port = kwargs["port"]
                if not port == "all":
                    port_name = pwr.data["dli_power"][_addr][port]["name"]
                    to_state = not pwr.data["dli_power"][_addr][port]["state"]
            elif _type == "esphome":
                port = port_name = kwargs["port"]
                if not port == "all":
                    to_state = not pwr.data["defined"][_grp]["is_on"][port]["state"]
            else:
                port = f"{_type}:{_addr}"
                port_name = _grp
                to_state = not pwr.data["defined"][_grp]["is_on"]

        if _type == "dli" or _type == "tasmota" or _type == "esphome":
            host_short = utils.get_host_short(_addr)
        else:
            host_short = None

        prompt = spin_text = name = confirmed = None  # init
        if _func == "pwr_all":
            if kwargs["action"] == "cycle":
                prompt = "{} Power Cycle All Powered {} Outlets".format(
                    "" if _type is None else _type + ":" + host_short, _on_str
                )
                spin_text = "Cycling All{} Ports".format(
                    "" if _type is None else " " + _type + ":" + host_short
                )
            elif kwargs["action"] == "toggle":
                if not kwargs["desired_state"]:
                    prompt = "Power All{} Outlets {}".format(
                        "" if _type is None else " " + _type + ":" + host_short,
                        _off_str,
                    )
                spin_text = "Powering {} ALL{} Outlets".format(
                    menu.format_line(kwargs["desired_state"]).text,
                    "" if _type is None else _type + " :" + host_short,
                )
        elif _func == "pwr_toggle":
            if _type == "dli" and port == "all":
                prompt = "Power {} ALL {} Outlets".format(
                    _off_str if not to_state else _on_str, host_short
                )
            elif not to_state:
                if _type == "dli":
                    prompt = f"Power {_off_str} {host_short} Outlet {port}({port_name})"
                elif _type == "esphome":
                    prompt = f"Power {_off_str} {host_short} Outlet {port}"
                else:  # GPIO or TASMOTA
                    prompt = f"Power {_off_str} Outlet {_grp}({_type}:{_addr})"

            spin_text = "Powering {} {}Outlet{}".format(
                menu.format_line(to_state).text,
                "ALL " if port == "all" else "",
                "s" if port == "all" else "",
            )
        elif _func == "pwr_rename":
            try:
                name = input(
                    "New name for{} Outlet {}: ".format(
                        " " + host_short if host_short else "",
                        port_name if not _type == "dli" else str(port) + "(" + port_name + ")",
                    )
                )
            except (KeyboardInterrupt, EOFError):
                name = None
                confirmed = False
                print("")  # So header doesn't print on same line as aborted prompt when DEBUG is on
            if name:
                old_name = port_name
                _rnm_str = "{red}{old_name}{norm} --> {green}{name}{norm}".format(
                    red="{{red}}",
                    green="{{green}}",
                    norm="{{norm}}",
                    old_name=old_name,
                    name=name,
                )
                if _type == "dli":
                    prompt = "Rename {} Outlet {}: {} ".format(host_short, port, _rnm_str)
                else:
                    old_name = _grp
                    prompt = "Rename Outlet {}:{} {} ".format(_type, host_short, _rnm_str)

                spin_text = "Renaming Port"

        elif _func == "pwr_cycle":
            if _type == "dli" and port == "all":
                prompt = "Power {} ALL {} Outlets".format(_cycle_str, host_short)
            elif _type == "dli":
                prompt = "Cycle Power on {} Outlet {}({})".format(host_short, port, port_name)
            elif _type == "esphome":
                _msg = f"{_grp}({host_short})" if _grp != host_short else f"{_grp}"
                prompt = f"Cycle Power on {_msg} Outlet {port}"
            else:  # GPIO or TASMOTA
                prompt = "Cycle Power on Outlet {}({})".format(port_name, port)
            spin_text = "Cycling {}Outlet{}".format(
                "ALL " if port == "all" else "", "s" if port == "all" else ""
            )

        if prompt:
            prompt = menu.format_line(prompt).text
            confirmed = confirmed if confirmed is not None else utils.user_input_bool(prompt)
        else:
            if _func != "pwr_rename":
                confirmed = True

        return confirmed, spin_text, name
