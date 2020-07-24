
import os
import sys

from textwrap import dedent
from logging import Logger
from logging import Formatter
from logging import FileHandler
from logging import StreamHandler
from logging import (NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL)

from .. util.filesystem import parse_path

level_colors  = {NOTSET:   'grey',
                 DEBUG:    'grey',
                 INFO:     'blue',
                 WARNING:  'yellow',
                 ERROR:    'red',
                 CRITICAL: 'red'}
color_numbers = {'white':   30,
                 'red':     31,
                 'orange':  32,
                 'yellow':  33,
                 'blue':    34,
                 'magenta': 35,
                 'green':   36,
                 'bronze':  37,
                 'grey':    29}


class log_cls(Logger):
    def __init__(self, path='',
                       level='DEBUG',
                       log_format='%(message)s',
                       exception_callback=None):
        """
        :param path:
            if path includes directory, a file handler
            is added at that location, otherwise
            path is used as name of logger
        :param log_format:
            format to be applied to handlers
            eg log_format:
                '[%(asctime)s] [%(levelname)s] %(message)s'
        :param exception_callback:
            function to be called after self.exception_handler()
        """
        if exception_callback is not None and not callable(exception_callback):
            raise TypeError('exception_callback must be callable')

        filedir, name, extn = parse_path(path, explicit_cwd=False)
        if isinstance(level, str):
            level = level.upper()

        super().__init__(name, level)

        self.formatter = Formatter(log_format)
        self.exception_callback = exception_callback
        self.exception_message  = ''

        self._add_stream_handler(stream=sys.stdout)
        self.path = self._add_file_handler(filedir, name, extn)

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
        assert id(p_log) != id(self)
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

    def _add_file_handler(self, filedir, filename, extn):
        if not filedir:
            return ''

        if not os.path.exists(filedir):
            os.makedirs(filedir)

        extn = extn or '.log'
        path = filedir + filename + extn

        h = FileHandler(path, mode='w', encoding='utf-8')

        h.setLevel(self.level)
        h.setFormatter(self.formatter)
        self.addHandler(h)

        return path

    def exception_handler(self, e_type, e_msg, e_traceback):
        """ sys.excepthook = log.exception_handler """

        _e_type_ = 'Exception'
        _e_msg_  = 'unknown error'
        filename = ''
        lineno   = ''

        if e_type:
            _e_type_ = e_type.__name__

        if e_msg:
            _e_msg_ = '{}'.format(str(e_msg).replace('"', "'"))

        if e_traceback:
            filename = e_traceback.tb_frame.f_code.co_filename
            lineno   = e_traceback.tb_lineno

        error_msg = self.__formatted_error_message(_e_type_,
                                                   _e_msg_,
                                                   filename,
                                                   lineno)
        self.error(error_msg, exc_info=(e_type, e_msg, e_traceback))

        if self.exception_callback:
            self.exception_callback()

        self.exception_message = '{}: {}'.format(_e_type_, _e_msg_)

        return self.exception_message

    def __formatted_error_message(self, _e_type_, _e_msg_, filename, lineno):

        error_msg = dedent('''
        
        banner_top
            (The result w+resign was added to the game information)
            
            <{e_type}>: {e_msg}
            {filename}, {lineno}
        banner_bottom

        ''').format(e_type=_e_type_,   e_msg=_e_msg_,
                    filename=filename, lineno=lineno)

        banner_char = '-'

        banner_width  = max(len(line) for line in error_msg.split('\n')) + 10
        banner_format = '{}^{}'.format(banner_char, banner_width)

        banner_top = '  {}  '.format(repr(self))
        banner_top = '{:{}}'.format(banner_top, banner_format)
        banner_bottom = banner_char * banner_width

        error_msg = (error_msg.replace('banner_top', banner_top, 1)
                              .replace('banner_bottom', banner_bottom, 1))

        return error_msg

    def __repr__(self):
        name = self.name or '(empty)'
        return 'vengeance log: {}'.format(name)


class colored_streamhandler_cls(StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream)

    # noinspection PyBroadException
    def emit(self, record):
        try:
            color = level_colors.get(record.levelno, 'white')
            color = color_numbers[color]
            message = self.format(record) + '\n'

            colored_message_a = '\x1b[{};1m'.format(color)
            colored_message_b = '{}\x1b[0m'.format(message)
            colored_message   = colored_message_a + colored_message_b

            self.stream.write(colored_message)
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)

