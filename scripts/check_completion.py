"""Read-only completion gate. Checks evidence coverage, not the truth of claims."""
import argparse
from datetime import datetime
import json
import re
from pathlib import Path
from check_inventory import check


def inspection_unavailable(row):
    """Reject explicit admissions of missing content inspection, not just short labels."""
    method = row.get('inspection_method', '').lower().strip()
    return method in ('binary', 'checksum', 'download', 'metadata') or bool(re.search(
        r'\b(?:assumed|assuming|unavailable|failed|path restriction|file not found|'
        r'not (?:opened|viewed|read|inspected|rendered|rasterized)|sibling)\b', method))


def check_file_plan(plan, before):
    """Check the saved file decisions before any remote mutation."""
    originals = {x['id'] for x in before['items']
                 if x['mimeType'] != 'application/vnd.google-apps.folder'}
    rows = plan.get('file_plan', [])
    ids = [x.get('source_id') for x in rows]
    issues = []
    if set(ids) != originals or len(ids) != len(set(ids)):
        issues.append({'type': 'prewrite_file_coverage', 'missing': sorted(originals-set(ids))})
    required = ['planned_path', 'purpose', 'classification_reason',
                'inspection_method', 'inspection_evidence']
    for row in rows:
        if any(not isinstance(row.get(k), str) or not row[k].strip() for k in required):
            issues.append({'type': 'incomplete_prewrite_decision', 'id': row.get('source_id')})
        if inspection_unavailable(row):
            issues.append({'type': 'content_not_inspected', 'id': row.get('source_id')})
    return issues


def check_completion(data):
    issues = []
    ancestry = data.get('root_ancestry', [])
    if len(ancestry) < 2 or any(not x.get('id') or not x.get('name') for x in ancestry):
        raise ValueError('root_ancestry must contain verified Drive-to-project IDs and names')
    root_path = '/'.join(x['name'] for x in ancestry)
    inventory = data['after']
    report = check(inventory, root_path, 230)
    issues.extend(report['issues'])
    before = data['before']
    if before.get('complete') is not True:
        raise ValueError('Complete before inventory required')
    originals = {x['id']: x for x in before['items']}
    if len(originals) != len(before['items']):
        raise ValueError('Duplicate original IDs')
    final = {x['id']: x for x in inventory['items']}
    rows = data.get('file_evidence', [])
    evidence = {x['source_id']: x for x in rows}
    if len(evidence) != len(rows):
        raise ValueError('Duplicate evidence source IDs')
    source_files = {k: v for k, v in originals.items()
                    if v['mimeType'] != 'application/vnd.google-apps.folder'}
    if set(evidence) != set(source_files):
        issues.append({'type': 'evidence_coverage',
                       'missing': sorted(set(source_files) - set(evidence)),
                       'unexpected': sorted(set(evidence) - set(source_files))})
    plan = data.get('plan', {})
    issues.extend(check_file_plan(plan, before))
    try:
        planned = datetime.fromisoformat(plan['recorded_at'].replace('Z', '+00:00'))
        written = datetime.fromisoformat(plan['first_write_at'].replace('Z', '+00:00'))
        plan_ok = planned.tzinfo and written.tzinfo and planned <= written and plan.get('evidence_path')
    except (KeyError, ValueError, TypeError):
        plan_ok = False
    if not plan_ok:
        issues.append({'type': 'missing_prewrite_plan', 'detail': 'Supply actual plan and first-write receipt times; never backdate'})
    for fid, source in originals.items():
        current = final.get(fid)
        if current is None:
            issues.append({'type': 'missing_original', 'id': fid})
            continue
        if fid not in source_files:
            continue
        native = source['mimeType'].startswith('application/vnd.google-apps.')
        if not native and (not source.get('md5Checksum') or source.get('size') is None
                           or source.get('md5Checksum') != current.get('md5Checksum')
                           or str(source.get('size')) != str(current.get('size'))):
            issues.append({'type': 'original_integrity', 'id': fid})
        row = evidence.get(fid, {})
        required = ['inspection_method', 'inspection_evidence', 'purpose', 'planned_path',
                    'classification_reason', 'active_id', 'match_method', 'match_evidence']
        if row.get('inspected') is not True or any(not isinstance(row.get(k), str) or not row[k].strip() for k in required):
            issues.append({'type': 'incomplete_file_evidence', 'id': fid})
        if inspection_unavailable(row):
            issues.append({'type': 'content_not_inspected', 'id': fid})
        inspected_id = row.get('inspection_source_id', fid)
        inspected_source = source_files.get(inspected_id, {})
        if inspected_id != fid and (native or not source.get('md5Checksum')
                                   or source['md5Checksum'] != inspected_source.get('md5Checksum')
                                   or str(source.get('size')) != str(inspected_source.get('size'))):
            issues.append({'type': 'unsupported_inspection_reuse', 'id': fid})
        active = final.get(row.get('active_id'), {})
        if active.get('active') is not True or active.get('mimeType') == 'application/vnd.google-apps.folder':
            issues.append({'type': 'missing_active_home', 'id': fid})
        method = row.get('match_method')
        if method == 'binary':
            if native or source.get('md5Checksum') != active.get('md5Checksum') or str(source.get('size')) != str(active.get('size')):
                issues.append({'type': 'active_content_mismatch', 'id': fid})
        elif method == 'decoded_pixels':
            if not source['mimeType'].startswith('image/') or not active.get('mimeType', '').startswith('image/'):
                issues.append({'type': 'invalid_pixel_comparison', 'id': fid})
        elif method == 'native_content':
            if not native:
                issues.append({'type': 'invalid_native_comparison', 'id': fid})
        else:
            issues.append({'type': 'missing_content_comparison', 'id': fid})
        if native and not row.get('original_content_evidence'):
            issues.append({'type': 'missing_native_retention_evidence', 'id': fid})
    return {'passed': not issues, 'root_path': root_path,
            'original_items': len(originals), 'original_files': len(source_files),
            'active_files': report['active_files'], 'maximum_path_length': report['maximum_path_length'],
            'issues': issues, 'scope': 'Coverage and metadata only. Reviewer must verify actual inspection, evidence, classification, permissions and receipt times.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--plan-only', action='store_true', help='Validate the saved per-file plan before any Drive writes')
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
        plan = data['plan']
        saved_path = Path(plan['evidence_path'])
        if not saved_path.is_absolute():
            saved_path = args.manifest.parent / saved_path
        saved = json.loads(saved_path.read_text(encoding='utf-8-sig'))
        if saved.get('recorded_at') != plan.get('recorded_at'):
            raise ValueError('Manifest plan timestamp differs from the saved plan')
        data['plan']['file_plan'] = saved.get('file_plan', [])
        if args.plan_only:
            if data['before'].get('complete') is not True:
                raise ValueError('Complete before inventory required')
            stamp = datetime.fromisoformat(plan['recorded_at'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('Plan timestamp must include timezone')
            issues = check_file_plan(data['plan'], data['before'])
            result = {'passed': not issues, 'issues': issues, 'scope': 'Saved per-file plan coverage; actual inspection still requires review'}
        else:
            result = check_completion(data)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        print(json.dumps({'passed': False, 'input_error': str(error)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
