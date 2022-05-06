
import gc
import inspect
import itertools
import functools
import re
import sys

# from functools import wraps as
from timeit import default_timer
from time import sleep

from ..conditional import is_utf_console
from ..conditional import config

if is_utf_console:
    __vengeance_prefix__ = '    ν: '    # 'ν': chr(957), nu
else:
    __vengeance_prefix__ = '    v: '    # 'v': chr(118)


def print_runtime(f=None,
                  color=None,
                  effect=None,
                  formatter=None,
                  end='\n'):

    def runtime_wrapper(_f_):
        @functools.wraps(_f_)
        def functools_wrapper(*args, **kwargs):
            tic  = default_timer()
            retv = _f_(*args, **kwargs)
            toc  = default_timer()
            elapsed = -(tic - toc)

            # named variables for .format(**locals())
            formatted_prefix   = __vengeance_prefix__
            formatted_function = function_name(_f_)
            formatted_elapsed  = format_seconds(elapsed)
            formatted_runtime  = '@{}: {}'.format(formatted_function, formatted_elapsed)

            if formatter is None:
                s = '{}{}'.format(formatted_prefix, formatted_runtime)
            else:
                s = formatter.format(**locals())

            s = styled(s, color, effect)
            flush_stdout()
            print_unicode(s, end)

            return retv

        return functools_wrapper

    if (f is not None) and not callable(f):
        f, color, effect, formatter, end = None, f, color, effect, end

    if color is None:     color     = config.get('color')
    if effect is None:    effect    = config.get('effect')
    if formatter is None: formatter = config.get('formatter')

    if f:
        return runtime_wrapper(f)
    else:
        return runtime_wrapper


def print_performance(f=None, repeat=5):

    def performance_wrapper(_f_):
        @functools.wraps(_f_)
        def functools_wrapper(*args, **kwargs):
            retv  = None
            best  = None
            worst = None
            total = 0.0
            functools_repeat = functools.partial(itertools.repeat, None)

            gc_enabled = gc.isenabled()
            gc.disable()

            for _ in functools_repeat(repeat):
                tic  = default_timer()
                retv = _f_(*args, **kwargs)
                toc  = default_timer()
                elapsed = -(tic - toc)

                if best is None:
                    best  = elapsed
                    worst = elapsed
                else:
                    best  = min(best,  elapsed)
                    worst = max(worst, elapsed)

                total += elapsed

            average = total / repeat

            num_trials = surround_single_brackets(format_integer(repeat, comma_sep='_'))
            num_trials = '{} trials'.format(num_trials)
            if repeat == 1:
                num_trials = num_trials[:-1]

            s = ('@{}() over {}:'
                 '\n        ★ best:     {}'
                 '\n        ☆ average:  {}'
                 '\n        ☆ worst:    {}'
                 .format(function_name(_f_),
                         num_trials,
                         format_seconds(best),
                         format_seconds(average),
                         format_seconds(worst))
                 )
            s = vengeance_message(s)

            flush_stdout()
            print_unicode(s)

            if gc_enabled:
                gc.enable()

            return retv

        return functools_wrapper

    if (f is not None) and not callable(f):
        f, repeat = None, f

    if f:
        return performance_wrapper(f)
    else:
        return performance_wrapper


