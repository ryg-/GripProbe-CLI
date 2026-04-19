import json
from pathlib import Path

from gripprobe.rebuild import rebuild_reports


def test_rebuild_reports_from_partial_case(tmp_path: Path) -> None:
    root = tmp_path
    (root / 'specs' / 'models').mkdir(parents=True)
    (root / 'specs' / 'models' / 'local_qwen2_5_7b.yaml').write_text(
        '\n'.join([
            'id: local_qwen2_5_7b',
            'label: local/qwen2.5:7b',
            'family: qwen',
            'size_class: small',
            'parameters_b: 7',
            'quantization: null',
            'backends:',
            '  - id: ollama',
            '    model_id: qwen2.5:7b',
            '    shell_model_id: local/qwen2.5:7b',
            '    model_hash: 845dbda0ea48',
            'supported_formats:',
            '  - markdown',
        ]) + '\n',
        encoding='utf-8',
    )
    run_dir = root / 'results' / 'runs' / 'run-x'
    case_dir = run_dir / 'cases' / 'gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd'
    workspace = case_dir / 'workspace'
    workspace.mkdir(parents=True)
    (case_dir / 'prompt.txt').write_text('prompt\n', encoding='utf-8')
    (case_dir / 'measured.stdout').write_text('DONE\n', encoding='utf-8')
    (case_dir / 'expected.txt').write_text(str(workspace) + '\n', encoding='utf-8')
    (case_dir / 'observed.txt').write_text(str(workspace) + '\n', encoding='utf-8')
    (workspace / 'pwd-output.txt').write_text(str(workspace) + '\n', encoding='utf-8')

    rebuilt_dir, results = rebuild_reports(run_dir)

    assert rebuilt_dir == run_dir.resolve()
    assert len(results) == 1
    assert results[0].status == 'PASS'
    assert (run_dir / 'reports' / 'summary.html').exists()
    assert (run_dir / 'reports' / 'cases' / 'gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd.html').exists()

    case_json = json.loads((case_dir / 'case.json').read_text(encoding='utf-8'))
    assert case_json['metadata']['rebuilt'] is True
    assert case_json['model']['model_hash'] == '845dbda0ea48'
