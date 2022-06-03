

class parsed_time_cls:

    def __init__(self, total_seconds):

        # a timedelta
        if hasattr(total_seconds, 'total_seconds'):
            total_seconds = total_seconds.total_seconds()

        if not isinstance(total_seconds, (float, int)):
            raise TypeError('value must be instance of (float, int)')

        self._total_seconds = int(total_seconds)
        self.sign          = None
        self.days          = None
        self.hours         = None
        self.minutes       = None
        self.seconds       = None
        self.microseconds  = None

        self.parse()

    def total_seconds(self):
        return self._total_seconds

    def parse(self):
        total_seconds = self.total_seconds()

        if total_seconds < 0:
            sign = '-'
        elif total_seconds == 0:
            sign = ''
        else:
            sign = '+'

        s  = abs(total_seconds)
        us = str(float(s))
        us = us.split('.')[-1]
        us = int(us)

        s = int(s)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)

        self.sign         = sign
        self.days         = d
        self.hours        = h
        self.minutes      = m
        self.seconds      = s
        self.microseconds = us

    def __repr__(self):
        s = ('vengeance.{}(sign={}, days={}, hours={}, minutes={}, seconds={}, microseconds={})'
             .format(self.__class__.__name__,
                     self.sign,
                     self.days,
                     self.hours,
                     self.minutes,
                     self.seconds,
                     self.microseconds))

        return s

