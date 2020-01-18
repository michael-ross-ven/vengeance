
import ctypes
import os
import pythoncom

from ctypes import POINTER
from ctypes import PyDLL
from ctypes import byref
from ctypes import c_void_p
from ctypes.wintypes import BOOL

from comtypes import COMError
from comtypes import GUID
from comtypes import IUnknown
from comtypes.automation import IDispatch as comtypes_idispatch
from comtypes.client import CreateObject as comtypes_createobject
from comtypes.client.dynamic import Dispatch as comtypes_dispatch

# noinspection PyUnresolvedReferences
from pythoncom import com_error as pythoncom_error
from win32com.client.gencache import EnsureDispatch

from ..util.filesystem import assert_path_exists
from ..util.filesystem import standardize_path
from ..util.text import vengeance_message
from .excel_constants import xlMaximized

# FindWindowExA only accepts ascii-encoded strings
FindWindowExA              = ctypes.windll.user32.FindWindowExA
SetForegroundWindow        = ctypes.windll.user32.SetForegroundWindow
AccessibleObjectFromWindow = ctypes.oledll.oleacc.AccessibleObjectFromWindow

corrupt_hwnds = set()

# FindWindowExA only accepts ascii-encoded strings
xl_main_ascii = 'XLMAIN'.encode('ascii')
xl_desk_ascii = 'XLDESK'.encode('ascii')
excel7_ascii  = 'EXCEL7'.encode('ascii')

xl_clsid  = '{00020400-0000-0000-C000-000000000046}'
native_om = -16


def open_workbook(path,
                  excel_app='new',
                  *,
                  read_only=False,
                  update_links=True):

    wb = is_workbook_open(path)
    if wb is None:
        wb = __open_workbook(excel_app, path, update_links, read_only)

    if (wb.ReadOnly is False) and read_only:
        raise AssertionError("'{}' is not opened read-only".format(wb.Name))

    if wb.ReadOnly and (read_only is False):
        vengeance_message("('{}' opened as read-only)".format(wb.Name))

    return wb


def is_workbook_open(path):
    """ scan all open workbooks across all Excel instances, match is determined by matching file paths
    :return captured Workbook or None
    """
    path = os.path.realpath(path)
    path = standardize_path(path)
    assert_path_exists(path)

    window_h = FindWindowExA(0, 0, xl_main_ascii, None)

    while window_h != 0:
        excel_app = __excel_application_from_hwnd(window_h)

        if excel_app:
            for wb in excel_app.Workbooks:
                if standardize_path(wb.FullName) == path:
                    return wb

        window_h = FindWindowExA(0, window_h, xl_main_ascii, None)

    return None


# noinspection PyUnusedLocal
def close_workbook(wb, save):
    """
    provides a few conveniences that the client may not want to deal with
        1) if Workbook is the only one in the Excel application, closes the application as well
        2) correctly releases the com pointer for the workbook
    """
    if save and wb.ReadOnly:
        raise AssertionError("'{}' is open as read-only, cannot save and close".format(wb.Name))

    excel_app = wb.Application
    display_alerts = excel_app.DisplayAlerts

    if save:
        wb.Save()

    excel_app.DisplayAlerts = False

    wb.Close()
    wb = None

    if excel_app.Workbooks.Count == 0:
        excel_app.Quit()
        excel_app = None
    else:
        excel_app.DisplayAlerts = display_alerts


def new_excel_instance():
    excel_app = comtypes_createobject('Excel.Application', dynamic=True)
    excel_app = __comtype_pointer_to_pythoncom(excel_app, comtypes_idispatch)
    excel_app = EnsureDispatch(excel_app)

    excel_app.WindowState = xlMaximized

    # excel_app_to_foreground(excel_app)
    reload_all_add_ins(excel_app)

    return excel_app


def empty_excel_instance():
    window_h = FindWindowExA(0, 0, xl_main_ascii, None)

    while window_h != 0:
        excel_app = __excel_application_from_hwnd(window_h)

        if __is_excel_app_empty(excel_app):
            vengeance_message('utilizing empty Excel instance')
            return excel_app

        window_h = FindWindowExA(0, window_h, xl_main_ascii, None)

    raise AssertionError('empty Excel instance not found')


def any_excel_instance():
    excel_app = (EnsureDispatch('Excel.Application')
                 or new_excel_instance())
    excel_app.Visible = True

    return excel_app


