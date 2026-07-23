from __future__ import annotations

import time
import unittest

from lmdesktopplus.system_info import SystemSampler


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


if __name__ == "__main__":
    unittest.main()
