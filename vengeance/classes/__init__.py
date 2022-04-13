
from .flux_cls import flux_cls
from .log_cls import log_cls

# following more traditional PascalCase naming convention for classes
# noinspection PyPep8Naming
from .flux_cls import flux_cls as Flux
# noinspection PyPep8Naming
from .log_cls import log_cls   as VenLog

__all__ = ['flux_cls',
           'log_cls',
           'Flux',
           'VenLog']
