"""Read G2 and amendment TEXT/METADATA only, never outcome bindings."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
G2 = ROOT / 'Experiments/fair_v2_oct24/A7/preregistration_v2_frozen.json'
G2_SHA = '8377548a064de1fadd28baf674290be02021457ab38b49056ac9dde45dddf9f5'
AMENDMENTS = {
    'N2': ('nachtrag_2_nacht.md', 'Foundry route and no replay; H3 keeps two A6 fields with separate denominators.'),
    'N3': ('nachtrag_3_c1_budget.md', 'C1 order/budget changed; primary populations and tests unchanged.'),
    'N4': ('nachtrag_4_c2c3_kosten.md', 'Sol-Flex-NoWrite is a separate execution condition; original 98 ratings retained.'),
    'N5': ('nachtrag_5_joint_vertragsverletzung.md', 'Prospective whole-Joint rejection fallback for B4 V1; no rewrite of B3. Report rate/cost and AS not applicable.'),
    'N6': ('nachtrag_6_c6_passagenweg.md', 'Passage route not performed; 480 graph + 60 empty + 60 gold response positions. No claim against original passage reader.'),
    'N7': ('nachtrag_7_guard_ungueltige_antwort.md', 'Keep full original contexts unassessed after known invalid guard replies. Preserve paid replies and execute only originally unstarted jobs.'),
    'N8': ('nachtrag_8_gesamt_und_komponentenurteil.md', 'Fixed A-F judgment, separate K1-K6 Holm family, descriptive H4 components and efficiency. Primary G2 family unchanged. Individual prior C2 exposure disclosed.'),
    'N10': ('nachtrag_10_budgetbedingte_stichprobe_h1.md', 'Optional cost-stopped H1 prefix: pooled source ratios and paired two-stage source/original-group bootstrap. Approximate, not proven equal inclusion. C3 keeps G2 missingness.'),
    'N14': ('nachtrag_14_h2_fehlwerte.md', 'Keep G2 primary H2 unchanged and additionally test sources with valid judgments in both contrast arms. H2/K2/K4 noninferiority needs both Holm analyses; H2/K5 superiority needs the additional analysis. No rerating or replay.'),
}
N14_PATH = 'Experiments/fair_v2_oct24/G1/nachtrag_14_h2_fehlwerte.md'
N14_COMMIT = 'f641691e95c09729ab39cedfd40508499faff557'
N14_SHA = '464c39c5cd7400f850dccd5d1909fc9b8dcaf1b129cebb93930deaa8acbc5983'
N14_BYTES = 1921


def pin(path):
    path = Path(path).absolute()
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': sha256(raw).hexdigest()}


def load_n14_publication(publication_path=None, *, root=None):
    """Validate the published protocol only; never follow any outcome binding.

    The exact text and single-path publication are fixed before natural H2
    analysis. A changed, missing or merely drafted receipt cannot authorize it.
    Explicit paths exist for artificial-file tests, not input discovery.
    """
    root = ROOT if root is None else Path(root)
    publication_path = (Path(__file__).with_name('n14_publication.json')
                        if publication_path is None else Path(publication_path))
    publication = json.loads(publication_path.read_bytes())
    if not isinstance(publication, dict) or not (
            publication.get('protocol') == 'N14-single-path-preregistration-publication:v1'
            and publication.get('path') == N14_PATH
            and publication.get('publication_commit') == N14_COMMIT
            and publication.get('mode') == 'single_path_fast_forward_commit'
            and publication.get('changed_paths') == [N14_PATH]
            and publication.get('remote_bytes_identical') is True
            and publication.get('natural_H2_analysis_started_by_this_task') is False
            and publication.get('sha256') == N14_SHA
            and type(publication.get('bytes')) is int
            and publication['bytes'] == N14_BYTES):
        raise ValueError('N14 must be separately published before H2 analysis with its exact approved text')
    # Use the fixed path, never a caller-selected path from an untrusted receipt.
    raw = (root / N14_PATH).read_bytes()
    if len(raw) != N14_BYTES or sha256(raw).hexdigest() != N14_SHA:
        raise ValueError('Published N14 original bytes changed before H2 analysis')
    return publication


def load_contract():
    raw = G2.read_bytes()
    if sha256(raw).hexdigest() != G2_SHA:
        raise ValueError('Frozen G2 bytes changed')
    frozen = json.loads(raw)
    if not frozen['frozen'] or frozen['status'] != 'FROZEN':
        raise ValueError('Frozen G2 required')
    sources = []
    for row in frozen['bindings']['sealed4']['sources']:
        sources.append({'source_id': row['source_id'], 'cohort': 'SEALED4', 'family': 'sealed4',
            'format': 'not_specified_in_frozen_source_metadata', 'draws': ['draw_1', 'draw_2'],
            'reference_count': row['reference_count']})
    for row in frozen['bindings']['A4']['sources']:
        sources.append({'source_id': row['source_id'], 'cohort': 'NEW20', 'family': row['family'],
            'format': row.get('stratum', 'not_specified_in_frozen_source_metadata'),
            'draws': ['draw_1', 'draw_2', 'draw_3']})
    metadata = frozen['bindings']['A5']['question_and_cluster_metadata']['metadata_roster']
    questions = metadata['question_ids_in_order']
    blocks = metadata['paragraph_overlap_components']
    if (len(sources) != 24 or sum(len(s['draws']) for s in sources) != 68
            or len(questions) != 60 or len(blocks) != 39
            or sorted(q for b in blocks for q in b) != sorted(questions)):
        raise ValueError('G2 fixed population metadata mismatch')
    amendments = []
    for identifier, (filename, note) in AMENDMENTS.items():
        path = ROOT / 'Experiments/fair_v2_oct24/G1' / filename
        # Text is the prospective protocol, no referenced experiment is opened.
        text = path.read_text(encoding='utf8')
        if not text.strip():
            raise ValueError('Missing amendment text: ' + identifier)
        amendments.append({'identifier': identifier, 'note': note, 'pin': pin(path)})
    publication_path = Path(__file__).with_name('n8_publication.json')
    publication = json.loads(publication_path.read_text(encoding='utf8'))
    n8_text = (ROOT / publication['amendment_path']).read_text(encoding='utf8')
    if (publication.get('single_path_commit') is not True or publication.get('remote_confirmed') is not True
            or sha256(n8_text.encode('utf8')).hexdigest() != publication['canonical_lf_sha256']):
        raise ValueError('N8 must be separately published and match its fixed text before analysis')
    c4_path = ROOT / 'Experiments/fair_v2_oct24/C4/amendment.json'
    n10_path = Path(__file__).with_name('n10_publication.json')
    n10_publication = json.loads(n10_path.read_text(encoding='utf8'))
    n10_text = (ROOT / n10_publication['amendment_path']).read_text(encoding='utf8')
    if (n10_publication.get('single_path_commit') is not True
            or n10_publication.get('remote_confirmed_by_coordinator') is not True
            or sha256(n10_text.encode('utf8')).hexdigest() != n10_publication['canonical_lf_sha256']):
        raise ValueError('N10 must be separately published and match its approved text before analysis')
    n14_path = Path(__file__).with_name('n14_publication.json')
    n14_publication = load_n14_publication(n14_path)
    c4_amendment = json.loads(c4_path.read_text(encoding='utf8'))
    core_fraction = float(c4_amendment['current']['fraction'])
    if not 0 < core_fraction <= 1:
        raise ValueError('C4 sampling amendment needs a valid fixed fraction')
    return {'protocol': frozen['protocol_id'], 'frozen_pin': pin(G2),
        'cells': [c['id'] for c in frozen['method']['cells']], 'sources': sources,
        'question_ids': questions, 'qa_blocks': blocks, 'analysis': frozen['analysis'],
        'hypotheses': frozen['hypotheses'], 'missingness': frozen['missingness'],
        'human_validation': frozen['human_validation'], 'second_evaluator': frozen['second_evaluator'],
        'evaluators': frozen['evaluators']['shared'],
        'expected_versions': frozen['analysis_implementation_contract'], 'amendments': amendments,
        'primary_control': 'AS_ORIGINAL', 'primary_treatment': 'V2_ROW',
        'N8_publication': publication, 'N8_publication_pin': pin(publication_path),
        'N10_publication': n10_publication, 'N10_publication_pin': pin(n10_path),
        'N14_publication': n14_publication, 'N14_publication_pin': pin(n14_path),
        'second_evaluator_core_fraction': core_fraction,
        'second_evaluator_sampling_amendment_pin': pin(c4_path),
        'natural_outcomes_opened': False, 'referenced_binding_files_opened': False}
