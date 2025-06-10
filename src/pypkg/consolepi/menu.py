#!/etc/ConsolePi/venv/bin/python3

import re
import sys
from os import system
from typing import Dict, Iterator, List, Tuple, Union, Any, Iterable

from consolepi import utils, log, config  # type: ignore

MIN_WIDTH = 55
MAX_COLS = 5
DEF_LEGEND_OPTIONS = {
    "back": ("b", "Back"),
    "next": ("n", "Next Page"),
    # "tl": ("tl", "Toggle (show/hide) Legend"),
    "x": ("x", "Exit")
}
COL_PAD = 3
L_OFFSET = 1  # Number of spaces the body of menu is offset from left.
MIN_LINES_FOR_SPLIT_COL = 2  # Min number of item entries that need to be avail in col to split next group


class Line:
    """Constructor Class for line object"""

    def __init__(self, line_len: int, line_text: str) -> None:
        self.len = line_len
        self.text = line_text


def format_line(line: Union[str, bool]) -> Line:
    """Format line for display in menu.

    Args:
        line (str|bool): If str is provided supports formatting placeholders {{red}}, {{blink}}, etc.
                            If bool is provided returns colorized [ON] (green), or [OFF] (red) string.

    Returns:
        object: Line object with len and text attributes, where len is the effective printed len with
                any ASCII formatting characters stripped, and line is formatted (with ASCII colors)
    """

    if isinstance(line, bool):
        line = "{{green}}ON{{norm}}" if line else "{{red}}OFF{{norm}}"

    colors = {
        "green": "\033[1;32m",  # Bold with normal ForeGround
        "red": "\033[1;31m",
        "yellow": "\033[1;33m",
        "blue": "\033[1;34m",
        "magenta": "\033[1;35m",
        "cyan": "\033[1;36m",
        "dgreen": "\033[2;32m",  # Dim with normal ForeGround
        "dred": "\033[2;31m",
        "dyellow": "\033[2;33m",
        "dblue": "\033[2;34m",
        "dmagenta": "\033[2;35m",
        "dcyan": "\033[2;36m",
        "inverted": "\033[7m",
        "norm": "\033[0m",  # Reset to Normal
        "dot": "\u00B7",  # no it's not a color it's a dot
    }

    _l = line
    if "{{" in line:
        for c in colors:
            _l = _l.replace(
                "{{" + c + "}}", ""
            )  # color format var removed to calc effective line length
            line = line.replace(
                "{{" + c + "}}", colors[c]
            )  # line formatted with coloring

    return Line(len(_l), line)


class TTY:
    def __init__(self) -> None:
        self.rows: Union[int, None] = None
        self.cols: Union[int, None] = None
        self.update()

    def __str__(self):
        return "\n".join([
            '',
            'TTY Size:',
            f'  rows: {self.rows}',
            f'  cols: {self.cols}',
            ''
        ])

    def update(self) -> None:
        if sys.stdin.isatty():
            self.rows, self.cols = utils.get_tty_size()
        else:
            self.rows = self.cols = None

    @staticmethod
    def __bool__() -> bool:
        return sys.stdin.isatty()


tty = TTY()


#
#  A section of the menu
#  Header, subhead, body, legend, footer
#
class MenuSection:
    def __init__(self, orig: Any = None, lines: list = [], width_list: list = [], rows: int = 0, cols: int = 0,
                 opts: list = [], overrides: dict = {}, update_method: Any = None, update_args: Union[list, tuple, set] = [],
                 update_kwargs: dict = {}, name: str = None, hide: bool = False) -> None:
        self.hide = hide if name != "legend" else hide or config.hide_legend
        self.orig = orig  # Original unformatted data
        self.lines = lines
        self.width_list = width_list
        self.opts = opts
        self.overrides = overrides
        self.rows = rows
        self.cols = cols
        self.name_in = name
        self.update_method = update_method
        self.update_args = update_args
        self.update_kwargs = update_kwargs

    def __repr__(self):
        if self.name_in:
            name = f" ({self.name_in})"
        else:
            name = "" if not self.update_method else f" ({repr(self.update_method).split('format_')[-1].split()[0]})"
        return f"<{self.__module__}.{type(self).__name__}{name} object at {hex(id(self))}>"

    def __str__(self):
        return "\n".join(self.lines)

    def __len__(self):
        return len(self.lines)

    def __bool__(self):
        return bool(self.lines)

    def __add__(self, data: Union[int, list]):
        if isinstance(data, list):
            line_info = [format_line(line) for line in data]
            self.width_list += [line.len for line in line_info]
            self.lines += [line.text for line in line_info]
            self.update()

    def __getitem__(self, index: Union[int, list, slice, tuple, set]) -> Any:
        if isinstance(index, (int, slice)):
            ret = self.lines[index]
        else:
            try:
                ret = [self.lines[i] for i in index]
            except Exception as e:
                ret = e
        return ret

    @property
    def name(self):
        return self.name_in if self.name_in else self._name()

    def _name(self):
        name = repr(self) if not self.update_method else f"{repr(self.update_method).split('format_')[-1].split()[0]}"
        return name

    def update(self, *args, **kwargs):
        if self.update_method:
            self.update_method(*[*self.update_args, *args], **{**self.update_kwargs, **kwargs})

    def append(self, data: str):
        line = format_line(data)
        self.lines += [line.text]
        self.width_list += [line.len]
        if line.len > self.cols:
            self.cols = line.len
        self.update()

    def get(self, attr: str, default: Any = None):
        if hasattr(self, attr):
            return getattr(self, attr)
        # elif attr in self.data_dict:
        #     return self.data_dict[attr]
        elif default:
            return default
        else:
            raise AttributeError(f'{self.__class__.__name__} does not have attribute {attr}')