def styled(message,
           color=None,
           effect=None):

    # region {ansi effect escape codes}
    __effect_end__   = '\x1b[0m'
    __effect_codes__ = {'bold':      '\x1b[1m',
                        'italic':    '\x1b[3m',
                        'underline': '\x1b[4m',
                        '':          ''}
    __color_codes__ = {'grey':           '\x1b[29m',
                       'gray':           '\x1b[29m',
                       'white':          '\x1b[38;2;255;255;255m',
                       'red':            '\x1b[31m',
                       'green':          '\x1b[32m',
                       'yellow':         '\x1b[33m',
                       'blue':           '\x1b[34m',
                       'magenta':        '\x1b[35m',
                       'cyan':           '\x1b[36m',
                       'bronze':         '\x1b[37m',
                       'bright red':     '\x1b[91m',
                       'bright green':   '\x1b[92m',
                       'bright yellow':  '\x1b[93m',
                       # 'bright yellow':  '\x1b[33;1m',
                       'bright blue':    '\x1b[94m',
                       'bright magenta': '\x1b[95m',
                       'bright cyan':    '\x1b[96m',
                       'black':          '\x1b[97m',
                       '':               ''}
    # endregion

    if color is None:  color  = config.get('color',  '')
    if effect is None: effect = config.get('effect', '')

    color  = (str(color).lower()
                        .replace('_', ' '))
    effects = (str(effect).lower()
                          .replace(' ', '')
                          .split('|'))

    if color not in __color_codes__:
        if not (color.startswith('\x1b') and color.endswith('m')):
            raise KeyError('styled: invalid color: {}'.format(color))

    for e in effects:
        if e not in __effect_codes__:
            if not (e.startswith('\x1b') and e.endswith('m')):
                raise KeyError('styled: invalid effect: {}'.format(e))

    if not is_utf_console:
        return message

    if not color and not effects:
        return message

    ansi_color  = __color_codes__.get(color, color)
    ansi_effect = ''.join(__effect_codes__.get(e, e) for e in effects)
    __effect_start__  = ansi_color + ansi_effect

    # only apply new style to any unstyled parts of message
    _message_ = message.replace(__effect_end__,
                                __effect_end__ + __effect_start__)

    _message_ = '{}{}{}'.format(__effect_start__,
                                _message_,
                                __effect_end__)

    return _message_


def deprecated(f=None, message='deprecated'):

    def deprecated_wrapper(_f_):
        @functools.wraps(_f_)
        def functools_wrapper(*args, **kwargs):

            _message_ = "'{}'".format(message)
            _message_ = '@{}: {}'.format(function_name(_f_), _message_)

            vengeance_warning(_message_,
                              DeprecationWarning,
                              stacklevel=4)

            return _f_(*args, **kwargs)

        return functools_wrapper

    if (f is not None) and not callable(f):
        f, message = None, f

    if callable(f):
        return deprecated_wrapper(f)
    else:
        return deprecated_wrapper


def vengeance_warning(message,
                      category=Warning,
                      stacklevel=3,
                      stackframe=None,
                      color=None,
                      effect=None):
    """
    follow icecream's implementation?
        call_frame = inspect.currentframe().f_back
    """
    import traceback
    import warnings

    # region {closure functions}
    stacklevel_min = 3
    aligned_indent = ' ' * len(__vengeance_prefix__)

    def first_non_vengeance_frame():
        nonlocal stackframe

        is_found = False
        tb_stack = reversed(traceback.extract_stack())

        for i, stackframe in enumerate(tb_stack):
            if '\\vengeance\\' not in stackframe.filename:
                is_found = True
                break

        if not is_found:
            stackframe = traceback.extract_stack(inspect.currentframe(), limit=stacklevel_min)[0]

    def extract_frame():
        nonlocal stackframe

        sl = max(stacklevel, stacklevel_min)
        stackframe = traceback.extract_stack(inspect.currentframe(), limit=sl)[0]

    def vengeance_formatwarning(*_, **__):
        line_1 = ' '.join(message.split()).lstrip()

        line_1 = '<{}> {}'.format(object_name(category), line_1)
        line_1 = vengeance_message(line_1)
        line_1 = styled(line_1, color, effect)

        line_2 = 'File "{}", line {}'.format(filename, lineno)
        line_2 = styled(line_2, color, effect)
        line_2 = aligned_indent + line_2

        _message_ = '{}\n{}\n'.format(line_1, line_2)

        return _message_
    # endregion

    if stacklevel is None and stackframe is None:
        first_non_vengeance_frame()
    elif isinstance(stacklevel, int) and stackframe is None:
        extract_frame()

    if stackframe is not None:
        filename = stackframe.filename
        lineno   = stackframe.lineno
    else:
        filename = '{unknown}'
        lineno   = '{unknown}'

    flush_stdout()

    _formatwarning_ = warnings.formatwarning

    warnings.formatwarning = vengeance_formatwarning
    warnings.warn(message)
    warnings.formatwarning = _formatwarning_

    flush_stdout()


