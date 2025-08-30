# /opt/scalp/engine/__init__.py
from .utils.pd_compat import patch_pandas_append
patch_pandas_append()  # active la compat pandas 2.x pour tout l'engine
# ping Sat Aug 30 09:00:38 AM UTC 2025
