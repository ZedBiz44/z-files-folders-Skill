import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_completion import check_completion


def manifest():
    f = {'id': 'source', 'mimeType': 'image/png', 'md5Checksum': 'a' * 32, 'size': '12'}
    return {'root_ancestry': [{'id': 'drive', 'name': 'Shared-Drive'}, {'id': 'project', 'name': 'Project'}],
            'before': {'complete': True, 'items': [f]},
            'after': {'complete': True, 'items': [dict(f, path='Archive/source.png', active=False), dict(f, id='copy', path='project-picture.png', active=True)]},
            'plan': {'recorded_at': '2026-09-16T10:00:00Z', 'first_write_at': '2026-09-16T10:01:00Z', 'evidence_path': 'private/plan.json'},
            'file_evidence': [{'source_id': 'source', 'inspected': True, 'inspection_method': 'successful image viewer', 'inspection_evidence': 'private/view.json', 'purpose': 'website graphic', 'planned_path': 'project-picture.png', 'classification_reason': 'finished website graphic', 'active_id': 'copy', 'match_method': 'binary', 'match_evidence': 'private/hash.json'}]}


class CompletionTests(unittest.TestCase):
    def test_complete(self):
        self.assertTrue(check_completion(manifest())['passed'])

    def test_missing_file_inspection(self):
        d = manifest(); d['file_evidence'] = []
        self.assertIn('evidence_coverage', [x['type'] for x in check_completion(d)['issues']])

    def test_sibling_jpeg_is_not_psd_inspection(self):
        d = manifest(); f = dict(d['before']['items'][0], id='psd', mimeType='image/x-photoshop', md5Checksum='b'*32)
        d['before']['items'].append(f)
        d['after']['items'] += [dict(f, path='Archive/source.psd', active=False), dict(f, id='psd-copy', path='project-editable.psd', active=True)]
        row = copy.deepcopy(d['file_evidence'][0]); row.update(source_id='psd', active_id='psd-copy', inspection_source_id='source')
        d['file_evidence'].append(row)
        self.assertIn('unsupported_inspection_reuse', [x['type'] for x in check_completion(d)['issues']])

    def test_every_original_checked(self):
        d = manifest(); d['after']['items'][0]['md5Checksum'] = 'c'*32
        self.assertIn('original_integrity', [x['type'] for x in check_completion(d)['issues']])

    def test_late_plan(self):
        d = manifest(); d['plan']['recorded_at'] = '2026-09-16T10:02:00Z'
        self.assertIn('missing_prewrite_plan', [x['type'] for x in check_completion(d)['issues']])

    def test_includes_parent_prefix(self):
        d = manifest(); d['root_ancestry'][0]['name'] = 'D'*220
        r = check_completion(d)
        self.assertFalse(r['passed']); self.assertTrue(r['root_path'].startswith('D'*220))

    def test_pixel_equivalence_requires_evidence(self):
        d = manifest(); d['after']['items'][1]['md5Checksum'] = 'b'*32
        self.assertFalse(check_completion(d)['passed'])
        d['file_evidence'][0].update(match_method='decoded_pixels', match_evidence='private/pixel-proof.json')
        self.assertTrue(check_completion(d)['passed'])
        d['file_evidence'][0]['match_evidence'] = ''
        self.assertFalse(check_completion(d)['passed'])


if __name__ == '__main__':
    unittest.main()