def flush_stdout(sleep_ms=None):
    print(end='')
    sys.stdout.flush()

    if sleep_ms:
        sleep(sleep_ms / 1000)


def print_unicode(s, end='\n'):
    """ replace all \x1b[34m with regex? """
    try:
        print(s, end=end)
    except UnicodeError:
        print(ascii(s), end=end)


def vengeance_message(message):
    return __vengeance_prefix__ + str(message)


def surround_double_brackets(h):
    return '⟪{}⟫'.format(h)


def surround_single_brackets(h):
    return '⟨{}⟩'.format(h)


def surround_square_brackets(h):
    return '⟦{}⟧'.format(h)


def format_integer(i, comma_sep='_'):
    """ eg:
    '1_000_000' = format_integer(1000000)
    """
    _i_ = '{:,}'.format(int(i))
    return _i_.replace(',', comma_sep)


def format_seconds(s):
    s = abs(s)

    ns = s * 1e9
    us = s * 1e6
    ms = s * 1e3

    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    if d >= 1:
        f_ms = '{:.0f}d {:.0f}h {:.0f}m'.format(d, h, m)
    elif h >= 1:
        f_ms = '{:.0f}h {:.0f}m {:.0f}s'.format(h, m, s)
    elif m >= 1:
        f_ms = '{:.0f}m {:.0f}s'.format(m, s)
    elif s >= 1:
        f_ms = '{:.1f} s'.format(s)
    elif ms >= 1:
        f_ms = '{:.1f} ms'.format(ms)
    elif us >= 1:
        if is_utf_console:  f_ms = '{:.0f} μs'.format(us)
        else:               f_ms = '{:.0f} us'.format(us)
    else:
        f_ms = '{:.0f} ns'.format(ns)

    return f_ms


def function_parameters(f):
    """
    eg:
        def function(something, *, also, also_1=None):
            pass

        Arguments(args=['something', 'also', 'also_1'],
                  varargs=None,
                  varkw=None)
        = inspect.getargs(function.__code__)

        (something, *, also, also_1=None) = inspect.signature(function)

        OrderedDict([('something',  <Parameter "something">),
                     ('also',       <Parameter "also">),
                     ('also_1',     <Parameter "also_1=None">)])
        = list(inspect.signature(function).parameters.items())
    """
    # region {closure param_cls}
    class param_cls:
        __slots__ = ('name',
                     'kind',
                     'default',
                     'value')

        def __init__(self, p):
            self.name    = p.name
            self.kind    = str(p.kind)
            self.default = p.default
            self.value   = None

            if object_name(p.default) != '_empty':
                self.value = p.default

        def __repr__(self):
            return '{}={!r}  {}'.format(self.name,
                                        self.value,
                                        '{' + self.kind + '}')
    # endregion

    i_params = inspect.signature(f).parameters
    n_params = [param_cls(p) for p in i_params.values()]

    return n_params


def function_name(f):
    try:
        name = f.__qualname__
    except AttributeError:
        try:
            if isinstance(f, property): name = str(f.fget).split(' ')[1]
            else:                       name = str(f)
        except:
            name = str(f)

    if '.' in name:         # probably a class method
        return name

    try:                   modulename = f.__module__
    except AttributeError: modulename = str(f)

    modulename = modulename.split('.')[-1]

    return '{}.{}'.format(modulename, name)


def object_name(o):
    try:                   return o.__name__
    except AttributeError: pass

    try:                   return o.__class__.__name__
    except AttributeError: pass

    try:                   return type(o).__name__
    except AttributeError: return ''


# noinspection DuplicatedCode
def snake_case(s):
    """ eg:
        'some_value' = snake_case('someValue')
    """
    camel_re = re.compile('''
        (?<=[a-z])[A-Z](?=[a-z])
    ''', re.VERBOSE)

    s = s.strip()

    matches = camel_re.finditer(s)
    matches = list(matches)

    _s_ = list(s)

    for match in reversed(matches):
        i_1 = match.span()[0]
        i_2 = i_1 + 1
        c = match.group().lower()

        _s_[i_1:i_2] = ['_', c]

    return ''.join(_s_).lower()




