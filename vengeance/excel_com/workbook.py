
import ctypes
import pythoncom

from ctypes import POINTER
from ctypes import PyDLL
from ctypes import byref
from ctypes import c_void_p
from ctypes import py_object
from ctypes.wintypes import BOOL

from _ctypes import COMError as ctypes_error
# from comtypes import COMError as ctypes_error
from comtypes import GUID
from comtypes import IUnknown
from comtypes.automation     import IDispatch as comtypes_idispatch
from comtypes.client         import CreateObject as comtypes_createobject
from comtypes.client.dynamic import Dispatch as comtypes_dispatch               # late-bound reference

# noinspection PyUnresolvedReferences
from pythoncom import com_error as pythoncom_error
from win32com.client.gencache import EnsureDispatch                             # early-bound reference

from ..util.filesystem import standardize_path
from ..util.filesystem import validate_path_exists

from ..util.text import vengeance_message
from ..util.text import vengeance_warning
from .excel_constants import *

# Windows api functions
FindWindowExA              = ctypes.windll.user32.FindWindowExA
SetForegroundWindow        = ctypes.windll.user32.SetForegroundWindow
AccessibleObjectFromWindow = ctypes.oledll.oleacc.AccessibleObjectFromWindow

# FindWindowExA only accepts ascii strings
xl_main_ascii = 'XLMAIN'.encode('ascii')
xl_desk_ascii = 'XLDESK'.encode('ascii')
excel7_ascii  = 'EXCEL7'.encode('ascii')

xl_clsid      = '{00020400-0000-0000-C000-000000000046}'
corrupt_hwnds = set()
native_om     = -16


def open_workbook(path,
                  excel_app='new',
                  *,
                  read_only=False,
                  update_links=True,
                  windowstate=xlMaximized):

    wb = get_opened_workbook(path)
    if wb is None:
        wb = __open_workbook_dispatch(path,
                                      excel_app,
                                      update_links=update_links,
                                      read_only=read_only,
                                      windowstate=windowstate)

    if (wb.ReadOnly is False) and read_only:
        raise AssertionError("'{}' is not open as read-only".format(wb.Name))

    if wb.ReadOnly and (read_only is False):
        vengeance_warning("'{}' is open as read-only".format(wb.Name))

    return wb


def get_opened_workbook(path):
    """ scan all open workbooks across all Excel instances for matching paths

    :return captured Workbook or None
    """
    path = standardize_path(path)

    workbooks = []
    for excel_app in all_excel_instances():
        for wb in excel_app.Workbooks:
            if path == standardize_path(wb.FullName):
                workbooks.append(wb)
            elif path == standardize_path(wb.Name):
                workbooks.append(wb)

    if workbooks:
        if len(workbooks) > 1:
            vengeance_warning("multiple workbooks matching path: '{}' exist in different "
                              "Excel applications... returning first match".format(path))
        return workbooks[0]

    return None


def is_workbook_open(path):
    wb = get_opened_workbook(path)
    return wb is not None


# noinspection PyUnusedLocal
def close_workbook(wb, save):
    """
    provides a few conveniences that the client may not want to deal with
        1) if Workbook is the only one in the Excel application, closes the application as well
        2) correctly releases the com pointer for the workbook
    """
    import gc

    if save and wb.ReadOnly:
        raise AssertionError("'{}' is open as read-only, cannot save and close".format(wb.Name))

    excel_app = wb.Application
    display_alerts = excel_app.DisplayAlerts

    if save:
        wb.Save()

    excel_app.DisplayAlerts = False
    wb.Close()
    wb = None
    del wb

    if excel_app.Workbooks.Count == 0:
        excel_app.Quit()
        excel_app = None
        del excel_app
    else:
        excel_app.DisplayAlerts = display_alerts

    gc.collect()


def __open_workbook_dispatch(path, excel_app,
                             *,
                             update_links,
                             read_only,
                             windowstate):

    path = validate_path_exists(path)
    excel_app = __validate_excel_application(excel_app, windowstate)

    if read_only:
        vengeance_message('(opening workbook as read-only ...)')

    excel_app.DisplayAlerts = False
    wb = excel_app.Workbooks.Open(path, update_links, read_only)
    excel_app.DisplayAlerts = True

    return wb


def __validate_excel_application(excel_app, windowstate=None):
    if excel_app in (None, 'new'):
        return new_excel_application(windowstate)

    if excel_app == 'any':
        return any_excel_application(windowstate)

    if excel_app == 'empty':
        excel_app = empty_excel_application(windowstate)
        if excel_app is None:
            raise AssertionError('empty Excel application not found')

        return excel_app

    if not hasattr(excel_app, 'Workbooks'):
        raise ValueError("excel_app parameter should be in (None, 'new', 'any', 'empty') or an application pointer")

    return excel_app


