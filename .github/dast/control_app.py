"""The API with one planted fault, used as the positive control of the DAST workflow.

A scan that finds nothing is only worth something if the same scan is known to find
something when it is there. This module imports the real application and adds one route the
normal application never has, ``GET /api/v1/dast-control/fault``. It answers 500 with an
HTML page that looks like a leaked Python traceback, so that

- Schemathesis reports a server error (``not_a_server_error``), and
- ZAP's passive rules raise a Medium alert: "Cross-Domain Misconfiguration" (10098) for the
  wildcard CORS header, and, as long as the API's policy allows inline styles, 10055. The
  fake trace also raises "Application Error Disclosure" (90022), which is only Low.

The workflow starts ``control_app:app`` instead of ``api.main:app`` only when it is run by
hand with the ``control`` input set, and expects its gate to fail. Nothing else imports this
module and the route is never part of the deployed application.
"""

from fastapi import Response

from api.main import app

FAKE_TRACEBACK = """<html><body><h1>Internal Server Error</h1><pre>
Traceback (most recent call last):
  File "/srv/app/api/routes/control.py", line 12, in fault
    raise RuntimeError("planted fault for the DAST positive control")
RuntimeError: planted fault for the DAST positive control
</pre></body></html>
"""


@app.get("/api/v1/dast-control/fault")
def fault() -> Response:
    """Answer 500 with a page that discloses a fake stack trace and allows any origin.

    :return: A 500 response with an HTML body
    """
    return Response(
        content=FAKE_TRACEBACK,
        status_code=500,
        media_type="text/html",
        headers={"Access-Control-Allow-Origin": "*"},
    )