#
#   The Primary Menu Object
#   Represents page
#
class MenuParts:
    def __init__(self, name: str = None):
        self.name = name
        self._header = None
        self._subhead = None
        self._body = None
        self._legend = None
        self._footer = None
        self.prev_slice = {}
        self.this_slice = {}
        self.next_slice = {}
        self.parts: Union[List[MenuSection], List[None]] = [
            self.header,
            self.subhead,
            self.body,
            self.legend,
            self.footer
        ]
        # +1 is for prompt line
        self.rows = 0 if len(self) == 0 else (len(self) + 1)
        self.cols = self._cols()
        # tty = tty

    @property
    def header(self):
        return self._header

    @header.setter
    def header(self, new_value):
        self._header = new_value
        self.update()
        # self._header.update(width=self.cols)

    @property
    def subhead(self):
        return self._subhead

    @subhead.setter
    def subhead(self, new_value):
        self._subhead = new_value
        self.update()
        # self._subhead.update(width=self.cols)

    @property
    def body(self):
        return self._body

    @body.setter
    def body(self, new_value):
        self._body = new_value
        self.update()
        # self._body.update(width=self.cols)

    @property
    def legend(self):
        return self._legend

    @legend.setter
    def legend(self, new_value):
        self._legend = new_value
        self.update()
        # self._legend.update(width=self.cols)

    @property
    def footer(self):
        return self._footer

    @footer.setter
    def footer(self, new_value):
        self._footer = new_value
        self.update()
        # self._footer.update(width=self.cols)

    def __repr__(self):
        name = "" if not self.name else f" ({(self.name)})"
        return f"<{self.__module__}.{type(self).__name__}{name} object at {hex(id(self))}>"

    def __len__(self):
        # parts = [self.header, self.subhead, self.body, self.legend, self.footer]
        return sum([p.rows for p in self.parts if p] or [0])

    def __str__(self):
        # ---- CLEAR SCREEN -----
        if not config.debug:
            _ = system("clear -x")
        else:
            print("")  # if DEBUG need this to get off the prompt line

        parts = [self.header, self.subhead, self.body, self.legend, self.footer]
        if self.legend and self.legend.hide:
            _ = parts.pop(parts.index(self.legend))
        log.clear()
        return "\n".join([line for p in parts for line in p.lines])

    def __iter__(self, key: str = None) -> Iterator[MenuSection]:
        # parts = [self.header, self.subhead, self.body, self.legend, self.footer]
        for p in self.parts:
            if not p or (key and p.name != key):  # or (p.name == "legend" and p.hide):
                continue
            else:
                yield p

    def _cols(self):
        # parts = [self.header, self.subhead, self.body, self.legend, self.footer]
        _ = "Do Nothing Break Point Line"  # TODO remove
        return max([p.cols for p in self.parts if p] or [0])

    def update(self):
        self.rows = 0 if len(self) == 0 else (len(self) + 1)
        self.cols = self._cols()
        if self.legend and self.legend.hide:
            if self.legend in self.parts:
                _ = self.parts.pop(self.parts.index(self.legend))
            parts = [self.header, self.subhead, self.footer]
        else:
            self.parts = [self.header, self.subhead, self.body, self.legend, self.footer]
            parts = [self.header, self.subhead, self.legend, self.footer]

        self.body_avail_rows = tty.rows - sum([p.rows for p in parts if p] or [0]) - 1  # -1 for prompt line

    def diag(self, diag_data: List[str] = None):
        tty.update()
        parts = [self.header, self.subhead, self.body, self.legend, self.footer]
        ret = ["", ""]
        if diag_data:
            ret += diag_data

        ret += [f"    tty rows, cols: {tty.rows} {tty.cols}"]
        ret += [
            f"    {p.name} rows, cols: {p.rows} {p.cols}"
            f"{'' if not p.name == 'body' else f' (Available Rows: {self.body_avail_rows})'}"
            for p in parts
        ]
        ret += [f"    Total Menu rows, cols: {self.rows} {self.cols}", ""]
        return "\n".join(ret)


