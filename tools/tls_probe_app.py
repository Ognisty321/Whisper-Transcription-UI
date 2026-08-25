#!/usr/bin/env python3
from __future__ import annotations

import json
import ssl
import sys
import urllib.request

print(json.dumps({"python": sys.version, "openssl": ssl.OPENSSL_VERSION}))
with urllib.request.urlopen("https://pypi.org/pypi/pip/json", timeout=30) as response:
    print("https_status=" + str(response.status))
