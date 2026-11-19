import unittest

from server import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir = tempfile.TemporaryDirectory()
        self.store = Store(self.dir.name + '/test.db')

    def tearDown(self):
        self.dir.cleanup()

    def test_register_verify_login_logout(self):
        _, code = self.store.register('Anna', 'Anna@Example.com', 'StrongPass123')
        self.assertTrue(self.store.verify('anna@example.com', code))
        token, error = self.store.login('anna@example.com', 'StrongPass123')
        self.assertIsNone(error)
        self.assertTrue(token)
        self.assertTrue(self.store.account(token))
        self.store.logout(token)
        self.assertIsNone(self.store.account(token))

    def test_duplicate_email_and_wrong_password(self):
        self.store.register('Anna', 'anna@example.com', 'StrongPass123')
        with self.assertRaises(ValueError):
            self.store.register('Another', 'anna@example.com', 'StrongPass456')
        token, error = self.store.login('anna@example.com', 'wrong')
        self.assertIsNone(token)
        self.assertEqual(error, 'invalid')

    def test_password_reset(self):
        self.store.register('Anna', 'anna@example.com', 'StrongPass123')
        code = self.store.begin_reset('anna@example.com')
        self.assertTrue(code)
        self.assertTrue(self.store.reset_password('anna@example.com', code, 'NewStrongPass456'))


if __name__ == '__main__':
    unittest.main()