class Menu:
    def __init__(self, name: str = None, left_offset: int = L_OFFSET):  # utils, debug=False, log=None, log_file=None):
        self.name = name
        self.left_offset = left_offset
        self.go: bool = True
        self.def_actions = {
            "dump": self.dump_formatter_data,
            "tl": self.toggle_legend
        }
        self.states = {True: "{{green}}ON{{norm}}", False: "{{red}}OFF{{norm}}"}
        self.ignored_errors: List[Union[str, re.Pattern]] = []  # Populated by menu script consolepi-menu.py
        self.log_sym_2bang: str = "\033[1;33m!!\033[0m"
        self.prev_page: int = 1
        self.cur_page: int = 1
        self.legend_options: Union[Dict[str, List[str]], None] = None
        self.init_pager()
        self.page = MenuParts(name)  # Needs to come after init_pager()
        self.actions: Union[Dict[str, str], None] = None  # set in print_menu()
        self.body_in = None
        self.items_in = None
        self.subs_in = None
        self.legend_in = None
        self.menu_actions_in: Union[Dict[str, str], None] = None
        self.pbody = None
        self.pitems = None
        self.psubs: Union[List[str], None] = None
        self.reverse = False
        self.prev_header = None
        self.tot_body_1col_rows = 0
        self.pages = {}
        self.item = 1
        self.tty = tty

    def __repr__(self):
        name = "" if not self.name else f" ({self.name})"
        return f"<{self.__module__}.{type(self).__name__}{name} object at {hex(id(self))}>"

    def init_pager(self):
        self.prev_page = self.cur_page
        self.prev_col_width: int = 0  # assigned in do_pager
        self.col_width: int = 0       # assigned in do_pager
        self.page_width: int = 0      # assigned in do_pager
        self.cur_page_width: int = 0  # assigned in pager_write_other_col

    def print_menu(
        self,
        body: list,
        subs: Union[List[str], None] = None,
        header: Union[str, list] = None,
        subhead: Union[str, list] = None,
        legend: Union[dict, list] = None,
        format_subs: bool = False,
        by_tens: bool = False,
        menu_actions: dict = {},
        hide_legend: bool = None,
    ) -> dict:
        """Format and print current menu, sized to fit terminal.  Pager implemented if required.

        Args:
            body (list): A list of lists or list of strings, where each inner list is made up of text for each menu-item
                         in that logical section/group.
            subs (list, optional): A list of sub-head lines that map to each inner body list.  This is the header for the
                                   specific logical grouping of menu-items. Should be of equal len to body list.
                                   Defaults to None.
            header (str|list, optional): The main header text for the menu. Multi-Line header via list of strings.
                                         Defaults to None.
            subhead (str|list, optional): Subhead text is printed below the main menu header with blank lines added before and
                                       after. Defaults to None.
            legend (dict|list, optional): If a list is provided it should be a list of strings matching keys in the class
                                          attribute legend_options.
                                          If dict is provided legend = {
                                              "opts": [keys], "overrides": {
                                                  "key": ("item", "description")
                                                  }
                                              }
                                          Where item and description are what prints in the legend.
                                          Defaults to None.
            col_pad (int, optional): The amount of spacing inserted in betweeen each vertical column in the menu. The col_pad is
                                     reduced to as low as 1 if menu overruns tty size.
                                     Defaults to 4.
            format_subs (bool, optional): Only Applies to sub-head auto formatting.
                                        Auto formatting results in '------- sub text -------' (width of section)
                                        Defaults to True.
            by_tens (bool, optional): Will start each section @ 1, 11, 21, 31... unless the section is greater than 10.
                                      Defaults to False.
            menu_actions (dict, optional): The Actions dict (TODO make object).  Determines what function is called when a menu
                                           item is selected Defaults to {}.
            menu_actions (bool, optional): Override config option for menus where you always want legend printed.

        Returns:
            [dict]: Returns the menu_actions dict which may include paging actions if warranted.
        """
        self.tty.update()

        do_size = False
        if not self.body_in:
            self.body_in = body
            do_size = True

        refresh = False
        if not self.subs_in:
            self.subs_in = subs

        # if a refresh triggered a change to subs/body reset to page 1
        elif subs:
            if len(body) != len(self.body_in):
                refresh = True
                self.subs_in = subs
                self.body_in = body
                self.reverse = False
                self.pbody, self.psubs, self.pitems = None, None, None
                self.prev_page, self.cur_page = 1, 1
                self.page.prev_slice = {}
                self.reverse = False

        # This sets the menu items (the numbers the user selects) as a list of List[int]
        if not self.items_in or refresh:
            x = 1
            self.items_in = []
            for idx, sec in enumerate(self.body_in):
                if idx > 0:
                    x += len(self.body_in[idx - 1])
                self.items_in.append([y + x for y in range(len(sec))])

        if menu_actions:
            self.menu_actions_in = menu_actions
            self.actions = None

        self.actions = self.menu_actions_in if not self.actions else {**self.menu_actions_in, **self.actions}

        if not self.legend_in or self.legend_in != legend:
            if isinstance(legend, dict):
                self.legend_in = legend
            elif isinstance(legend, list):
                self.legend_in = {"opts": legend}

        self.legend_options = DEF_LEGEND_OPTIONS if not self.legend_options else {**DEF_LEGEND_OPTIONS, **self.legend_options}
        header = self.format_header(header)
        subhead = self.format_subhead(subhead)
        self.format_legend(self.legend_in)
        if hide_legend is not None:
            self.page.legend.hide = hide_legend
        self.format_footer()

        if not subs:
            header.append("")

        if do_size:
            self.size = self.calc_size(self.body_in, subs, format_subs=format_subs, by_tens=by_tens)

        self.pg_cnt = 0
        try:
            self.size.get_cols(self.page.body_avail_rows)
            if len(self.size.pages) > 1:
                self.page.body_avail_rows -= 1
            self.pg_cnt = len(self.size.pages)
            self.addl_rows = self.size.addl_rows
        except Exception as e:
            log.error(f"Exception in size.get_cols() {e}")

        # if str was passed place in list to iterate over
        if isinstance(body, str):
            body = [body]

        # ensure body is a list of lists for mapping with list of subs
        _body = [body] if len(body) >= 1 and isinstance(body[0], str) else body

        # Override body and sub lists when navigating paged output
        _body = _body if not self.pbody else self.pbody
        subs = subs if not self.psubs else self.psubs
        items = self.items_in if not self.pitems else self.pitems

        if subs and len(_body) != len(subs):
            raise ValueError("body list and sub list not of equal size")

        prev_pages = self.pages
        if self.pages:
            self.pages = {k: [] for k in self.pages.keys() if k <= self.cur_page}

        # -- // EMPTY MENU No Adapters / HOSTS / REMOTES \\ --
        if not body:
            return self.empty_menu()

        # # -- // SET STARTING ITEM # \\ --
        if not self.reverse:
            item = min([item for sublist in items for item in sublist])
        else:
            item = max([item for sublist in items for item in sublist])

        if not self.reverse:
            self.page.next_slice = {}
        self.page.this_slice = {}

        start = 1 if not self.reverse else 10
        col_lines = []
        addl_rows = 0
        section_slices = {}

        equal_sections = True if by_tens or len(set([len(section) for section in _body])) == 1 else False
        max_section = max([len(section) + addl_rows for section in _body])
        for idx, _section in enumerate(_body):
            if subs:
                try:
                    sec = self.subs_in.index(subs[idx])
                except ValueError as e:
                    log.debug(f"{e.__class__.__name__}: {e}", show=log.DEBUG or config.debug)
                    match = [i for i, x in enumerate(self.subs_in) if x.startswith(subs[idx].split(" @")[0])]
                    if match and len(match) == 1:
                        sec = match[0]
                        self.subs_in[sec] = subs[idx]  # update original all subs list to include updated sub entry
                    else:
                        sec = idx
                sub = subs[idx]
            else:
                sec = idx
                sub = None

            if by_tens and _body.index(_section) > 0:
                if not self.reverse:
                    item = start + 10 if item <= start + 10 else item
                    start += 10
                else:  # TODO This is not tested
                    item = start - 10 if item >= start - 10 else item
                    start -= 10

            # -- Get # of addl_rows added to section by formatter (ran for 1st section only)
            if _body.index(_section) == 0:
                if not hasattr(self, "addl_rows"):
                    this_lines, this_width, this_rows = self.format_section(
                        body=_section,
                        sub=sub,
                        index=item,
                        format_sub=format_subs,
                    )

                    # determine how many addl rows were added by formatter
                    addl_rows = this_rows - len(_section)
                else:
                    addl_rows = self.addl_rows
                # determine number of rows if menu printed as 1 col
                self.tot_body_1col_rows = sum([len(_section) + addl_rows for _section in _body])

            # current col must have room for 3 items from section otherwise new section starts in next col
            if self.page.body_avail_rows - len(col_lines) >= 3 + addl_rows:
                if (len(col_lines) + len(_section) + addl_rows) >= self.tot_body_1col_rows / 2 and \
                        (len(col_lines) + len(_section) + addl_rows) <= self.page.body_avail_rows:
                    _end = len(_section)
                elif (len(col_lines) + len(_section) + addl_rows) >= self.page.body_avail_rows:
                    if self.pg_cnt == 1 and len(_body) <= 3 and max_section <= self.page.body_avail_rows:
                        _end = len(_section)
                    else:                                       # HACK the -1 below is a hack
                        _end = self.page.body_avail_rows - (len(col_lines) + addl_rows) - 1  # FIXME avail rows 52 cols 190 hide legend.  wsl menu 108 through sec 15 on 1st page 2nd page sec 16 gets stripped to slice(12, 13, 1) rather than (0, 13, 1)
                elif len(_section) + addl_rows <= self.page.body_avail_rows:             # It's the first col of the next page shouldn't be stripped.  _end should be 11 it's being set to 12 body_avail_rows is 45 disregarding space at top and bot body is 43
                    _end = len(_section)
                else:
                    _end = self.page.body_avail_rows - len(col_lines) - addl_rows
            elif self.pg_cnt == 1 and len(_body) <= 3 and max_section <= self.page.body_avail_rows:
                _end = len(_section)
            else:
                _end = self.page.body_avail_rows - addl_rows

            # -- break sections with too many rows to fit tty into list of slices for each col that fit into limits of tty
            if 0 < _end < len(_section):
                _slice = [slice(0, _end, 1)]
                while len(_section[_end:len(_section)]) + addl_rows > self.page.body_avail_rows:
                    _start, _end = _end, _end + (self.page.body_avail_rows - addl_rows)
                    _slice += [slice(_start, _end, 1)]

                # Add any remaining slices in section
                if _end < len(_section):
                    _slice += [slice(_end, len(_section), 1)]
            else:
                _slice = [slice(0, len(_section), 1)]

            for s in _slice:
                sub_section = _section[s]

                # Update sub-header for section if CONTINUED
                _sub_key = 0 if not self.reverse else -1
                try:
                    if sub and sub_section[_sub_key].split()[0] != self.body_in[sec][0].split()[0]:
                        if "Local Adapters" in sub:
                            # if self.name != "rename_menu":
                            sub = f"[CONTINUED] {sub.replace('Rename ', '')}"
                        else:
                            sub = f"[CONTINUED] {sub.split('] ')[-1].split(' @')[0].split(' on ')[-1]}"
                except Exception as e:
                    sub = f"{sub} <-- Exception ({e.__class__.__name__})"

                # if debug enabled Add index of section to section header (sub)
                if sub and config.debug and not sub.startswith(f"-{sec}-"):
                    sub = f"-{sec}-{sub}"

                this_lines, this_width, this_rows = self.format_section(
                    body=sub_section,
                    sub=sub,
                    index=item,
                    format_sub=format_subs
                )

                item = item + len(sub_section) if not self.reverse else item - len(sub_section)

                # Broken out this way for easier debug / verification of logic (step through in debugger)
                if col_lines and len(col_lines) + this_rows > self.page.body_avail_rows:
                    self.pager_write_col_to_page(col_lines, section_slices)
                    section_slices = {}
                    # -- Prev Col written update col with current lines
                    col_lines = this_lines
                    self.col_width = this_width
                elif col_lines and len(col_lines) + len(this_lines) >= self.tot_body_1col_rows / 2 and (
                    not self.pages or (
                        len(self.pages[self.cur_page]) > 0 and not (
                            len(col_lines) + len(_section) + addl_rows) <= len(self.pages[self.cur_page])
                    )
                ):
                    self.pager_write_col_to_page(col_lines, section_slices)
                    section_slices = {}
                    # -- Prev Col written update col with current lines
                    col_lines = this_lines
                    self.col_width = this_width
                elif col_lines and max_section <= self.page.body_avail_rows and equal_sections:
                    self.pager_write_col_to_page(col_lines, section_slices)
                    section_slices = {}
                    # -- Prev Col written update col with current lines
                    col_lines = this_lines
                    self.col_width = this_width
                elif col_lines and sum([len(s) + addl_rows for s in _body[idx:]]) <= len(col_lines) and \
                        not len(col_lines) + len(this_lines) <= self.page.body_avail_rows:  # len(self.pages[self.cur_page]):
                    self.pager_write_col_to_page(col_lines, section_slices)
                    section_slices = {}
                    # -- Prev Col written update col with current lines
                    col_lines = this_lines
                    self.col_width = this_width
                elif col_lines and self.cur_page == 1 and self.pg_cnt == 1 and \
                        len(_body) <= 3 and max_section <= self.page.body_avail_rows:
                    self.pager_write_col_to_page(col_lines, section_slices)
                    section_slices = {}
                    # -- Prev Col written update col with current lines
                    col_lines = this_lines
                    self.col_width = this_width
                else:  # -- Appending to Existing Column Col not written to Page Yet
                    if not self.reverse:
                        col_lines += this_lines
                    else:
                        col_lines = this_lines + col_lines

                    if this_width > self.col_width:
                        self.col_width = this_width

                if self.cur_page_width >= self.page.legend.cols:
                    self.page.legend.lines = [f"{line:{self.cur_page_width}}" for line in self.page.legend.lines]
                    self.page.legend.cols = self.cur_page_width

                section_slices[sec] = s if not self.reverse else \
                    slice(len(self.body_in[sec]) - s.stop, len(self.body_in[sec]) - s.start, 1)

        # Write Final Col
        self.pager_write_col_to_page(col_lines, section_slices)

        if self.reverse:
            self.pages = {**prev_pages, **self.pages}

        self.page.body = MenuSection(
            lines=self.pages[self.cur_page],
            rows=len(self.pages[self.cur_page]),
            cols=self.cur_page_width,
            name="body"
        )

        # Adds Next/Back option as appropriate for Paged Menu
        self.pager_update_legend()

        # update slices (first/last items) in the event tty was resized and no page change was selected
        self.update_slices()

        # FIXME this was issue with con menu where legend was widest section
        self.cur_page_width = max([self.cur_page_width, self.page.legend.cols, self.page.footer.cols, self.page.header.cols])

        for menu_part in [self.page.legend, self.page.footer, self.page.header]:
            menu_part.update(width=self.cur_page_width)
            # menu_part.update(width=self.page.cols)

        # -- // PRINT THE MENU \\ --
        print(self.page)

        self.init_pager()

        return {**self.def_actions, **self.actions}

    def dump_formatter_data(self):
        diag_data = [f"    Total Rows(1 col): {self.tot_body_1col_rows}"]
        print(self.page.diag(diag_data))
        input('Press Enter to Continue... ')

    def empty_menu(self) -> None:
        '''Print Menu with Empty body when no body is provided to print_menu().
        '''
        self.page.body = MenuSection(
            lines=[],
            rows=0,
            cols=0,
            name="body"
        )

        self.format_subhead(
            [
                "",
                "No local serial devices found.",
                "No remote ConsolePis discovered and reachable.",
                "No Manually Defined TELNET/SSH hosts configured.",
                f"{self.log_sym_2bang}  There is Nothing to display  {self.log_sym_2bang}"
            ]
        )
        opts = ["x"] if not self.legend_in or "refresh" not in self.legend_in.get("opts", []) else ["refresh", "x"]
        self.page.legend.update(legend={"opts": opts}, width=self.page.cols)

        for menu_part in [self.page.legend, self.page.footer, self.page.header]:
            menu_part.update(width=self.page.cols)

        print(self.page)
        self.init_pager()

        return self.menu_actions_in

    def calc_size(self, body: list, subs: Union[list, None],
                  format_subs: bool = False, by_tens: bool = False) -> object:
        # tty = tty
        body = utils.listify(body)
        body = [body] if len(body) >= 1 and isinstance(body[0], str) else body
        reverse = self.reverse
        format_section = self.format_section
        cur_page = self.cur_page
        body_avail_rows = self.page.body_avail_rows
        left_offset = self.left_offset

        class Size:
            def __init__(self):
                self.body_avail_rows = body_avail_rows
                self.left_offset = left_offset
                self.lines = []
                self.cols = []
                self.rows = []
                self.pages = {}
                self.col_width: int = 0
                self.page_width: int = 0
                # self.vert_cols: int = 0  # TODO Remove once verified no side effects
                self.page: int = 1
                self.body = body  # original unformatted data
                self.subs = subs
                self.addl_rows = None
                self.format_section = format_section
                self.cur_page = cur_page
                self.prev_slice = {}
                self.this_slice = {}
                self.next_slice = {}

            def __call__(self, lines, cols, rows):
                self.append(lines, cols, rows)
                return self

            def __iter__(self, key: Union[slice, tuple, int] = None) -> Iterable[Tuple[int, int, int, int]]:
                print("hit")
                if key:
                    if isinstance(key, tuple):
                        _slice = slice(*key)
                    else:
                        _slice = key
                else:
                    _slice = slice(0, len(self.lines), 1)

                for idx, (_lines, _rows, _cols) in enumerate(zip(self.lines[_slice],
                                                                 self.rows[_slice],
                                                                 self.cols[_slice])):
                    yield idx, _lines, _rows, _cols

            def append(self, lines: list = None, cols: int = None, rows: int = None):
                if lines:
                    self.lines += [lines]
                if cols:
                    self.cols += [cols]
                if rows:
                    self.rows += [rows]

            def get_cols(self, body_avail_rows: int = None):
                body_avail_rows = self.body_avail_rows if body_avail_rows is None else body_avail_rows
                # first pass to determine what is possible then break, second pass populates menu
                self.addl_rows = addl_rows  # FIXME why does addl_rows have value here
                for _pass in range(2):
                    col_lines = []
                    section_slices = {}
                    self.pages = {}
                    self.page = 1
                    _stop = False
                    item = 1
                    for idx, lines in enumerate(body):
                        rows = self.rows[idx]

                        if self.body_avail_rows - len(lines) >= 3 + addl_rows:
                            _end = self.body_avail_rows - len(lines) - addl_rows
                        else:
                            _end = self.body_avail_rows - addl_rows

                        # -- break sections with too many rows to fit tty into list of slices for each col that fit into tty
                        if 0 < _end < len(lines):
                            _slice = [slice(0, _end, 1)]
                            while len([lines[s] for s in _slice]) > self.body_avail_rows:
                                _start, _end = _end, _end + (self.body_avail_rows - addl_rows)
                                _slice += [slice(_start, _end, 1)]

                            # Add any remaining slices in section
                            if _end < rows:
                                _slice += [slice(_end, len(lines), 1)]
                        else:
                            _slice = [slice(0, len(lines), 1)]

                        for s in _slice:
                            sub_section = self.body[idx][s]

                            # -- Format Sub Heading for CONTINUED Lines
                            sub = None if not self.subs else self.subs[idx]
                            _sub_key = 0 if not reverse else -1
                            if sub and sub_section[_sub_key] != self.body[idx][0]:
                                sub = f"[CONTINUED] {sub.split('] ')[-1].split(' @')[0]}"

                            this_lines, this_cols, _ = self.format_section(
                                body=sub_section,
                                sub=sub,
                                index=item,
                                format_sub=format_subs,
                            )

                            item = item + len(sub_section) if not reverse else item - len(sub_section)

                            section_slices[idx] = s if not reverse else \
                                slice(len(self.body[idx]) - s.stop, len(self.body[idx]) - s.start)

                            if len(col_lines) + len(this_lines) > self.body_avail_rows:

                                if self.page not in self.pages:
                                    self.pager_write_first_col(col_lines, page=self.page)
                                else:
                                    self.pager_write_other_col(col_lines, page=self.page)

                                # if self.page == self.cur_page:
                                #     self.vert_cols += 1

                                if tty.cols and self.page_width + self.col_width > tty.cols:
                                    self.page += 1
                                    if _pass == 0:
                                        self.body_avail_rows -= 1
                                        _stop = True
                                        break

                                # -- Prev Col written update col with current lines
                                col_lines = this_lines
                                self.col_width = this_cols
                                if self.page == self.cur_page:
                                    self.this_slice = {**self.this_slice, **section_slices}
                                elif self.page < self.cur_page:
                                    self.prev_slice = {**self.prev_slice, **section_slices}
                                else:
                                    self.next_slice = {**self.next_slice, **section_slices}
                                section_slices = {}
                            else:  # -- Appending to Existing Column Col not written to Page Yet
                                if not reverse:
                                    col_lines += this_lines
                                else:
                                    col_lines = this_lines + col_lines

                                if this_cols > self.col_width:
                                    self.col_width = this_cols

                        # abort loop and start next loop with updated body size
                        if _stop:
                            break
                    # abort loop and start next loop with updated body size
                    if _stop:
                        break

                # Write Final Col
                if self.page not in self.pages:
                    self.pager_write_first_col(col_lines, page=self.page)  # type: ignore
                else:
                    self.pager_write_other_col(col_lines, page=self.page)  # type: ignore

                # if self.page == self.cur_page:
                #     self.vert_cols += 1

                if self.page == self.cur_page:
                    self.this_slice = {**self.this_slice, **section_slices}  # type: ignore
                elif self.page < self.cur_page:
                    self.prev_slice = {**self.prev_slice, **section_slices}  # type: ignore
                else:
                    self.next_slice = {**self.next_slice, **section_slices}  # type: ignore

            # -- // Helpers called by pager_write_col_to_page() \\ --
            def pager_write_first_col(self, col_lines: list, page: int) -> None:
                '''Writes first Col to Page

                Args:
                    col_lines (list): list of strings representing each menu option/choice.
                    page (int): The Page to write the output to
                '''
                self.pages[page] = [f"{line:{self.col_width}}" for line in col_lines]
                self.page_width = self.col_width
                self.prev_col_width = self.col_width

            def pager_write_other_col(self, col_lines: list, page: int) -> None:
                '''Writes additional col to existing page

                Args:
                    col_lines (list): list of strings representing each menu option/choice.
                    page (int): The Page to write the output to
                '''
                # - pad any cols that are shorter with spaces matching the longest col on the page
                if len(self.pages[page]) < len(col_lines):
                    for _ in range(len(col_lines) - len(self.pages[page])):
                        self.pages[page] += [" " * self.page_width]
                elif len(col_lines) < len(self.pages[page]):
                    for _ in range(len(self.pages[page]) - len(col_lines)):
                        col_lines += [f"{' ':{self.col_width}}"]

                col_pad = COL_PAD - self.left_offset
                if not reverse:
                    self.pages[page] = [
                        f"{line[0]}{' ':{col_pad}}{line[1]:{self.col_width}}"
                        for line in zip(self.pages[page], col_lines)
                    ]
                else:  # Add From Right to Left when parsing slices in reverse order (Back)
                    self.pages[page] = [
                        f"{line[0]:{self.col_width}}{' ':{col_pad}}{line[1]:{self.col_width}}"
                        for line in zip(col_lines, self.pages[page])
                    ]

                self.page_width += (col_pad + self.col_width)

        size = Size()
        start = item = 1
        addl_rows = 0
        for i, _section in enumerate(body):
            if by_tens and i > 0:
                item = start + 10 if item <= start + 10 else item
                start += 10
            this_lines, this_width, this_rows = self.format_section(
                body=_section,
                sub=None if subs is None else subs[i],
                index=item, format_sub=format_subs
            )
            if i == 0:
                addl_rows = this_rows - len(_section)
            size = size(this_lines, this_width, this_rows)
            item = item + len(_section)

        return size

    def toggle_legend(self):
        '''Toggles Display of the Legend.
        '''
        config.hide_legend = self.page.legend.hide = not self.page.legend.hide
        # if self.page.legend.hide:
        #     self.page.legend.lines = []
        #     self.page.legend.rows, self.page.legend.cols = 0, 0

    def pager_write_col_to_page(self, col_lines: list, col_slices: dict, legend_lines: list = None) -> None:
        '''Writes Column completed column to Page (Body) extending to legend once beyond legend text.

        Args:
            col_lines (list): list of formatted strings representing each menu option/choice
            col_slices (dict): {idx: (start, stop)} Where idx is the index of the parent section
                              from the original data provided to the menu (self.body_in) and
                              start, stop = where to slice that section for the current sub-section
            legend_lines (list, optional): list of formatted strings representing each menu option/choice
                                           written to legend once page is beyond legend text
                                           Default to None


        '''
        page = 1 if not self.pages else len(self.pages)
        if tty.cols and self.page_width + (COL_PAD - self.left_offset) + self.col_width > tty.cols:
            # Increment page unless this is first col of first page
            page = page if not self.pages[page] else page + 1

        for idx in col_slices:
            if page == self.cur_page:
                _attr = getattr(self.page, "this_slice")
            elif page < self.cur_page:
                _attr = getattr(self.page, "prev_slice")
            else:
                _attr = getattr(self.page, "next_slice")

            # pager only parses slices for next page adjust first slice to match index of original body (body_in)
            # if not self.cur_page < self.prev_page and idx in self.page.prev_slice:
            if not self.reverse:
                if idx in self.page.prev_slice:
                    col_slices[idx] = slice(
                        self.page.prev_slice[idx].stop + col_slices[idx].start,
                        self.page.prev_slice[idx].stop + col_slices[idx].stop,
                        1
                    )
            else:
                if idx in self.page.next_slice:
                    col_slices[idx] = slice(
                        self.page.next_slice[idx].stop - col_slices[idx].stop,
                        self.page.next_slice[idx].stop - col_slices[idx].start,
                        1
                    )

            if not _attr.get(idx):
                # overflow from prev_slices when parsing backward would go into next_slice, next_slice is retained
                # as prev this_slice so just ignore the overflow.
                # if not self.cur_page < self.prev_page or page <= self.cur_page:
                if not self.reverse or page <= self.cur_page:
                    _attr[idx] = col_slices[idx]
            else:
                # if not self.cur_page < self.prev_page:
                if not self.reverse:
                    _attr[idx] = slice(_attr[idx].start, col_slices[idx].stop, 1)
                else:
                    _attr[idx] = slice(col_slices[idx].start, _attr[idx].stop, 1)

        # -- // Col Full but PAGE DOESN't EXIST YET - Write First Col \\ --
        if not self.pages.get(page):
            # When parsing in reverse only print cur_page
            if not (page > self.cur_page and self.reverse):
                self.pager_write_first_col(col_lines, page)
        else:  # -- // PAGE NOT FULL write existing col_lines to page \\ --
            self.pager_write_other_col(col_lines, page)
            if legend_lines:
                self.pager_write_other_col(legend_lines, page)  # , legend=True)

        if page == self.cur_page:
            self.cur_page_width = self.page_width  # self.page_width updated in helper methods

    # -- // Helpers called by pager_write_col_to_page() \\ --
    def pager_write_first_col(self, col_lines: list, page: int) -> None:
        '''Writes first Col to Page

        Args:
            col_lines (list): list of strings representing each menu option/choice.
            page (int): The Page to write the output to
        '''
        self.pages[page] = [f"{line:{self.col_width}}" for line in col_lines]
        self.page_width = self.col_width
        self.prev_col_width = self.col_width

    def pager_write_other_col(self, col_lines: list, page: int) -> None:
        '''Writes additional col to existing page

        Args:
            col_lines (list): list of strings representing each menu option/choice.
            page (int): The Page to write the output to
        '''
        # - pad any cols that are shorter with spaces matching the longest col on the page
        if len(self.pages[page]) < len(col_lines):
            for _ in range(len(col_lines) - len(self.pages[page])):
                self.pages[page] += [" " * self.page_width]
        elif len(col_lines) < len(self.pages[page]):
            for _ in range(len(self.pages[page]) - len(col_lines)):
                col_lines += [f"{' ':{self.col_width}}"]

        col_pad = COL_PAD - self.left_offset
        if not self.reverse:
            self.pages[page] = [
                f"{line[0]}{' ':{col_pad}}{line[1]:{self.col_width}}"
                for line in zip(self.pages[page], col_lines)
            ]
        else:  # Add From Right to Left when parsing slices in reverse order (Back)
            self.pages[page] = [
                f"{line[0]:{self.col_width}}{' ':{col_pad}}{line[1]:{self.col_width}}"
                for line in zip(col_lines, self.pages[page])
            ]

        self.page_width += (col_pad + self.col_width)

    def pager_update_legend(self):
        '''Updates the Legend with Back/Next Options as appropriate for Paged menu.
        '''
        # -- Add Navigation options when menu is paged
        if self.page.prev_slice:
            self.actions = {**self.actions, **{"b": self.pager_prev_page}}
            if "back" not in self.page.legend.opts:
                self.page.legend.opts.insert(len(self.page.legend.opts) - 2, 'back')
            self.legend_options["back"] = ("b", "Back (Prev Page)")
        else:  # Page 1
            # Restore legend options to default (resets Back)
            self.legend_options = {**self.legend_options, **DEF_LEGEND_OPTIONS}
            # self.actions = {**self.actions, **self.menu_actions_in}
            if "b" in self.actions and self.actions["b"] and self.actions["b"].__name__ == "pager_prev_page":
                del self.actions["b"]
                if 'back' in self.page.legend.opts:
                    self.page.legend.opts.pop(
                        self.page.legend.opts.index('back')
                    )

        if self.page.next_slice:
            self.actions = {**self.actions, **{"n": self.pager_next_page}}
            self.page.legend.opts.insert(len(self.page.legend.opts) - 2, 'next')
        else:
            if "n" in self.actions:
                del self.actions["n"]
            if "next" in self.page.legend.opts:
                self.page.legend.opts.pop(
                    self.page.legend.opts.index('next')
                )

        # Tweak order of Final Legend Options so that last entries are refresh, back, next, exit
        for opt in ["refresh", "back", "next", "x"]:
            if opt in self.page.legend.opts:
                self.page.legend.opts.pop(
                    self.page.legend.opts.index(opt)
                )
                self.page.legend.opts += [opt]

    def pager_next_page(self):
        '''Configure Menu to advance to next Page.

        pbody and psubs attributes are updated, they override the original body/subs lists provided to the menu
        prev_slice is updated to include this_slice (the page your navigating from)
        this_slice is reset and populated (Slices for the page we are navigating to) by print_menu()
        next_slice is reset and populated with slices for anything that doesn't fit into this_slice (the new page)

        This ensures all sections print, if all pages where stashed on the original instantiation, a section could be
        skipped given the menu size is dynamic (log area, and user could resize)
        '''
        self.reverse = False
        self.pbody = [self.body_in[sec][self.page.next_slice[sec]] for sec in self.page.next_slice]
        self.pitems = [self.items_in[sec][self.page.next_slice[sec]] for sec in self.page.next_slice]
        self.psubs = None if not self.subs_in else [self.subs_in[sec] for sec in self.page.next_slice]

        # Add slices for this_page to prev_page adjust last section start/stop if it's split between pages
        _first_key = [_ for _ in sorted(self.page.this_slice.keys())][0]
        if _first_key in self.page.prev_slice:
            self.page.this_slice[_first_key] = slice(self.page.prev_slice[_first_key].start,
                                                     self.page.this_slice[_first_key].stop, 1)
        self.page.prev_slice = {**self.page.prev_slice, **self.page.this_slice}
        self.page.next_slice = {}

        self.prev_page = self.cur_page
        self.cur_page += 1

    def pager_prev_page(self, reprint: bool = False):
        '''Configure Menu to go to Prev Page.

        pbody and psubs attributes are updated, they override the original body/subs lists provided to the menu
        next_slice is set to this_slice (the page we are moving from)
        prev_slice remains as is (which will include all previous pages)
        this_slice is reset and populated by print_menu()

        The Menu is built in reverse, high to low / right to left

        This ensures all sections print, if all pages where stashed on the original instantiation, a section could be
        skipped given the menu size is dynamic (log area, and user could resize)
        '''
        if self.cur_page - 1 > 1 or reprint:
            self.reverse = True
            self.pbody = [self.body_in[sec][self.page.prev_slice[sec]][::-1]
                          for sec in sorted(self.page.prev_slice, reverse=True)]
            self.pitems = [self.items_in[sec][self.page.prev_slice[sec]][::-1]
                           for sec in sorted(self.page.prev_slice, reverse=True)]
            self.psubs = [self.subs_in[sec] for sec in sorted(self.page.prev_slice, reverse=True)]

            # Add slices for this_page to next page slices adjust last section start/stop if it's split between pages
            _last_key = [_ for _ in sorted(self.page.this_slice)][-1]
            if _last_key in self.page.next_slice:
                self.page.next_slice[_last_key] = slice(self.page.this_slice[_last_key].start,
                                                        self.page.next_slice[_last_key].stop, 1)
            self.page.next_slice = {**self.page.this_slice, **self.page.next_slice}

            self.prev_page = self.cur_page
        else:
            self.pbody, self.psubs, self.pitems = None, None, None
            self.prev_page = 1
            self.page.prev_slice = {}
            self.reverse = False
            self.actions = {**self.actions, **self.menu_actions_in}

        if not reprint:
            self.cur_page -= 1

    def pager_reverse_parse_update(self):
        # Clean prev_slices that have been populated to this_slice
        self.page.this_slice = {k: v for k, v in sorted(self.page.this_slice.items())}
        for idx in self.page.this_slice:
            if idx in self.page.prev_slice:
                if self.page.this_slice[idx].start == 0:  # _attr = this_slice
                    del self.page.prev_slice[idx]
                else:
                    self.page.prev_slice[idx] = slice(0, self.page.this_slice[idx].start, 1)
        # If user caused reduction of avail lines for error display or tty resize a section could be removed
        # this will re-populate any orphaned sections into prev_slice
        if len(self.page.prev_slice) not in self.page.this_slice:
            self.page.prev_slice[len(self.page.prev_slice)] = slice(0, len(self.body_in[len(self.page.prev_slice)]), 1)

    def update_slices(self):
        # Ensure slice dicts are sorted
        if self.page.prev_slice:
            self.page.prev_slice = {k: self.page.prev_slice[k] for k in sorted(self.page.prev_slice)}
        if self.page.this_slice:
            self.page.this_slice = {k: self.page.this_slice[k] for k in sorted(self.page.this_slice)}
        if self.page.next_slice:
            self.page.next_slice = {k: self.page.next_slice[k] for k in sorted(self.page.next_slice)}

        if not self.page.this_slice or self.cur_page > self.prev_page:
            return
        elif self.reverse:
            self.pager_reverse_parse_update()
        else:
            if self.page.next_slice:
                for _last_key in [_ for _ in self.page.this_slice.keys()][::-1]:
                    if _last_key not in self.page.next_slice:
                        break
                    else:
                        if self.page.this_slice[_last_key].stop == len(self.body_in[_last_key]):
                            del self.page.next_slice[_last_key]
                        else:
                            self.page.next_slice[_last_key] = slice(self.page.this_slice[_last_key].stop,
                                                                    self.page.next_slice[_last_key].stop, 1)
            if self.page.prev_slice:
                _first_key = [_ for _ in sorted(self.page.this_slice.keys())][-1]
                if _first_key in self.page.prev_slice:
                    if self.page.this_slice[_first_key].start == 0:
                        del self.page.prev_slice[_first_key]
                    else:
                        self.page.prev_slice[_first_key] = slice(0, self.page.this_slice[_first_key].start, 1)

