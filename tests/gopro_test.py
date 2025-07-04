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
    @mock.patch("gopro.requests.get")
    @mock.patch("gopro.requests.post")
    def test_capture_photo(self, mock_post, mock_get, mock_sleep, mock_tempfile, mock_unlink):
        mock_sleep.return_value = None
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

        mock_post.assert_called_once()
        called_url = mock_post.call_args[0][0]
        self.assertEqual(called_url, "https://1.2.3.4/api/v1/command/shutter")
        self.assertEqual(mock_post.call_args.kwargs["verify"], "/tmp/ca.pem")

        expected_list_url = "https://1.2.3.4/api/v1/media/list"
        expected_photo_url = "https://1.2.3.4/api/v1/media/100GOPRO/GOPR0001.JPG"
        self.assertEqual(mock_get.call_args_list[0][0][0], expected_list_url)
        self.assertEqual(mock_get.call_args_list[1][0][0], expected_photo_url)
        for call in mock_get.call_args_list:
            self.assertEqual(call.kwargs.get("verify"), "/tmp/ca.pem")
        self.assertEqual(result, b"data")


if __name__ == "__main__":
    unittest.main()
