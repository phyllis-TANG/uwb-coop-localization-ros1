"""Ensure media-QC failures remain failures, plus a tiny real decode smoke test."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_videos


class VideoAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'sample.mov'
        self.path.write_bytes(b'mock video')

    def tearDown(self):
        self.temp.cleanup()

    def metadata(self):
        return subprocess.CompletedProcess([], 0, json.dumps({'streams': [{'codec_name': 'h264', 'width': 64, 'height': 64}]}), '')

    def test_probe_failure_not_accepted(self):
        failure = subprocess.CompletedProcess([], 1, '', 'corrupt input')
        with mock.patch.object(audit_videos.subprocess, 'run', return_value=failure):
            result = audit_videos.check_video(self.path, True)
        self.assertEqual(result['status'], 'failed')

    def test_missing_stream_not_accepted(self):
        with mock.patch.object(audit_videos.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{}', '')):
            result = audit_videos.check_video(self.path)
        self.assertEqual(result['status'], 'failed')

    def test_metadata_alone_is_not_full_decode_or_reference_acceptance(self):
        with mock.patch.object(audit_videos.subprocess, 'run', return_value=self.metadata()) as runner:
            result = audit_videos.check_video(self.path)
        self.assertEqual(result['status'], 'metadata_passed_decode_pending')
        self.assertEqual(result['decode_status'], 'pending')
        self.assertEqual(runner.call_count, 1)
        command = runner.call_args[0][0]
        self.assertNotIn('-show_format', command)
        self.assertNotIn('-show_streams', command)

    def test_decode_error_even_exit_zero_not_accepted(self):
        for code in (0, 1):
            decoded = subprocess.CompletedProcess([], code, '', 'decoding error')
            with mock.patch.object(audit_videos.subprocess, 'run', side_effect=[self.metadata(), decoded]):
                result = audit_videos.check_video(self.path, True)
            self.assertEqual(result['status'], 'failed')

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg/ffprobe not installed')
    def test_small_real_video_full_decode(self):
        made = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=white:s=64x64:r=5',
                               '-t', '0.4', '-c:v', 'mpeg4', '-y', str(self.path)], capture_output=True, text=True)
        self.assertEqual(made.returncode, 0, made.stderr)
        result = audit_videos.check_video(self.path, True)
        self.assertEqual(result['status'], 'file_health_passed', result)
        self.assertEqual(result['decode_returncode'], 0)


if __name__ == '__main__':
    unittest.main()
