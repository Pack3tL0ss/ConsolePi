#!/etc/ConsolePi/venv/bin/python

# import ast
import json
import os
# import re
import readline # NoQA - allows input to accept backspace
import shlex
import subprocess
import sys
import re
import time
import threading
from collections import OrderedDict as od
from halo import Halo

# --// ConsolePi imports \\--
sys.path.insert(0, '/etc/ConsolePi/src/pypkg')
from consolepi import ConsolePi  # NoQA
from consolepi import Rename  # NoQA
# from consolepi.gdrive import GoogleDrive # <-- hidden import burried in refresh method of ConsolePiMenu Class

MIN_WIDTH = 55
MAX_COLS = 5


class ConsolePiMenu(Rename):

    def __init__(self):
        self.cpi = ConsolePi()
        self.go = True
        self.debug = self.cpi.config.cfg.get('debug', False)
        self.spin = Halo(spinner='dots')
        self.states = {
            True: '{{green}}ON{{norm}}',
            False: '{{red}}OFF{{norm}}'
        }
        self.error_msgs = []
        self.ignored_errors = [
            re.compile('Connection to .* closed')
        ]
        self.log_sym_2bang = '\033[1;33m!!\033[0m'
        if sys.stdin.isatty():
            self.rows, self.cols = self.cpi.utils.get_tty_size()
        self.do_menu_load_warnings()
        self.display_con_settings = False
        self.menu_rows = 0  # Updated in menu_formatting
        self.menu_cols = 0
        super().__init__()

    def do_menu_load_warnings(self):
        '''Displays and logs warnings based on data collected/validated during menu load.'''
        if not self.cpi.config.root:
            self.cpi.config.log_and_show('Running without sudo privs ~ Results may vary!\n'
                                         'Use consolepi-menu to launch menu', logit=False)
        for adapters in [self.cpi.remotes.data[r].get('adapters', {}) for r in self.cpi.remotes.data]:
            if isinstance(adapters, list):
                _msg = 'You have remotes running older versions ~ older API schema.  You Should Upgrade those Remotes'
                self.cpi.config.log_and_show(_msg, log=self.cpi.config.log.warning)
                break

    # =======================
    #     MENUS FUNCTIONS
    # =======================
    def print_mlines(self, body, subs=None, header=None, subhead=None, footer=None, foot_opts=['x'], foot_fmt=None, col_pad=4,
                     force_cols=False, do_cols=True, do_format=True, by_tens=False):
        '''
        format and print current menu.

        build the content and in the calling method and pass into this function for format & printing
        params:
            body: a list of lists or list of strings, where each inner list is made up of text for each
                    menu-item in that logical section/group.
            subs: a list of sub-head lines that map to each inner body list.  This is the header for
                the specific logical grouping of menu-items. body and subs lists should be of = len
            header: The main Header text for the menu
            footer: an optional text string or list of strings to be added to the menu footer.
            foot_opts: {list} - list of 'strs' to match key from footer_options dict defined in 
                menu_formatting method.  Determines what menu options are displayed in footer.
                (defaults options: x. Exit)
            col_pad: how many spaces will be placed between horizontal menu sections.
            force_cols: By default the menu will print as a single column, with force_cols=True
                    it will bypass the vertical fit test - print section in cols horizontally
            foot_fmt: {dict} - Optional formatting dict.  top-level should be designated keywork that
                specifies supported formatting options (_rjust = right justify).  2nd level should be
                the footer_options key to match on where the value = the text.  Example:
                foot_fmt={'_rjust': {'back': 'menu # alone will toggle the port'}} ~ will result in 
                b.  Back                                            menu # alone will toggle the port
                where 'b.  Back' comes from the pre-defined foot_opts dict.
            do_cols: bool, If specified and set to False will bypass horizontal column printing and
                    resulting in everything printing vertically on one screen
            do_format: bool, Only applies to sub_head auto formatting.  If specified and set to False
                    will not perform formatting on sub-menu text.
                    Auto formatting results in '------- text -------' (width of section)
            by_tens: Will start each section @ 1, 11, 21, 31... unless the section is greater than 10
                    menu_action statements should match accordingly

        '''
        cpi = self.cpi
        utils = cpi.utils
        config = cpi.config
        line_dict = od({'header': {'lines': header}, 'body': {'sections': [], 'rows': [],
                        'width': []}, 'footer': {'lines': footer}})
        '''
        Determine header and footer length used to determine if we can print with
        a single column
        '''
        subs = utils.listify(subs)
        subhead = utils.listify(subhead)
        if subhead:
            subhead = [f"{' ' + line if not line.startswith(' ') else line}" for line in subhead]
            subhead.insert(0, '')
            if not subs:
                subhead.append('')

        head_len = len(self.menu_formatting('header', text=header, do_print=False)[0])
        if subhead:
            head_len += len(subhead)
        elif not subs:
            head_len += 1  # blank line added during print

        # TODO REMOVE TEMP during re-factor
        if isinstance(footer, dict):
            foot_lines = self.menu_formatting('footer', footer=footer, do_print=False)[0]
            foot_len = len(foot_lines)
            line_dict['footer']['lines'] = foot_lines
        else:
            foot_len = len(self.menu_formatting('footer', text=footer, do_print=False)[0])
        '''
        generate list for each sections where each line is padded to width of longest line
        collect width of longest line and # of rows/menu-entries for each section

        All of this is used to format the header/footer width and to ensure consistent formatting
        during print of multiple columns
        '''
        # if str was passed place in list to iterate over
        if isinstance(body, str):
            body = [body]

        # ensure body is a list of lists for mapping with list of subs
        body = [body] if len(body) >= 1 and isinstance(body[0], str) else body

        # if subs is not None:
        #     subs = [subs] if not isinstance(subs, list) else subs

        i = 0
        item = start = 1
        for _section in body:
            if by_tens and i > 0:
                item = start + 10 if item <= start + 10 else item
                start += 10
            _item_list, _max_width = self.menu_formatting('body', text=_section,
                                                          sub=subs if subs is None else subs[i],
                                                          index=item, do_print=False, do_format=do_format)
            line_dict['body']['width'].append(_max_width)
            line_dict['body']['rows'].append(len(_item_list))
            line_dict['body']['sections'].append(_item_list)
            item = item + len(_section)
            i += 1

        '''
        print multiple sections vertically - determine best cut point to start next column
        '''
        _rows = line_dict['body']['rows']
        tot_body_rows = sum(_rows)  # The # of rows to be printed
        # TODO what if rows for 1 section is greater than term rows
        tty_body_avail = (self.rows - head_len - foot_len)
        _begin = 0
        _end = 1
        _iter_start_stop = []
        _pass = 0
        # # -- won't fit in a single column calc sections we can put in the column
        # # #if not tot_body_rows < tty_body_avail:   # Force at least 2 cols while testing
        _r = []
        [_r.append(r) for r in _rows if r not in _r]  # deteremine if all sections are of equal size (common for dli)
        if len(_r) == 1 or force_cols:
            for x in range(0, len(line_dict['body']['sections'])):
                _iter_start_stop.append([x, x + 1])
                # _tot_width.append(sum(body['width'][x:x + 1]) + (col_pad * (cols - 1)))
                next
        else:
            while True:
                r = sum(_rows[_begin:_end])
                if not r >= tty_body_avail and not r >= tot_body_rows / 2:
                    _end += 1
                else:
                    if r > tty_body_avail and _end > 1:
                        if _begin != _end - 1:  # NoQA Indicates the individual section is > then avail rows so give up until paging implemented
                            _end = _end - 1
                    if not _end == (len(_rows)):
                        _iter_start_stop.append([_begin, _end])
                        _begin = _end
                        _end = _begin + 1

                if _end == (len(_rows)):
                    _iter_start_stop.append([_begin, _end])
                    break
                if _pass > len(_rows) + 20:  # should not hit this anymore
                    config.log_and_show(f'menu formatter exceeded {len(_rows) + 20} passses and gave up!!!')
                    break
                _pass += 1

        sections = []
        _tot_width = []
        for _i in _iter_start_stop:
            this_max_width = max(line_dict['body']['width'][_i[0]:_i[1]])
            _tot_width.append(this_max_width)
            _column_list = []
            for _s in line_dict['body']['sections'][_i[0]:_i[1]]:
                for _line in _s:
                    _fnl_line = '{:{_len}}'.format(_line, _len=this_max_width)
                    _s[_s.index(_line)] = _fnl_line
                _column_list += _s
            sections.append(_column_list)

        line_dict['body']['sections'] = sections
        '''
        set the initial # of columns
        '''
        body = line_dict['body']
        cols = len(body['sections']) if len(body['sections']) <= MAX_COLS else MAX_COLS
        if not force_cols:  # TODO OK to remove and refactor tot_1_col_len is _tot_body_rows calculated above
            # TODO tot_1_col_len is inaccurate
            tot_1_col_len = sum(line_dict['body']['rows']) + len(line_dict['body']['rows']) \
                            + head_len + foot_len
            cols = 1 if not do_cols or tot_1_col_len < self.rows else cols

        # -- if any footer or subhead lines are longer adjust _tot_width (which is the longest line from any section)
        # TODO This is likely wrong if there are formatters {{}} in the footer, the return should be fully formmated
        foot = self.menu_formatting('footer', text=line_dict['footer']['lines'], do_print=False)[0]
        _foot_width = [len(line) for line in foot]
        if isinstance(_tot_width, int):
            _tot_width = [_tot_width]
        _tot_width = max(_foot_width + _tot_width)

        if subhead:
            _subhead_width = [len(line) for line in subhead]
            _tot_width = max(_subhead_width) if max(_subhead_width) > _tot_width else _tot_width

        if MIN_WIDTH < self.cols:
            _tot_width = MIN_WIDTH if _tot_width < MIN_WIDTH else _tot_width

        # -- // Generate Final Body Rows \\ --
        _final_rows = []
        pad = ' ' * col_pad

        _final_rows = body['sections'][0]
        for s in body['sections']:
            if body['sections'].index(s) == 0:
                continue
            else:
                if len(_final_rows) > len(s):
                    for _spaces in range(len(_final_rows) - len(s)):
                        s.append(' ' * len(s[0]))
                elif len(s) > len(_final_rows):
                    for _spaces in range(len(s) - len(_final_rows)):
                        _final_rows.append(' ' * len(_final_rows[0]))
                _final_rows = [a + pad + b for a, b in zip(_final_rows, s)]

        # --// PRINT MENU \\--
        _tot_width = len(_final_rows[0]) if len(_final_rows[0]) > _tot_width else _tot_width
        self.menu_cols = _tot_width  # FOR DEBUGGING
        self.menu_formatting('header', text=header, width=_tot_width, do_print=True)
        if subhead:
            for line in subhead:
                print(line)
                self.menu_rows += 1
        elif not subs:  # TODO remove auto first blank line from subhead/subs and have formatter always do 1st blank line
            print('')  # Add blank line after header if no subhead and no subs
            self.menu_rows += 1
        for row in _final_rows:   # TODO print here, also can print in the formatter method
            print(row)
            self.menu_rows += 1

        # TODO REMOVE TEMP during re-factor
        if isinstance(footer, dict):
            self.menu_formatting('footer', footer=footer, width=_tot_width, do_print=True)
        else:
            self.menu_formatting('footer', text=footer, width=_tot_width, do_print=True)

    # TODO text kwarg is being depricated can remove once all are switched to footer dict
    def menu_formatting(self, section, sub=None, text=None, footer={}, width=MIN_WIDTH,
                        l_offset=1, index=1, do_print=True, do_format=True):
        cpi = self.cpi
        utils = cpi.utils
        config = cpi.config
        log = config.log
        mlines = []
        max_len = None
        # footer options also supports an optional formatting dict
        # place '_rjust' in the list and the subsequent item should be a dict
        # 
        # _rjust: {dict} right justify addl text on same line with
        # one of the other footer options.  
        # i.e. 
        footer_options = {
            'power': ['p', 'Power Control Menu'],
            'dli': ['d', '[dli] Web Power Switch Menu'],
            'rshell': ['rs', 'Remote Shell Menu'],
            'key': ['k', 'Distribute SSH public Key to Remote Hosts'],
            'shell': ['sh', 'Enter Local Shell'],
            'rn': ['rn', 'Rename Adapters'],
            'refresh': ['r', 'Refresh'],
            'sync': ['s', 'Sync with cloud'],
            'con': ['c', 'Change Default Serial Settings (devices marked with ** only)'],
            'picohelp': ['h', 'Display Picocom Help'],
            'back': ['b', 'Back'],
            'x': ['x', 'Exit']
        }

        # -- append any errors from config (ConsolePi_data object)
        self.error_msgs += cpi.error_msgs
        cpi.error_msgs = []

        # -- Adjust width if there is an error msg longer then the current width
        # -- Delete any errors defined in ignore errors
        # TODO Move all menu formatting to it's own library - clean this up
        # Think I process errors here and maybe in print_mlines as well
        # addl processing in FOOTER
        if self.error_msgs:
            _error_lens = []
            for _error in self.error_msgs:
                if isinstance(_error, list):
                    log.error('{} is a list expected string'.format(_error))
                    _error = ' '.join(_error)
                if not isinstance(_error, str):
                    msg = 'Error presented to formatter with unexpected type {}'.format(type(_error))
                    log.error(msg)
                    _error = msg
                for e in self.ignored_errors:
                    if isinstance(e, re.Pattern) and e.match(_error):
                        self.error_msgs.remove(_error)
                        break
                    elif isinstance(e, str) and (e == _error or e in _error):
                        self.error_msgs.remove(_error)
                        break
                    else:
                        _error_lens.append(self.format_line(_error)[0])
            if _error_lens:
                width = width if width >= max(_error_lens) + 5 else max(_error_lens) + 5
            width = width if width <= self.cols else self.cols

        # --// HEADER \\--
        if section == 'header':
            # ---- CLEAR SCREEN -----
            if not self.debug:
                os.system('clear')
            mlines.append('=' * width)
            _len, fmtd_header = self.format_line(text)
            a = width - _len
            b = (a/2) - 2
            if text:
                c = int(b) if b == int(b) else int(b) + 1
                if isinstance(text, list):
                    for t in text:
                        mlines.append(' {0} {1} {2}'.format('-' * int(b), t, '-' * c))
                else:
                    mlines.append(' {0} {1} {2}'.format('-' * int(b), fmtd_header, '-' * c))
            mlines.append('=' * width)

        # --// BODY \\--
        elif section == 'body':
            max_len = 0
            blines = list(text) if isinstance(text, str) else text
            pad = True if len(blines) + index > 10 else False
            indent = l_offset + 4 if pad else l_offset + 3
            width_list = []
            for _line in blines:
                # -- format spacing of item entry --
                _i = str(index) + '. ' if not pad or index > 9 else str(index) + '.  '
                # -- generate line and calculate line length --
                _line = ' ' * l_offset + _i + _line
                _line_len, _line = self.format_line(_line)
                width_list.append(_line_len)
                mlines.append(_line)
                index += 1
            max_len = 0 if not width_list else max(width_list)
            if sub:
                # -- Add sub lines to top of menu item section --
                x = ((max_len - len(sub)) / 2) - (l_offset + (indent/2))
                mlines.insert(0, '')
                width_list.insert(0, 0)
                if do_format:
                    mlines.insert(1, '{0}{1} {2} {3}'.format(' ' * indent,
                                                             '-' * int(x),
                                                             sub,
                                                             '-' * int(x) if x == int(x) else '-' * (int(x) + 1)))
                    width_list.insert(1, len(mlines[1]))
                else:
                    mlines.insert(1, ' ' * indent + sub)
                    width_list.insert(1, len(mlines[1]))
                max_len = max(width_list)  # update max_len in case subheading is the longest line in the section
                mlines.insert(2, ' ' * indent + '-' * (max_len - indent))
                width_list.insert(2, len(mlines[2]))

            # -- adding padding to line to full width of longest line in section --
            mlines = self.pad_lines(mlines, max_len, width_list)  # Refactoring in progress

        # --// FOOTER \\--
        elif section == 'footer':
            #######
            # Being Depricated. Remove once converted
            #######
            if text and isinstance(text, (str, list)):
                mlines.append('')
                text = [text] if isinstance(text, str) else text
                for t in text:
                    if '{{r}}' in t:
                        _t = t.split('{{r}}')
                        mlines.append('{}{}'.format(_t[0], _t[1].rjust(width - len(_t[0]))))
                    else:
                        mlines.append(self.format_line(t)[1])

            # TODO temp indented this to be under text to avoid conflict during refactor
                mlines += [' x.  exit', '']
                mlines.append('=' * width)

            ########
            # REDESIGNED FOOTER LOGIC
            ########
            if footer:
                opts = utils.listify(footer.get('opts', []))
                if 'x' not in opts:
                    opts.append('x')
                no_match_overrides = no_match_rjust = []  # init
                pre_text = post_text = foot_text = []  # init
                # replace any pre-defined options with those passed in as overrides
                if footer.get('overrides') and isinstance(footer['overrides'], dict):
                    footer_options = {**footer_options, **footer['overrides']}

                    no_match_overrides = [e for e in footer['overrides']
                                          if e not in footer_options and e not in footer.get('rjust', {})]

                # update footer_options with any specially formmated (rjust) additions
                if footer.get('rjust'):
                    r = footer.get('rjust')
                    f = footer_options
                    foot_overrides = {k: [f[k][0], '{}{}'.format(f[k][1], r[k].rjust(
                                      width - len(f' {f[k][0]}.{" " if len(f[k][0]) == 2 else "  "}{f[k][1]}')))]
                                      for k in r if k in f}

                    footer_options = {**footer_options, **foot_overrides}
                    no_match_rjust = [e for e in footer['rjust'] if e not in footer_options]

                if footer.get('before'):
                    footer['before'] = [footer['before']] if isinstance(footer['before'], str) else footer['before']
                    pre_text = [f' {line}' for line in footer['before']]

                if opts:
                    f = footer_options
                    foot_text = [f' {f[k][0]}.{" " if len(f[k][0]) == 2 else "  "}{f[k][1]}' for k in opts]

                if footer.get('after'):
                    footer['after'] = [footer['after']] if isinstance(footer['after'], str) else footer['after']
                    post_text = [f' {line}' for line in footer['after']]

                mlines = mlines + [''] + pre_text + foot_text + post_text + [''] + ['=' * width]
                # TODO probably simplify to make this a catch all at the end of this method
                mlines = [self.format_line(line)[1] for line in mlines]

                # log errors if non-match overrides/rjust options were sent
                if no_match_overrides + no_match_rjust:
                    config.log_and_show(f'menu_formatting passed options ({",".join(no_match_overrides + no_match_rjust)})'
                                        ' that lacked a match in footer_options = No impact to menu', log=config.log.error)

            # --// ERRORs - append to footer \\-- #
            if len(self.error_msgs) > 0:
                errors = self.error_msgs = utils.unique(self.error_msgs)
                for _error in errors:
                    if isinstance(_error, list):
                        log.error('{} is a list expected string'.format(_error))
                        _error = ' '.join(_error)
                    error_len, _error = self.format_line(_error.strip())
                    x = ((width - (error_len + 4)) / 2)
                    mlines.append('{0}{1}{2}{3}{0}'.format(
                        self.log_sym_2bang,
                        ' ' * int(x),
                        _error,
                        ' ' * int(x) if x == int(x) else ' ' * (int(x) + 1)))
                if errors:  # TODO None Type added to list after rename  why
                    mlines.append('=' * width)
                if do_print:
                    self.error_msgs = []  # clear error messages after print

        else:
            self.error_msgs.append('formatting function passed an invalid section')

        # --// DISPLAY THE MENU \\--
        if do_print:
            for _line in mlines:
                print(_line)
                self.menu_rows += 1  # TODO DEBUGGING make easier then remove
        # TODO refactor max_len to widest_line as thats what it is
        return mlines, max_len

    def pad_lines(self, line_list, max_width, width_list, sub=True):
        for _line in line_list:
            i = line_list.index(_line)
            line_list[i] = '{}{}'.format(_line, ' ' * (max_width - width_list[i]))
        return line_list

    def format_line(self, line):
        # accepts line as str with menu formatting placeholders ({{red}}, {{green}}, etc)
        # OR line as bool when bool it will convert it to a formatted ON/OFF str
        # returns 2 value tuple line length, formatted-line
        if isinstance(line, bool):
            line = '{{green}}ON{{norm}}' if line else '{{red}}OFF{{norm}}'
        colors = {
            'green': '\033[1;32m',  # Bold with normal ForeGround
            'red': '\033[1;31m',
            'yellow': '\033[1;33m',
            'blue': '\033[1;34m',
            'magenta': '\033[1;35m',
            'cyan': '\033[1;36m',
            'dgreen': '\033[2;32m',  # Dim with normal ForeGround
            'dred': '\033[2;31m',
            'dyellow': '\033[2;33m',
            'dblue': '\033[2;34m',
            'dmagenta': '\033[2;35m',
            'dcyan': '\033[2;36m',
            'inverted': '\033[7m',
            'norm': '\033[0m',  # Reset to Normal
            'dot': u'\u00B7'  # no it's not a color it's a dot
        }
        _l = line
        if '{{' in line:
            for c in colors:
                _l = _l.replace('{{' + c + '}}', '')  # color format var removed so we can get the tot_cols used by line
                line = line.replace('{{' + c + '}}', colors[c])  # line formatted with coloring
        return len(_l), line

    def picocom_help(self):
        print('##################### picocom Command Sequences ########################\n')
        print(' This program will launch serial session via picocom')
        print(' This is a list of the most common command sequences in picocom')
        print(' To use them press and hold ctrl then press and release each character\n')
        print('   ctrl+ a - x Exit session - reset the port')
        print('   ctrl+ a - q Exit session - without resetting the port')
        print('   ctrl+ a - b set baudrate')
        print('   ctrl+ a - u increase baud')
        print('   ctrl+ a - d decrease baud')
        print('   ctrl+ a - i change the number of databits')
        print('   ctrl+ a - f cycle through flow control options')
        print('   ctrl+ a - y cycle through parity options')
        print('   ctrl+ a - v Show configured port options')
        print('   ctrl+ a - c toggle local echo')
        print('\n########################################################################\n')
        input('Press Enter to Continue... ')

    def power_menu(self, calling_menu='main_menu'):
        cpi = self.cpi
        pwr = cpi.pwr
        states = self.states
        menu_actions = {
            'b': self.main_menu,
            'x': self.exit,
            'power_menu': self.power_menu,
        }
        choice = ''

        # Ensure Power Threads are complete
        if not cpi.pwr_init_complete:
            with Halo(text='Waiting for Outlet init threads to complete', spinner='dots'):
                cpi.wait_for_threads()
                outlets = pwr.data['defined']
        else:
            outlets = cpi.outlet_update()

        if not outlets:
            cpi.error_msgs.append('No Linked Outlets are connected')
            return

        while choice.lower() not in ['x', 'b']:
            item = 1
            # if not self.DEBUG:
            #     os.system('clear')

            header = 'Power Control Menu'
            subhead = [
                '  enter item # to toggle power state on outlet',
                '  enter c + item # i.e. "c2" to cycle power on outlet'
            ]

            # Build menu items for each linked outlet
            state_list = []
            body = []
            footer = {'opts': [], 'before': []}
            for r in sorted(outlets):
                outlet = outlets[r]

                # -- // Linked DLI OUTLET MENU LINE(s) \\ --
                if outlet['type'].lower() == 'dli':
                    if outlet.get('linked_devs') and outlet.get('is_on'):  # Avoid orphan header when no outlets are linked
                        for dli_port in outlet['is_on']:
                            _outlet = outlet['is_on'][dli_port]
                            _state = states[_outlet['state']]
                            state_list.append(_outlet['state'])
                            _state = self.format_line(_state)[1]
                            _name = ' ' + _outlet['name'] if 'ON' in _state else _outlet['name']
                            body.append(f"[{_state}] {_name} ({r} Port:{dli_port})")
                            menu_actions[str(item)] = {
                                'function': pwr.pwr_toggle,
                                'args': [outlet['type'], outlet['address']],
                                'kwargs': {'port': dli_port, 'desired_state': not _outlet['state']},
                                'key': r
                                }
                            menu_actions['c' + str(item)] = {
                                'function': pwr.pwr_cycle,
                                'args': ['dli', outlet['address']],
                                'kwargs': {'port': dli_port},
                                'key': 'dli_pwr'
                                }
                            menu_actions['r' + str(item)] = {
                                'function': pwr.pwr_rename,
                                'args': ['dli', outlet['address']],
                                'kwargs': {'port': dli_port},
                                'key': 'dli_pwr'
                                }
                            item += 1

                # -- // GPIO or tasmota OUTLET MENU LINE \\ --
                else:
                    # pwr functions put any errors (aborts) in pwr.data[grp]['error']
                    if pwr.data['defined'][r].get('errors'):
                        cpi.error_msgs.append(f'{r} - {pwr.data["defined"][r]["errors"]}')
                        del pwr.data['defined'][r]['errors']
                    if isinstance(outlet['is_on'], bool):
                        _state = states[outlet['is_on']]
                        state_list.append(outlet['is_on'])
                        _state = self.format_line(_state)[1]
                        body.append(f"[{_state}] {' ' + r if 'ON' in _state else r} ({outlet['type']}:{outlet['address']})")
                        menu_actions[str(item)] = {
                            'function': pwr.pwr_toggle,
                            'args': [outlet['type'], outlet['address']],
                            'kwargs': {
                                'noff': True if 'noff' not in outlet else outlet['noff']},
                            'key': r
                            }
                        menu_actions['c' + str(item)] = {
                            'function': pwr.pwr_cycle,
                            'args': [outlet['type'], outlet['address']],
                            'kwargs': {'noff': True if 'noff' not in outlet else outlet['noff']},
                            'key': r
                            }
                        menu_actions['r' + str(item)] = {
                            'function': pwr.pwr_rename,
                            'args': [outlet['type'], outlet['address']],
                            'key': r
                            }
                        item += 1
                    else:   # refactored power.py pwr_get_outlets this should never hit
                        cpi.error_msgs.append('DEV NOTE {} outlet state is not bool: {}'.format(r, outlet['error']))

            if item > 2:
                if False in state_list:
                    footer['before'].append(' all on:    Turn all outlets {{green}}ON{{norm}}')
                    menu_actions['all on'] = {
                        'function': pwr.pwr_all,
                        'kwargs': {'outlets': outlets, 'action': 'toggle', 'desired_state': True}
                        }
                if True in state_list:
                    footer['before'].append(' all off:   Turn all outlets {{red}}OFF{{norm}}')
                    menu_actions['all off'] = {
                        'function': pwr.pwr_all,
                        'kwargs': {'outlets': outlets, 'action': 'toggle', 'desired_state': False}
                        }
                    footer['before'].append(' cycle all: Cycle all outlets '
                                            '{{green}}ON{{norm}}{{dot}}{{red}}OFF{{norm}}{{dot}}{{green}}ON{{norm}}')

                    menu_actions['cycle all'] = {
                        'function': pwr.pwr_all,
                        'kwargs': {'outlets': outlets, 'action': 'cycle'}
                        }
                footer['before'].append('')

            # text = [' b.  Back', ' r.  Refresh']
            footer['opts'] = ['back', 'refresh']
            if pwr.dli_exists and not calling_menu == 'dli_menu':
                footer['opts'].insert(0, 'dli')
                menu_actions['d'] = self.dli_menu
            # footer += text
            self.print_mlines(body, header=header, subhead=subhead, footer=footer)
            choice = self.wait_for_input(lower=True)
            if choice not in ['b', 'r']:
                self.exec_menu(choice, menu_actions, calling_menu='power_menu')
            elif choice == 'b':
                return
            elif choice == 'r':
                if pwr.dli_exists:
                    with Halo(text='Refreshing Outlets', spinner='dots'):
                        outlets = cpi.outlet_update(refresh=True, upd_linked=True)

    def wait_for_input(self, prompt=" >>  ", lower=False, terminate=True):
        try:
            if self.debug:
                self.menu_rows += 1  # TODO REMOVE AFTER SIMPLIFIED
                prompt = f' m[r:{self.menu_rows}, c:{self.menu_cols}] a[r:{self.rows}, c:{self.cols}]{prompt}'
            choice = input(prompt) if not lower else input(prompt).lower()
            self.menu_rows = 0  # TODO REMOVE AFTER SIMPLIFIED
            return choice
        except (KeyboardInterrupt, EOFError):
            if terminate:
                print('Exiting based on User Input')
                self.exit()
            else:
                self.cpi.error_msgs.append('User Aborted')
                print('')  # prevents header and prompt on same line in debug
                return ''

    # ------ // DLI WEB POWER SWITCH MENU \\ ------ #
    def dli_menu(self, calling_menu='power_menu'):
        cpi = self.cpi
        pwr = cpi.pwr
        # dli_dict = self.get_dli_outlets(key='dli_pwr')
        menu_actions = {
            'b': self.power_menu,
            'x': self.exit,
            'dli_menu': self.dli_menu,
            'power_menu': self.power_menu
        }
        states = self.states
        choice = ''
        if not cpi.pwr_init_complete:
            with Halo(text='Ensuring Outlet init threads are complete', spinner='dots'):
                cpi.wait_for_threads('init')
        dli_dict = pwr.data['dli_power']
        while choice not in ['x', 'b']:
            # if not self.DEBUG:
            #     os.system('clear')

            index = start = 1
            outer_body = []
            slines = []
            for dli in sorted(dli_dict):
                state_dict = []
                mlines = []
                port_dict = dli_dict[dli]  # pylint: disable=unsubscriptable-object
                # strip off all but hostname if address is fqdn
                host_short = dli.split('.')[0] if '.' in dli and not dli.split('.')[0].isdigit() else dli

                # -- // MENU ITEMS LOOP \\ --
                for port in port_dict:
                    pname = port_dict[port]['name']
                    cur_state = port_dict[port]['state']
                    state_dict.append(cur_state)
                    to_state = not cur_state
                    on_pad = ' ' if cur_state else ''
                    mlines.append('[{}] {}{}{}'.format(
                        states[cur_state], on_pad, 'P' + str(port) + ': ' if port != index else '', pname))
                    menu_actions[str(index)] = {
                        'function': pwr.pwr_toggle,
                        'args': ['dli', dli],
                        'kwargs': {'port': port, 'desired_state': to_state},
                        'key': 'dli_pwr'
                        }
                    menu_actions['c' + str(index)] = {
                        'function': pwr.pwr_cycle,
                        'args': ['dli', dli],
                        'kwargs': {'port': port},
                        'key': 'dli_pwr'
                        }
                    menu_actions['r' + str(index)] = {
                        'function': pwr.pwr_rename,
                        'args': ['dli', dli],
                        'kwargs': {'port': port},
                        'key': 'dli_pwr'
                        }
                    index += 1
                # add final entry for all operations
                if True not in state_dict:
                    _line = 'ALL {{green}}ON{{norm}}'
                    desired_state = True
                elif False not in state_dict:
                    _line = 'ALL {{red}}OFF{{norm}}'
                    desired_state = False
                else:
                    _line = 'ALL [on|off]. i.e. "{} off"'.format(index)
                    desired_state = None
                # build appropriate menu_actions item will represent ALL ON or ALL OFF if current state
                # of all outlets is the inverse
                # if there is a mix item#+on or item#+off will both be valid but item# alone will not.
                if desired_state in [True, False]:
                    menu_actions[str(index)] = {
                        'function': pwr.pwr_toggle,
                        'args': ['dli', dli],
                        'kwargs': {'port': 'all', 'desired_state': desired_state},
                        'key': 'dli_pwr'
                        }
                elif desired_state is None:
                    for s in ['on', 'off']:
                        desired_state = True if s == 'on' else False
                        menu_actions[str(index) + ' ' + s] = {
                            'function': pwr.pwr_toggle,
                            'args': ['dli', dli],
                            'kwargs': {'port': 'all', 'desired_state': desired_state},
                            'key': 'dli_pwr'
                            }
                mlines.append(_line)
                # Add cycle line if any outlets are currently ON
                index += 1
                if True in state_dict:
                    mlines.append('Cycle ALL')
                    menu_actions[str(index)] = {
                        'function': pwr.pwr_cycle,
                        'args': ['dli', dli],
                        'kwargs': {'port': 'all'},
                        'key': 'dli_pwr'
                        }
                index = start + 10
                start += 10

                outer_body.append(mlines)   # list of lists where each list = printed menu lines
                slines.append(host_short)   # list of strings index to index match with body list of lists

            header = 'DLI Web Power Switch'
            # footer = [
            #     ' b.  Back{{r}}menu # alone will toggle the port,',
            #     ' r.  Refresh{{r}}c# to cycle or r# to rename [i.e. \'c1\']'
            # ]
            footer = {'opts': ['back', 'refresh']}
            footer['rjust'] = {
                'back': 'menu # alone will toggle the port,',
                'refresh': 'c# to cycle or r# to rename [i.e. \'c1\']'
            }
            if (not calling_menu == 'power_menu' and pwr.data) and (pwr.gpio_exists or pwr.tasmota_exists or pwr.linked_exists):
                menu_actions['p'] = self.power_menu
                # footer.insert(0, ' p.  Power Control Menu (linked, GPIO, tasmota)')
                footer['opts'].insert(0, 'power')
                footer['overrides'] = {'power': ['p', 'Power Control Menu (linked, GPIO, tasmota)']}
            # for dli menu remove in tasmota errors
            # self.error_msgs = [self.error_msgs.remove(_error) for _error in self.error_msgs if 'TASMOTA' in _error]
            for _error in cpi.error_msgs:
                if 'TASMOTA' in _error:
                    cpi.error_msgs.remove(_error)
            self.print_mlines(outer_body, header=header, footer=footer, subs=slines, force_cols=True, by_tens=True)

            # choice = input(" >>  ").lower()
            choice = self.wait_for_input()
            if choice == 'r':
                self.spin.start('Refreshing Outlets')
                # dli_dict = self.get_dli_outlets(refresh=True, key='dli_pwr')
                dli_dict = cpi.outlet_update(refresh=True, key='dli_power')
                self.spin.succeed()
            elif choice == 'b':
                return
            else:
                self.exec_menu(choice, menu_actions, calling_menu='dli_menu')

    def key_menu(self):
        cpi = self.cpi
        config = cpi.config
        rem = cpi.remotes.data
        choice = ''
        menu_actions = {
            'b': self.main_menu,
            'x': self.exit,
            'key_menu': self.key_menu
        }
        while choice.lower() not in ['x', 'b']:
            header = ' Remote SSH Key Distribution Menu '

            # Build menu items for each serial adapter found on remote ConsolePis
            item = 1
            all_list = []
            mlines = []
            subs = ['Send SSH Public Key to...']
            for host in sorted(rem):
                if 'rem_ip' not in rem[host]:
                    config.log.warning('[KEY_MENU] {} lacks rem_ip skipping'.format(host))
                    continue
                if rem[host]['rem_ip'] is not None:
                    rem_ip = rem[host].get('rem_ip')
                    rem_user = rem[host].get('user', config.static.get('FALLBACK_USER', 'pi'))
                    mlines.append(f'{host} @ {rem_ip}')
                    this = (host, rem_ip, rem_user)
                    menu_actions[str(item)] = {'function': cpi.gen_copy_key, 'args': [this]}
                    all_list.append(this)
                    item += 1

            # -- add option to loop through all remotes and deploy keys --
            footer = {'opts': 'back',
                      'before': ['a.  {{cyan}}*all*{{norm}} remotes listed above', '']}
            menu_actions['a'] = {'function': cpi.gen_copy_key, 'args': [all_list]}
            self.print_mlines(mlines, subs=subs, header=header, footer=footer, do_format=False)
            choice = self.wait_for_input()

            self.exec_menu(choice, menu_actions, calling_menu='key_menu')

    def gen_adapter_lines(self, adapters, item=1, remote=False, rem_user=None, host=None, rename=False):
        # rem = self.data['remote']
        cpi = self.cpi
        config = cpi.config
        rem = cpi.remotes.data
        utils = cpi.utils
        flow_pretty = {
            'x': 'xon/xoff',
            'h': 'RTS/CTS',
            'n': 'NONE'
        }
        menu_actions = {}
        mlines = []
        # If remotes present adapter data in old format convert to new
        if isinstance(adapters, list):
            adapters = {adapters[adapters.index(d)]['dev']: {'config': {k: adapters[adapters.index(d)][k]
                        for k in adapters[adapters.index(d)]}} for d in adapters}
        # Generate menu_lines for manually configured hosts
        elif adapters.get('_hosts'):
            for h in adapters['_hosts']:
                menu_line = adapters['_hosts'][h].get('menu_line')
                if not menu_line:
                    host_pretty = h.replace('/host/', '')
                    _addr = adapters['_hosts'][h]['address']
                    if ':' in _addr:
                        _a, _p = _addr.split(':')
                        _a = utils.get_host_short(_a)
                        _m = adapters['_hosts'][h].get('method')
                        _addr = _a if (_m == 'telnet' and _p == '23') or \
                            (_m == 'ssh' and _p == '22') else f'{_a}:{_p}'
                    menu_line = f'{host_pretty} @ {_addr}'
                mlines.append(menu_line)
                menu_actions[str(item)] = {'cmd': adapters['_hosts'][h].get('cmd')}
                item += 1

            return mlines, menu_actions, item

        for _dev in sorted(adapters.items(), key=lambda i: i[1]['config'].get('port', 0)):
            this_dev = adapters[_dev[0]].get('config', adapters[_dev[0]])
            if this_dev.get('port', 0) != 0:
                def_indicator = ''
            else:
                def_indicator = '**'
                self.display_con_settings = True
            baud = this_dev.get('baud', config.default_baud)
            dbits = this_dev.get('dbits', 8)
            flow = this_dev.get('flow', 'n')
            parity = this_dev.get('parity', 'n')
            sbits = this_dev.get('sbits', 1)
            dev_pretty = _dev[0].replace('/dev/', '')

            # Generate Menu Line
            menu_line = f'{dev_pretty} {def_indicator}[{baud} {dbits}{parity[0].upper()}{sbits}]'
            if flow != 'n' and flow in flow_pretty:
                menu_line += f' {flow_pretty[flow]}'
            mlines.append(menu_line)

            # -- // LOCAL ADAPTERS \\ --
            if not remote:
                # Generate connect command used to connect to device
                fallback_cmd = f'picocom {this_dev} --baud {baud} --flow {flow} --databits {dbits} --parity {parity}'
                _cmd = this_dev.get('cmd', fallback_cmd)
                if not rename:
                    menu_actions[str(item)] = {'cmd': _cmd, 'pwr_key': _dev[0]}
                else:
                    rn_this = {_dev[0]: adapters[_dev[0]]}
                    menu_actions[str(item)] = {'function': self.do_rename_adapter, 'args': [_dev[0]]}
                    menu_actions['s' + str(item)] = {'function': cpi.show_adapter_details, 'args': [rn_this]}
                    menu_actions['c' + str(item)] = {'cmd': _cmd}

            # -- // REMOTE ADAPTERS \\ --
            # TODO can just make the command once and prepend remote bit for remotes.
            else:
                if not rem_user:  # the user advertised by the remote we ssh to the remote with this user
                    rem_user = config.FALLBACK_USER

                # Generate connect command used to connect to remote device
                fallback_cmd = f'sudo -u {config.loc_user} ssh -t {rem_user}@{rem[host].get("rem_ip")} \"{config.REM_LAUNCH}' \
                               f' picocom {_dev[0]} --baud {baud} --flow {flow} --databits {dbits} --parity {parity}\"'
                _cmd = this_dev.get('cmd', fallback_cmd)
                menu_actions[str(item)] = {'cmd': _cmd}
            item += 1

        return mlines, menu_actions, item

    def rename_menu(self, direct_launch=False):
        cpi = self.cpi
        local = cpi.local
        choice = ''
        menu_actions = {}
        while choice not in ['b']:
            if choice == 'r':
                local.adapters = local.build_adapter_dict(refresh=True)
            loc = local.adapters

            slines = []
            mlines, menu_actions, item = self.gen_adapter_lines(loc, rename=True)  # pylint: disable=unused-variable
            slines.append('Select Adapter to Rename')   # list of strings index to index match with body list of lists
            footer = {'before': [
                's#. Show details for the adapter i.e. \'s1\'',
                'c#. Connect to the device i.e. \'c1\'',
                '',
                'The system is updated with new adapter(s) when you leave this menu.',
                ''
            ], 'opts': []}
            if not direct_launch:
                footer['opts'].append('back')

            footer['opts'].append('refresh')
            menu_actions['r'] = None

            self.print_mlines(mlines, header='Define/Rename Local Adapters', footer=footer, subs=slines, do_format=False)
            menu_actions['x'] = self.exit

            # choice = input(" >> ").lower()
            choice = self.wait_for_input(lower=True, terminate=False)
            if choice in menu_actions:
                if not choice == 'b':
                    self.exec_menu(choice, menu_actions, calling_menu='rename_menu')
            else:
                if choice:
                    if choice != 'b' or direct_launch:
                        cpi.error_msgs.append('Invalid Selection \'{}\''.format(choice))

        # trigger refresh udev and restart ser2net after rename
        if self.udev_pending:
            error = self.trigger_udev()
            cpi.error_msgs.append(error)

    # ------ // MAIN MENU \\ ------ #
    def main_menu(self):
        cpi = self.cpi
        config = cpi.config
        remotes = cpi.remotes
        loc = cpi.local.adapters
        pwr = cpi.pwr
        rem = remotes.data

        menu_actions = {
            'h': self.picocom_help,
            'r': remotes.refresh,
            'x': self.exit,
            'sh': cpi.launch_shell
        }
        if config.power and cpi.pwr.data:
            if cpi.pwr.linked_exists or cpi.pwr.gpio_exists or cpi.pwr.tasmota_exists:
                menu_actions['p'] = self.power_menu
            elif cpi.pwr.dli_exists:  # if no linked outlets but dlis defined p sends to dli_menu
                menu_actions['p'] = self.dli_menu

            if cpi.pwr.dli_exists:
                menu_actions['d'] = self.dli_menu

        # DIRECT LAUNCH TO POWER IF NO ADAPTERS (given there are outlets)
        if not loc and not rem and config.power:
            cpi.error_msgs.append('No Adapters Found, Outlets Defined... Launching to Power Menu')
            cpi.error_msgs.append('use option "b" to access main menu options')
            if config.pwr.dli_exists and not config.pwr.linked_exists:
                self.exec_menu('d')
            else:
                self.exec_menu('p')

        # Build menu items for each locally connected serial adapter
        outer_body = []
        slines = []
        mlines, loc_menu_actions, item = self.gen_adapter_lines(loc)
        if loc_menu_actions:
            menu_actions = {**loc_menu_actions, **menu_actions}

        outer_body.append(mlines)   # list of lists where each list = printed menu lines
        slines.append('[LOCAL] Directly Connected')   # Sub-heads: list of str idx to idx match with outer_body list of lists

        # Build menu items for each serial adapter found on remote ConsolePis
        for host in sorted(rem):
            if rem[host].get('rem_ip') and len(rem[host]['adapters']) > 0:
                remotes.connected = True
                mlines, rem_menu_actions, item = self.gen_adapter_lines(rem[host]['adapters'], item=item, remote=True,
                                                                        rem_user=rem[host].get('rem_user'), host=host)
                if rem_menu_actions:
                    menu_actions = {**menu_actions, **rem_menu_actions}

                outer_body.append(mlines)
                slines.append('[Remote] {} @ {}'.format(host, rem[host]['rem_ip']))

        # Build menu items for each manually defined host with show_in_main = True
        # TODO add background reachability check
        if config.hosts and config.hosts.get('main'):
            hosts = config.hosts['main']
            for g in hosts:
                mlines, host_menu_actions, item = self.gen_adapter_lines({'_hosts': hosts[g]}, item=item, host=g)
                if host_menu_actions:
                    menu_actions = {**menu_actions, **host_menu_actions}

                outer_body.append(mlines)
                slines.append(g)

        # -- // General Menu Command Options \\ --
        text = []
        if self.display_con_settings:
            text.append(f' c.  Change default Serial Settings **[{self.baud} {self.data_bits}{self.parity.upper()}1'
                        f' flow={self.flow_pretty[self.flow]}]')
            menu_actions['c'] = self.con_menu
        text.append(' h.  Display picocom help')

        if config.power:  # and config.outlets is not None:
            if pwr.outlets_exists:
                text.append(' p.  Power Control Menu')
            if pwr.dli_exists:
                text.append(' d.  [dli] Web Power Switch Menu')

        if remotes.connected or config.hosts:
            text.append(' s.  Remote Shell Menu')
            menu_actions['s'] = self.rshell_menu
            if remotes.connected:
                text.append(' k.  Distribute SSH Key to Remote Hosts')
                menu_actions['k'] = self.key_menu

        text.append(' sh. Enter Local Shell')
        if loc:  # and config.root:
            text.append(' rn. Rename Local Adapters')
            menu_actions['rn'] = self.rename_menu
        text.append(' r.  Refresh')

        self.print_mlines(outer_body, header='{{cyan}}Console{{red}}Pi{{norm}} {{cyan}}Serial Menu{{norm}}',
                          footer=text, subs=slines, do_format=False)

        choice = self.wait_for_input()
        self.exec_menu(choice, menu_actions)
        return

    # ------ // REMOTE SHELL MENU \\ ------ #
    def rshell_menu(self, do_ssh_hosts=False):
        choice = ''
        cpi = self.cpi
        local = cpi.local
        config = cpi.config
        rem = cpi.remotes.data
        menu_actions = {
            'rshell_menu': self.rshell_menu,
            'b': self.main_menu,
            'x': self.exit
        }

        while choice.lower() not in ['x', 'b']:
            # if not self.DEBUG:
            #     os.system('clear')
            outer_body = []
            mlines = []
            subs = []
            item = 1

            # Build menu items for each reachable remote ConsolePi
            subs.append('Remote ConsolePis')
            for host in sorted(rem):
                if rem[host].get('rem_ip'):
                    mlines.append(f'{host} @ {rem[host]["rem_ip"]}')
                    _rem_user = rem[host].get('user', config.FALLBACK_USER)
                    _cmd = f'sudo -u {local.user} ssh -t {_rem_user}@{rem[host]["rem_ip"]}'
                    menu_actions[str(item)] = {'cmd': _cmd}
                    item += 1
            outer_body.append(mlines)

            # Build menu items for each manually defined host in hosts.json
            if config.hosts:
                mlines = []
                for _sub in config.hosts['rshell']:
                    subs.append(_sub)
                    ssh_hosts = config.hosts['rshell'][_sub]
                    for host in sorted(ssh_hosts):
                        r = ssh_hosts[host]
                        if 'address' in r:
                            mlines.append(f"{host.split('/')[-1]} @ {r['address']}")
                            _host = r['address'].split(':')[0]
                            _port = '' if ':' not in r['address'] else r['address'].split(':')[1]
                            if 'method' in r and r['method'].lower() == 'ssh':
                                # configure fallback command
                                _cmd = 'sudo -u {0} ssh -t {3} {1}@{2}'.format(config.loc_user,
                                                                               r.get('username', config.FALLBACK_USER),
                                                                               _host, '' if not _port else '-p {}'.format(_port))
                                _cmd = r.get('cmd', _cmd)
                            elif 'method' in r and r['method'].lower() == 'telnet':
                                # configure fallback command
                                _cmd = 'sudo -u {0} telnet {1} {2}'.format(config.loc_user,
                                                                           r['address'].split(':')[0], _port)
                                _cmd = r.get('cmd', _cmd)
                            menu_actions[str(item)] = {'cmd': _cmd, 'pwr_key': host, 'no_error_check': True}
                            item += 1

                    outer_body.append(mlines)

            text = ' b.  Back'
            self.print_mlines(outer_body, header='Remote Shell Menu',
                              subhead='Enter item # to connect to remote',
                              footer=text, subs=subs)
            choice = self.wait_for_input(terminate=False)
            self.exec_menu(choice, menu_actions, calling_menu='rshell_menu')

    # ------ // EXECUTE MENU SELECTIONS \\ ------ #
    def exec_menu(self, choice, menu_actions, calling_menu='main_menu'):
        cpi = self.cpi
        pwr = cpi.pwr
        config = cpi.config
        utils = cpi.utils
        # log = config.log
        if not self.debug and calling_menu not in ['dli_menu', 'power_menu']:
            os.system('clear')

        if choice is None:
            return
        else:
            ch = choice.lower()

        if ch == '':
            self.rows, self.cols = utils.get_tty_size()  # re-calc tty size in case they've adjusted the window
            return
        elif ch == 'exit':
            self.exit()
        elif ch in menu_actions and menu_actions[ch] is None:
            return
        elif 'self.' in ch or 'config.' in ch or 'cloud.' in ch or 'local.' in ch or 'cpi.' in ch or 'remotes.' in ch \
             or 'this.' in ch:
            local = cpi.local  # NoQA
            remotes = cpi.remotes
            cloud = remotes.cloud  # NoQA
            _ = f"self.var  = {ch.replace('this.', '').replace('true', 'True').replace('false', 'False')}"
            try:
                exec(_)
                if isinstance(self.var, (dict, list)):
                    print(json.dumps(self.var, indent=4, sort_keys=True))
                    print('type: {}'.format(type(self.var)))
                else:
                    print(self.var)
                    print('type: {}'.format(type(self.var)))
                input('Press Enter to Continue... ')
            except Exception as e:
                if hasattr(self, 'var'):
                    print(self.var)
                print(e)
            return
        else:
            try:
                if isinstance(menu_actions[ch], dict):
                    if menu_actions[ch].get('cmd'):
                        menu_actions[ch]['cmd'] = menu_actions[ch]['cmd'].replace('{{timestamp}}', time.strftime('%F_%H.%M'))
                        # -- // AUTO POWER ON LINKED OUTLETS \\ --
                        if config.power and 'pwr_key' in menu_actions[ch]:  # pylint: disable=maybe-no-member
                            cpi.exec_auto_pwron(menu_actions[ch]['pwr_key'])
                            # if '/dev/' in c[1] or ( len(c) >= 4 and '/dev/' in c[3] ):
                            #     menu_dev = c[1] if c[0] != 'ssh' else c[3].split()[2]
                            #     if c[0] != 'ssh':
                            #         config.exec_auto_pwron(menu_dev)

                        # --// execute the command \\--
                        try:
                            # --- TODO CHANGE THIS!!! switched back to handle cipher error, but banner txt is send back
                            # via stderr. so not ideal as is
                            if 'no_error_check__' in menu_actions[ch] and menu_actions[ch]['no_error_check__']:
                                c = menu_actions[ch]['cmd']
                                os.system(c)
                            else:
                                # c looks like the following
                                # (local): [picocom', '/dev/White3_7003', '--baud 9600', '--flow n', '--databits 8', '--parity n']
                                # (remote): ['ssh', '-t', 'pi@10.1.30.28', 'remote_launcher.py picocom /dev/AP303P-BARN_7001 --baud 9600 ...']  # NoQA
                                c = shlex.split(menu_actions[ch]['cmd'])
                                result = subprocess.run(c, stderr=subprocess.PIPE)
                                _stderr = result.stderr.decode('UTF-8')
                                if _stderr or result.returncode == 1:
                                    _error = utils.error_handler(c, _stderr)  # pylint: disable=maybe-no-member
                                    # if _error:
                                    #     _error = _error.replace('\r', '').split('\n')
                                    #     [self.error_msgs.append(i) for i in _error if i]  # Remove any trailing empy items

                            # -- // resize the terminal to handle serial connections that jack the terminal size \\ --
                            c = ' '.join([str(i) for i in c])
                            if 'picocom' in c:  # pylint: disable=maybe-no-member
                                os.system('/etc/ConsolePi/src/consolepi-commands/resize >/dev/null')
                        except KeyboardInterrupt:
                            self.error_msgs.append('Aborted last command based on user input')

                    elif 'function' in menu_actions[ch]:
                        args = menu_actions[ch]['args'] if 'args' in menu_actions[ch] else []
                        kwargs = menu_actions[ch]['kwargs'] if 'kwargs' in menu_actions[ch] else {}
                        confirmed, spin_text, name = self.confirm_and_spin(menu_actions[ch], *args, **kwargs)
                        if confirmed:
                            # update kwargs with name from confirm_and_spin method
                            if menu_actions[ch]['function'].__name__ == 'pwr_rename':
                                kwargs['name'] = name

                            # // -- CALL THE FUNCTION \\--
                            if spin_text:  # start spinner if spin_text set by confirm_and_spin
                                with Halo(text=spin_text, spinner='dots2'):
                                    response = menu_actions[ch]['function'](*args, **kwargs)
                            else:  # no spinner
                                response = menu_actions[ch]['function'](*args, **kwargs)

                            # --// Power Menus \\--
                            if calling_menu in ['power_menu', 'dli_menu']:
                                if menu_actions[ch]['function'].__name__ == 'pwr_all':
                                    with Halo(text='Refreshing Outlet States', spinner='dots'):
                                        cpi.outlet_update(refresh=True, upd_linked=True)  # TODO can I move this to Outlets Class
                                else:
                                    _grp = menu_actions[ch]['key']
                                    _type = menu_actions[ch]['args'][0]
                                    _addr = menu_actions[ch]['args'][1]
                                    # --// EVAL responses for dli outlets \\--
                                    if _type == 'dli':
                                        host_short = utils.get_host_short(_addr)
                                        _port = menu_actions[ch]['kwargs']['port']
                                        # --// Operations performed on ALL outlets \\--
                                        if isinstance(response, bool) and _port is not None:
                                            if menu_actions[ch]['function'].__name__ == 'pwr_toggle':
                                                self.spin.start('Request Sent, Refreshing Outlet States')
                                                # threading.Thread(target=self.get_dli_outlets, kwargs={'upd_linked': True, 'refresh': True}, name='pwr_toggle_refresh').start()
                                                upd_linked = True if calling_menu == 'power_menu' else False  # else dli_menu
                                                threading.Thread(target=cpi.outlet_update, kwargs={'upd_linked': upd_linked, 'refresh': True}, name='pwr_toggle_refresh').start()
                                                if _grp in pwr.data['defined']:
                                                    pwr.data['defined'][_grp]['is_on'][_port]['state'] = response
                                                elif _port != 'all':
                                                    pwr.data['dli_power'][_addr][_port]['state'] = response
                                                else:  # dli toggle all
                                                    for t in threading.enumerate():
                                                        if t.name == 'pwr_toggle_refresh':
                                                            t.join()    # if refresh thread is running join ~ wait for it to complete. # TODO Don't think this works or below
                                                                        # wouldn't have been necessary.

                                                            # toggle all returns True (ON) or False (OFF) if command successfully sent.  In reality the ports
                                                            # may not be in the  state yet, but dli is working it.  Update menu items to reflect end state
                                                            for p in pwr.data['dli_power'][_addr]:
                                                                pwr.data['dli_power'][_addr][p]['state'] = response
                                                            break
                                                self.spin.stop()
                                            # Cycle operation returns False if outlet is off, only valid on powered outlets
                                            elif menu_actions[ch]['function'].__name__ == 'pwr_cycle' and not response:
                                                self.error_msgs.append('{} Port {} if Off.  Cycle is not valid'.format(host_short, _port))
                                            elif menu_actions[ch]['function'].__name__ == 'pwr_rename':
                                                if response:
                                                    _name = pwr._dli[_addr].name(_port)
                                                    if _grp in pwr.data.get('defined', {}):
                                                        pwr.data['defined'][_grp]['is_on'][_port]['name'] = _name
                                                    else:
                                                        # threading.Thread(target=self.get_dli_outlets, kwargs={'upd_linked': True, 'refresh': True}, name='pwr_rename_refresh').start()
                                                        threading.Thread(target=cpi.outlet_update, kwargs={'upd_linked': True, 'refresh': True}, name='pwr_rename_refresh').start()
                                                    pwr.data['dli_power'][_addr][_port]['name'] = _name
                                        # --// str responses are errors append to error_msgs \\--
                                        # TODO refactor response to use new cpi.response(...)
                                        elif isinstance(response, str) and _port is not None:
                                            cpi.error_msgs.append(response)
                                        # --// Can Remove After Refactoring all responses to bool or str \\--
                                        elif isinstance(response, int):
                                            if menu_actions[ch]['function'].__name__ == 'pwr_cycle' and _port == 'all':
                                                if response != 200:
                                                    self.error_msgs.append('Error Response Returned {}'.format(response))
                                            else:  # This is a catch as for the most part I've tried to refactor so the pwr library returns port state on success (True/False)
                                                if response in [200, 204]:
                                                    cpi.error_msgs.append('DEV NOTE: check pwr library ret=200 or 204')
                                                else:
                                                    cpi.error_msgs.append('Error returned from dli {} when attempting to {} port {}'.format(
                                                        host_short, menu_actions[ch]['function'].__name__, _port))

                                    # --// EVAL responses for GPIO and tasmota outlets \\--
                                    else:
                                        if menu_actions[ch]['function'].__name__ == 'pwr_toggle':
                                            if _grp in pwr.data.get('defined', {}):
                                                if isinstance(response, bool):
                                                    pwr.data['defined'][_grp]['is_on'] = response
                                                else:
                                                    pwr.data['defined'][_grp]['errors'] = response
                                        elif menu_actions[ch]['function'].__name__ == 'pwr_cycle' and not response:
                                            self.error_msgs.append('Cycle is not valid for Outlets in the off state')
                                        elif menu_actions[ch]['function'].__name__ == 'pwr_rename':
                                            self.error_msgs.append('rename not yet implemented for {} outlets'.format(_type))
                            elif calling_menu in['key_menu', 'rename_menu']:
                                if response:
                                    response = [response] if isinstance(response, str) else response
                                    for _ in response:
                                        if _:  # strips empty lines
                                            cpi.error_msgs.append(_)
                        else:   # not confirmed
                            cpi.error_msgs.append('Operation Aborted by User')
                elif menu_actions[ch].__name__ in ['power_menu', 'dli_menu']:
                    menu_actions[ch](calling_menu=calling_menu)
                else:
                    menu_actions[ch]()
            except KeyError as e:
                cpi.error_msgs.append('Invalid selection {}, please try again.'.format(e))
                return False  # indicates an error
        return True

    def confirm_and_spin(self, action_dict, *args, **kwargs):
        '''
        called by the exec menu.
        Collects user Confirmation if operation warrants it (Powering off or cycle outlets)
        and Generates appropriate spinner text

        returns tuple
            0: Bool True if user confirmed False if aborted (set to True when no confirmation reqd)
            1: str spinner_text used in exec_menu while function runs
            3: str name (for rename operation)
        '''
        pwr = self.cpi.pwr
        utils = self.cpi.utils
        _func = action_dict['function'].__name__
        _off_str = '{{red}}OFF{{norm}}'
        _on_str = '{{green}}ON{{norm}}'
        _cycle_str = '{{red}}C{{green}}Y{{red}}C{{green}}L{{red}}E{{norm}}'
        _type = _addr = None
        if 'desired_state' in kwargs:
            to_state = kwargs['desired_state']
        if _func in ['pwr_toggle', 'pwr_cycle', 'pwr_rename']:
            _type = args[0].lower()
            _addr = args[1]
            _grp = action_dict['key']
            if _type == 'dli':
                port = kwargs['port']
                if not port == 'all':
                    port_name = pwr.data['dli_power'][_addr][port]['name']
                    to_state = not pwr.data['dli_power'][_addr][port]['state']
            else:
                port = f'{_type}:{_addr}'
                port_name = _grp
                to_state = not pwr.data['defined'][_grp]['is_on']
        if _type == 'dli' or _type == 'tasmota' or _type == 'esphome':
            host_short = utils.get_host_short(_addr)
        else:
            host_short = None

        prompt = spin_text = name = confirmed = None  # init
        if _func == 'pwr_all':
            # self.spin.start('Powering *ALL* Outlets {}'.format(self.states[kwargs['desired_state']]))
            if kwargs['action'] == 'cycle':
                prompt = '{} Power Cycle All Powered {} Outlets'.format('' if _type is None else _type + ':' + host_short,
                                                                        _on_str)
                spin_text = 'Cycling All{} Ports'.format('' if _type is None else ' ' + _type + ':' + host_short)
            elif kwargs['action'] == 'toggle':
                if not kwargs['desired_state']:
                    prompt = 'Power All{} Outlets {}'.format('' if _type is None else ' ' + _type + ':' + host_short, _off_str)
                spin_text = 'Powering {} ALL{} Outlets'.format(self.format_line(kwargs['desired_state'])[1],
                                                               '' if _type is None else _type + ' :' + host_short)
        elif _func == 'pwr_toggle':
            if _type == 'dli' and port == 'all':
                prompt = 'Power {} ALL {} Outlets'.format(
                    _off_str if not to_state else _on_str, host_short)
            elif not to_state:
                if _type == 'dli':
                    prompt = 'Power {} {} Outlet {}({})'.format(
                        _off_str, host_short, port, port_name)
                else:  # GPIO or TASMOTA
                    prompt = 'Power {} Outlet {}({}:{})'.format(
                        _off_str, _grp, _type, _addr)
            spin_text = 'Powering {} {}Outlet{}'.format(self.format_line(to_state)[1],
                                                        'ALL ' if port == 'all' else '',
                                                        's' if port == 'all' else '')
        elif _func == 'pwr_rename':
            try:
                name = input('New name for{} Outlet {}: '.format(
                    ' ' + host_short if host_short else '',
                    port_name if not _type == 'dli' else str(port) + '(' + port_name + ')'))
            except KeyboardInterrupt:
                name = None
                confirmed = False
                print('')  # So header doesn't print on same line as aborted prompt when DEBUG is on
            if name:
                old_name = port_name
                _rnm_str = '{red}{old_name}{norm} --> {green}{name}{norm}'.format(
                    red='{{red}}', green='{{green}}', norm='{{norm}}', old_name=old_name, name=name)
                if _type == 'dli':
                    prompt = 'Rename {} Outlet {}: {} '.format(
                         host_short, port, _rnm_str)
                else:
                    old_name = _grp
                    prompt = 'Rename Outlet {}:{} {} '.format(
                        _type, host_short, _rnm_str)

                spin_text = 'Renaming Port'

        elif _func == 'pwr_cycle':
            if _type == 'dli' and port == 'all':
                prompt = 'Power {} ALL {} Outlets'.format(
                    _cycle_str, host_short)
            elif _type == 'dli':
                prompt = 'Cycle Power on {} Outlet {}({})'.format(
                    host_short, port, port_name)
            else:  # GPIO or TASMOTA
                prompt = 'Cycle Power on Outlet {}({})'.format(
                    port_name, port)
            spin_text = 'Cycling {}Outlet{}'.format('ALL ' if port == 'all' else '', 's' if port == 'all' else '')

        if prompt:
            prompt = self.format_line(prompt)[1]
            confirmed = confirmed if confirmed is not None else utils.user_input_bool(prompt)
        else:
            if _func != 'pwr_rename':
                confirmed = True

        return confirmed, spin_text, name

    # Connection SubMenu
    def con_menu(self, rename=False, con_dict=None):
        # cpi = self.cpi
        menu_actions = {
            '1': self.baud_menu,
            '2': self.data_bits_menu,
            '3': self.parity_menu,
            '4': self.flow_menu,
            'b': self.main_menu if not rename else self.do_rename_adapter,  # not called
            'x': self.exit
        }
        if con_dict:
            self.con_dict = {
                'baud': self.baud,
                'data_bits': self.data_bits,
                'parity': self.parity,
                'flow': self.flow
            }
            self.baud = con_dict['baud']
            self.data_bits = con_dict['data_bits']
            self.parity = con_dict['parity']
            self.flow = con_dict['flow']

        while True:
            self.menu_formatting('header', text=' Connection Settings Menu ')
            print(' 1. Baud [{}]'.format(self.baud))
            print(' 2. Data Bits [{}]'.format(self.data_bits))
            print(' 3. Parity [{}]'.format(self.parity_pretty[self.parity]))
            print(' 4. Flow [{}]'.format(self.flow_pretty[self.flow]))
            text = ' b.  Back{}'.format(' (Apply Changes to Files)' if rename else '')
            self.menu_formatting('footer', text=text)
            # choice = input(" >>  ")
            choice = self.wait_for_input(" >>  ")
            ch = choice.lower()
            try:
                if ch == 'b':
                    break
                menu_actions[ch]()  # could parse and store if decide to use this for something other than rename

            except KeyError as e:
                if ch:
                    self.cpi.error_msgs.append('Invalid selection {}, please try again.'.format(e))

    # Baud Menu
    def baud_menu(self):
        config = self.cpi.config
        menu_actions = od([
            ('1', 300),
            ('2', 1200),
            ('3', 9600),
            ('4', 19200),
            ('5', 57600),
            ('6', 115200),
            ('c', 'custom')
        ])
        text = ' b.  Back'
        std_baud = [110, 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200, 128000, 256000]

        while True:
            # -- Print Baud Menu --
            self.menu_formatting('header', text=' Select Desired Baud Rate ')

            for key in menu_actions:
                # if not callable(menu_actions[key]):
                _cur_baud = menu_actions[key]
                print(' {0}. {1}'.format(key, _cur_baud if _cur_baud != self.baud else '[{}]'.format(_cur_baud)))

            self.menu_formatting('footer', text=text)
            choice = self.wait_for_input(" Baud >>  ")
            ch = choice.lower()

            # -- Evaluate Response --
            try:
                if ch == 'c':
                    while True:
                        self.baud = input(' Enter Desired Baud Rate >>  ')
                        if not config.canbeint(self.baud):
                            print('Invalid Entry {}'.format(self.baud))
                        elif int(self.baud) not in std_baud:
                            _choice = input(' {} is not a standard baud rate are you sure? (y/n) >> '.format(self.baud)).lower()
                            if _choice not in ['y', 'yes']:
                                break
                        else:
                            break
                    # menu_actions['con_menu']()
                elif ch == 'b':
                    break  # return to con_menu
                elif ch == 'x':
                    self.exit()
                # elif type(menu_actions[ch]) == int:
                else:
                    self.baud = menu_actions[ch]
                    break
                    # menu_actions['con_menu']()
            except KeyError as e:
                if choice:
                    self.cpi.error_msgs.append('Invalid selection {} please try again.'.format(e))
                # menu_actions['baud_menu']()

        return self.baud

    # Data Bits Menu
    def data_bits_menu(self):
        valid = False
        while not valid:
            self.menu_formatting('header', text=' Enter Desired Data Bits ')
            print(' Default 8, Current {}, Valid range 5-8'.format(self.data_bits))
            self.menu_formatting('footer', text=' b.  Back')
            choice = input(' Data Bits >>  ')
            try:
                if choice.lower() == 'x':
                    self.exit()
                elif choice.lower() == 'b':
                    valid = True
                elif int(choice) >= 5 and int(choice) <= 8:
                    self.data_bits = choice
                    valid = True
                else:
                    self.cpi.error_msgs.append('Invalid selection {} please try again.'.format(choice))
            except ValueError:
                if choice:
                    self.cpi.error_msgs.append('Invalid selection {} please try again.'.format(choice))
        # self.con_menu()
        return self.data_bits

    def parity_menu(self):
        def print_menu():
            self.menu_formatting('header', text=' Select Desired Parity ')
            print(' Default No Parity\n')
            print(' 1. None')
            print(' 2. Odd')
            print(' 3. Even')
            text = ' b.  Back'
            self.menu_formatting('footer', text=text)
        valid = False
        while not valid:
            print_menu()
            valid = True
            choice = input(' Parity >>  ')
            choice = choice.lower()
            if choice == '1':
                self.parity = 'n'
            elif choice == '2':
                self.parity = 'o'
            elif choice == '3':
                self.parity = 'e'
            elif choice == 'b':
                pass
            elif choice == 'x':
                self.exit()
            else:
                valid = False
                if choice:
                    self.cpi.error_msgs.append('Invalid selection {} please try again.'.format(choice))
        return self.parity

    def flow_menu(self):
        def print_menu():
            self.menu_formatting('header', text=' Select Desired Flow Control ')
            print(' Default No Flow\n')
            print(' 1. No Flow Control (default)')
            print(' 2. Xon/Xoff (software)')
            print(' 3. RTS/CTS (hardware)')
            text = ' b.  Back'
            self.menu_formatting('footer', text=text)
        valid = False
        while not valid:
            print_menu()
            choice = input(' Flow >>  ').lower()
            if choice in ['1', '2', '3', 'b', 'x']:
                valid = True
            try:
                if choice == '1':
                    self.flow = 'n'
                elif choice == '2':
                    self.flow = 'x'
                elif choice == '3':
                    self.flow = 'h'
                elif choice == 'b':
                    # self.con_menu()
                    pass
                elif choice == 'x':
                    self.exit()
                else:
                    if choice:
                        self.cpi.error_msgs.append('Invalid selection {} please try again.'.format(choice))
            except Exception as e:
                if choice:
                    self.cpi.error_msgs.append('Invalid selection {} please try again.'.format(e))
        # self.exec_menu('c', calling_menu='flow_menu')
        return self.flow

    # # Back to main menu
    # def back(self):
    #     self.menu_actions['main_menu']()

    # Exit program
    def exit(self):
        self.go = False
        cpi = self.cpi
        if cpi.pwr._dli:
            for address in cpi.pwr._dli:
                if cpi.pwr._dli[address].dli:
                    if getattr(cpi.pwr._dli[address], 'rest'):
                        threading.Thread(target=cpi.pwr._dli[address].dli.close).start()
                    else:
                        threading.Thread(target=cpi.pwr._dli[address].dli.session.close).start()
        # - if exit directly from rename menu after performing a rename trigger / reload udev
        if self.udev_pending:
            cmd = 'sudo udevadm control --reload && sudo udevadm trigger && sudo systemctl stop ser2net && sleep 1 && sudo systemctl start ser2net '
            with Halo(text='Triggering reload of udev do to name change', spinner='dots1'):
                error = cpi.utils.do_shell_cmd(cmd)
            if error:
                print(error)

        sys.exit(0)


# =======================
#      MAIN PROGRAM
# =======================
if __name__ == "__main__":
    # if argument passed to menu load the class and print the argument (used to print variables/debug)
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ['rn', 'rename', 'addconsole']:
            menu = ConsolePiMenu(bypass_remote=True)
            while menu.go:
                menu.rename_menu(direct_launch=True)
        else:
            menu = ConsolePiMenu(bypass_remote=True)
            config = menu.config
            var_in = sys.argv[1].replace('self', 'menu')
            if 'outlet' in var_in:
                config.wait_for_threads()
            exec('var  = ' + var_in)
            if isinstance(var, (dict, list)):                     # NoQA pylint: disable=undefined-variable
                print(json.dumps(var, indent=4, sort_keys=True))  # NoQA pylint: disable=undefined-variable
            else:
                print(var)                                        # NoQA pylint: disable=undefined-variable
    else:
        # Launch main menu
        menu = ConsolePiMenu()
        while menu.go:
            menu.main_menu()
