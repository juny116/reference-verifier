"""Loopback-only review UI, bounded in-memory reports, explicit exports."""
from collections import OrderedDict
from pathlib import Path
from threading import Lock, BoundedSemaphore
from time import monotonic
from uuid import uuid4
from urllib.parse import urlsplit
import asyncio
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response, JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .documents import read_docx, export_document
from .verification import Verifier

app = FastAPI(title='Reference Verifier', docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
reports = OrderedDict()
lock = Lock()
slots = BoundedSemaphore(2)
WEB = Path(__file__).with_name('web')

@app.middleware('http')
async def guard(request, call_next):
    if request.method == 'POST':
        origin = request.headers.get('origin')
        if origin and urlsplit(origin).netloc != request.headers.get('host'):
            return JSONResponse({'detail': 'Cross-origin requests are not allowed.'}, status_code=403)
        try:
            if int(request.headers.get('content-length', '0')) > 5_100_000:
                return JSONResponse({'detail': 'Request exceeds 5 MB.'}, status_code=413)
        except ValueError:
            return JSONResponse({'detail': 'Invalid content length.'}, status_code=400)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    return response

@app.get('/')
def index(): return FileResponse(WEB / 'index.html')

@app.get('/app.js')
def script(): return FileResponse(WEB / 'app.js', media_type='text/javascript')

@app.get('/style.css')
def style(): return FileResponse(WEB / 'style.css', media_type='text/css')

@app.get('/api/demo')
def demo():
    return {'text': 'Vaswani (2017). "Attention Is All You Need". Advances in Neural Information Processing Systems.\nLeCun (2018). "Deep learning". Nature. DOI: 10.1038/nature14539\nImaginary (2024). "Unicorn-Powered Bibliographic Teleportation". Fictional Journal.'}

@app.post('/api/check')
async def check(request: Request):
    if not slots.acquire(blocking=False): raise HTTPException(429, 'Two checks are already running. Try again shortly.')
    try:
        form = await request.form(max_files=1, max_fields=5)
        mode = str(form.get('mode', 'demo'))
        if mode not in ('demo', 'live'): raise ValueError('Unknown mode.')
        upload = form.get('file')
        if upload is not None and getattr(upload, 'filename', ''):
            if not upload.filename.lower().endswith('.docx'): raise ValueError('Upload a DOCX reference list.')
            data = await upload.read(5_000_001)
            lines = read_docx(data)
        else:
            text = str(form.get('text', ''))
            if len(text) > 120_000: raise ValueError('Text is too long.')
            lines = [line.strip() for line in text.splitlines() if line.strip()]
        verifier = Verifier(demo=mode == 'demo', ai=form.get('ai') == 'true')
        report = await asyncio.to_thread(verifier.verify, lines)
        ident = uuid4().hex
        with lock:
            for old, (stamp, _) in list(reports.items()):
                if monotonic() - stamp > 3600: del reports[old]
            while len(reports) >= 32: reports.popitem(last=False)
            reports[ident] = (monotonic(), report)
        return {'id': ident, **report}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    finally: slots.release()


def get_report(ident):
    with lock:
        stored = reports.get(ident)
        if stored is None or monotonic() - stored[0] > 3600:
            raise HTTPException(404, 'Report expired. Run the check again.')
        return stored[1]

class ExportRequest(BaseModel):
    report_id: str
    selections: dict[str, str] = Field(default_factory=dict)
    format: str = 'docx'

@app.post('/api/export')
def export(payload: ExportRequest):
    try: data = export_document(get_report(payload.report_id), payload.selections, payload.format)
    except ValueError as exc: raise HTTPException(400, str(exc)) from None
    media = 'text/plain' if payload.format == 'txt' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return Response(data, media_type=media, headers={'Content-Disposition': f'attachment; filename="reviewed-references.{payload.format}"'})

@app.get('/api/report/{ident}')
def report(ident: str):
    return Response(json.dumps(get_report(ident), indent=2, ensure_ascii=False), media_type='application/json',
                    headers={'Content-Disposition': 'attachment; filename="reference-report.json"'})
