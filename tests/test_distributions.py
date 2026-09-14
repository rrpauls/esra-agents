import tempfile
import unittest
from pathlib import Path

from scripts.build_distributions import build
from scripts.validate_distributions import validate


class DistributionTests(unittest.TestCase):
    def test_archives_validate_and_are_reproducible(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            outputs_one = build(Path(first))
            outputs_two = build(Path(second))
            self.assertEqual([], validate(Path(first)))
            self.assertEqual([], validate(Path(second)))
            for one, two in zip(outputs_one, outputs_two, strict=True):
                self.assertEqual(one.read_bytes(), two.read_bytes())


if __name__ == "__main__":
    unittest.main()
