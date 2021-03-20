
import pyodbc
from .flux_cls import flux_cls


class odbc_service_cls:

    def __init__(self, cn_str, sql):
        self.cn_str = cn_str
        self.sql    = sql

        self._cn = pyodbc.connect(self.cn_str)
        self._cr = self._cn.cursor()

    def execute(self):
        self._cr.execute(self.sql)

    def rows(self):
        self.execute()

        m = [col[0] for col in self._cr.description]
        m.extend(list(row) for row in self._cr.fetchall())

        self.disconnect()

        return m

    def flux_rows(self):
        return flux_cls(self.rows())

    def disconnect(self):
        if self._cn is None:
            return

        if self._cr:
            self._cr.close()

        self._cn.close()
        self._cr = None
        self._cn = None


