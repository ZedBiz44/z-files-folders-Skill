"""Check a complete, freshly fetched inventory; never read or change Drive."""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


def check(data, root_path, max_path=250):
    if not isinstance(data, dict) or data.get('complete') is not True:
        raise ValueError('A complete, untruncated inventory is required')
    if not root_path or not 1 <= max_path <= 250:
        raise ValueError('Supply the full root path and a limit from 1 to 250')
    items = data.get('items')
    if not isinstance(items, list):
        raise ValueError('items must be a list')
    ids, paths, groups, issues = set(), set(), defaultdict(list), []
    longest = 0
    active_files = 0
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Every item must be an object')
        fid, path, mime = (item.get(k) for k in ('id', 'path', 'mimeType'))
        if not all(isinstance(v, str) and v for v in (fid, path, mime)):
            raise ValueError('Every item requires id, relative path and mimeType')
        if type(item.get('active')) is not bool:
            raise ValueError('Every item requires an explicit active boolean')
        if fid in ids:
            raise ValueError('Duplicate inventory ID: ' + fid)
        ids.add(fid)
        path = path.replace('\\', '/')
        if path.startswith('/') or any(p in ('', '.', '..') for p in path.split('/')):
            raise ValueError('Paths must be unambiguous and relative to root_path')
        if path in paths:
            issues.append({'type': 'duplicate_path', 'id': fid, 'path': path})
        paths.add(path)
        length = len(root_path.rstrip('/\\') + '/' + path)
        longest = max(longest, length)
        if length > max_path:
            issues.append({'type': 'path_too_long', 'id': fid, 'path': path, 'length': length})
        if not item['active'] or mime == 'application/vnd.google-apps.folder':
            continue
        active_files += 1
        md5 = item.get('md5Checksum')
        if mime.startswith('application/vnd.google-apps.'):
            continue  # Native content and shortcut target access need separate review.
        if not isinstance(md5, str) or not re.fullmatch(r'[0-9a-fA-F]{32}', md5):
            issues.append({'type': 'missing_binary_checksum', 'id': fid, 'path': path})
            continue
        groups[md5.lower()].append({'id': fid, 'path': path})
    for group in groups.values():
        if len(group) > 1:
            issues.append({'type': 'active_exact_duplicates', 'items': group})
    return {'passed': not issues, 'items_checked': len(items), 'active_files': active_files,
            'maximum_path_length': longest, 'path_limit': max_path, 'issues': issues,
            'scope': 'Metadata check only; content classification, access, source retention and findability require independent review.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory', type=Path)
    parser.add_argument('--root-path', required=True)
    parser.add_argument('--max-path', type=int, default=250)
    args = parser.parse_args()
    try:
        data = json.loads(args.inventory.read_text(encoding='utf-8-sig'))
        report = check(data, args.root_path, args.max_path)
    except (OSError, ValueError) as error:
        print(json.dumps({'passed': False, 'input_error': str(error)}))
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
