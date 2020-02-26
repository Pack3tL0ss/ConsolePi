#!/etc/ConsolePi/venv/bin/python3

import subprocess
import shlex
import time
import psutil
import os
import sys
import stat
import grp
import json
import threading
import socket

try:
    loc_user = os.getlogin()
except Exception:
    loc_user = os.getenv('SUDO_USER', os.getenv('USER'))


class Utils():
    def __init__(self):
        print(__name__)
        # self.config = cpi.config

    def user_input_bool(self, question):
        '''Ask User Y/N Question require Y/N answer

        Error and reprompt if user's response is not valid
        Appends '? (y/n): ' to question/prompt provided

        Params:
            question:str, The Question to ask
        Returns:
            answer:bool, Users Response yes=True
        '''
        valid_answer = ['yes', 'y', 'no', 'n']
        try:
            answer = input(question + '? (y/n): ').strip()
        except (KeyboardInterrupt, EOFError):
            print('')  # prevents header printing on same line when in debug
            return False
        while answer.lower() not in valid_answer:
            if answer != '':
                print(f" \033[1;33m!!\033[0m Invalid Response \'{answer}\' Valid Responses: {valid_answer}")
            answer = input(question + '? (y/n): ').strip()
        if answer[0].lower() == "y":
            return True
        else:
            return False

    def kill_hung_session(self, dev):
        '''Kill hung picocom session

        If picocom process still active and user is diconnected from SSH
        it makes the device unavailable.  When error_handler determines that is the case
        This function is called giving the user the option to kill it.
        '''
        def find_procs_by_name(name, dev):
            '''Return the pid of process matching name, where dev was referenced in the cmdline options

            Params:
                name:str, name of process to find
                dev:str, dev which needs to be in the cmdline arguments for the process

            Returns:
                The pid of the matching process
            '''
            ppid = None
            for p in psutil.process_iter(attrs=["name", "cmdline"]):
                if name == p.info['name'] and dev in p.info['cmdline']:
                    ppid = p.pid  # if p.ppid() == 1 else p.ppid()
                    break
            return ppid

        def terminate_process(pid):
            '''send terminate, then kill if still alive to pid

            params: pid of process to be killed
            '''
            p = psutil.Process(pid)
            for x in range(0, 2):
                p.terminate()
                if p.status() != 'Terminated':
                    p.kill()
                else:
                    break

        ppid = find_procs_by_name('picocom', dev)
        retry = 0
        msg = '\n{} appears to be in use (may be a previous hung session).\nDo you want to Terminate the existing session'.format(
                                                                                                        dev.replace('/dev/', ''))
        if ppid is not None and self.user_input_bool(msg):
            while ppid is not None and retry < 3:
                print('An Existing session is already established to {}.  Terminating process {}'.format(
                                                                        dev.replace('/dev/', ''), ppid))
                try:
                    terminate_process(ppid)
                    time.sleep(3)
                    ppid = find_procs_by_name('picocom', dev)
                except PermissionError:
                    print('PermissionError: session is locked by user with higher priv. can not kill')
                    break
                except psutil.AccessDenied:
                    print('AccessDenied: Session is locked by user with higher priv. can not kill')
                    break
                except psutil.NoSuchProcess:
                    ppid = find_procs_by_name('picocom', dev)
                retry += 1
        return ppid is None

    def error_handler(self, cmd, stderr, user=loc_user):
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
        if stderr and 'FATAL: cannot lock /dev/' not in stderr:
            # Handle key change Error
            if 'WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!' in stderr:
                print('@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n'
                      '@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @\n'
                      '@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n'
                      'IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!\n'
                      'Someone could be eavesdropping on you right now (man-in-the-middle attack)!\n'
                      'It is also possible that a host key has just been changed.'
                      )
                while True:
                    try:
                        choice = input('\nDo you want to remove the old host key and re-attempt the connection (y/n)? ')
                        if choice.lower() in ['y', 'yes']:
                            _cmd = shlex.split(stderr.replace('\r', '').split('remove with:\n')[1].split('\n')[0].replace('ERROR:   ', ''))  # NoQA
                            _cmd = shlex.split('sudo -u {}'.format(user)) + _cmd
                            subprocess.run(_cmd)
                            print('\n')
                            subprocess.run(cmd)
                            break
                        elif choice.lower() in ['n', 'no']:
                            break
                        else:
                            print("\n!!! Invalid selection {} please try again.\n".format(choice))
                    except (KeyboardInterrupt, EOFError):
                        print('')
                        return 'Aborted last command based on user input'
                    except ValueError:
                        print("\n!! Invalid selection {} please try again.\n".format(choice))
            elif 'All keys were skipped because they already exist on the remote system' in stderr:
                print('Skipped: key already exists')
            elif '/usr/bin/ssh-copy-id: INFO:' in stderr:
                if 'sh: 1:' in stderr:
                    return ''.join(stderr.split('sh: 1:')[1:]).strip()
            # ssh cipher suite errors
            elif 'no matching cipher found. Their offer:' in stderr:
                print('Connection Error: {}\n'.format(stderr))
                cipher = stderr.split('offer:')[1].strip().split(',')
                aes_cipher = [c for c in cipher if 'aes' in c]
                if aes_cipher:
                    cipher = aes_cipher[-1]
                else:
                    cipher = cipher[-1]
                cmd += ['-c', cipher]

                print('Reattempting Connection using cipher {}'.format(cipher))
                r = subprocess.run(cmd)
                if r.returncode:
                    return 'Error on Retry Attempt'  # TODO better way... handle banners... paramiko?
            else:
                return stderr   # return value that was passed in

        # Handle hung sessions always returncode=1 doesn't always present stderr
        elif cmd[0] == 'picocom':
            if self.kill_hung_session(cmd[1]):
                subprocess.run(cmd)
            else:
                return 'User Abort or Failure to kill existing session to {}'.format(cmd[1].replace('/dev/', ''))
    # subprocess.run(['/bin/bash', '-c', cmd])
    # if not return_stdout:
    #     response = subprocess.run(['/bin/bash', '-c', cmd], stderr=subprocess.PIPE)
    # else:
    #     response = subprocess.run(['/bin/bash', '-c', cmd], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    #     _stdout = response.stdout.decode('UTF-8').strip()
    # _stderr = response.stderr.decode('UTF-8')
    # if do_print:
    #     print(_stderr)

    def shell_output_cleaner(self, output):
        strip_words = [
            '/usr/bin/ssh-copy-id: '
        ]
        return ''.join([x.replace(i, '') for x in self.listify(output) for i in strip_words])

    def do_shell_cmd(self, cmd, do_print=False, handle_errors=True, return_stdout=False, timeout=5):
        '''Runs shell cmd (i.e. ssh), sends any stderr output to error_handler.

        params:
        cmd: str or list of commands/args sent to subprocess
        handle_errors bool: default True sends stderr to error_handler
        return_stdout bool: run with shell and return tuple returncode, stdout, stderr

        returns:
        by default there is no return unless there is an error
        return_stdout=True will return tuple returncode, stdout, stderr
        '''
        if not return_stdout:
            if isinstance(cmd, str):
                cmd = shlex.split(cmd)
            proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
            err = proc.communicate(timeout=timeout)[1]
            if err is not None and do_print:
                print(self.shell_output_cleaner(err), file=sys.stdout)
            # if proc.returncode != 0 and handle_errors:
            if err and handle_errors:
                err = self.error_handler(cmd, err)

            proc.wait()
            return err
        else:  # cmd should be string as entered in bash
            res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, universal_newlines=True)
            return res.returncode, res.stdout.strip(), res.stderr.strip()

    def check_install_apt_pkg(self, pkg: str, verify_cmd=None):
        verify_cmd = 'which {}'.format(pkg) if verify_cmd is None else verify_cmd

        def verify(verify_cmd):
            if isinstance(verify_cmd, str):
                verify_cmd = shlex.split(verify_cmd)
            r = subprocess.run(verify_cmd,
                               stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            return r.returncode == 0

        if not verify(verify_cmd):
            resp = subprocess.run(['/bin/bash', '-c', 'apt install -y {}'.format(pkg)],
                                  stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            if resp != 0:
                if verify(verify_cmd):
                    return (0, '{} Install Success'.format(pkg))
        else:
            return (0, 'Already Installed')

        return (resp.returncode, resp.stdout.decode('UTF-8') if resp.returncode == 0 else resp.stderr.decode('UTF-8'))

    def set_perm(self, file):
        gid = grp.getgrnam("consolepi").gr_gid
        if os.geteuid() == 0:
            os.chown(file, 0, gid)
            os.chmod(file, (stat.S_IWGRP + stat.S_IRGRP + stat.S_IWRITE + stat.S_IREAD))

    def json_print(self, obj):
        print(json.dumps(obj, indent=4, sort_keys=True))

    def format_eof(self, file):
        cmd = 'sed -i -e :a -e {} {}'.format('\'/^\\n*$/{$d;N;};/\\n$/ba\'', file)
        return self.do_shell_cmd(cmd, handle_errors=False)

    def append_to_file(self, file, line):
        '''Determine if last line of file includes a newline character
        write line provided on the next line

        params:
            file: file to write to
            line: line to write
        '''
        # strip any blank lines from end of file and remove LF
        self.format_eof(file)

        # determine if last line in file has LF
        with open(file) as f:
            _lines = f.readlines()
            _last = _lines[-1]

        # prepend newline if last line of file lacks it to prevent appending to that line
        if '\n' not in _last:
            line = '\n{}'.format(line)

        with open(file, 'a+') as f:
            f.write(line)

    def get_picocom_ver(self):
        '''return version of picocom'''
        x = subprocess.run('picocom  --help | head -1 | cut -dv -f2', stdout=subprocess.PIPE, shell=True)
        if x.returncode == 0:
            return float(x.stdout.decode('UTF-8').strip())

    def verify_telnet_installed(self, host_dict):
        '''Install TELNET pkg if not already and TELNET hosts are defined

        params: host_dict.  The dict with manually defined host details
        return: True if not needed by any defined hosts, or is installed.
            returns are not currently used.
        '''
        def telnet_install_thread(host_dict=host_dict):
            if 'telnet' not in host_dict['_methods']:
                return True

            r = self.check_install_apt_pkg('telnet')
            if r[0] != 0:
                # apt seems to return an error even when success
                r = subprocess.run(['which', 'telnet'], capture_output=True).returncode
                if r != 0:
                    return False
            else:
                return True

        threading.Thread(target=telnet_install_thread, name='telnet_install_verify').start()

    def get_tty_size(self):
        size = subprocess.run(['stty', 'size'], stdout=subprocess.PIPE)
        rows, cols = size.stdout.decode('UTF-8').split()
        return int(rows), int(cols)

    # TODO check if using kwarg sort added to fix re-order of error_msgs
    def unique(self, _list, sort=False):
        out = []
        [out.append(i) for i in _list if i not in out and i is not None]
        return out if not sort else sorted(out)

    def is_reachable(self, host, port, timeout=3):
        s = socket.socket()
        try:
            s.settimeout(timeout)
            s.connect((host, port))
            _reachable = True
        except Exception as e:
            print("something's wrong with %s:%d. Exception is %s" % (host, port, e))
            _reachable = False
        finally:
            s.close()
        return _reachable

    def format_dev(self, dev, hosts=None, udev=None, with_path=False):
        '''Properly format devs found in user created JSON

        params:
            dev(str or list of str): i.e. '/dev/idf_switch_1'
            with_path(bool):  strips any prefix if False
                            adds /dev/ or /host/ if True

        returns:
            list of formatted devs
        '''
        if udev and not hosts:
            data = udev
            pfx = '/dev/'
            pfx_else = '/host/'
        else:
            data = hosts.get('_host_list', [])
            pfx = '/host/'
            pfx_else = '/dev/'

        dev = [dev] if not isinstance(dev, (list, dict)) else dev
        if with_path:
            for d in dev:
                if '/' not in d:
                    _pfx = pfx if pfx + d in data else pfx_else
                    if isinstance(dev, list):  # dli represented by dict dev: port or port list
                        dev[dev.index(d)] = _pfx + d
                    else:
                        dev[_pfx + d] = dev.pop(d)
            return dev
        else:  # return dev list with prefixes stripped
            return [d.split('/')[-1] for d in dev] if isinstance(dev, list) \
                else {d.split('/')[-1]: dev[d] for d in dev}

    def valid_file(self, file):
        return os.path.isfile(file) and os.stat(file).st_size > 0

    def listify(self, var):
        return var if isinstance(var, list) or var is None else [var]

    def get_host_short(self, host):
        '''Extract hostname from fqdn

        Arguments:
            host {str} -- hostname. If ip address is provided it's returned as is

        Returns:
            str -- host_short (lab1.example.com becomes lab1)
        '''
        return host.split('.')[0] if '.' in host and not host.split('.')[0].isdigit() else host
