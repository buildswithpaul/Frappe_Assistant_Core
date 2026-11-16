"""The exceptions the installed SDK really raises for AR's HTTP errors.

Hand-built SDK exceptions drift from the SDK's own mapping: from 1.14.0 a 503 is an
``ARRateLimitError`` coded ``AR_BUSY``, not an ``ARAPIError``. Building them through a real client
keeps the tests on whatever the installed SDK does.
"""

from unittest.mock import patch

import requests
from assistant_runtime_sdk import ARError, AssistantRuntimeClient


def sdk_http_error(status_code: int, retry_after: str | None = None) -> ARError:
    """Return what a real SDK client raises when AR answers a short GET with ``status_code``."""
    response = requests.Response()
    response.status_code = status_code
    response.url = "https://ar.test/api/method/users.get_my_credit_status"
    response._content = b"{}"
    if retry_after is not None:
        response.headers["Retry-After"] = retry_after
    client = AssistantRuntimeClient(tenant_id="t", tenant_secret="s", ar_url="https://ar.test")
    with patch("requests.get", return_value=response):
        try:
            client.get_my_credit_status("user")
        except ARError as exc:
            return exc
    raise AssertionError(f"The SDK raised nothing for HTTP {status_code}")
