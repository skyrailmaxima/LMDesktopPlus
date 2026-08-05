from __future__ import annotations

import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from lmdesktopplus.system_info import (
    SystemSampler,
    parse_rocm_smi_csv,
    probe_amd_sysfs_card,
)


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


ROCM_CSV = """device,GPU use (%),VRAM Total Memory (B),VRAM Total Used Memory (B),Temperature (Sensor edge) (C),Card Series,Card Model
card0,18,21458059264,27856896,62.0,Radeon RX 7900 XT,0x744c
"""


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


class AmdGpuTests(unittest.TestCase):
    def test_parse_rocm_smi_csv(self):
        row = parse_rocm_smi_csv(ROCM_CSV)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["source"], "rocm-smi")
        self.assertEqual(row["name"], "Radeon RX 7900 XT")
        self.assertEqual(row["percent"], 18.0)
        self.assertEqual(row["temperature_c"], 62.0)
        self.assertAlmostEqual(row["memory_total_mb"], 21458059264 / (1024 * 1024), places=1)
        self.assertAlmostEqual(row["memory_used_mb"], 27856896 / (1024 * 1024), places=1)

    def test_probe_amd_sysfs_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            card = Path(tmp) / "card0"
            device = card / "device"
            hwmon = device / "hwmon" / "hwmon1"
            hwmon.mkdir(parents=True)
            (device / "gpu_busy_percent").write_text("33\n", encoding="utf-8")
            (device / "mem_info_vram_total").write_text(str(8 * 1024 * 1024 * 1024), encoding="utf-8")
            (device / "mem_info_vram_used").write_text(str(2 * 1024 * 1024 * 1024), encoding="utf-8")
            (device / "product_name").write_text("Radeon RX 6800\n", encoding="utf-8")
            (hwmon / "temp1_input").write_text("71000\n", encoding="utf-8")
            row = probe_amd_sysfs_card(card)
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(row["source"], "amdgpu-sysfs")
            self.assertEqual(row["name"], "Radeon RX 6800")
            self.assertEqual(row["percent"], 33.0)
            self.assertEqual(row["temperature_c"], 71.0)
            self.assertEqual(row["memory_total_mb"], 8192.0)
            self.assertEqual(row["memory_used_mb"], 2048.0)

    @patch("lmdesktopplus.system_info.first_executable")
    @patch("lmdesktopplus.preopt.run_capture")
    def test_gpu_prefers_rocm_when_nvidia_missing(self, run_capture, first_executable):
        def which(names):
            # first_executable is called with a list
            if names == ["nvidia-smi"]:
                return None
            if names == ["rocm-smi"]:
                return "/usr/bin/rocm-smi"
            return None

        first_executable.side_effect = which
        run_capture.return_value = completed(ROCM_CSV)
        gpu = SystemSampler._gpu()
        self.assertEqual(gpu["source"], "rocm-smi")
        self.assertEqual(gpu["name"], "Radeon RX 7900 XT")


if __name__ == "__main__":
    unittest.main()
