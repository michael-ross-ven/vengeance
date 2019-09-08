
import os
import sys
from textwrap import dedent

from logging import Logger
from logging import Formatter
from logging import FileHandler
from logging import StreamHandler
from logging import DEBUG

from concurrent.futures import ProcessPoolExecutor


class log_cls(Logger):

    def __init__(self, name, f_dir=None, log_format=None):
        super().__init__(name)

        self.log_format  = log_format
        self.formatter   = None
        self.child_desig = None
        self._callback   = None

        self._file_handler   = None
        self._stream_handler = None

        self.err_msg = ''

        self._set_level()
        self._add_formatter()
        self._add_file_handler(f_dir)
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

    def _add_file_handler(self, f_dir):
        if f_dir is None:
            return

        if not os.path.exists(f_dir):
            os.makedirs(f_dir)

        f_name = self.name
        if not f_name.endswith('.log'):
            f_name += '.log'

        h = FileHandler(str(f_dir) + f_name, mode='w')
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
        self.err_msg = str(e_msg)

        has_child = not bool(self.child_desig)
        child_frame = e_trace
        s_frame     = e_trace

        # naviagate to most recent stack frame
        while s_frame.tb_next is not None:
            if has_child is False:
                if self.child_desig in _frame_filename(s_frame):
                    child_frame = s_frame
                    has_child = True

            s_frame = s_frame.tb_next

        code_file = _frame_filename(s_frame)
        file = os.path.split(code_file)[1]
        line = s_frame.tb_lineno

        log_msg = '''\n\n\n
        ____________________________   vengeance   ____________________________
              the result 'w+resign' was added to the game information
              
              "{e_msg}"
              error type:   <{e_type}>
              file:   {file}, line: {line} 
        ____________________________   vengeance   ____________________________
        \n\n\n'''.format(name=self.name,
                         e_msg=e_msg,
                         e_type=e_type.__name__,
                         file=file,
                         line=line)

        log_msg = dedent(log_msg)

        # propagate error through base class exception
        self.error(log_msg, exc_info=(e_type, e_msg, child_frame))

        self._close_file_handlers()
        self.callback()

    # def __repr__(self):
    #     return 'log  {}'.format(self.name)


class pool_executor_log_cls(ProcessPoolExecutor):
    def __init__(self, max_workers=None,
                       base_name='pool_executor_log_cls',
                       f_dir=None):

        super().__init__(max_workers)

        self.base_name = base_name
        self.f_dir     = f_dir

    def submit(self, fn, *args, **kwargs):
        kwargs['i'] = self._queue_count
        kwargs['base_name'] = self.base_name
        kwargs['f_dir']     = self.f_dir

        return super().submit(_function_wrapper, fn, *args, **kwargs)


# noinspection PyBroadException
def _function_wrapper(fn, *args, **kwargs):
    i = kwargs.pop('i') + 1
    base_name = kwargs.pop('base_name')
    f_dir     = kwargs.pop('f_dir')

    try:
        return fn(*args, **kwargs)
    except Exception:
        name = '{}_{}.log'.format(base_name, i)
        log_ = log_cls(name, f_dir)
        log_.exception_handler(*sys.exc_info())


def _frame_filename(s_frame):
    return s_frame.tb_frame.f_code.co_filename