def new_excel_application(windowstate=None):
    excel_app = comtypes_createobject('Excel.Application', dynamic=True)
    excel_app = __comtype_pointer_to_pythoncom_object(excel_app, comtypes_idispatch)
    excel_app = EnsureDispatch(excel_app)

    reload_all_add_ins(excel_app)
    excel_application_to_foreground(excel_app, windowstate)

    return excel_app


def any_excel_application(windowstate=None):
    excel_app = EnsureDispatch('Excel.Application')
    if excel_app:
        excel_application_to_foreground(excel_app, windowstate)
    else:
        excel_app = new_excel_application(windowstate)

    return excel_app


def empty_excel_application(windowstate=None):
    for excel_app in all_excel_instances():

        if __is_excel_application_empty(excel_app):
            vengeance_message('utilizing empty Excel instance: {}'.format(excel_app.Hwsd))
            excel_application_to_foreground(excel_app, windowstate)

            return excel_app

    return None


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
    vengeance_message('reloading Excel add-ins...')

    for add_in in excel_app.AddIns:
        if add_in.Installed:
            name = add_in.Name

            try:
                add_in.Installed = False
                add_in.Installed = True
                print('\t   * {}'.format(name))
            except (ctypes_error, pythoncom_error, NameError) as e:
                vengeance_warning('failed to load Excel add-in: {}\n{}'.format(name, e))

    print()


def excel_application_to_foreground(excel_app, windowstate=None):
    if windowstate not in (None, xlNormal, xlMaximized):
        raise ValueError('windowstate must be in: (None, xlNormal, xlMaximized)')

    if windowstate is not None:
        excel_app.WindowState = windowstate

    excel_app.Visible = True
    SetForegroundWindow(excel_app.Hwnd)


def __next_window_handle(window_h=0):
    return FindWindowExA(0, window_h, xl_main_ascii, None)


def __excel_application_from_window_handle(window_h):
    """
    comtypes library is used to search windows handles for Excel application,
    then the application pointer is converted to a pywin object

    obj_ptr = POINTER(comtypes_idispatch)()
        Expected type [_CT], got Type[IDispatch] instead
        this is probably not correct way to set up this pointer

        from pywintypes import IID
    """
    global corrupt_hwnds

    if window_h in corrupt_hwnds:
        return None

    desk_hwnd   = FindWindowExA(window_h,  None, xl_desk_ascii, None)
    excel7_hwnd = FindWindowExA(desk_hwnd, None, excel7_ascii,  None)

    if excel7_hwnd == 0:
        corrupt_hwnds.add(window_h)
        return None

    # noinspection PyTypeChecker
    obj_ptr = POINTER(comtypes_idispatch)()
    xl_guid = GUID.from_progid(xl_clsid)
    AccessibleObjectFromWindow(excel7_hwnd,
                               native_om,
                               byref(xl_guid),
                               byref(obj_ptr))

    # comtypes Dispatch() call rejected; user may be editing cell
    try:
        com_ptr   = comtypes_dispatch(obj_ptr).Application
        excel_app = __comtype_pointer_to_pythoncom_object(com_ptr, comtypes_idispatch)
    except (ctypes_error, pythoncom_error, NameError) as e:
        raise ChildProcessError('remote procedure call to Excel Application rejected\n\n'
                                '(check if cursor is still active within a cell somewhere, '
                                'Excel will reject automation calls while waiting on '
                                'user input)') from e

    # win32com Dispatch() call rejected; COM files corrupted
    try:
        return EnsureDispatch(excel_app)
    except AttributeError as e:
        import subprocess
        import win32com

        gc_folder = win32com.__gen_path__
        subprocess.call('explorer "{}"'.format(gc_folder))

        raise ChildProcessError('\nError dispatching Excel Application from win32com module. \n'
                                'Deleting the contents of the gencache folder, then rerunning may resolve the error\n'
                                '\t(win32com gencache folder location: {})\n'
                                .format(gc_folder)) from e


# noinspection PyTypeChecker
def __comtype_pointer_to_pythoncom_object(ptr, interface):
    com_obj          = PyDLL(pythoncom.__file__).PyCom_PyObjectFromIUnknown
    com_obj.restype  = py_object
    com_obj.argtypes = (POINTER(IUnknown), c_void_p, BOOL)

    # noinspection PyProtectedMember
    return com_obj(ptr._comobj, byref(interface._iid_), True)


# noinspection PyUnusedLocal
def __is_excel_application_empty(excel_app):
    """ an Excel application with no workbooks or a an Excel application
    with the default workbook opened
    """
    for wb in excel_app.Workbooks:
        if wb.Saved:
            return False

        for ws in wb.Sheets:
            if ws.UsedRange.Address != '$A$1':
                return False

    return True