def all_excel_instances():
    excel_apps = []
    window_h = FindWindowExA(0, 0, xl_main_ascii, None)

    while window_h != 0:
        excel_app = __excel_application_from_hwnd(window_h)
        if excel_app:
            excel_apps.append(excel_app)

        window_h = FindWindowExA(0, window_h, xl_main_ascii, None)

    return excel_apps


def reload_all_add_ins(excel_app):
    vengeance_message('reloading Excel add-ins...')

    for add_in in excel_app.AddIns:
        if add_in.Installed:
            name = add_in.Name
            try:
                add_in.Installed = False
                add_in.Installed = True
                print('\t   * {}'.format(name))
            except COMError:
                vengeance_message('failed to load add-in: {}' + name)


def excel_application_to_foreground(excel_app):
    excel_app.Visible = True
    SetForegroundWindow(excel_app.Hwnd)


def __is_excel_app_empty(excel_app):
    if excel_app is None:
        return False

    workbooks = list(excel_app.Workbooks)
    if not workbooks:
        excel_app.Visible = True
        return True

    if len(workbooks) == 1:
        wb = workbooks[0]

        if wb.Saved and wb.Name == 'Book1':
            ws = wb.Sheets[1]
            if ws.Name == 'Sheet1' and ws.UsedRange.Address == '$A$1':
                return True

    return False


def __open_workbook(excel_app, path, update_links, read_only):
    if read_only:
        vengeance_message('opening workbook as read-only ...')

    excel_app = __convert_excel_application(excel_app)

    excel_app.DisplayAlerts = False
    wb = excel_app.Workbooks.Open(path, update_links, read_only)
    excel_app.DisplayAlerts = True

    return wb


def __convert_excel_application(excel_app):
    if excel_app in (None, 'new'):
        excel_app = new_excel_instance()
        excel_application_to_foreground(excel_app)

        return excel_app

    if excel_app == 'empty':
        excel_app = empty_excel_instance()
        excel_application_to_foreground(excel_app)

        return excel_app

    if excel_app == 'any':
        return any_excel_instance()

    if not hasattr(excel_app, 'Workbooks'):
        raise TypeError("excel_app should be an application pointer or in (None, 'new', 'empty', 'any')")

    return excel_app


# noinspection PyTypeChecker
def __excel_application_from_hwnd(window_h):
    """
    comtypes library is used to search windows handles for Excel application,
    then the application pointer is converted to a pywin object
    """
    global corrupt_hwnds

    if window_h in corrupt_hwnds:
        return None

    desk_hwnd   = FindWindowExA(window_h, None, xl_desk_ascii, None)
    excel7_hwnd = FindWindowExA(desk_hwnd, None, excel7_ascii, None)

    if excel7_hwnd == 0:
        corrupt_hwnds.add(window_h)
        return None

    obj_ptr = POINTER(comtypes_idispatch)()
    xl_guid = GUID.from_progid(xl_clsid)

    AccessibleObjectFromWindow(excel7_hwnd,
                               native_om,
                               byref(xl_guid),
                               byref(obj_ptr))
    try:
        com_ptr   = comtypes_dispatch(obj_ptr).Application
        excel_app = __comtype_pointer_to_pythoncom(com_ptr, comtypes_idispatch)
    except (COMError, pythoncom_error, NameError) as e:
        raise ChildProcessError('remote procedure call to Excel application rejected\n\n'
                                '(check if cursor is still active within a cell somewhere, '
                                'Excel will reject automation calls while waiting on '
                                'user input)') from e

    try:
        excel_app = EnsureDispatch(excel_app)
        excel_app.Visible = True

        return excel_app
    except AttributeError as e:
        raise AttributeError('error dispatching Excel application from win32com module: \n'
                             'Deleting the win32com folder, then re-running function may resolve the error\n'
                             'gencache folder location: %userprofile%\\AppData\\Local\\Temp\\gen_py') from e


# noinspection PyTypeChecker
def __comtype_pointer_to_pythoncom(ptr, interface):
    com_obj = PyDLL(pythoncom.__file__).PyCom_PyObjectFromIUnknown

    com_obj.restype  = ctypes.py_object
    com_obj.argtypes = (POINTER(IUnknown), c_void_p, BOOL)

    # noinspection PyProtectedMember
    return com_obj(ptr._comobj,
                   byref(interface._iid_),
                   True)





