#!/etc/ConsolePi/venv/bin/python3

import sys
# import logging
from halo import Halo
from collections import OrderedDict as od
import os

from consolepi import utils

MIN_WIDTH = 55
MAX_COLS = 5


class Menu():

    def __init__(self, config):  # utils, debug=False, log=None, log_file=None):
        self.config = config
        # self.utils = menu.utils
        # self.log = menu.log
        self.go = True
        # self.debug = menu.debug
        # self.debug = config.debug
        self.spin = Halo(spinner='dots')
        self.states = {
            True: '{{green}}ON{{norm}}',
            False: '{{red}}OFF{{norm}}'
        }
        self.error_msgs = []
        self.ignored_errors = []
        self.log_sym_2bang = '\033[1;33m!!\033[0m'
        if sys.stdin.isatty():
            self.rows, self.cols = utils.get_tty_size()
        self.menu_rows = 0  # Updated in menu_formatting
        self.menu_cols = 0

    # def get_logger(self, log_file):
    #     '''Return custom log object.'''
    #     fmtStr = "%(asctime)s [%(module)s:%(funcName)s:%(lineno)d:%(process)d][%(levelname)s]: %(message)s"
    #     dateStr = "%m/%d/%Y %I:%M:%S %p"
    #     logging.basicConfig(filename=log_file,
    #                         # level=logging.DEBUG if self.debug else logging.INFO,
    #                         level=logging.DEBUG if self.cfg['debug'] else logging.INFO,
    #                         format=fmtStr,
    #                         datefmt=dateStr)
    #     return logging.getLogger('ConsolePi')

    # def log_and_show(self, msg, logit=True, showit=True, log=None):
    #     if logit:
    #         log = self.log.info if log is None else log
    #         log(msg)

    #     if showit:
    #         msg = msg.replace('\t', '').split('\n')

    #         [self.error_msgs.append(f'{m.split("]")[1].strip() if "]" in m else m}')
    #             for m in msg
    #             if (']' in m and m.split(']')[1].strip() not in self.error_msgs)
    #             or ']' not in m and m not in self.error_msgs]

    # =======================
    #     MENUS FUNCTIONS
    # =======================
    def print_mlines(self, body, subs=None, header=None, subhead=None, footer=None, foot_fmt=None, col_pad=4,
                     error_msgs=[], force_cols=False, do_cols=True, do_format=True, by_tens=False):
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
            footer: {dict} - where footer['opts'] is list of 'strs' to match key from footer_options dict defined in
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
        # utils = self.utils
        line_dict = od({'header': {'lines': header}, 'body': {'sections': [], 'rows': [],
                        'width': []}, 'footer': {'lines': footer}})

        if error_msgs:
            self.error_msgs += error_msgs
        self.error_msgs += self.config.error_msgs
        self.config.error_msgs = []
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
                    self.plog(f'menu formatter exceeded {len(_rows) + 20} passses and gave up!!!', log=True)
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
        # _final_rows = []
        pad = ' ' * col_pad
        _final_rows = [] if not body['sections'] else body['sections'][0]

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
        if _final_rows:
            _tot_width = len(_final_rows[0]) if len(_final_rows[0]) > _tot_width else _tot_width
        else:
            _tot_width = 0
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

        # utils = self.utils
        log = self.config.log
        # plog = self.config.plog
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

        # -- append any errors from menu builder
        # self.error_msgs += self.menu.error_msgs
        # self.menu.error_msgs = []

        # -- Adjust width if there is an error msg longer then the current width
        # -- Delete any errors defined in ignore errors
        # TODO Move all menu formatting to it's own library - clean this up
        # Think I process errors here and maybe in print_mlines as well
        # addl processing in FOOTER
        if self.error_msgs:
            _temp_error_msgs = self.error_msgs
            for _error in _temp_error_msgs:
                if isinstance(_error, str) and '\n' in _error:
                    _e = _error.split('\n')
                    self.error_msgs.remove(_error)
                    self.error_msgs += _e

            _error_lens = []
            for _error in self.error_msgs:
                if isinstance(_error, list):
                    log.error('{} is a list expected string'.format(_error))
                    _error = ' '.join(_error)
                if not isinstance(_error, str):
                    msg = 'Error presented to formatter with unexpected type {}'.format(type(_error))
                    log.error(msg)
                    _error = msg
                if _error == '':  # Remove empty errors
                    self.error_msgs.remove(_error)
                for e in self.ignored_errors:
                    _e = _error.strip('\r\n')
                    if hasattr(e, 'match') and e.match(_e):
                        self.error_msgs.remove(_error)
                        break
                    elif isinstance(e, str) and (e == _error or e in _error):
                        self.error_msgs.remove(_error)
                        break
                    else:
                        _error_lens.append(self.format_line(_error).len)
            if _error_lens:
                width = width if width >= max(_error_lens) + 5 else max(_error_lens) + 5
            width = width if width <= self.cols else self.cols

        # --// HEADER \\--
        if section == 'header':
            # ---- CLEAR SCREEN -----
            if not self.config.debug:
                os.system('clear')
            mlines.append('=' * width)
            line = self.format_line(text)
            _len = line.len
            fmtd_header = line.text
            # _len, fmtd_header = self.format_line(text)
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
                # _line_len, _line = self.format_line(_line)
                line = self.format_line(_line)
                # width_list.append(_line_len)
                width_list.append(line.len)
                mlines.append(line.text)
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
                        # mlines.append(self.format_line(t)[1])
                        mlines.append(self.format_line(t).text)

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
                    foot_text = [f' {f[k][0]}.{" " if len(f[k][0]) == 2 else "  "}{f[k][1]}' for k in opts if k in f]

                if footer.get('after'):
                    footer['after'] = [footer['after']] if isinstance(footer['after'], str) else footer['after']
                    post_text = [f' {line}' for line in footer['after']]

                mlines = mlines + [''] + pre_text + foot_text + post_text + [''] + ['=' * width]
                # TODO probably simplify to make this a catch all at the end of this method
                # mlines = [self.format_line(line)[1] for line in mlines]
                mlines = [self.format_line(line).text for line in mlines]

                # log errors if non-match overrides/rjust options were sent
                if no_match_overrides + no_match_rjust:
                    self.config.plog(f'menu_formatting passed options ({",".join(no_match_overrides + no_match_rjust)})'
                                     ' that lacked a match in footer_options = No impact to menu', log=True, level='error')

            # --// ERRORs - append to footer \\-- #
            if len(self.error_msgs) > 0:
                errors = self.error_msgs = utils.unique(self.error_msgs)
                for _error in errors:
                    if isinstance(_error, list):
                        log.error('{} is a list expected string'.format(_error))
                        _error = ' '.join(_error)
                    error = self.format_line(_error.strip())
                    x = ((width - (error.len + 4)) / 2)
                    mlines.append('{0}{1}{2}{3}{0}'.format(
                        self.log_sym_2bang,
                        ' ' * int(x),
                        error.text,
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
        class Line():
            '''Constructor Class for line object'''
            def __init__(self, line_len, line_text):
                self.len = line_len
                self.text = line_text

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
        # return len(_l), line
        return Line(len(_l), line)
