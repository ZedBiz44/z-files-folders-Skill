"""Read-only completion gate. Checks evidence coverage, not the truth of claims."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from check_inventory import check


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
    args = parser.parse_args()
    try:
        result = check_completion(json.loads(args.manifest.read_text(encoding='utf-8-sig')))
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        print(json.dumps({'passed': False, 'input_error': str(error)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
