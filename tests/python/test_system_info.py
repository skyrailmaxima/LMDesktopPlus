from __future__ import annotations

import subprocess
import time
import unittest
from unittest.mock import patch

from lmdesktopplus.system_info import SystemSampler


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class SystemSamplerTests(unittest.TestCase):
    def test_sample_shape(self):
        sampler = SystemSampler()
        sampler.sample()
        time.sleep(0.02)
        sample = sampler.sample()
        self.assertIn("cpu", sample)
        self.assertIn("memory", sample)
        self.assertGreaterEqual(sample["cpu"]["percent"], 0)
        self.assertLessEqual(sample["cpu"]["percent"], 100)
        self.assertGreaterEqual(sample["memory"]["total"], sample["memory"]["used"])

    @patch("lmdesktopplus.system_info.first_executable", return_value="/usr/bin/nvidia-smi")
    @patch("lmdesktopplus.preopt.run_capture")
    def test_nvidia_gpu_via_try_run(self, run_capture, _first):
        run_capture.return_value = completed(
            "GeForce, 12, 100, 8000, 55\n"
        )
        gpu = SystemSampler._nvidia_gpu()
        self.assertIsNotNone(gpu)
        assert gpu is not None
        self.assertEqual(gpu["source"], "nvidia-smi")
        self.assertEqual(gpu["percent"], 12.0)

    @patch("lmdesktopplus.system_info.first_executable", return_value="/usr/bin/nvidia-smi")
    @patch(
        "lmdesktopplus.preopt.run_capture",
        side_effect=subprocess.TimeoutExpired(["nvidia-smi"], 2),
    )
    def test_nvidia_timeout_returns_none(self, _run, _first):
        self.assertIsNone(SystemSampler._nvidia_gpu())


if __name__ == "__main__":
    unittest.main()
