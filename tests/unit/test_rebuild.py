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


def test_rebuild_reports_recomputes_existing_case_json_when_requested(tmp_path: Path) -> None:
    root = tmp_path
    (root / 'specs' / 'models').mkdir(parents=True)
    (root / 'specs' / 'tests').mkdir(parents=True)
    (root / 'specs' / 'models' / 'local_qwen3_8b.yaml').write_text(
        '\n'.join([
            'id: local_qwen3_8b',
            'label: local/qwen3:8b',
            'family: qwen',
            'size_class: small',
            'quantization: null',
            'backends:',
            '  - id: ollama',
            '    model_id: qwen3:8b',
            '    shell_model_id: local/qwen3:8b',
            '    model_hash: 500a1f067a9f',
            'supported_formats:',
            '  - tool',
        ]) + '\n',
        encoding='utf-8',
    )
    (root / 'specs' / 'tests' / 'shell_date.yaml').write_text(
        '\n'.join([
            'id: shell_date',
            'title: Shell Date',
            'category: shell',
            'prompt: test',
            'validators:',
            '  - type: file_equals',
            '    target: date-output.txt',
            '    expected_from: today',
        ]) + '\n',
        encoding='utf-8',
    )
    run_dir = root / 'results' / 'runs' / 'run-y'
    case_dir = run_dir / 'cases' / 'gptme__local_qwen3_8b__ollama__tool__shell_date'
    workspace = case_dir / 'workspace'
    workspace.mkdir(parents=True)
    (case_dir / 'prompt.txt').write_text('prompt\n', encoding='utf-8')
    (case_dir / 'warmup.stdout').write_text('[gripprobe] process_finished_at=2026-04-20T17:26:39+02:00 exit_code=124 timeout=true\nSystem:\nRan command: `date +%F > date-output.txt`\n', encoding='utf-8')
    (case_dir / 'warmup.stderr').write_text('', encoding='utf-8')
    (case_dir / 'measured.stdout').write_text('[gripprobe] process_finished_at=2026-04-20T17:28:39+02:00 exit_code=124 timeout=true\nSystem:\nRan command: `date +%F > date-output.txt`\n', encoding='utf-8')
    (case_dir / 'measured.stderr').write_text('', encoding='utf-8')
    (workspace / 'date-output.txt').write_text('2026-04-20\n', encoding='utf-8')
    (case_dir / 'case.json').write_text(
        json.dumps(
            {
                'case_id': 'gptme__local_qwen3_8b__ollama__tool__shell_date',
                'run_id': 'run-y',
                'shell': 'gptme',
                'model': {
                    'id': 'local_qwen3_8b',
                    'label': 'local/qwen3:8b',
                    'family': 'qwen',
                    'size_class': 'small',
                    'quantization': None,
                    'backend': 'ollama',
                    'model_id': 'qwen3:8b',
                    'shell_model_id': 'local/qwen3:8b',
                    'model_hash': '500a1f067a9f',
                },
                'format': 'tool',
                'test': 'shell_date',
                'title': 'Shell Date',
                'status': 'TIMEOUT',
                'trajectory': 'clean',
                'invoked': 'yes',
                'match_percent': 0,
                'timings': {'warmup_seconds': 120.0, 'measured_seconds': 120.0},
                'logs': {
                    'prompt': 'prompt.txt',
                    'warmup_stdout': 'warmup.stdout',
                    'warmup_stderr': 'warmup.stderr',
                    'measured_stdout': 'measured.stdout',
                    'measured_stderr': 'measured.stderr',
                },
                'metadata': {
                    'measured_exit_code': 124,
                    'warmup_exit_code': 124,
                    'shell_version': 'gptme v0.31.0+unknown',
                },
            },
            indent=2,
            ensure_ascii=False,
        ) + '\n',
        encoding='utf-8',
    )

    rebuilt_dir, results = rebuild_reports(run_dir, recompute_case_json=True)

    assert rebuilt_dir == run_dir.resolve()
    assert len(results) == 1
    assert results[0].status == 'TIMEOUT'
    assert results[0].match_percent == 100
    assert results[0].run_id == 'run-y'
    assert results[0].metadata['artifact_reached_before_timeout'] is True
    assert results[0].metadata['source'] == 'recomputed'
    assert results[0].metadata['shell_version'] == 'gptme v0.31.0+unknown'

    case_json = json.loads((case_dir / 'case.json').read_text(encoding='utf-8'))
    assert case_json['run_id'] == 'run-y'
    assert case_json['match_percent'] == 100
    assert case_json['metadata']['artifact_reached_before_timeout'] is True
    assert case_json['metadata']['source'] == 'recomputed'


