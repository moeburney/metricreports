import Util

__author__ = 'rohan'

import unittest

class MyTestCase(unittest.TestCase):
    def test_something(self):
        self.assertEqual(True, False)

    def test_createUser(self):
        user = Util.createUser("example","customerservice103@gmail.com","gotohome")
        print user
        self.assertIsNotNone(user,"User is created")
if __name__ == '__main__':
    unittest.main()
