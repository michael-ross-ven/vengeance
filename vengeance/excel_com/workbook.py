
import ctypes
import gc
import os
import pythoncom

# noinspection PyUnresolvedReferences
from pythoncom import com_error as pythoncom_error
from _ctypes import COMError as ctypes_error

from ctypes import byref
from ctypes import c_void_p
from ctypes import py_object
from ctypes import POINTER
from ctypes import PyDLL
from ctypes.wintypes import BOOL

from comtypes                 import IUnknown
from comtypes.client          import CreateObject as comtypes_createobject
from comtypes.automation      import IDispatch    as comtypes_idispatch
from comtypes.client.dynamic  import Dispatch     as comtypes_dispatch       # late-bound references

from time import sleep

from win32com.client.gencache import EnsureDispatch                          # early-bound references

from ..util.filesystem import parse_path
from ..util.filesystem import standardize_path
from ..util.filesystem import validate_path_exists

from ..util.text import styled
from ..util.text import vengeance_message

from .excel_constants import (xlMaximized,
                              xlNormal,
                              xlMinimized)

# Windows api functions
FindWindowExA              = ctypes.windll.user32.FindWindowExA
SetForegroundWindow        = ctypes.windll.user32.SetForegroundWindow
AccessibleObjectFromWindow = ctypes.oledll.oleacc.AccessibleObjectFromWindow
OpenProcess                = ctypes.windll.kernel32.OpenProcess
TerminateProcess           = ctypes.windll.kernel32.TerminateProcess
CloseHandle                = ctypes.windll.kernel32.CloseHandle

corrupt_hwnds = set()

NATIVE_OM         = -16
WM_CLOSE          = 16
PROCESS_TERMINATE = 1


def open_workbook(path,
                  excel_app='new',
                  *,
                  reload_addins=False,
                  display_alerts=False,
                  enable_events=True,
                  windowstate=xlMaximized,
                  **kwargs):

    wb = get_opened_workbook(path)
    if wb is None:
        wb = __open_workbook_dispatch(path,
                                      excel_app,
                                      reload_addins=reload_addins,
                                      display_alerts=display_alerts,
                                      enable_events=enable_events,
                                      windowstate=windowstate,
                                      **kwargs)

    kw_read_only = kwargs.get('ReadOnly', False)
    wb_read_only = wb.ReadOnly

    if (wb_read_only is False) and kw_read_only:
        raise ValueError("'{}' NOT open as read-only".format(wb.Name))
    elif wb_read_only:
        print(vengeance_message("'{}' open as read-only".format(wb.Name)))

    return wb


def get_opened_workbook(path):
    """ scan all open workbooks across all Excel instances for matching paths

    :return captured Workbook or None
    """
    p_path = parse_path(path.lower(), abspath=False)
    name   = p_path.basename + p_path.extension

    workbooks = []
    for excel_app in all_excel_instances():
        for wb in excel_app.Workbooks:

            wb_path = wb.FullName
            wb_name = wb.Name.lower()

            if name == wb_name:
                workbooks.append(wb)
            else:
                try:
                    if p_path.directory and os.path.samefile(path, wb_path):
                        workbooks.append(wb)
                except Exception:
                    pass

    if not workbooks:
        return None

    if len(workbooks) > 1:
        print(vengeance_message("multiple workbooks in different Excel instances found: '{}' "
                                .format([wb.FullName for wb in workbooks])))

    return workbooks[0]


def is_workbook_open(path):
    wb = get_opened_workbook(path)
    return wb is not None


def close_workbook(wb, save):
    """
    provides a few conveniences that the client may not want to deal with
        1) if Workbook is the only one in the Excel application, closes the application as well
        2) correctly releases the com pointer for the workbook
    """
    import win32gui
    import win32process

    # from win32gui import PostMessage
    # from win32api import OpenProcess
    # from win32api import TerminateProcess
    # from win32api import CloseHandle
    # GetWindowThreadProcessId   = ctypes.windll.user32.GetWindowThreadProcessId

    if save and wb.ReadOnly:
        raise AssertionError("'{}' is open as read-only, cannot save and close".format(wb.Name))

    excel_app      = wb.Application
    window_h       = excel_app.Hwnd
    display_alerts = excel_app.DisplayAlerts

    excel_app.DisplayAlerts = False
    wb.Close(save)
    excel_app.DisplayAlerts = display_alerts

    __close_blank_workbooks(excel_app)

    if __is_excel_application_empty(excel_app):
        excel_app.Quit()
        sleep(1)

        tid, pid = win32process.GetWindowThreadProcessId(window_h)
        win32gui.PostMessage(window_h, WM_CLOSE, 0, 0)
        sleep(1)

        try:
            hid = OpenProcess(PROCESS_TERMINATE, 0, pid)
            if hid:
                TerminateProcess(hid, 0)
                CloseHandle(hid)
                sleep(1)

        except Exception:
            pass

    del excel_app
    del wb

    gc.collect()