def test_rebuild_reports_recomputes_case_json_without_model_hash_in_spec(tmp_path: Path) -> None:
    root = tmp_path
    (root / 'specs' / 'models').mkdir(parents=True)
    (root / 'specs' / 'tests').mkdir(parents=True)
    (root / 'specs' / 'models' / 'local_qwen2_5_7b.yaml').write_text(
        '\n'.join([
            'id: local_qwen2_5_7b',
            'label: local/qwen2.5:7b',
            'family: qwen',
            'size_class: small',
            'quantization: null',
            'backends:',
            '  - id: ollama',
            '    model_id: qwen2.5:7b',
            '    shell_model_id: local/qwen2.5:7b',
            'supported_formats:',
            '  - markdown',
        ]) + '\n',
        encoding='utf-8',
    )
    (root / 'specs' / 'tests' / 'python_file_simple.yaml').write_text(
        '\n'.join([
            'id: python_file_simple',
            'title: Python File Simple',
            'category: python',
            'prompt: test',
            'validators:',
            '  - type: file_equals',
            '    target: python-output.txt',
            '    expected: "PYTHON_OK\\n"',
        ]) + '\n',
        encoding='utf-8',
    )
    run_dir = root / 'results' / 'runs' / 'run-z'
    case_dir = run_dir / 'cases' / 'continue-cli__local_qwen2_5_7b__ollama__markdown__python_file_simple'
    workspace = case_dir / 'workspace'
    workspace.mkdir(parents=True)
    (case_dir / 'prompt.txt').write_text('prompt\n', encoding='utf-8')
    (case_dir / 'warmup.stdout').write_text('DONE\n', encoding='utf-8')
    (case_dir / 'warmup.stderr').write_text('', encoding='utf-8')
    (case_dir / 'measured.stdout').write_text('DONE\n', encoding='utf-8')
    (case_dir / 'measured.stderr').write_text('', encoding='utf-8')
    (case_dir / 'expected.txt').write_text('PYTHON_OK\n', encoding='utf-8')
    (case_dir / 'observed.txt').write_text('PYTHON_OK\n', encoding='utf-8')
    (workspace / 'python-output.txt').write_text('PYTHON_OK\n', encoding='utf-8')
    (case_dir / 'case.json').write_text(
        json.dumps(
            {
                'case_id': 'continue-cli__local_qwen2_5_7b__ollama__markdown__python_file_simple',
                'run_id': 'run-z',
                'shell': 'continue-cli',
                'model': {
                    'id': 'local_qwen2_5_7b',
                    'label': 'local/qwen2.5:7b',
                    'family': 'qwen',
                    'size_class': 'small',
                    'quantization': None,
                    'backend': 'ollama',
                    'model_id': 'qwen2.5:7b',
                    'shell_model_id': 'local/qwen2.5:7b',
                    'model_hash': 'unknown',
                },
                'format': 'markdown',
                'test': 'python_file_simple',
                'title': 'Python File Simple',
                'status': 'PASS',
                'trajectory': 'clean',
                'invoked': 'yes',
                'match_percent': 100,
                'timings': {'warmup_seconds': 1.0, 'measured_seconds': 1.0},
                'logs': {
                    'prompt': 'prompt.txt',
                    'warmup_stdout': 'warmup.stdout',
                    'warmup_stderr': 'warmup.stderr',
                    'measured_stdout': 'measured.stdout',
                    'measured_stderr': 'measured.stderr',
                },
                'metadata': {
                    'model_hash': 'unknown',
                    'shell_version': '1.5.45',
                },
            },
            indent=2,
            ensure_ascii=False,
        ) + '\n',
        encoding='utf-8',
    )

    rebuilt_dir, results = rebuild_reports(run_dir, recompute_case_json=True)

    assert rebuilt_dir == run_dir.resolve()
    assert len(results) == 1
    assert results[0].status == 'PASS'
    assert results[0].model.model_hash == 'unknown'

    case_json = json.loads((case_dir / 'case.json').read_text(encoding='utf-8'))
    assert case_json['model']['model_hash'] == 'unknown'
    assert case_json['metadata']['source'] == 'recomputed'
