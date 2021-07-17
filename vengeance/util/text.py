
import gc
import inspect
import itertools
import functools
import re
import sys

from timeit import default_timer
from time import sleep

from ..conditional import is_utf_console
from ..conditional import is_tty_console
from ..conditional import config

if is_utf_console: __vengeance_prefix__ = '    ν: '    # 'ν': chr(957), nu
else:              __vengeance_prefix__ = '    v: '    # 'v': chr(118)

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


def print_runtime(f=None,
                  color=None,
                  effect=None,
                  formatter=None):

    def runtime_wrapper(_f_):
        @functools.wraps(_f_)
        def functools_wrapper(*args, **kwargs):
            tic  = default_timer()
            retv = _f_(*args, **kwargs)
            toc  = default_timer()
            elapsed = -(tic - toc)

            # variables for .format(**locals())
            vengeance_prefix   = __vengeance_prefix__
            formatted_function = function_name(_f_)
            formatted_elapsed  = format_seconds(elapsed)
            formatted_runtime  = '@{}: {}'.format(formatted_function, formatted_elapsed)

            if formatter is None:
                s = '{}{}'.format(vengeance_prefix, formatted_runtime)
            else:
                s = formatter.format(**locals())

            s = styled(s, color, effect)

            flush_stdout()
            print_unicode(s)

            return retv

        return functools_wrapper

    if (f is not None) and not callable(f):
        f, color, effect, formatter = None, f, color, effect

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

            trials = format_header_lite(format_integer(repeat))
            star_best  = styled('★★★ ',     'blue')
            star_avg   = styled('★★   ', 'blue')
            star_worst = styled('★    ',     'blue')

            s = ('@{} of {}  trials'
                 '\n        {}best:    {}'
                 '\n        {}average: {}'
                 '\n        {}worst:   {}'
                 .format(function_name(_f_), trials,
                         star_best,  format_seconds(best),
                         star_avg,   format_seconds(average),
                         star_worst, format_seconds(worst)))
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
    """
    # _message_ = (ansi_start +
    #              _message_ +
    #              ansi_end)

    # only apply style to non-whitespace parts of message
    _message_ = _style_non_whitespace_only(_message_,
                                           ansi_start, ansi_end)
    """
    if color is None:  color  = config.get('color')
    if effect is None: effect = config.get('effect')

    color  = color  or ''
    effect = effect or ''

    color  = (color.lower()
                   .replace('_', ' ')
                   .replace('gray', 'grey'))
    effect = (effect.lower()
                    .replace(' ', '')
                    .split('|'))

    if color not in __color_codes__:
        if not (color.startswith('\x1b') and color.endswith('m')):
            raise KeyError('styled: invalid color: {}'.format(color))

    for e in effect:
        if e not in __effect_codes__:
            if not (e.startswith('\x1b') and e.endswith('m')):
                raise KeyError('styled: invalid effect: {}'.format(e))

    if not is_utf_console:       return message
    if is_tty_console:           return message
    if not color and not effect: return message

    ansi_color  = __color_codes__.get(color, color)
    ansi_effect = ''.join(__effect_codes__.get(e, e) for e in effect)

    ansi_start = ansi_color + ansi_effect
    ansi_end   = __effect_end__

    # only apply new style to any unstyled parts of message
    _message_ = message.replace(ansi_end, ansi_end + ansi_start)

    _message_ = (ansi_start +
                 _message_ +
                 ansi_end)

    # only apply style to non-whitespace parts of message
    # _message_ = _style_non_whitespace_only(_message_,
    #                                        ansi_start, ansi_end)

    return _message_


def _style_non_whitespace_only(message,
                               ansi_start, ansi_end):
    r"""
    whitespace_re = re.compile(
        r'''
        (?P<whitespace>
            [\\s]+
        )
        |
        (?P<non_whitespace>
            [^\\s]+
        )
        ''', re.X | re.I | re.DOTALL | re.UNICODE)
    """
    whitespace_re = re.compile(
        r'''
        (?P<whitespace>
            ^[\s]+
        )|
        .+
        ''', re.X | re.DOTALL)

    matches = []
    for match in whitespace_re.finditer(message):
        s = match.group()
        
        if match.lastgroup == 'whitespace':
            matches.append(s)
        else:
            matches.append(ansi_start + s + ansi_end)

    return ''.join(matches)


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
                      color=config.get('color'),
                      effect=config.get('effect')):
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

    original_formatwarning = warnings.formatwarning
    warnings.formatwarning = vengeance_formatwarning
    warnings.warn(message)
    warnings.formatwarning = original_formatwarning

    flush_stdout()


def flush_stdout(sleep_ms=None):
    print(end='')
    sys.stdout.flush()

    if sleep_ms:
        sleep(sleep_ms / 1000)


def print_unicode(s):
    """ replace all \x1b[34m with regex? """
    try:
        print(s)
    except UnicodeError:
        print(ascii(s))


def vengeance_message(message):
    return __vengeance_prefix__ + str(message)


def format_header(h):
    return '⟪{}⟫'.format(h)


def format_header_lite(h):
    return '⟨{}⟩'.format(h)


def format_integer(i):
    """ eg: '1_000_000' = format_integer(1000000) """
    return '{:,}'.format(int(i)).replace(',', '_')


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
        f_ms = '{:.1f} sec'.format(s)
    elif ms >= 1:
        f_ms = '{:.1f} ms'.format(ms)
    elif us >= 1:
        if is_utf_console: f_ms = '{:.0f} μs'.format(us)
        else:              f_ms = '{:.0f} us'.format(us)
    else:
        f_ms = '{:.0f} ns'.format(ns)

    return f_ms


def function_parameters(f):
    # region {closure}
    class param_cls:
        __slots__ = ('name',
                     'kind',
                     'default',
                     'value')

        def __init__(self, p):
            self.name    = p.name
            self.kind    = str(p.kind)
            self.default = p.default
            self.value   = p.default

        def __repr__(self):
            return '{} {}'.format(self.name, self.kind)
    # endregion

    i_params = inspect.signature(f).parameters
    n_params = [param_cls(p) for p in i_params.values()]

    return n_params


def function_name(f):
    name = f.__qualname__
    if '.' in name:
        return name

    modulename = f.__module__.split('.')[-1]
    return '{}.{}'.format(modulename, name)


def object_name(o):
    try:                   return o.__name__
    except AttributeError: pass

    try:                   return o.__class__.__name__
    except AttributeError: pass

    return type(o).__name__




