# Infolumi Reference Search

DOCX 문서의 참고문헌을 읽고 PubMed 서지 정보로 정리해 주는 Discord 봇입니다. 언어모델이 참고문헌을 구조화하고, PubMed에서 논문을 찾아 DOCX 또는 TXT 파일로 반환합니다.

## 처리 흐름

1. 봇을 멘션한 메시지에서 DOCX 첨부파일을 받습니다.
2. 문서의 문단을 참고문헌 목록으로 읽고 묶음별로 모델에 파싱을 요청합니다.
3. 저자·제목·연도·저널 정보로 PubMed를 검색합니다.
4. PMID로 메타데이터를 연결하고 원래 문헌 순서대로 서식을 적용합니다.
5. Discord 스레드에 진행 상황과 완성된 파일을 보냅니다.

모델이 일부 참고문헌을 파싱하지 못하거나 검색 결과가 없으면 해당 위치를 `Not Found`로 남깁니다. PubMed의 반환 순서가 바뀌어도 PMID를 기준으로 연결합니다.

## 구조

```text
infolumi/
├── bot.py                 # Discord 첨부파일·스레드 처리
├── pipeline.py            # 파싱→검색→서식 적용 흐름
├── documents.py           # DOCX 읽기와 DOCX/TXT 쓰기
├── model_parser.py        # 참고문헌 파싱 프롬프트 구성
├── chat_model.py          # 비동기 모델 호출
├── reference_parsing.py   # 묶음 분할과 모델 JSON 파싱
├── pubmed_client.py       # PubMed 검색·메타데이터 조회
├── article_metadata.py    # PMID별 논문 인덱스
├── citation_formatting.py # 저자·저널·권호·페이지 서식
└── extras/                # 대화 메모리·멘션·보조 봇 도구
```

`ReferencePipeline`은 Discord 객체 없이도 동작합니다. 파서와 PubMed 클라이언트를 주입할 수 있어 문서 처리와 외부 연결을 각각 검증할 수 있습니다. 문서 입출력과 동기 HTTP 요청은 별도 스레드에서 실행합니다.

## 설치와 실행

Python 3.10 이상에서 저장소 루트를 기준으로 실행합니다.

```bash
pip install -r requirements.txt
python -m infolumi --config-dir /absolute/path/to/conf --config-name config
```

Hydra 설정에서 다음 항목을 읽습니다.

| 항목 | 용도 |
|---|---|
| `discord.token` | Discord 봇 연결 |
| `model.type` | `chatgpt` 모델 loader 선택 |
| `model.model_name`, `model.temperature`, `model.max_tokens` | 모델 생성 옵션 |
| `template.system`, `template.parse` | 참고문헌 구조화 프롬프트 |
| `output_format` | `docx` 또는 `txt`, 기본값 `docx` |

`template.parse`는 `{references}`에 문헌 묶음을 받습니다. 파서 응답은 입력 순서의 JSON 배열이며 각 항목의 `authors`, `title`, `year`, `volume`, `journal`을 검색에 사용합니다. API 인증은 모델 클라이언트의 환경변수로 지정합니다.

## 테스트

```bash
python -m unittest discover -s tests -v
```

문서→파싱→조회→출력 흐름, 누락 문헌의 위치 유지, PubMed 응답 처리, DOCX/TXT 출력과 대화 메모리를 검사합니다.

[이전 파일과 새 모듈 대응표](docs/module-map.md)
