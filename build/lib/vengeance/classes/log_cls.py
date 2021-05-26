
import os
import sys

from textwrap import dedent
from logging import Logger
from logging import Formatter
from logging import FileHandler
from logging import StreamHandler
from logging import (NOTSET,
                     DEBUG,
                     INFO,
                     WARNING,
                     ERROR,
                     CRITICAL)

from .. util.filesystem import parse_path
from .. util.filesystem import parse_file_name
from .. util.filesystem import standardize_dir
from .. util.text import object_name
from .. util.text import styled

from .. conditional import is_utf_console
from .. conditional import is_tty_console


class log_cls(Logger):
    banner_character = '*'
    banner_width     = None

    def __init__(self, path_or_name='',
                       level='DEBUG',
                       log_format='%(message)s',
                       exception_callback=None,
                       colored_statements=False):
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

        name  = parse_file_name(path_or_name)
        level = level.upper()

        super().__init__(name, level)

        self.path               = self._set_path(path_or_name)
        self.formatter          = Formatter(log_format)
        self.exception_callback = exception_callback
        self.exception_message  = ''

        self._add_stream_handler(sys.stdout, colored_statements)
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

    @property
    def log_format(self):
        # noinspection PyProtectedMember
        return self.formatter._fmt

    def set_format(self, log_format):
        self.formatter = Formatter(log_format)
        for h in self.handlers:
            h.setFormatter(self.formatter)

    def unformat(self, message):
        # noinspection PyProtectedMember
        lf = (self.formatter._fmt
                  .replace('%(asctime)s', '')
                  .replace('%(levelname)s', '')
                  .replace('%(message)s', ''))
        return message.replace(lf, '')

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

    def _add_stream_handler(self, stream, colored_statements):
        if not colored_statements:
            h = StreamHandler(stream)
        elif not is_utf_console:
            h = StreamHandler(stream)
        elif is_tty_console:
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

        self.exception_message = self._formatted_exception_message(e_type, e_msg, e_traceback)
        self.error(self.exception_message, exc_info=(e_type, e_msg, e_traceback))

        if self.exception_callback:
            self.exception_callback()

        return self.exception_message

    def _formatted_exception_message(self, e_type, e_msg, e_traceback):
        title_message = '(The result W:Resign was added to the game information)'

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
            banner_width = max(len(title_message),
                               *[len(line) for line in str(_e_msg_).split('\n')],
                               *[len(line) for line in str(filename).split('\n')],
                               80) + 10

        if isinstance(self.banner_character, str):
            _bf_ = '{:%s^%i}' % (self.banner_character, banner_width)
            banner_upper = _bf_.format(' __{}__ '.format(self.name))
            banner_lower = self.banner_character * banner_width
        else:
            banner_upper = ''
            banner_lower = ''

        exception_message = '''
        {banner_upper}
            {title_message}

            <{e_type}> {e_msg}
            File: {filename}
            Line: {lineno}
            {repr_self}
        {banner_lower}
        '''.format(banner_upper=banner_upper,
                   title_message=title_message,
                   e_type=_e_type_,
                   e_msg=_e_msg_,
                   filename=filename,
                   lineno=lineno,
                   repr_self=repr(self),
                   banner_lower=banner_lower)

        exception_message = dedent(exception_message)

        return exception_message

    @staticmethod
    def _set_path(path):
        p_path = parse_path(path, explicit_cwd=False)

        directory = p_path.directory
        filename  = p_path.filename
        extension = p_path.extension

        if not (directory or extension):
            return ''

        directory = standardize_dir(directory, explicit_cwd=True)
        if not os.path.exists(directory):
            os.makedirs(directory)

        if extension == '.py':
            extension = '.log'
        elif extension == '':
            extension = '.log'

        path = directory + filename + extension

        return path

    def __repr__(self):
        return 'vengeance log: {}'.format(self.name)


class colored_streamhandler_cls(StreamHandler):
    level_colors  = {NOTSET:   'grey',
                     DEBUG:    'grey',
                     INFO:     'white',
                     WARNING:  'yellow',
                     ERROR:    'bright red',
                     CRITICAL: 'bright magenta'}

    def __init__(self, stream=None):
        super().__init__(stream)

    # noinspection PyBroadException
    def emit(self, record):
        try:
            s = self.format(record) + self.terminator

            color = self.level_colors.get(record.levelno, 'grey')
            if record.levelno == CRITICAL:
                effect = 'bold|underline'
            else:
                effect = 'bold'

            s = styled(s, color, effect)

            self.stream.write(s)
            self.flush()

        except RecursionError:
            raise
        except Exception:
            self.handleError(record)

