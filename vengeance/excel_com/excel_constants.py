
# excel-specific constants
# (explicitly encoded as ascii instead of utf to avoid issues w/ C++ safearray strings)
xl_class_name   = 'XLMAIN'.encode('ascii')
xl_desk_class   = 'XLDESK'.encode('ascii')
xl_excel7_class = 'EXCEL7'.encode('ascii')

# HKEY_CLASSES_ROOT\Excel.Application: excel's clsid
xl_clsid = '{00020400-0000-0000-C000-000000000046}'

excel_errors = {-2146826281: 'error div0',
                -2146826246: 'error na',
                -2146826259: 'error name',
                -2146826288: 'error null',
                -2146826252: 'error num',
                -2146826265: 'error ref',
                -2146826273: 'error value',
                0x800A07FA:  'error div0'}

# colors
xlClear = -4142

# find parameters
xlCellTypeFormulas = -4123
xlValues           = -4163
xlErrors           = 16
xlWhole            = 1
xlPart             = 2
xlNext             = 1
xlPrevious         = 2
xlByRows           = 1
xlByColumns        = 2
xlUp               = -4162
xlToRight          = -4161

# other enums
xlPasteColumnWidths    = 8
xlMaximized            = -4137
xlCalculationManual    = -4135
xlCalculationAutomatic = -4105

# external / windows api
native_om = -16

