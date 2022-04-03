
import csv
import gc
import os
import pickle
import shutil

from collections import namedtuple
from datetime import date
from datetime import datetime
from functools import lru_cache
from glob import glob
from io import StringIO
from os.path import isdir  as os_isdir
from os.path import isfile as os_isfile
from urllib.parse import urlparse
from urllib.request import urlopen

from ..conditional import is_windows_os
from ..conditional import ultrajson_installed

if ultrajson_installed:
    # noinspection PyUnresolvedReferences
    import ujson as json
else:
    import json

pickle_extensions = {'.flux',
                     '.pkl',
                     '.pickle'}


def read_file(path,
              encoding=None,
              mode='r',
              filetype=None,
              **kwargs):

    was_gc_enabled   = gc.isenabled()
    if was_gc_enabled: gc.disable()

    path, encoding, filetype, mode, kwargs = __validate_io_arguments(path,
                                                                     encoding,
                                                                     mode,
                                                                     filetype,
                                                                     kwargs,
                                                                     'read')
    is_url = is_path_a_url(path)

    if filetype == '.csv':
        data = __read_csv(path, mode, encoding, kwargs)

    elif filetype == '.json':
        data = __read_json(path, mode, encoding, kwargs)

    elif is_url:
        data = __url_request(path, encoding=encoding)

    elif filetype in pickle_extensions:
        with open(path, mode) as f:
            data = pickle.load(f, **kwargs)

    else:
        with open(path, mode, encoding=encoding) as f:
            data = f.read()

    if was_gc_enabled: gc.enable()

    return data


def write_file(path,
               data,
               encoding=None,
               mode='w',
               filetype=None,
               **kwargs):

    was_gc_enabled   = gc.isenabled()
    if was_gc_enabled: gc.disable()

    is_data_bytes = isinstance(data, bytes)

    path, encoding, filetype, mode, kwargs = __validate_io_arguments(path,
                                                                     encoding,
                                                                     mode,
                                                                     filetype,
                                                                     kwargs,
                                                                     'write',
                                                                     is_data_bytes)

    if filetype == '.csv':
        newline = kwargs.pop('newline')
        with open(path, mode, encoding=encoding, newline=newline) as f:
            csv.writer(f, **kwargs).writerows(data)

    elif filetype == '.json':
        with open(path, mode, encoding=encoding) as f:
            json.dump(data, f, **kwargs)

    elif filetype in pickle_extensions:
        with open(path, mode) as f:
            pickle.dump(data, f, **kwargs)

    else:
        with open(path, mode, encoding=encoding) as f:
            f.write(data)

    if was_gc_enabled: gc.enable()


def __validate_io_arguments(path,
                            encoding,
                            mode,
                            filetype,
                            kwargs,
                            read_or_write,
                            is_data_bytes=False):

    path          = __validate_path(path)
    filetype      = __validate_filetype(path, filetype)
    mode          = __validate_mode(mode, filetype, is_data_bytes)
    encoding      = __validate_encoding(mode, encoding)
    read_or_write = __validate_read_or_write(path, mode, read_or_write)
    kwargs        = __validate_file_keyword_args(encoding,
                                                 filetype,
                                                 kwargs,
                                                 read_or_write)

    return (path,
            encoding,
            filetype,
            mode,
            kwargs)


def __validate_path(path):
    return standardize_path(path, abspath=True)


def __validate_filetype(path, filetype):
    """ check for file types that require specialized io libraries / protocols """
    notimplemented_extensions = {'.7z',
                                 '.zip',
                                 '.gzip',
                                 '.bz',
                                 '.tar',
                                 '.png',
                                 '.jpg',
                                 '.jpeg',
                                 '.gif',
                                 '.pdf'}

    filetype = filetype or parse_file_extension(path, include_dot=True)
    filetype = filetype.lower().strip()

    if filetype and not filetype.startswith('.'):
        filetype = '.' + filetype

    if filetype.startswith('.xl') or filetype in notimplemented_extensions:
        raise NotImplementedError("file type not supported: '{}'".format(filetype))

    return filetype


def __validate_mode(mode, filetype, is_data_bytes):
    is_rw_mode          = ('+' in mode)
    is_bytes_mode       = ('b' in mode)
    is_pickle_extension = (filetype in pickle_extensions)
    is_csv_extension    = (filetype in ('.csv',))

    if is_rw_mode:
        raise ValueError('read-write mode not supported')
    if is_csv_extension and is_bytes_mode:
        raise ValueError('csv filetype does not accept bytes mode')

    if is_pickle_extension and (not is_bytes_mode):
        mode = mode + 'b'
    elif is_data_bytes and (not is_bytes_mode):
        mode = mode + 'b'

    return mode