def __open_workbook_dispatch(path,
                             excel_app,
                             *,
                             reload_addins,
                             display_alerts,
                             enable_events,
                             windowstate,
                             **kwargs):
    """
    UpdateLinks
        0: don’t update
        1: update external links but not remote links
        2: update remote links but not external links
        3: update all links
        default: prompt the user
    """
    if windowstate not in (None, xlMaximized, xlNormal, xlMinimized):
        raise ValueError('windowstate must be in (None, xlMaximized ({}), xlNormal ({}), xlMinimized ({}))'
                         .format(xlMaximized, xlNormal, xlMinimized))

    path      = validate_path_exists(path)
    excel_app = __validate_excel_dispatch(excel_app)

    if display_alerts:
        excel_application_to_foreground(excel_app, windowstate, add_workbook_if_empty=False)

    _display_alerts_ = excel_app.DisplayAlerts
    _enable_events_  = excel_app.EnableEvents

    excel_app.DisplayAlerts = display_alerts
    excel_app.EnableEvents  = enable_events
    wb = excel_app.Workbooks.Open(path,
                                  **kwargs)
    excel_app.DisplayAlerts = _display_alerts_
    excel_app.EnableEvents  = _enable_events_

    excel_application_to_foreground(excel_app, windowstate, add_workbook_if_empty=False)

    if reload_addins:
        reload_all_add_ins(excel_app)

    return wb


def __validate_excel_dispatch(excel_app):
    if excel_app in (None, 'new'):   return new_excel_application()
    elif excel_app == 'any':         return any_excel_application()
    elif excel_app == 'empty':       return empty_excel_application()

    if not hasattr(excel_app, 'Workbooks'):
        raise ValueError("excel_app parameter must be in (None, 'new', 'any', 'empty') or an Excel application pointer")

    return excel_app


def new_excel_application():
    """
    ?
    excel_app = comtypes_createobject('Excel.Application', dynamic=False)
    """
    excel_app = comtypes_createobject('Excel.Application', dynamic=True)
    excel_app = __iunknown_pointer_to_python_object(excel_app, comtypes_idispatch)

    try:
        excel_app = EnsureDispatch(excel_app)
    except AttributeError:
        # win32com Dispatch() call rejected: COM files may be corrupted
        __move_win32com_gencache_folder()
        raise ChildProcessError('Error dispatching Excel Application from win32com module. '
                                '\n\n\t(contents of the win32com gen_py folder may be corrupt)') from None

    return excel_app


def any_excel_application():
    excel_app = EnsureDispatch('Excel.Application') or \
                new_excel_application()
    return excel_app


def empty_excel_application():

    for excel_app in all_excel_instances():
        if __is_excel_application_empty(excel_app):
            print(vengeance_message('utilizing empty Excel instance'))
            return excel_app

    raise AssertionError('empty Excel application not found')


def __is_excel_application_empty(excel_app):
    """ an Excel application with no workbooks or a an Excel application
    with the default workbook opened
    """
    for wb in excel_app.Workbooks:
        if not __is_workbook_blank(wb):
            return False

    return True


# noinspection PyUnusedLocal
def __close_blank_workbooks(excel_app):
    workbooks = [wb for wb in excel_app.Workbooks
                    if __is_workbook_blank(wb)]

    _display_alerts_ = excel_app.DisplayAlerts
    excel_app.DisplayAlerts = False

    for wb in workbooks:
        wb.Close(False)

        wb = None
        del wb

    excel_app.DisplayAlerts = _display_alerts_


def __is_workbook_blank(wb):
    if not wb.Saved:
        return False

    for ws in wb.Sheets:
        if ws.UsedRange.Address != '$A$1':
            return False

    return True


def all_excel_instances():
    window_h = __next_window_handle()

    excel_hwnds = set()
    while window_h != 0:
        excel_app = __excel_application_from_window_handle(window_h)

        if excel_app is None:
            window_h = __next_window_handle(window_h)
            continue

        hwnd = excel_app.Hwnd
        if hwnd in excel_hwnds:
            window_h = __next_window_handle(window_h)
            continue

        excel_hwnds.add(hwnd)
        yield excel_app

        window_h = __next_window_handle(window_h)


def reload_all_add_ins(excel_app):
    print(vengeance_message('reloading Excel add-ins'))

    for add_in in excel_app.AddIns:
        if add_in.Installed:
            name = add_in.Name

            try:
                add_in.Installed = False
                add_in.Installed = True
                print('        * {}'.format(name))
            except (ctypes_error, pythoncom_error, NameError) as e:
                print('        * error loading Excel add-in: {}, {}'.format(name, e))

    print()


