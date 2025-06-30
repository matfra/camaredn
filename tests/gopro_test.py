import unittest
from unittest import mock

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import gopro


class TestCaptureGoProPhoto(unittest.TestCase):
    @mock.patch("os.unlink")
    @mock.patch("tempfile.NamedTemporaryFile")
    @mock.patch("gopro.time.sleep")
    @mock.patch("gopro.socket.create_connection")
    @mock.patch("gopro.requests.get")
    @mock.patch("gopro.requests.post")
    def test_capture_photo(self, mock_post, mock_get, mock_create_conn, mock_sleep, mock_tempfile, mock_unlink):
        mock_sleep.return_value = None
        mock_conn = mock.MagicMock()
        mock_create_conn.return_value.__enter__.return_value = mock_conn
        mock_create_conn.return_value.__exit__.return_value = False
        list_resp = mock.Mock()
        list_resp.json.return_value = {
            "id": "1554375628411872255",
            "media": [
                {
                    "d": "100GOPRO",
                    "fs": [
                        {
                            "cre": 1696600109,
                            "glrv": 817767,
                            "ls": -1,
                            "mod": 1696600109,
                            "n": "GOPR0001.JPG",
                            "raw": 1,
                            "s": 2806303,
                        }
                    ],
                }
            ],
        }
        list_resp.raise_for_status.return_value = None
        photo_resp = mock.Mock()
        photo_resp.content = b"data"
        photo_resp.raise_for_status.return_value = None
        mock_get.side_effect = [list_resp, photo_resp]

        tmp_file = mock.Mock()
        tmp_file.name = "/tmp/ca.pem"
        mock_tempfile.return_value = tmp_file

        result = gopro.capture_gopro_photo(ip_address="1.2.3.4", timeout=1, root_ca="CERT")

        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(
            mock_post.call_args_list[0][0][0],
            "https://1.2.3.4/api/v1/camera/setting",
        )
        self.assertEqual(
            mock_post.call_args_list[0].kwargs["json"],
            {"setting_id": 175, "value": 1},
        )
        self.assertEqual(
            mock_post.call_args_list[1][0][0],
            "https://1.2.3.4/api/v1/camera/preset",
        )
        self.assertEqual(
            mock_post.call_args_list[1].kwargs["json"],
            {"preset_id": 65539},
        )
        self.assertEqual(
            mock_post.call_args_list[2][0][0],
            "https://1.2.3.4/api/v1/command/shutter",
        )
        for call in mock_post.call_args_list:
            self.assertEqual(call.kwargs.get("verify"), "/tmp/ca.pem")

        expected_list_url = "https://1.2.3.4/api/v1/media/list"
        expected_photo_url = "https://1.2.3.4/api/v1/media/100GOPRO/GOPR0001.JPG"
        self.assertEqual(mock_get.call_args_list[0][0][0], expected_list_url)
        self.assertEqual(mock_get.call_args_list[1][0][0], expected_photo_url)
        for call in mock_get.call_args_list:
            self.assertEqual(call.kwargs.get("verify"), "/tmp/ca.pem")
        self.assertEqual(result, b"data")


if __name__ == "__main__":
    unittest.main()
