import json
from io import BytesIO
import pytest
from docx import Document
from fastapi.testclient import TestClient
from reference_verifier.models import Record
from reference_verifier.parsing import parse_reference, extract_with_llm, normalize_doi
from reference_verifier.verification import Verifier, merge_records
from reference_verifier.providers import ProviderError
from reference_verifier.documents import export_document, selected_lines, read_docx
from reference_verifier.server import app

class Source:
    name = 'Fixture'
    def __init__(self, records=(), fail=False): self.records, self.fail = records, fail
    def search(self, ref):
        if self.fail: raise ProviderError('offline')
        return self.records

def record(**kwargs):
    return Record(**({'title':'Deep learning', 'authors':['Yann LeCun'], 'year':'2015', 'doi':'10.1038/nature14539', 'sources':[{'name':'Fixture','url':'https://example.org'}]} | kwargs))

def test_demo_outcomes():
    report = Verifier(demo=True).verify(['Vaswani (2017). "Attention Is All You Need".', 'LeCun (2018). "Deep learning". DOI: 10.1038/nature14539', 'Imaginary (2024). "Unicorn-Powered Bibliographic Teleportation".'])
    assert [r['status'] for r in report['results']] == ['matched','needs_review','not_found']

@pytest.mark.parametrize('raw', ['LeCun (2018). "Deep learning". DOI: 10.1038/nature14539', 'Smith (2015). "Deep learning". DOI: 10.1038/nature14539', 'LeCun (2015). "Different research title". DOI: 10.1038/nature14539', 'LeCun (2015). "Deep learning". DOI: 10.1000/wrong'])
def test_identifier_does_not_override_conflicts(raw):
    result = Verifier([Source([record()])]).verify([raw])['results'][0]
    assert result['status'] == 'needs_review'

def test_outage_is_not_absence_or_confirmation():
    assert Verifier([Source(fail=True)]).verify(['A title'])['results'][0]['status'] == 'incomplete_search'
    assert Verifier([Source([record()]), Source(fail=True)]).verify(['10.1038/nature14539'])['results'][0]['status'] == 'needs_review'

def test_ambiguous_candidates_need_review():
    result = Verifier([Source([record(), record(doi='10.1000/other')])]).verify(['LeCun (2015). "Deep learning".'])
    assert result['results'][0]['status'] == 'needs_review'

def test_shared_identifier_preserves_conflicting_evidence():
    merged = merge_records([record(), record(year='2016', authors=['Another Author'])])
    assert len(merged) == 1
    assert any('year' in c for c in merged[0].conflicts)
    assert any('authors' in c for c in merged[0].conflicts)
    assert Verifier([Source(merged)]).verify(['10.1038/nature14539'])['results'][0]['status'] == 'needs_review'

def test_doi_year_is_not_publication_year():
    ref = parse_reference('https://doi.org/10.1000/2018.1234')
    assert ref.year == '' and ref.authors == []
    assert normalize_doi('https://doi.org/10.1000/Test).') == '10.1000/test'

class FakeSession:
    def post(self, *args, **kwargs): return self
    def raise_for_status(self): pass
    def json(self): return {'choices':[{'message':{'content':json.dumps({'title':'Invented work','authors':['Madeup Author'],'year':'2027'})}}]}

def test_ai_cannot_add_missing_metadata(monkeypatch):
    monkeypatch.setenv('REFERENCE_LLM_API_KEY','test')
    monkeypatch.setenv('REFERENCE_LLM_MODEL','test')
    ref = extract_with_llm('LeCun (2015). "Deep learning".', FakeSession())
    assert (ref.title, ref.year, ref.authors) == ('Deep learning','2015',['LeCun'])
    assert len(ref.warnings) == 3

def test_explicit_export_and_docx_roundtrip():
    raw = 'LeCun (2018). "Deep learning". DOI: 10.1038/nature14539'
    report = Verifier(demo=True).verify([raw])
    assert selected_lines(report,{}) == [raw]
    corrected = selected_lines(report,{'0':'0'})
    assert '(2015)' in corrected[0]
    assert read_docx(export_document(report,{'0':'0'},'docx')) == corrected
    with pytest.raises(ValueError): selected_lines(report,{'0':'99'})
    with pytest.raises(ValueError): selected_lines(report,{'9':'0'})
    with pytest.raises(ValueError): read_docx(b'not a zip')

def test_ui_api_export_requires_selection():
    with TestClient(app) as client:
        raw = 'LeCun (2018). "Deep learning". DOI: 10.1038/nature14539'
        response = client.post('/api/check',data={'text':raw,'mode':'demo'})
        assert response.status_code == 200
        report = response.json()
        exported = client.post('/api/export',json={'report_id':report['id'],'format':'txt'})
        assert exported.text.strip() == raw
        assert client.post('/api/export',json={'report_id':report['id'],'selections':{'0':'99'}}).status_code == 400
        assert client.post('/api/check',data={'text':raw},headers={'origin':'https://untrusted.example'}).status_code == 403
        assert client.post('/api/check',data={'text':''}).status_code == 400
        assert client.get('/api/report/absent').status_code == 404
        assert 'frame-ancestors' in client.get('/').headers['content-security-policy']


def test_identifier_punctuation_is_significant():
    r = record(doi='10.1000/a-b')
    result = Verifier([Source([r])]).verify(['LeCun (2015). "Deep learning". DOI: 10.1000/a.b'])
    assert result['results'][0]['status'] == 'needs_review'

def test_missing_supplied_year_needs_review():
    result = Verifier([Source([record(year='')])]).verify(['LeCun (2015). "Deep learning". DOI: 10.1038/nature14539'])
    assert result['results'][0]['status'] == 'needs_review'


def test_private_deployment_auth(monkeypatch):
    import hashlib
    monkeypatch.setenv('REFERENCE_AUTH_USER', 'reader')
    monkeypatch.setenv('REFERENCE_AUTH_SHA256', hashlib.sha256(b'test-password').hexdigest())
    with TestClient(app) as client:
        for path in ['/', '/app.js', '/api/demo', '/api/report/unknown']:
            assert client.get(path).status_code == 401
        assert client.post('/api/check', data={'text':'title'}).status_code == 401
        assert client.get('/',auth=('reader','wrong')).status_code == 401
        assert client.get('/',auth=('reader','test-password')).status_code == 200
        assert client.get('/',headers={'authorization':'Basic !invalid'}).status_code == 401
        monkeypatch.delenv('REFERENCE_AUTH_SHA256')
        assert client.get('/').status_code == 503
