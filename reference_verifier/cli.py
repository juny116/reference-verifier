import argparse
import json
from pathlib import Path
from .documents import read_input, export_document
from .verification import Verifier


def main():
    parser = argparse.ArgumentParser(description='Find source-backed candidates. No automatic corrections.')
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check')
    check.add_argument('input'); check.add_argument('--demo', action='store_true')
    check.add_argument('--ai', action='store_true', help='Send reference text to the configured model for extraction')
    check.add_argument('--output', default='report.json')
    export = sub.add_parser('export')
    export.add_argument('report'); export.add_argument('--selections', required=True)
    export.add_argument('--output', required=True)
    serve = sub.add_parser('serve'); serve.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if args.command == 'serve':
        import uvicorn
        uvicorn.run('reference_verifier.server:app', host='127.0.0.1', port=args.port)
    elif args.command == 'check':
        report = Verifier(demo=args.demo, ai=args.ai).verify(read_input(args.input))
        Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        print(json.dumps(report['summary'])); print(f'Report: {args.output}')
    else:
        report = json.loads(Path(args.report).read_text())
        choices = json.loads(Path(args.selections).read_text())
        target = Path(args.output)
        target.write_bytes(export_document(report, choices, target.suffix[1:]))
        print(f'Exported selected corrections: {target}')

if __name__ == '__main__': main()
