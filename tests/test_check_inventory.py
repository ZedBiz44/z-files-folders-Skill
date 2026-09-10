import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('checker', Path(__file__).parents[1] / 'scripts/check_inventory.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def item(fid='a', path='project-file.png', active=True):
    return dict(id=fid, path=path, active=active, mimeType='image/png', md5Checksum='a'*32)


class InventoryTests(unittest.TestCase):
    def run_check(self, rows, **kwargs):
        return module.check({'complete': True, 'items': rows}, 'Drive/Project', **kwargs)

    def test_retained_archive_duplicate_is_allowed(self):
        self.assertTrue(self.run_check([item(), item('b', 'Archive/file.png', False)])['passed'])

    def test_identical_active_versions_fail(self):
        result = self.run_check([item(), item('b', 'project-file-02.png')])
        self.assertEqual(result['issues'][0]['type'], 'active_exact_duplicates')

    def test_archive_path_is_included(self):
        self.assertFalse(self.run_check([item(path='Archive/'+'x'*240, active=False)])['passed'])

    def test_missing_checksum_fails_for_binary(self):
        row = item(); row.pop('md5Checksum')
        self.assertFalse(self.run_check([row])['passed'])

    def test_native_document_needs_separate_content_review(self):
        row = item(); row['mimeType']='application/vnd.google-apps.document'; row.pop('md5Checksum')
        self.assertTrue(self.run_check([row])['passed'])

    def test_incomplete_or_unclassified_input_rejected(self):
        with self.assertRaises(ValueError): module.check({'complete':False,'items':[]}, 'Drive')
        row=item(); row.pop('active')
        with self.assertRaises(ValueError): self.run_check([row])

    def test_duplicate_ids_and_ambiguous_paths_rejected(self):
        with self.assertRaises(ValueError): self.run_check([item(),item()])
        with self.assertRaises(ValueError): self.run_check([item(path='../file.png')])


if __name__ == '__main__': unittest.main()
