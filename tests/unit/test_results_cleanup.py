from pathlib import Path

from gripprobe.results import remove_transient_files


def test_remove_transient_lock_files(tmp_path: Path) -> None:
    keep = tmp_path / 'keep.txt'
    lock_root = tmp_path / 'logs' / 'session-a'
    lock_root.mkdir(parents=True)
    lock_one = lock_root / '.lock'
    lock_two = tmp_path / '.lock'

    keep.write_text('keep\n', encoding='utf-8')
    lock_one.write_text('x\n', encoding='utf-8')
    lock_two.write_text('y\n', encoding='utf-8')

    remove_transient_files(tmp_path)

    assert keep.exists()
    assert not lock_one.exists()
    assert not lock_two.exists()
