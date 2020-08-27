
import os
import sys

from textwrap import dedent
from logging import Logger
from logging import Formatter
from logging import FileHandler
from logging import StreamHandler
from logging import (NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL)

from .. util.filesystem import parse_path
from .. util.filesystem import standardize_dir
from .. util.text import object_name
from .. util.text import vengeance_message


class log_cls(Logger):

    def __init__(self, path_or_name='',
                       level='DEBUG',
                       log_format='%(message)s',
                       exception_callback=None):
        """
        :param path_or_name:
            parsed to determine name of logger
            if path_or_name includes directory or file extension, a file handler is added
        :param log_format:
            format to be applied to handlers
            eg log_format:
                '[%(asctime)s] [%(levelname)s] %(message)s'
        :param exception_callback:
            function to be invoked when self.exception_handler() is called
            sys.excepthook is automatically set to self.exception_handler if
            exception_callback is a valid function
        """
        if (exception_callback is not None) and not callable(exception_callback):
            raise TypeError('exception_callback must be callable')

        filedir, logname, extn = parse_path(path_or_name, explicit_cwd=False)
        if isinstance(level, str):
            level = level.upper().strip()

        super().__init__(logname, level)

        self.path      = self.__set_path(filedir, logname, extn)
        self.formatter = Formatter(log_format)

        self.exception_callback = exception_callback
        self.exception_message  = ''
        self.banner_character   = '*'
        self.banner_width       = None

        self._add_stream_handler(sys.stdout)
        self._add_file_handler(self.path)

        if exception_callback:
            sys.excepthook = self.exception_handler

    @property
    def stream_handlers(self):
        handlers = []
        for h in self.handlers:
            if type(h) in (StreamHandler, colored_streamhandler_cls):
                handlers.append(h)

        return handlers

    @property
    def file_handlers(self):
        handlers = []
        for h in self.handlers:
            if isinstance(h, FileHandler):
                handlers.append(h)

        return handlers

    def reset_format(self, log_format):
        self.formatter = Formatter(log_format)
        for h in self.handlers:
            h.setFormatter(self.formatter)

    def add_parent_log(self, p_log):
        if id(p_log) == id(self):
            raise ValueError('parent log and self are the same')

        self.parent = p_log
        self.close_stream_handlers()

    def close(self):
        self.close_stream_handlers()
        self.close_file_handlers()

    def close_stream_handlers(self):
        for h in self.stream_handlers:
            h.close()
            self.removeHandler(h)

    def close_file_handlers(self):
        for h in self.file_handlers:
            h.close()
            self.removeHandler(h)

    def _add_stream_handler(self, stream):
        is_terminal = stream.isatty()

        if is_terminal:
            h = StreamHandler(stream)
        else:
            h = colored_streamhandler_cls(stream)

        h.setLevel(self.level)
        h.setFormatter(self.formatter)
        self.addHandler(h)

    def _add_file_handler(self, path):
        if not path:
            return

        h = FileHandler(path, mode='w', encoding='utf-8')

        h.setLevel(self.level)
        h.setFormatter(self.formatter)
        self.addHandler(h)

    def exception_handler(self, e_type, e_msg, e_traceback):
        """
        sys.excepthook = log.exception_handler

        try:
            1 / 0
        except:
            log.exception_handler(*sys.exc_info())
        """
        try:
            self.exception_message = self.__formatted_exception_message(e_type, e_msg, e_traceback)
        except Exception:
            self.exception_message = 'error occurred in log_cls.__formatted_exception_message()'
            vengeance_message(self.exception_message)

        self.error(self.exception_message, exc_info=(e_type, e_msg, e_traceback))

        if self.exception_callback:
            self.exception_callback()

        return self.exception_message

    def __formatted_exception_message(self, e_type, e_msg, e_traceback):
        title_message = '(The result w:resign was added to the game information ...)'

        _e_type_ = 'Exception'
        _e_msg_  = 'unknown error'
        filename = 'unknown'
        lineno   = 'unknown'

        if e_type:
            _e_type_ = object_name(e_type)
        if e_msg:
            _e_msg_ = '{}'.format(str(e_msg).replace('"', "'"))
        if e_traceback:
            filename = e_traceback.tb_frame.f_code.co_filename
            lineno   = e_traceback.tb_lineno

        if isinstance(self.banner_width, int):
            banner_width = self.banner_width
        else:
            banner_width = max([len(title_message),
                                *[len(line) for line in str(_e_msg_).split('\n')],
                                *[len(line) for line in str(filename).split('\n')]]) + 10
            banner_width = max(banner_width, 90)

        # banner_top    = '{}^{}'.format(self.banner_character, banner_width)
        # banner_top    = '{:{}}'.format('  ' + repr(self) + '  ', banner_top)
        # banner_bottom = banner_char * len(banner_top)

        banner_top    = self.banner_character * banner_width
        banner_bottom = self.banner_character * banner_width

        exception_message = dedent('''
        {banner_top}
            {title_message}
            {repr_self}
            
            <{e_type}> {e_msg}
            File: {filename}
            Line: {lineno}
        {banner_bottom}
        
        ''').format(banner_top=banner_top,
                    title_message=title_message,
                    repr_self=repr(self),
                    e_type=_e_type_,
                    e_msg=_e_msg_,
                    filename=filename,
                    lineno=lineno,
                    banner_bottom=banner_bottom)

        return exception_message

    @staticmethod
    def __set_path(filedir, logname, extn):
        if extn == '.py':
            extn = ''

        if not (filedir or extn):
            return ''

        filedir = standardize_dir(filedir, explicit_cwd=True)
        if not os.path.exists(filedir):
            os.makedirs(filedir)

        extn = extn or '.log'
        path = filedir + logname + extn

        return path

    def __repr__(self):
        return 'vengeance log: {}'.format(self.name)


class colored_streamhandler_cls(StreamHandler):

    # https://en.wikipedia.org/wiki/ANSI_escape_code
    level_colors  = {NOTSET:   'grey',
                     DEBUG:    'grey',
                     INFO:     'white',
                     WARNING:  'bright_yellow',
                     ERROR:    'red',
                     CRITICAL: 'bright_magenta'}
    ascii_escapes = {'end':            '\x1b[0m',       # misc
                     'bold':           '\x1b[1m',
                     'italic':         '\x1b[3m',
                     'underline':      '\x1b[4m',

                     'grey':           '\x1b[29m',      # colors
                     'white':          '\x1b[30m',
                     'red':            '\x1b[31m',
                     'orange':         '\x1b[32m',
                     'yellow':         '\x1b[33m',
                     'blue':           '\x1b[34m',
                     'magenta':        '\x1b[35m',
                     'green':          '\x1b[36m',
                     'bronze':         '\x1b[37m',
                     'bright_red':     '\x1b[91m',
                     'bright_yellow':  '\x1b[93m',
                     'bright_magenta': '\x1b[95m'}

    def __init__(self, stream=None):
        super().__init__(stream)

    def emit(self, record):
        try:
            escapes    = self.ascii_escapes
            color_name = self.level_colors.get(record.levelno, 'grey')

            colored_message = ('{asci_color}{asci_effect}{message}{ascii_end}\n'
                               .format(asci_color=escapes[color_name],
                                       asci_effect=escapes['bold'],
                                       message=self.format(record),
                                       ascii_end=escapes['end']))

            self.stream.write(colored_message)
            self.flush()

        except RecursionError:
            raise
        except Exception:
            self.handleError(record)

