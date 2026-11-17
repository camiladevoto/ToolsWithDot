import unittest
import collect_jobs as m
class JobCollectorTest(unittest.TestCase):
    def test_location(self):
        self.assertEqual(m.norm_location('Remote - Spain'),'remote_spain_explicit')
        self.assertEqual(m.norm_location('Remote - United States'),'remote_scope_unverified')
    def test_no_seniority_claim(self):
        self.assertEqual(m.classify('Senior Platform Engineer'),[])
    def test_email(self):
        self.assertEqual(m.application_emails('Apply: careers@acme.co'),['careers@acme.co'])
    def test_no_invalid_slug(self):
        with self.assertRaises(ValueError): m.validate_slug('bad/../../path')
if __name__=='__main__': unittest.main()
