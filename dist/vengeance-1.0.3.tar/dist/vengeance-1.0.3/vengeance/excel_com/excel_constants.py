
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
xl_yellow = 13434879
xl_clear  = -4142

# find parameters
xl_values     = -4163
xl_cell_type_formulas = -4123
xl_errors     = 16
xl_whole      = 1
xl_part       = 2
xl_next       = 1
xl_previous   = 2
xl_by_rows    = 1
xl_by_columns = 2
xl_up         = -4162
xl_to_right   = -4161

# enums
xl_paste_column_widths = 8
xl_range_ms_xml = 12
xl_range_value_ms_persist_xml = 12

# external / windows / shell constants
xl_maximized = -4137
sw_show      = 1
native_om    = -16

vb_ok_only = 0
process_terminate = 1
