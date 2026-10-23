"""Read-only public metadata APIs. Source failures remain visible to callers."""
import os
import time
from urllib.parse import quote
import xml.etree.ElementTree as ET
import requests
from .models import Record
from .parsing import normalize_doi


class ProviderError(Exception):
    pass


class HTTP:
    def __init__(self, session=None):
        self.session = session or requests.Session()

    def get(self, url, params=None, headers=None):
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, headers={'User-Agent': 'ReferenceVerifier/0.1 (bibliographic matching)', **(headers or {})}, timeout=12)
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                if response.status_code == 404: return None
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                # Never expose exception URLs containing API keys.
                raise ProviderError('Source request failed or timed out') from None
        raise ProviderError('Source rate limited')


def source(name, record_id, url):
    return [{'name': name, 'id': str(record_id), 'url': url}]


class Crossref:
    name = 'Crossref'
    def __init__(self, http=None): self.http = http or HTTP()
    def search(self, ref):
        params = {'mailto': os.getenv('CROSSREF_MAILTO')} if os.getenv('CROSSREF_MAILTO') else {}
        direct = bool(ref.doi)
        url = 'https://api.crossref.org/works' + ('/' + quote(ref.doi, safe='') if direct else '')
        if not direct: params.update({'query.bibliographic': ref.raw, 'rows': 5})
        res = self.http.get(url, params)
        if res is None: return []
        data = res.json()['message']
        items = [data] if direct else data.get('items', [])
        records = []
        for item in items:
            dates = item.get('published', item.get('issued', {})).get('date-parts', [[]])
            doi = normalize_doi(item.get('DOI'))
            records.append(Record(title=' '.join(item.get('title', [])),
                authors=[' '.join(filter(None, (a.get('given'), a.get('family')))) for a in item.get('author', [])],
                year=str(dates[0][0]) if dates and dates[0] else '',
                venue=' '.join(item.get('container-title', [])), doi=doi,
                sources=source(self.name, doi, 'https://doi.org/' + doi)))
        return records


class OpenAlex:
    name = 'OpenAlex'
    def __init__(self, http=None): self.http = http or HTTP()
    def search(self, ref):
        headers = {'Authorization': 'Bearer ' + os.environ['OPENALEX_API_KEY']} if os.getenv('OPENALEX_API_KEY') else {}
        direct = bool(ref.doi)
        url = 'https://api.openalex.org/works' + ('/https://doi.org/' + quote(ref.doi, safe='') if direct else '')
        params = None if direct else {'search': ref.title or ref.raw, 'per-page': 5}
        res = self.http.get(url, params, headers)
        if res is None: return []
        data = res.json()
        items = [data] if direct else data.get('results', [])
        return [Record(title=i.get('display_name') or '',
            authors=[a.get('author', {}).get('display_name', '') for a in i.get('authorships', [])],
            year=str(i.get('publication_year') or ''),
            venue=((i.get('primary_location') or {}).get('source') or {}).get('display_name') or '',
            doi=normalize_doi(i.get('doi')), pmid=str((i.get('ids') or {}).get('pmid') or '').rstrip('/').split('/')[-1],
            sources=source(self.name, i.get('id', ''), i.get('id', ''))) for i in items]


class PubMed:
    name = 'PubMed'
    base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
    def __init__(self, http=None): self.http = http or HTTP()
    def search(self, ref):
        common = {'db': 'pubmed', 'tool': 'reference-verifier'}
        if os.getenv('NCBI_API_KEY'): common['api_key'] = os.environ['NCBI_API_KEY']
        if ref.pmid:
            ids = [ref.pmid]
        else:
            term = f'{ref.doi}[AID]' if ref.doi else (ref.title or ref.raw)
            res = self.http.get(self.base + 'esearch.fcgi', {**common, 'term': term, 'retmode': 'json', 'retmax': 5})
            if res is None: return []
            ids = res.json()['esearchresult'].get('idlist', [])
        if not ids: return []
        time.sleep(0.35)
        res = self.http.get(self.base + 'efetch.fcgi', {**common, 'id': ','.join(ids), 'retmode': 'xml'})
        if res is None: return []
        records = []
        for article in ET.fromstring(res.content).findall('.//PubmedArticle'):
            def txt(path):
                node = article.find(path)
                return ''.join(node.itertext()) if node is not None else ''
            pmid = txt('.//MedlineCitation/PMID')
            doi = next((n.text for n in article.findall('.//ArticleId') if n.get('IdType') == 'doi'), '')
            authors = [' '.join(filter(None, (a.findtext('ForeName'), a.findtext('LastName'), a.findtext('CollectiveName')))) for a in article.findall('.//Author')]
            records.append(Record(title=txt('.//ArticleTitle'), authors=authors,
                year=txt('.//JournalIssue/PubDate/Year') or txt('.//ArticleDate/Year'),
                venue=txt('.//Journal/Title'), doi=normalize_doi(doi), pmid=pmid,
                sources=source(self.name, pmid, f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/')))
        return records