# -- // MENU PART FORMATTERS \\ --
    @staticmethod
    def format_line(line: Union[str, bool]) -> object:
        return format_line(line)

    def format_header(self, text: Union[str, List[str]], width: int = MIN_WIDTH) -> MenuSection:
        if tty and width > tty.cols:
            width = tty.cols
        orig = text
        head_lines = ["=" * width]
        width_list = [width]
        text = utils.listify(text)
        for t in text:
            line = format_line(t)
            width_list += [line.len]
            a = width - line.len
            b = (a / 2) - 2
            c = int(b) if b == int(b) else int(b) + 1
            head_lines.append(f" {'-' * int(b)} {line.text} {'-' * c}")
        head_lines.append("=" * width)
        width_list += [width]

        _header = MenuSection(
            orig=orig,
            lines=head_lines,
            width_list=width_list,
            rows=len(head_lines),
            cols=max(width_list),
            name="header",
            update_method=self.format_header,
            update_args=(text, ),
            update_kwargs={"width": max(width_list)},
        )
        # _header.update_method = self.format_header
        # _header.update_args = (text)
        # _header.update_kwargs = {"width": width}
        self.page.header = _header

        return self.page.header

    def format_subhead(self, text: Union[str, list]) -> MenuSection:
        if not text:
            _subhead = MenuSection(name="subhead")
            self.page.subhead = _subhead
            return _subhead

        subhead = utils.listify(text)
        # indent each subhead line with a space if not provided that way
        subhead = [
            f"{' ' + line if not line.startswith(' ') else line}"
            for line in subhead
        ]
        subhead.insert(0, "")
        if not self.subs_in:
            subhead += [""]
        max_len = max([len(sh) for sh in subhead])

        _subhead = MenuSection(lines=subhead, rows=len(subhead), cols=max_len)
        _subhead.update_method = self.format_subhead
        _subhead.update_args = (text)
        self.page.subhead = _subhead

        return _subhead

    def format_section(self, body: list, sub: str = None, index: int = 1,
                       left_offset: int = None, format_sub: bool = False) -> MenuSection:
        left_offset = self.left_offset if not left_offset else left_offset
        max_len = 0
        mlines = []
        _end_index_len = len(str(len(body) + index - 1))
        indent = left_offset + _end_index_len + 2  # The 2 is for '. '
        width_list = []
        for _line in body:
            # -- format spacing of item entry --
            _i = f"{str(index)}. {' ' * (_end_index_len - len(str(index)))}"
            # -- generate line and calculate line length --
            _line = " " * left_offset + _i + _line.rstrip()  # rstrip handle errant tabs in dli port name
            line = format_line(_line)
            # if not self.cur_page < self.prev_page:
            if not self.reverse:
                width_list.append(line.len)
                mlines.append(line.text)
                index += 1
            else:
                width_list.insert(0, line.len)
                mlines.insert(0, line.text)
                index -= 1
        max_len = 0 if not width_list else max(width_list)
        if sub:
            # -- Add subs lines to top of menu item section --
            x = ((max_len - len(sub)) / 2) - (left_offset + (indent / 2))
            mlines.insert(0, "")
            width_list.insert(0, 0)
            if format_sub:
                mlines.insert(
                    1,
                    "{0}{1} {2} {3}".format(
                        " " * indent,
                        "-" * int(x),
                        sub,
                        "-" * int(x) if x == int(x) else "-" * (int(x) + 1),
                    ),
                )
                width_list.insert(1, len(mlines[1]))
            else:
                mlines.insert(1, " " * indent + sub)
                width_list.insert(1, len(mlines[1]))
                # update max_len in case subsheading is the longest line in the section
                max_len = max(width_list)
            mlines.insert(2, " " * indent + "-" * (max_len - indent))
            width_list.insert(2, len(mlines[2]))

        # -- adding padding to line to full width of longest line in section --
        mlines = [f"{line}{' ' * (max_len - line_len) if line_len < max_len else ''}"
                  for line, line_len in zip(mlines, width_list)]
        return mlines, max_len, len(mlines)

    def format_legend(self, legend: dict = {}, left_offset: int = None, **kwargs) -> MenuSection:
        if self.page.legend and self.page.legend.hide:
            return self.page.legend

        left_offset = self.left_offset if not left_offset else left_offset
        col_pad = COL_PAD - left_offset
        width_list = []
        opts = utils.listify(legend.get("opts", []))

        if kwargs.get("opts"):
            opts = [*opts, *utils.listify(opts)]

        # Ensure exit is the last option unless only 2 opts
        if "x" in opts:
            opts.pop(opts.index("x"))
        if len(opts) > 2:
            opts.append("x")
        else:
            opts.insert(0, "x")
        opts = utils.unique(opts)

        no_match_overrides, no_match_rjust = [], []  # init
        pre_text, post_text, legend_text = [], [], []  # init

        # replace any pre-defined options with those passed in as overrides
        legend_options = self.legend_options or DEF_LEGEND_OPTIONS
        if legend.get("overrides") and isinstance(legend["overrides"], dict):
            legend_options = {**legend_options, **legend["overrides"]}
            no_match_overrides = [
                e for e in legend["overrides"]
                if e not in legend_options and e not in legend.get("rjust", {})
            ]

        # update legend_options with any specially formmated (rjust) additions
        width = self.page.cols
        if legend.get("rjust"):
            r = legend.get("rjust")
            f = legend_options
            legend_overrides = {
                k: [f[k][0], "{}{}".format(f[k][1], r[k].rjust(width - len(f' {f[k][0]}.{" " if len(f[k][0]) == 2 else "  "}{f[k][1]}')))]
                for k in r
                if k in f
            }

            legend_options = {**legend_options, **legend_overrides}
            no_match_rjust = [e for e in legend["rjust"] if e not in legend_options]

        if legend.get("before"):
            legend["before"] = utils.listify(legend["before"])
            pre_text = [format_line(f" {line}") for line in legend["before"]]
            width_list += [line.len for line in pre_text]
            pre_text = [line.text for line in pre_text]

        if opts:
            f = legend_options
            legend_text = [
                f'{" " * left_offset}{f[k][0]}.{" " if len(f[k][0]) == 2 else "  "}{f[k][1]}'
                for k in opts
                if k in f
            ]
            legend_text = [format_line(line) for line in legend_text]
            legend_width_list = [line.len for line in legend_text]
            legend_text = [line.text for line in legend_text]
            _middle = int(len(legend_text) / 2)
            col_1_max = max([_len for _len in legend_width_list[_middle:len(legend_width_list)]])
            col_2_max = max([_len for _len in legend_width_list[0:_middle]] or [0])
            col_1_text = [line for line in legend_text[_middle:len(legend_text)]]
            col_2_text = [line for line in legend_text[0:_middle]]
            if col_2_max > 0:
                if len(col_2_text) < len(col_1_text):
                    col_2_text += [""]
                legend_text = [
                    f"{col[0]:{col_1_max}}{' ':{col_pad}}{col[1]:{col_2_max}}" for col in zip(col_1_text, col_2_text)
                ]
                width_list += [col_1_max + col_pad + col_2_max]
                legend_text.insert(0, " " + "-" * (col_1_max + col_pad + col_2_max - 1))

                # if multi-paged output, and there is room on last line of legend display toggle legend options
                if (self.actions and "b" in self.actions and self.actions["b"] and self.actions["b"].__name__ == "pager_prev_page") or 'next' in opts:
                    _tl = " 'TL' to hide "
                    line_slice = slice(0, len(legend_text[0]) - len(_tl) - 5)
                    legend_text[0] = f'{legend_text[0][line_slice]}{_tl}{"-" * 5}'

            else:  # legend consists of only 1 item
                legend_text = col_1_text
                width_list = legend_width_list
                legend_text.insert(0, " " + "-" * (col_1_max - 1))

        if legend.get("after"):
            legend["after"] = utils.listify(legend["after"])
            post_text = [format_line(f" {line}") for line in legend["after"]]
            width_list += [line.len for line in post_text]
            post_text = [line.text for line in post_text]

        mlines = [""] + pre_text + legend_text + post_text

        # log errors if non-match overrides/rjust options were sent
        if no_match_overrides + no_match_rjust:
            log.error(
                f'menu_formatting passed options ({",".join(no_match_overrides + no_match_rjust)})'
                " that lacked a match in legend_options = No impact to menu")

        # TODO update attributes if self.page has attr legend
        if not hasattr(self.page, "legend") or self.page.legend is None:
            _legend = MenuSection(lines=mlines, cols=max(width_list), rows=len(mlines), opts=opts or [],
                                  overrides=legend.get("overrides", {}), name="legend")
        else:
            _legend = getattr(self.page, "legend")
            _legend.lines = mlines
            _legend.cols = max(width_list)
            _legend.rows = len(mlines)
            _legend.opts = opts or []

        _legend.update_method = self.format_legend
        _legend.update_kwargs = {"legend": {"before": legend.get("before", []), "opts": _legend.opts,
                                            "after": legend.get("after", []), "overrides": _legend.overrides}}

        # _legend.update(width=self.page.cols)
        self.page.legend = _legend

        return _legend

    def format_footer(self, width: int = MIN_WIDTH) -> MenuSection:
        if tty and width > tty.cols:
            width = tty.cols
        foot_width_list = []
        mlines = []

        # Remove any error_msgs matching re from ignored_errors list
        if log.error_msgs:
            for _error in log.error_msgs:
                for e in self.ignored_errors:
                    _e = _error.strip("\r\n")
                    if hasattr(e, "match") and e.match(_e):
                        log.error_msgs.remove(_error)
                        break
                    elif isinstance(e, str) and e in _error:
                        log.error_msgs.remove(_error)
                        break

        # --// ERRORs - append to footer \\-- #
        if log.error_msgs:
            errors = log.error_msgs
            for _ in range(2):
                for _error in errors:
                    error = format_line(_error)
                    foot_width_list.append(error.len + 6)  # +6 is for "!! {error.msg} !!"
                    x = (width - (error.len + 6)) / 2
                    mlines.append(
                        "{0} {1}{2}{3} {0}".format(
                            self.log_sym_2bang,
                            " " * int(x),
                            error.text,
                            " " * int(x) if x == int(x) else " " * (int(x) + 1),
                        )
                    )

                if max(foot_width_list) <= width:
                    break
                else:
                    mlines = []
                    width = max(foot_width_list)

        mlines.insert(0, "")
        page_text = f"| Page {self.cur_page} of {len(self.pages)} |"

        top_line = "=" * width
        bot_line = top_line
        if self.page.prev_slice or self.page.next_slice:
            bot_line = "=" * (width - len(page_text) - 5) + page_text + "=" * 5
        if self.page.legend.hide:
            legend_text = " Use 'TL' to Toggle Legend "
            bot_line = "=" * 5 + legend_text + bot_line[len(legend_text) + 5:]

        if log.error_msgs:
            mlines.insert(1, top_line)

        mlines += [bot_line]

        _footer = MenuSection(
            lines=mlines,
            width_list=foot_width_list,
            rows=len(mlines),
            cols=width,
            update_method=self.format_footer,
            update_kwargs={"width": width},
            name="footer",
        )
        self.page.footer = _footer

        return _footer


# This object is currently not used, but will be to simplify the logic in cpi_exec
# Which currently is a functional but it's a Shit Show.
class MenuExecute:
    def __init__(self, function, args, kwargs, calling_menu: str = None):
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.calling_menu = calling_menu
