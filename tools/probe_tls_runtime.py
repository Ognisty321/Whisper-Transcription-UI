#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import ssl
import sqlite3
import sys
import urllib.request
import zlib

result = {
    "python": sys.version,
    "openssl": ssl.OPENSSL_VERSION,
    "sqlite": sqlite3.sqlite_version,
    "zlib": zlib.ZLIB_VERSION,
    "ssl_module": ssl._ssl.__file__,
}
with urllib.request.urlopen("https://pypi.org/pypi/pip/json", timeout=30) as response:
    body = response.read(4096)
    result["https_status"] = response.status
    result["https_prefix_sha256"] = hashlib.sha256(body).hexdigest()
print(json.dumps(result, indent=2))
