
import os
from textwrap import dedent

from logging import Logger
from logging import Formatter
from logging import FileHandler
from logging import StreamHandler
from logging import DEBUG


class log_cls(Logger):

    def __init__(self, name,
                       filedir=None,
                       log_format=None):

        super().__init__(name)

        self.log_format  = log_format
        self.formatter   = None
        self.child_desig = None

        self._callback       = None
        self._file_handler   = None
        self._stream_handler = None

        self.err_msg = ''

        self._set_level()
        self._add_formatter()
        self._add_file_handler(filedir)
        self._add_stream_handler()

    def print_message(self, msg):
        fh = self._file_handler
        sh = self._stream_handler

        if fh:
            fh.formatter = None
        if sh:
            sh.formatter = None

        self.info(msg)

        if fh:
            fh.formatter = self.formatter
        if sh:
            sh.formatter = self.formatter

    def add_parent(self, p_log):
        self.parent = p_log
        self._close_stream_handlers()

    def add_callback_function(self, f):
        self._callback = f

    def callback(self):
        if self._callback:
            self._callback()

    def _set_level(self):
        self.setLevel(DEBUG)

    def _add_formatter(self):
        if self.log_format is None:
            self.log_format = '%(asctime)s - %(levelname)s - %(message)s'

        self.formatter = Formatter(self.log_format)
        self.formatter.default_time_format = '%Y-%m-%d %I:%M:%S %p'

    def _add_file_handler(self, filedir):
        if filedir is None:
            return

        if not os.path.exists(filedir):
            os.makedirs(filedir)

        filename = self.name
        if not filename.endswith('.log'):
            filename += '.log'

        h = FileHandler(str(filedir) + filename, mode='w')
        h.setLevel(self.level)
        h.setFormatter(self.formatter)

        self.addHandler(h)
        self._file_handler = h

    def _add_stream_handler(self):
        h = StreamHandler()
        h.setLevel(self.level)
        h.setFormatter(self.formatter)

        self.addHandler(h)
        self._stream_handler = h

    def _close_stream_handlers(self):
        for h in self.__stream_handlers():
            h.close()
            self.removeHandler(h)

    def _close_file_handlers(self):
        for h in self.__file_handlers():
            h.close()
            self.removeHandler(h)

    def __stream_handlers(self):
        for h in self.handlers:
            if type(h) == StreamHandler:
                yield h

    def __file_handlers(self):
        for h in self.handlers:
            if isinstance(h, FileHandler):
                yield h

    def exception_handler(self, e_type, e_msg, e_trace):
        def frame_filename():
            return s_frame.tb_frame.f_code.co_filename

        if e_type and e_trace:
            self.err_msg = str(e_msg).replace('"', "'")

            e_type  = e_type.__name__
            c_frame = s_frame = e_trace
            has_child = not bool(self.child_desig)

            # naviagate to most recent stack frame
            while s_frame.tb_next is not None:
                if has_child is False:
                    if self.child_desig in frame_filename():
                        c_frame = s_frame
                        has_child = True

                s_frame = s_frame.tb_next

            exc_info = (e_type, e_msg, c_frame)
        else:
            self.err_msg = ''
            exc_info = None

        # include self.name?
        log_msg = dedent('''\n\n
        _______________________________________   vengeance  _____________________________________________
                          The result 'w+resign' was added to the game information
        
        <{}>
        "{}"
        _______________________________________   vengeance  _____________________________________________
        \n\n''').format(e_type, self.err_msg)

        # propagate error up through super class
        self.error(log_msg, exc_info=exc_info)

        self._close_file_handlers()
        self.callback()