def __validate_encoding(mode, encoding):
    is_bytes_mode = ('b' in mode)

    if is_bytes_mode:
        encoding = None

    return encoding


def __validate_file_keyword_args(encoding, filetype, kwargs, read_or_write):
    kwargs = kwargs or {}

    if 'kwargs' in kwargs:
        kwargs.update(kwargs.pop('kwargs'))

    if read_or_write == 'read':
        if filetype == '.csv':
            kwargs['newline'] = kwargs.get('newline', '')
            kwargs['nrows']   = kwargs.get('nrows',   None)

    if read_or_write == 'write':
        if filetype == '.csv':
            kwargs['newline'] = kwargs.get('newline', '')

        if filetype == '.json':
            kwargs['indent']       = kwargs.get('indent',       4)
            kwargs['ensure_ascii'] = kwargs.get('ensure_ascii', encoding in (None, 'ascii'))
            kwargs['default']      = kwargs.get('default',      json_unhandled_conversion)

            if ultrajson_installed:
                for k in ('default', 'separators'):
                    try:             del kwargs[k]
                    except KeyError: pass

    return kwargs


# noinspection PyRedundantParentheses
def __validate_read_or_write(path, mode, read_or_write):
    is_read_mode   = ('r' in mode)
    is_write_mode  = ('w' in mode)
    is_append_mode = ('a' in mode)
    is_url         = is_path_a_url(path)

    if read_or_write.startswith('r'):
        if (not is_read_mode) or is_append_mode:
            raise ValueError('invalid read mode: {}'.format(mode))

    elif read_or_write.startswith('w'):
        if (not is_write_mode):
            raise ValueError('invalid write mode: {}'.format(mode))
        if is_url:
            raise NotImplementedError('can not write to url: {}'.format(path))

    return read_or_write


def __read_csv(path, mode, encoding, kwargs):
    """
    _csv.Error: new-line character seen in unquoted field - do you need to open the file in universal-newline mode?
        fixed by passing lineterminator='\r'
        or newline='\r', newline=''
    """
    # region {closure}
    def read_csv_rows():
        if read_all_rows:
            return list(csv_reader)

        m = []
        try:
            for i in range(nrows):
                m.append(next(csv_reader))
        except StopIteration:
            pass

        return m

    # noinspection PyUnusedLocal
    def remove_url_from_rows(m):
        num_deleted = 0

        try:
            while is_path_a_url(m[0][0]):
                del m[0]
                num_deleted += 1
        except Exception as e:
            pass

        # if nrows specified, append rows to make up for deleted rows
        if not read_all_rows:
            try:
                for _ in range(num_deleted):
                    m.append(next(csv_reader))
            except StopIteration:
                pass

        return m
    # endregion

    newline  = kwargs.pop('newline')
    nrows    = kwargs.pop('nrows')
    read_all_rows = (nrows is None)

    if is_path_a_url(path):
        with StringIO(__url_request(path, encoding=encoding), newline=newline) as f:
            csv_reader = csv.reader(f, **kwargs)
            csv_m = read_csv_rows()
            csv_m = remove_url_from_rows(csv_m)

            return csv_m

    with open(path, mode, encoding=encoding, newline=newline) as f:
        csv_reader = csv.reader(f, **kwargs)
        csv_m = read_csv_rows()

        return csv_m


def __read_json(path, mode, encoding, kwargs):
    if is_path_a_url(path):
        s = __url_request(path, encoding=encoding)
        return json.loads(s, **kwargs)

    with open(path, mode, encoding=encoding) as f:
        return json.load(f, **kwargs)


def __url_request(url, encoding=None):
    with urlopen(url) as request:
        if request.code != 200:
            raise IOError('bad url request: ({}) {}'.format(request.code, url))

        byte_string = request.read()

        if encoding:
            return byte_string.decode(encoding)
        else:
            return byte_string


def json_dumps_extended(o, **kwargs):
    kwargs['ensure_ascii'] = kwargs.get('ensure_ascii', False)
    kwargs['indent']       = kwargs.get('indent', 4)
    kwargs['default']      = kwargs.get('default', json_unhandled_conversion)

    if ultrajson_installed:
        del kwargs['default']

    return json.dumps(o, **kwargs)


def json_unhandled_conversion(v):
    """
    convert certain python objects to json string representations, eg:
        date, datetime, set
    """
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, set):
        return list(v)
    # if isinstance(v, Decimal) ?

    raise TypeError("object '{}', of type '{}' is not JSON serializable".format(v, type(v)))


