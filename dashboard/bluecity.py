"""Read-only BlueCity adapter using the repository's supplied API contract.

Only token acquisition POST and allowlisted analytics GET requests exist here.
No site configuration endpoints are implemented.
"""
import json
import os
import time
from urllib.request import Request, HTTPRedirectHandler
from urllib.parse import urlencode

ENDPOINTS = {
    'turning_counts': 'https://core.api.bluecity.ai/api/v2/turningmovement/',
    'phases': 'https://spm.api.bluecity.ai/api/v2/spm/phase/details/customer/',
}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Unexpected redirect from BlueCity; request stopped')

class BlueCity:
    def __init__(self):
        self.token = None
        self.expires = 0

    def _request(self, url, payload=None, token=None):
        from urllib.request import build_opener
        headers = {'Accept':'application/json'}
        if token: headers['Authorization'] = 'Bearer '+token
        if payload is not None: headers['Content-Type'] = 'application/json'
        req = Request(url,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
        with build_opener(NoRedirect).open(req,timeout=30) as response:
            body = response.read(10_000_001)
            if len(body) > 10_000_000: raise ValueError('Upstream response exceeds 10 MB')
            return json.loads(body)

    def query(self, kind, params):
        if kind not in ENDPOINTS: raise ValueError('Unsupported read-only endpoint')
        if not self.token or time.time() >= self.expires:
            username, password = os.getenv('BLUECITY_USERNAME'), os.getenv('BLUECITY_PASSWORD')
            if not username or not password: raise ValueError('Set BlueCity credentials locally before collecting cloud data')
            result = self._request('https://core.api.bluecity.ai/api/token/', {'username':username,'password':password})
            self.token = result['access']
            # Refresh conservatively; do not rely on conflicting example expiry statements.
            self.expires = time.time()+300
        return self._request(ENDPOINTS[kind]+'?'+urlencode(params),token=self.token)
