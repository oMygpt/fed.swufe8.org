import unittest
from modules.auth import get_user_info


class TestAuth(unittest.TestCase):
    def test_admin_info(self):
        info = get_user_info("admin")
        self.assertEqual(info["role"], "admin")
        self.assertEqual(info["display"], "管理员")

    def test_user_mapping(self):
        info = get_user_info("economy")
        self.assertEqual(info["role"], "user")
        self.assertEqual(info["display"], "经济学院")
        self.assertEqual(info["college"], "economy")


if __name__ == "__main__":
    unittest.main()
