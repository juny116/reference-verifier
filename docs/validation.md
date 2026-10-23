# Validation

Local validation, 2026-10-23:

- Python 3.12: 14 automated tests passed, including four parametrized conflict cases. A dependency emitted a TestClient/httpx deprecation warning.
- Offline CLI: one metadata match, one review-needed wrong-year reference, one not-found fictional title.
- Live smoke check: DOI `10.1038/nature14539` resolved through Crossref, OpenAlex, and PubMed. All three services responded successfully. Differences in the author spelling `Geoffrey Hinton` / `Geoffrey E. Hinton` remained visible and produced review-needed status.
- Browser demo: loaded all three examples and selected the wrong-year correction. DOCX export was round-trip tested; an additional CLI DOCX export succeeded.
- Optional AI extraction was tested with mocked output containing unsupported fields. No paid model call was made.

These are functional checks and a small live smoke test, not a retrieval-quality benchmark or evidence of zero hallucinations. The GitHub workflow runs offline tests and the demo on Python 3.10 and 3.12; its actual run status must be checked separately.
