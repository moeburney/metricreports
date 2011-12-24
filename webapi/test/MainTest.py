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

    def test_sendemail(self):
        emails = ['kanaderohan@gmail.com','mail@rohankanade.com']
        print Util.sendemail(emails,"test subject","body","acc info")
    def test_getOpenAlerts(self):
        print Util.getOpenAlerts("acc_example")
    def test_getAccounts(self):
        print Util.getAccounts()
    def test_getLatestSnapShot(self):
        print Util.getLatestSnapShot("example","127.0.0.1")
    def test_getservers(self):
        print Util.getServers("example")
if __name__ == '__main__':
    unittest.main()
