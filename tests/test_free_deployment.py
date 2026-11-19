import tempfile, unittest
from server import SqliteStore

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=SqliteStore(self.tmp.name+'/test.db')
    def tearDown(self):self.tmp.cleanup()
    def test_register_verify_login_logout(self):
        _,code=self.store.register('Anna','Anna@Example.com','StrongPass123');self.assertTrue(self.store.verify('anna@example.com',code));token,error=self.store.login('anna@example.com','StrongPass123');self.assertIsNone(error);self.assertTrue(self.store.account(token));self.store.logout(token);self.assertIsNone(self.store.account(token))
    def test_duplicate_email(self):
        self.store.register('Anna','anna@example.com','StrongPass123')
        with self.assertRaises(ValueError):self.store.register('Another','anna@example.com','StrongPass456')
    def test_reset(self):
        self.store.register('Anna','anna@example.com','StrongPass123');code=self.store.begin_reset('anna@example.com');self.assertTrue(code);self.assertTrue(self.store.reset_password('anna@example.com',code,'NewStrongPass456'));token,error=self.store.login('anna@example.com','NewStrongPass456');self.assertIsNone(error);self.assertTrue(token)

if __name__=='__main__':unittest.main()
