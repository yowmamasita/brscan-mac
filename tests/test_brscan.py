import importlib.machinery
import importlib.util
import os
import struct
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("brscan_under_test", str(ROOT / "brscan"))
spec = importlib.util.spec_from_loader(loader.name, loader)
brscan = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = brscan
loader.exec_module(brscan)


class FragmentSocket:
    def __init__(self, fragments):
        self.fragments = list(fragments)
        self.sent = []
        self.timeout = None
        self.closed = False

    def settimeout(self, timeout):
        self.timeout = timeout

    def recv(self, _size):
        if not self.fragments:
            return b""
        return self.fragments.pop(0)

    def sendall(self, data):
        self.sent.append(data)

    def close(self):
        self.closed = True


class BrscanTests(unittest.TestCase):
    def test_fragmented_greeting_and_buffered_response(self):
        sock = FragmentSocket([b"+O", b"K 200\r", b"\n\x00", b"\x01\x00"])
        with patch.object(brscan.socket, "create_connection", return_value=sock) as connect:
            scanner = brscan.Scanner("scanner.local", timeout=7)
            scanner.connect()
            self.assertEqual(scanner.take(3), b"\x00\x01\x00")
            scanner.close()

        connect.assert_called_once_with(("scanner.local", brscan.PORT), timeout=8)
        self.assertEqual(sock.timeout, 7)
        self.assertTrue(sock.closed)

    def test_environment_host_can_fall_back_to_ip(self):
        self.assertEqual(
            brscan.host_candidates(None, {"BRSCAN_HOST": "scanner.local", "BRSCAN_IP": "fallback-ip"}),
            ["scanner.local", "fallback-ip"],
        )
        self.assertEqual(
            brscan.host_candidates("cli.local", {"BRSCAN_HOST": "other.local", "BRSCAN_IP": "fallback-ip"}),
            ["cli.local"],
        )

    def test_explicit_host_never_tries_fallback(self):
        calls = []

        def fail_connect(address, timeout):
            calls.append(address[0])
            raise OSError("offline test")

        with patch.object(brscan.socket, "create_connection", side_effect=fail_connect):
            scanner = brscan.Scanner("cli.local")
            with self.assertRaises(brscan.ScanError):
                scanner.connect()
        self.assertEqual(calls, ["cli.local"])

    def test_failed_greeting_is_closed_without_environment_fallback(self):
        bad = FragmentSocket([b"not-a-greeting\n"])
        good = FragmentSocket([b"+OK 200\r\n"])
        with patch.object(brscan.socket, "create_connection", side_effect=[bad, good]) as connect:
            scanner = brscan.Scanner("scanner.local", fallback_hosts=("fallback-ip",))
            with self.assertRaisesRegex(brscan.ScanError, "unexpected scanner greeting"):
                scanner.connect()
        self.assertTrue(bad.closed)
        self.assertIsNone(scanner.sock)
        self.assertEqual(connect.call_count, 1)

    def test_tcp_connection_failure_uses_environment_fallback(self):
        good = FragmentSocket([b"+OK 200\r\n"])
        calls = []

        def create_connection(address, timeout):
            calls.append(address[0])
            if address[0] == "scanner.local":
                raise OSError("offline test")
            return good

        with patch.object(brscan.socket, "create_connection", side_effect=create_connection):
            scanner = brscan.Scanner("scanner.local", fallback_hosts=("fallback-ip",))
            scanner.connect()
            scanner.close()
        self.assertEqual(calls, ["scanner.local", "fallback-ip"])

    def test_timeout_setup_failure_closes_connected_socket(self):
        sock = FragmentSocket([b"+OK 200\r\n"])
        with patch.object(sock, "settimeout", side_effect=OSError("timeout setup")):
            with patch.object(brscan.socket, "create_connection", return_value=sock):
                scanner = brscan.Scanner("scanner.local", fallback_hosts=("fallback-ip",))
                with self.assertRaisesRegex(brscan.ScanError, "configure scanner connection"):
                    scanner.connect()
        self.assertTrue(sock.closed)
        self.assertIsNone(scanner.sock)

    def test_host_is_required_without_environment(self):
        with patch.dict(os.environ, {"BRSCAN_HOST": "", "BRSCAN_IP": ""}, clear=False):
            with patch.object(brscan.socket, "create_connection") as connect:
                self.assertEqual(brscan.main([]), 1)
                connect.assert_not_called()

    def test_invalid_arguments_do_not_open_network(self):
        with patch.object(brscan.socket, "create_connection") as connect:
            with self.assertRaises(SystemExit) as page_exit:
                brscan.main(["--host", "scanner.local", "--pages", "0"])
            self.assertEqual(page_exit.exception.code, 2)
            with self.assertRaises(SystemExit) as dpi_exit:
                brscan.main(["--host", "scanner.local", "--resolution", "301"])
            self.assertEqual(dpi_exit.exception.code, 2)
            with self.assertRaises(SystemExit) as brightness_exit:
                brscan.main(["--host", "scanner.local", "--brightness", "101"])
            self.assertEqual(brightness_exit.exception.code, 2)
            with self.assertRaises(SystemExit) as contrast_exit:
                brscan.main(["--host", "scanner.local", "--contrast", "-1"])
            self.assertEqual(contrast_exit.exception.code, 2)
            with self.assertRaises(SystemExit) as output_exit:
                brscan.main(["--host", "scanner.local", "result.bmp"])
            self.assertEqual(output_exit.exception.code, 2)
            connect.assert_not_called()

    def test_packbits_valid_and_malformed_runs(self):
        self.assertEqual(brscan.unpackbits(b"\x02abc\xfeZ\x80"), b"abcZZZ")
        with self.assertRaisesRegex(brscan.ScanError, "literal"):
            brscan.unpackbits(b"\x02ab")
        with self.assertRaisesRegex(brscan.ScanError, "repeat"):
            brscan.unpackbits(b"\xfe")

    def test_fragmented_scan_page_and_end_marker(self):
        header = b"\x00" * 9 + struct.pack("<H", 1)
        sock = FragmentSocket([b"\x40" + header[:3], header[3:] + b"A\x82\x03", b"\x00\x01\x00\x84"])
        scanner = brscan.Scanner("scanner.local")
        scanner.sock = sock
        chunks, ended = scanner.scan_page(300, "GRAY64", "RLENGTH", 1, 1, 50, 50, lambda *_: None)
        self.assertFalse(ended)
        self.assertEqual(chunks, [(brscan.RAW, b"A")])

    def test_malformed_scan_chunk_is_scan_error(self):
        # The declared payload is two bytes, but the synthetic peer closes after one.
        header = b"\x00" * 9 + struct.pack("<H", 2)
        scanner = brscan.Scanner("scanner.local")
        scanner.sock = FragmentSocket([b"\x40" + header + b"A"])
        with self.assertRaisesRegex(brscan.ScanError, "mid-scan"):
            scanner.scan_page(300, "GRAY64", "RLENGTH", 1, 1, 50, 50, lambda *_: None)

    def test_png_and_pdf_bytes(self):
        gray = brscan.Page("gray", bytes((0, 127, 200, 255)), 2, 2, 300)
        png = brscan.png_bytes(gray)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(struct.unpack(">II", png[16:24]), (2, 2))

        pdf = brscan.pdf_bytes([gray])
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"/Count 1", pdf)
        self.assertTrue(pdf.endswith(b"%%EOF\n"))

    def test_malformed_image_data_raises_scan_error(self):
        with self.assertRaisesRegex(brscan.ScanError, "JPEG"):
            brscan.jpeg_size(b"\xff\xd8")
        with self.assertRaisesRegex(brscan.ScanError, "image data"):
            brscan.Page("gray", b"\x00", 2, 2, 300)
        with self.assertRaisesRegex(brscan.ScanError, "no image"):
            brscan.build_page([], "gray", 1, 300)

    def test_synthetic_jpeg_size_and_color_page(self):
        jpeg = (b"\xff\xd8\xff\xc0" + struct.pack(">H", 17) + b"\x08" +
                struct.pack(">HH", 3, 4) + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00" +
                b"\xff\xd9")
        self.assertEqual(brscan.jpeg_size(jpeg), (4, 3))
        page = brscan.build_page([(brscan.JPEG, jpeg)], "color", 4, 300)
        self.assertEqual((page.kind, page.w, page.h, page.data), ("jpeg", 4, 3, jpeg))

    def test_conversion_errors_are_reported_and_temp_file_removed(self):
        gray = brscan.Page("gray", b"\x00", 1, 1, 300)
        with TemporaryDirectory() as directory:
            target = str(Path(directory) / "scan.tiff")
            missing_sips_paths = []

            def missing_sips(command, **_kwargs):
                missing_sips_paths.append(command[4])
                raise FileNotFoundError("sips")

            with patch.object(brscan.subprocess, "run", side_effect=missing_sips):
                with self.assertRaisesRegex(brscan.ScanError, "sips"):
                    brscan.save([gray], target)
            self.assertEqual(len(missing_sips_paths), 1)
            self.assertFalse(os.path.exists(missing_sips_paths[0]))

            result = subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"synthetic conversion failure")
            failed_sips_paths = []

            def failed_sips(command, **_kwargs):
                failed_sips_paths.append(command[4])
                return result

            with patch.object(brscan.subprocess, "run", side_effect=failed_sips):
                with self.assertRaisesRegex(brscan.ScanError, "synthetic conversion failure"):
                    brscan.save([gray], target)
            self.assertEqual(len(failed_sips_paths), 1)
            self.assertFalse(os.path.exists(failed_sips_paths[0]))


if __name__ == "__main__":
    unittest.main()
