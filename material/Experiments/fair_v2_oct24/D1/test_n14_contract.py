"""N14 publication/receipt checks using protocol metadata and artificial files only."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from . import contract, run


def store(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf8')


@pytest.fixture
def published_files(tmp_path):
    # The prospective amendment is protocol text, not C3 labels or source data.
    original = contract.ROOT / contract.N14_PATH
    target = tmp_path / contract.N14_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes(original.read_bytes())
    receipt = json.loads(Path(contract.__file__).with_name('n14_publication.json').read_bytes())
    receipt_path = tmp_path / 'artificial-publication.json'
    store(receipt_path, receipt)
    return tmp_path, target, receipt_path, receipt


def test_N14_exact_single_path_publication_and_text_are_accepted(published_files):
    root, _, receipt_path, receipt = published_files
    assert contract.load_n14_publication(receipt_path, root=root) == receipt


@pytest.mark.parametrize(('field', 'value'), [
    ('protocol', 'draft'),
    ('path', '../../private/outcomes.json'),
    ('publication_commit', '0' * 40),
    ('mode', 'local_only'),
    ('changed_paths', []),
    ('changed_paths', [contract.N14_PATH, 'README.md']),
    ('remote_bytes_identical', False),
    ('remote_bytes_identical', 1),
    ('natural_H2_analysis_started_by_this_task', True),
    ('natural_H2_analysis_started_by_this_task', None),
    ('sha256', '0' * 64),
    ('bytes', contract.N14_BYTES + 1),
    ('bytes', str(contract.N14_BYTES)),
])
def test_N14_invalid_or_foreign_receipt_is_rejected(published_files, field, value):
    root, _, receipt_path, receipt = published_files
    altered = deepcopy(receipt)
    altered[field] = value
    store(receipt_path, altered)
    with pytest.raises(ValueError, match='N14 must be separately published'):
        contract.load_n14_publication(receipt_path, root=root)


def test_N14_missing_receipt_fails_closed_without_discovery(tmp_path):
    with pytest.raises(FileNotFoundError):
        contract.load_n14_publication(tmp_path / 'missing-receipt.json', root=tmp_path)


def test_N14_missing_fixed_text_fails_closed(published_files):
    root, target, receipt_path, _ = published_files
    target.unlink()
    with pytest.raises(FileNotFoundError):
        contract.load_n14_publication(receipt_path, root=root)


def test_N14_byte_change_is_rejected_even_if_receipt_is_unchanged(published_files):
    root, target, receipt_path, _ = published_files
    target.write_bytes(target.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='N14 original bytes changed'):
        contract.load_n14_publication(receipt_path, root=root)


def test_N14_non_mapping_receipt_is_rejected(published_files):
    root, _, receipt_path, _ = published_files
    store(receipt_path, [])
    with pytest.raises(ValueError, match='N14 must be separately published'):
        contract.load_n14_publication(receipt_path, root=root)


def test_load_contract_binds_N14_without_opening_outcomes():
    value = contract.load_contract()
    assert value['N14_publication']['publication_commit'] == contract.N14_COMMIT
    assert value['N14_publication']['sha256'] == contract.N14_SHA
    assert value['N14_publication_pin'] == contract.pin(Path(contract.__file__).with_name('n14_publication.json'))
    assert [r['identifier'] for r in value['amendments']].count('N14') == 1
    assert value['natural_outcomes_opened'] is False
    assert value['referenced_binding_files_opened'] is False


def test_load_contract_requires_N14_before_any_analysis(monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError('N14 deliberately missing in synthetic negative test')
    monkeypatch.setattr(contract, 'load_n14_publication', fail)
    with pytest.raises(ValueError, match='N14 deliberately missing'):
        contract.load_contract()


def test_implementation_receipt_pins_N14_and_its_decision_rule():
    value = contract.load_contract()
    versions = {'python': '3.13.12', 'numpy': '2.4.4',
                'scipy': '1.17.1', 'matplotlib': 'synthetic-test'}
    receipt = run.implementation_receipt(value, {'origin': 'synthetic'}, versions)
    assert receipt['N14_publication'] == value['N14_publication_pin']
    rule = receipt['interpretations_fixed_before_natural_inputs']['N14_H2_missingness']
    assert 'G2 primary estimates and Holm family remain unchanged' in rule
    assert 'both respective contrast arms' in rule
    assert 'H2/K2/K4 noninferiority requires Holm confirmation in both analyses' in rule
    assert 'H2/K5 superiority only if confirmed in the additional analysis' in rule
    assert receipt['receipt_written_before_analysis'] is True
