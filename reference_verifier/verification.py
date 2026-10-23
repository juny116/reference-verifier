"""Conservative matching: ranking is not a probability or a truth guarantee."""
from dataclasses import asdict
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import time
import xml.etree.ElementTree as ET
from .models import Record
from .parsing import normalize, parse_reference, extract_with_llm
from .providers import Crossref, OpenAlex, PubMed, ProviderError


def similarity(a, b):
    if not a or not b: return 0.0
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def author_present(name, candidates):
    tokens = set(normalize(name).split())
    return bool(tokens) and any(tokens <= set(normalize(c).split()) for c in candidates)


def merge_records(records):
    merged = []
    for record in records:
        if not record.title: continue
        target = None
        for existing in merged:
            shared_id = ((record.doi and record.doi == existing.doi) or
                         (record.pmid and record.pmid == existing.pmid))
            conflicting_id = ((record.doi and existing.doi and record.doi != existing.doi) or
                              (record.pmid and existing.pmid and record.pmid != existing.pmid))
            same_text = (normalize(record.title) == normalize(existing.title) and
                         record.year and record.year == existing.year and record.authors and existing.authors and
                         normalize(record.authors[0]) == normalize(existing.authors[0]))
            if shared_id or (same_text and not conflicting_id):
                target = existing
                break
        if target is None:
            merged.append(copy.deepcopy(record))
            continue
        for field in ('title', 'year', 'doi', 'pmid', 'venue'):
            old, new = getattr(target, field), getattr(record, field)
            if old and new and (old != new if field in ('doi', 'pmid') else normalize(old) != normalize(new)):
                target.conflicts.append(f'{field}: {old} ≠ {new} ({record.sources[0]["name"]})')
            elif not old: setattr(target, field, new)
        if not target.authors: target.authors = list(record.authors)
        elif record.authors and {normalize(a) for a in target.authors} != {normalize(a) for a in record.authors}:
            target.conflicts.append('authors: ' + '; '.join(target.authors) + ' ≠ ' + '; '.join(record.authors))
        for entry in record.sources:
            if entry not in target.sources: target.sources.append(entry)
    return merged


def compare(ref, record):
    diffs = []
    title_score = similarity(ref.title, record.title)
    score = title_score * 0.7
    for field in ('doi', 'pmid', 'title', 'year'):
        original, candidate = getattr(ref, field), getattr(record, field)
        if not original: state = 'not_supplied'
        elif not candidate: state = 'missing_in_source'
        elif (original == candidate if field in ('doi', 'pmid') else normalize(original) == normalize(candidate)): state = 'equal'
        else: state = 'different'
        diffs.append({'field': field, 'input': original, 'candidate': candidate, 'state': state})
    authors_match = bool(ref.authors) and all(author_present(a, record.authors) for a in ref.authors)
    diffs.append({'field': 'authors', 'input': '; '.join(ref.authors), 'candidate': '; '.join(record.authors),
                  'state': ('equal' if authors_match else 'different') if ref.authors else 'not_supplied'})
    exact_identifier = bool((ref.doi and ref.doi == record.doi) or (ref.pmid and ref.pmid == record.pmid))
    if exact_identifier: score += 1
    if ref.year and ref.year == record.year: score += .15
    if authors_match: score += .15
    conflicts = [d['field'] for d in diffs if d['state'] == 'different']
    # Missing supplied identifiers count as unresolved evidence too.
    unresolved_id = any(d['state'] == 'missing_in_source' for d in diffs)
    strong = (exact_identifier or (title_score == 1 and authors_match and ref.year == record.year and bool(ref.year)))
    strong = bool(strong and not conflicts and not unresolved_id and not record.conflicts)
    reasons = []
    if exact_identifier: reasons.append('Exact identifier found in source metadata.')
    if conflicts: reasons.append('Input differs from source: ' + ', '.join(conflicts) + '.')
    if not ref.title: reasons.append('No independently extracted input title to compare.')
    if record.conflicts: reasons.append('Sources disagree; inspect the alternate values.')
    if not strong: reasons.append('Review the candidate before replacing the original reference.')
    return {'record': record.to_dict(), 'rank_score': round(score, 4), 'strong_match': strong,
            'differences': diffs, 'reasons': reasons}


class DemoProvider:
    name = 'Demo fixtures'
    def __init__(self):
        self.records = [Record(**r) for r in json.loads(Path(__file__).with_name('demo_records.json').read_text())]
    def search(self, ref):
        # Intentionally no network; deliberately show a wrong-year candidate.
        return [r for r in self.records if (ref.doi and ref.doi == r.doi) or similarity(ref.title or ref.raw, r.title) > .5]


class Verifier:
    def __init__(self, providers=None, *, demo=False, ai=False):
        self.demo, self.ai = demo, ai
        self.providers = providers if providers is not None else ([DemoProvider()] if demo else [Crossref(), OpenAlex(), PubMed()])
    def verify(self, lines):
        started = time.monotonic()
        results = []
        if not 1 <= len(lines) <= 30: raise ValueError('Provide 1–30 references, one per line or paragraph.')
        for index, raw in enumerate(lines):
            if not raw.strip() or len(raw) > 4000: raise ValueError('Each reference must contain 1–4000 characters.')
            ref = extract_with_llm(raw) if self.ai and not self.demo else parse_reference(raw)
            records, outcomes = [], []
            def retrieve(provider):
                try:
                    found = provider.search(ref)
                    return found, {'name': provider.name, 'state': 'ok', 'count': len(found)}
                except (ProviderError, ValueError, KeyError, TypeError, AttributeError, ET.ParseError):
                    return [], {'name': provider.name, 'state': 'unavailable', 'count': 0,
                                'message': 'Source unavailable or malformed response. Not evidence of absence.'}
            with ThreadPoolExecutor(max_workers=3) as pool:
                for found, outcome in pool.map(retrieve, self.providers):
                    records.extend(found); outcomes.append(outcome)
            candidates = sorted((compare(ref, r) for r in merge_records(records)), key=lambda c: c['rank_score'], reverse=True)[:5]
            for i, c in enumerate(candidates): c['id'] = str(i)
            source_errors = any(o['state'] != 'ok' for o in outcomes)
            ambiguous = len(candidates) > 1 and candidates[0]['rank_score'] - candidates[1]['rank_score'] < .08
            if not candidates:
                status = 'incomplete_search' if source_errors else 'not_found'
            elif candidates[0]['strong_match'] and not ambiguous and not source_errors:
                status = 'matched'
            else: status = 'needs_review'
            results.append({'index': index, 'input': asdict(ref), 'status': status,
                            'sources': outcomes, 'candidates': candidates,
                            'note': 'No candidate found is not proof of a fabricated reference.' if not candidates else
                            ('Similar candidates; choose the correct work.' if ambiguous else 'Source metadata matching does not validate the paper’s claims.')})
        return {'mode': 'demo' if self.demo else 'live', 'results': results,
                'elapsed_seconds': round(time.monotonic() - started, 3),
                'summary': {s: sum(r['status'] == s for r in results) for s in ('matched', 'needs_review', 'not_found', 'incomplete_search')}}
