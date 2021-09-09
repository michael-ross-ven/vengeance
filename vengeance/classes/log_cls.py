
import os
import sys

from collections import deque
from collections import namedtuple

from logging import Logger
from logging import Formatter
from logging import FileHandler
from logging import StreamHandler
from logging import LogRecord
from logging import (NOTSET,
                     DEBUG,
                     INFO,
                     WARNING,
                     ERROR,
                     FATAL,
                     CRITICAL)
# from logging import getLevelName as get_level_name

from textwrap import dedent
from typing import List

from .. util.filesystem import parse_path
from .. util.filesystem import standardize_path
from .. util.text import object_name
from .. util.text import styled
from .. util.text import flush_stdout


class log_cls(Logger):
    # max_num_records = None
    max_num_records = 10

    # default_time_format = '%Y-%m-%d %H:%M:%S'
    # default_msec_format = '%s,%03d'

    levels_mapping = {'notset':   NOTSET,
                      'debug':    DEBUG,
                      'info':     INFO,
                      'warning':  WARNING,
                      'error':    ERROR,
                      'fatal':    CRITICAL,
                      'critical': CRITICAL,

                      NOTSET:     'notset',
                      DEBUG:      'debug',
                      INFO:       'info',
                      WARNING:    'warning',
                      ERROR:      'error',
                      FATAL:      'critical',
                      CRITICAL:   'critical'}

    def __init__(self, name_or_path='',
                       level='NOTSET',
                       *,
                       log_format='[{asctime}] [{levelname}] {message}',
                       date_format=None,
                       file_mode='w',
                       file_encoding='utf-8',
                       exception_callback=None,
                       colored_statements=False):
        """
        :param name_or_path:
            parsed to determine name of logger
            if name_or_path includes directory or file extension, a file handler is added
        :param log_format:
            format to be applied to handlers
            eg log_format:
                '[%(asctime)s] [%(levelname)s] %(message)s'
                {asctime}; {levelname}; "{message}"
        :param exception_callback:
            function to be invoked when self.exception_handler() is called
            sys.excepthook is automatically set to self.exception_handler if
            exception_callback is a valid function

        log_format='[{levelname}] [{asctime}] {message}',
        log_format='[{asctime}] [{levelname}] [{threadName}] [{process}] {message}',
        log_format='[{asctime}.{msecs:.4f}] [{levelname}] [{threadName}] [{process}] {message}'
        date_format='%Y-%m-%d %I:%M:%S %p',

        %(name)s            Name of the logger (logging channel)
        %(levelno)s         Numeric logging level for the message (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        %(levelname)s       Text logging level for the message    ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        %(pathname)s        Full pathname of the source file where the logging call was issued (if available)
        %(filename)s        Filename portion of pathname
        %(module)s          Module (name portion of filename)
        %(lineno)d          Source line number where the logging call was issued (if available)
        %(funcName)s        Function name
        %(created)f         Time when the LogRecord was created (time.time() return value)
        %(asctime)s         Textual time when the LogRecord was created
        %(msecs)d           Millisecond portion of the creation time
        %(relativeCreated)d Time in milliseconds when the LogRecord was created, relative to the time the logging 
                            module was loaded (typically at application startup time)
        %(thread)d          Thread ID (if available)
        %(threadName)s      Thread name (if available)
        %(process)d         Process ID (if available)
        %(message)s         The result of record.getMessage(), computed just as the record is emitted
        """
        ''' @types '''
        self.records: deque[LogRecord]

        if (exception_callback is not None) and not callable(exception_callback):
            raise TypeError('exception_callback must be callable')

        name  = parse_path(name_or_path).filename
        level = self.levelname(level)

        super().__init__(name, level)

        self.name_or_path       = name_or_path
        self.mode               = file_mode
        self.encoding           = file_encoding
        self.formatter          = self.log_formatter(log_format, date_format)
        self.records            = deque(maxlen=self.max_num_records)
        self.exception_callback = exception_callback
        self.exception_message  = ''

        self.add_stream_handler(self.level, colored_statements, sys.stdout)
        self.add_file_handler(name_or_path, self.level, file_mode, file_encoding)

        if exception_callback:
            sys.excepthook = self.exception_handler

    @property
    def stream_handlers(self) -> List[StreamHandler]:
        handlers = []
        for h in self.handlers:
            if isinstance(h, StreamHandler) and not isinstance(h, FileHandler):
                handlers.append(h)

        return handlers

    @property
    def paths(self) -> List[str]:
        return [h.baseFilename for h in self.file_handlers]

    @property
    def paths_parsed(self) -> List[namedtuple]:
        return [parse_path(h.baseFilename) for h in self.file_handlers]

    @property
    def file_handlers(self) -> List[FileHandler]:
        handlers = []
        for h in self.handlers:
            if isinstance(h, FileHandler):
                handlers.append(h)

        return handlers

    def path_hyperlinks(self) -> str:
        links = []
        for path in self.paths:
            links.append('File "{}", line 1'.format(path))

        links = '\n'.join(links)
        return links

    def levelname(self, level=None) -> str:
        if level is None and 'level' in self.__dict__:
            if self.level is None:
                raise ValueError('self.level is None')
            else:
                return self.levelname(self.level)

        _level_ = level
        if isinstance(_level_, str):
            _level_ = _level_.lower()

        if _level_ not in self.levels_mapping:
            raise KeyError(_level_)

        if isinstance(_level_, int):
            _level_ = self.levels_mapping[_level_]

        return _level_.upper()

    def reset_formatter(self, log_format, date_format):
        self.formatter = self.log_formatter(log_format, date_format)
        for h in self.handlers:
            h.setFormatter(self.formatter)

    def reset_level(self, level):
        level = self.levelname(level).lower()
        level = self.levels_mapping[level]

        self.level = level

        for h in self.handlers:
            h.setLevel(level)

    def close(self):
        self.close_stream_handlers()
        self.close_file_handlers()

    def close_stream_handlers(self, i=None):
        handlers = self.stream_handlers
        if isinstance(i, int):
            handlers = [handlers[i]]

        for h in handlers:
            h.close()
            self.removeHandler(h)

    def close_file_handlers(self, i=None):
        handlers = self.file_handlers
        if isinstance(i, int):
            handlers = [handlers[i]]

        for h in handlers:
            h.close()
            self.removeHandler(h)

    def clear_files(self, i=None):
        handlers = self.file_handlers
        if isinstance(i, int):
            handlers = [handlers[i]]

        for h in handlers:
            h.close()
            # noinspection PyProtectedMember
            h._open()

    def remove_stream_handlers(self, i=None):
        self.close_stream_handlers(i)

    def remove_file_handlers(self, i=None):
        self.close_file_handlers(i)

    def clear_file_handlers(self, i=None):
        self.clear_files(i)

    def set_level(self, level):
        self.reset_level(level)

    def add_parent_log(self, parent_log):
        """ if trying to write to same paths?? """
        if id(parent_log) == id(self):
            raise ValueError('parent log refers to the same object as current log')

        self.parent = parent_log

    def add_stream_handler(self, level=None,
                                 colored_statements=False,
                                 stream=sys.stdout):

        if colored_statements:
            h = colored_streamhandler_cls(stream)
        else:
            h = StreamHandler(stream)

        level = self.levelname(level)

        h.setLevel(level)
        h.setFormatter(self.formatter)
        self.addHandler(h)

    def add_file_handler(self, path,
                               level=None,
                               mode='w',
                               encoding='utf-8'):

        _, path = self.parse_name_or_path(path)
        if not path:
            return

        level = self.levelname(level)
        h = FileHandler(path, mode=mode, encoding=encoding)

        h.setLevel(level)
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
        self.exception_message = self._formatted_exception_message(e_type, e_msg)
        self.critical(self.exception_message, exc_info=(e_type, e_msg, e_traceback))
        flush_stdout(sleep_ms=500)

        if self.exception_callback:
            self.exception_callback()

        return self.exception_message

    def _formatted_exception_message(self, e_type, e_msg):
        from multiprocessing import current_process
        from threading import current_thread

        _e_type_ = object_name(e_type) or 'Exception'
        _e_msg_  = str(e_msg).replace('"', "'")

        exception_message = '''
    
            (The result 'W:resign' was added to the game information)
            
            Error:    {e_type}: {e_msg}
            Process:  {process_name}
            Thread:   {thread_name}
            Log:      {repr_self}
            
 
        '''.format(e_type=_e_type_,
                   e_msg=_e_msg_,
                   process_name=current_process().name,
                   thread_name=current_thread().name,
                   repr_self=self.name)
        exception_message = exception_message.strip()

        _bw_ = max(len(line) for line in exception_message.split('\n')) + 8
        _bf_ = '{:*^%i}' % _bw_
        banner_upper = _bf_.format('  __Fatal Exception__  ')
        banner_lower = '*' * _bw_

        exception_message = '''
        
        {banner_upper}
            {exception_message}
        {banner_lower}
        Log Paths:
        {paths}
        

        '''.format(banner_upper=banner_upper,
                   exception_message=exception_message,
                   banner_lower=banner_lower,
                   paths=self.path_hyperlinks())
        exception_message = dedent(exception_message)

        return exception_message

    def handle(self, record: LogRecord):
        self.records.append(record)
        super().handle(record)

    def __repr__(self):
        def sort_filehandlers_last(h):
            if 'FileHandler' in h: return 2
            else:                  return 1

        ln = self.levelname()
        rh = sorted([object_name(h) for h in self.handlers],
                    key=sort_filehandlers_last)
        rh = ' | '.join(rh)

        return '{}: [{}]  handlers={{{}}}'.format(self.name, ln, rh)

    @staticmethod
    def parse_name_or_path(name_or_path):
        p_path = parse_path(name_or_path, abspath=False)

        directory = p_path.directory
        filename  = p_path.filename
        extension = p_path.extension

        if not (directory or extension):
            return filename, None

        if not os.path.exists(directory):
            raise FileExistsError('log directory does not exist: \n{}'.format(directory))

        directory = standardize_path(directory)
        path = directory + filename + extension

        return filename, path

    @staticmethod
    def log_formatter(log_format, date_format):
        if '%(' in log_format:
            style_format = '%'
        elif '{' in log_format:
            style_format = '{'
        else:
            style_format = '$'

        return Formatter(log_format,
                         date_format,
                         style_format)


class colored_streamhandler_cls(StreamHandler):
    level_effects = {NOTSET:   None,
                     DEBUG:    'bold',
                     INFO:     'bold',
                     WARNING:  'bold',
                     ERROR:    'bold',
                     CRITICAL: 'bold'}

    level_colors  = {NOTSET:   'grey',
                     DEBUG:    'grey',
                     INFO:     'white',
                     WARNING:  'yellow',
                     ERROR:    'bright red',
                     CRITICAL: 'bright magenta'}

    def __init__(self, stream=None):
        super().__init__(stream)

    def emit(self, record):
        color  = self.level_colors.get(record.levelno)
        effect = self.level_effects.get(record.levelno)

        s = self.format(record) + self.terminator
        s = styled(s, color, effect)

        try:
            self.flush()
            self.stream.write(s)
        except RecursionError as e:
            raise e
        except Exception as e:
            print('{} Error: {}'.format(self.__class__.__name__, e))
            self.handleError(record)