def clear_dir(filedir):
    filedir = standardize_path(filedir, abspath=True)

    if not os.path.exists(filedir):
        return

    if not os_isdir(filedir):
        raise TypeError('"{}" is not a directory'.format(filedir))

    for item in os.listdir(filedir):
        path = filedir + item

        if os_isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


def copy_dir(s_dir, d_dir, ignore=None, dirs_exist_ok=False):
    """
    shutil.copytree will fail if shutil.rmtree hasn't finished deleting folder:
        PermissionError: [WinError 5] Access is denied
    """
    s_dir = standardize_path(s_dir)
    d_dir = standardize_path(d_dir)

    if ignore:
        if isinstance(ignore, str):
            ignore = (ignore,)
        elif isinstance(ignore, set):
            ignore = tuple(ignore)

        ignore = shutil.ignore_patterns(*ignore)

    if not dirs_exist_ok and os.path.exists(d_dir):
        shutil.rmtree(d_dir)

    shutil.copytree(src=s_dir,
                    dst=d_dir,
                    ignore=ignore,
                    dirs_exist_ok=dirs_exist_ok)


def file_creation_datetime(path):
    unix_t = os.path.getctime(path)
    return datetime.fromtimestamp(unix_t)


def file_modified_datetime(path):
    unix_t = os.stat(path).st_mtime
    return datetime.fromtimestamp(unix_t)


@lru_cache(8)
def is_path_a_url(path):
    u = urlparse(path).netloc
    return bool(u)


def parse_path(path,
               pathsep='/',
               abspath=False) -> namedtuple:

    ParsedPath = namedtuple('ParsedPath', ('directory',
                                           'filename',
                                           'extension'))

    _path_ = path
    _path_ = standardize_path(_path_, pathsep, abspath)

    directory, filename  = os.path.split(_path_)
    filename,  extension = os.path.splitext(filename)

    directory = standardize_path(directory, pathsep, abspath)

    return ParsedPath(directory, filename, extension)


def parse_file_name(path):
    filename, _ = os.path.splitext(path)

    return filename


def parse_file_extension(filename, include_dot=True):
    _, extension = os.path.splitext(filename)
    if (include_dot is False) and extension.startswith('.'):
        extension = extension[1:]

    return extension


def standardize_path(path,
                     pathsep='/',
                     abspath=False):

    _path_ = path or ''
    if not _path_ and (not abspath):
        return ''

    if (not abspath) and (not os.path.isabs(_path_)):
        _path_ = os.path.relpath(_path_)
    else:
        _path_ = os.path.realpath(_path_)

    if pathsep == '/':
        _path_ = _path_.replace('\\', '/')
    else:
        _path_ = _path_.replace('/', '\\')

    _path_ = _path_.replace('"', '') \
                   .replace("'", '')

    if _path_ and os_isdir(_path_):
        if not _path_.endswith(pathsep):
            _path_ += pathsep

    return _path_


def traverse_dir(rootdir='.',
                 pathsep='/',
                 abspath=True,
                 *,
                 recurse=False,
                 subdirs_only=False,
                 files_only=False):

    if not is_windows_os:
        raise NotImplementedError('only available on windows OS')

    if (subdirs_only is False) and (files_only is False):
        subdirs_only = True
        files_only   = True

    rootdir = standardize_path(rootdir, pathsep, abspath)

    if recurse:
        args = 'dir /b /s "{}"'.format(rootdir)
    else:
        args = 'dir /b "{}"'.format(rootdir)

    with os.popen(args) as os_cmd:
        out = os_cmd.read()
        out = out.split('\n')
        out.sort()

    if out and out[0] == '':
        del out[0]

    if recurse is False:
        out = [rootdir + p for p in out]

    if subdirs_only and files_only:
        return out
    elif subdirs_only:
        return [path for path in out
                     if os_isdir(path)]
    elif files_only:
        return [path for path in out
                     if os_isfile(path)]


def validate_path_exists(path):

    p_path = parse_path(path, abspath=True)
    path   = ''.join(p_path)

    if not os.path.exists(p_path.directory):
        raise FileNotFoundError('directory not found: \n\t{}'.format(p_path.directory))

    if not os.path.exists(path):
        glob_paths = glob(p_path.directory + p_path.filename + '.*')
        if glob_paths:
            extension = parse_file_extension(os.path.split(glob_paths[0])[1], include_dot=True)
            raise FileNotFoundError('file extension not found: '
                                    '\n\t{}'
                                    '\n\t{}'
                                    '\n\tdid you mean: {}?'.format(p_path.directory,
                                                                   p_path.filename,
                                                                   extension))

        raise FileNotFoundError('file not found: '
                                '\n\t{}'
                                '\n\t{}'.format(p_path.directory,
                                                p_path.filename + p_path.extension))

    return path