def excel_application_to_foreground(excel_app, windowstate=None, add_workbook_if_empty=False):
    excel_app.Visible = True

    # excel_app will stay invisible until a workbook is added
    if add_workbook_if_empty and (excel_app.Visible is False) and (excel_app.Workbooks.Count == 0):
        excel_app.Workbooks.Add()
        excel_app.Visible = True

    # make sure window is not minimized (xlMinimized has weird behavior)
    if excel_app.WindowState != xlMaximized:
        excel_app.WindowState = xlNormal

    if windowstate is not None:
        excel_app.WindowState = windowstate

    SetForegroundWindow(excel_app.Hwnd)


def __next_window_handle(window_h=0):
    return FindWindowExA(0, window_h, b'XLMAIN', 0)


# noinspection PyTypeChecker,PyProtectedMember,PyUnresolvedReferences
def __excel_application_from_window_handle(window_h):
    """
    comtypes library is used to search windows handles for Excel application,
    then the application pointer is converted to a pywin object

    obj_ptr = POINTER(comtypes_idispatch)()
        Expected type [_CT], got Type[IDispatch] instead
        this is probably not correct way to set up this pointer

        from pywintypes import IID?
    """
    global corrupt_hwnds

    if window_h in corrupt_hwnds:
        return None

    xl_desk_hwnd = FindWindowExA(window_h,     0, b'XLDESK', 0)
    excel7_hwnd  = FindWindowExA(xl_desk_hwnd, 0, b'EXCEL7', 0)

    if excel7_hwnd == 0:
        corrupt_hwnds.add(window_h)
        return None

    obj_ptr = POINTER(comtypes_idispatch)()
    AccessibleObjectFromWindow(excel7_hwnd,
                               NATIVE_OM,
                               byref(obj_ptr._iid_),
                               byref(obj_ptr))

    try:
        com_ptr   = comtypes_dispatch(obj_ptr).Application
        excel_app = __iunknown_pointer_to_python_object(com_ptr, comtypes_idispatch)
    except (ctypes_error, pythoncom_error, NameError):
        # comtypes Dispatch() call rejected: user may be editing cell
        raise ChildProcessError('Remote Procedure Call to Excel Application rejected. '
                                '\n'
                                '\n\t(Excel will reject automation calls while waiting on user input, '
                                '\n\tcheck if cursor is still active within a cell somewhere)') from None

    try:
        return EnsureDispatch(excel_app)
    except AttributeError:
        # win32com Dispatch() call rejected: COM files may be corrupted
        __move_win32com_gencache_folder()

        raise ChildProcessError('Error dispatching Excel Application from win32com module. '
                                '\n\n\t(contents of the win32com gen_py folder may be corrupt)') from None


# noinspection PyTypeChecker, PyProtectedMember
def __iunknown_pointer_to_python_object(com_ptr, interface):
    PyObjectFromIUnknown = PyDLL(pythoncom.__file__).PyCom_PyObjectFromIUnknown

    PyObjectFromIUnknown.restype  = py_object
    PyObjectFromIUnknown.argtypes = (POINTER(IUnknown),
                                     c_void_p,
                                     BOOL)

    o = PyObjectFromIUnknown(com_ptr._comobj,
                             byref(interface._iid_),
                             True)

    return o


# noinspection PyBroadException
def __move_win32com_gencache_folder():
    """
    move win32com gen_py cache files to site-packages folder
    from
        %userprofile%/Local/Temp/gen_py/
    to
        %python_folder%/Lib/site-packages/win32com/gen_py/

    helps prevent win32com EnsureDispatch() call rejection due to corrupted COM files
    """
    try:
        import shutil
        import site
        import subprocess
        import win32com
        from pathlib import Path

        gcf_site    = site.getsitepackages()[1] + '\\win32com\\gen_py\\'
        gcf_corrupt = os.environ['userprofile'] + '\\AppData\\Local\\Temp\\gen_py\\'

        if not os.path.exists(gcf_corrupt):
            gcf_corrupt = win32com.__gen_path__

        if standardize_path(gcf_corrupt).lower() == standardize_path(gcf_site).lower():
            return

        s = vengeance_message('Attempting to reset win32com gencache folder ...\n')
        s = styled(s, 'yellow', 'bold')
        print(s)

        if os.path.exists(gcf_corrupt):
            subprocess.call('explorer.exe "{}"'.format(Path(gcf_corrupt).parent))
            shutil.rmtree(gcf_corrupt)

        if not os.path.exists(gcf_site):
            subprocess.call('explorer.exe "{}"'.format(Path(gcf_site).parent))
            os.makedirs(gcf_site)

    except Exception:
        pass
