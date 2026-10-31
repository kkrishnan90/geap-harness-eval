import io
import unittest

from clinlog.cli import main
from clinlog.config import Config, load_config
from clinlog.metrics import Metrics
from clinlog.pipeline import TRUNCATION_MARK, Pipeline


class PipelineTest(unittest.TestCase):
    def test_counts_and_newlines(self):
        m = Metrics()
        p = Pipeline(metrics=m)
        out = list(p.process(["plain\n", "ssn 000-12-3456\r\n", "a=1 b=2\n"]))
        self.assertEqual(out, ["plain", "ssn [PHI:SSN]", "a=1 b=2"])
        self.assertEqual(m.total("lines_in"), 3)
        self.assertEqual(m.get("lines_in", format="kv"), 1)
        self.assertEqual(m.get("lines_redacted", format="text"), 1)
        self.assertEqual(m.total("lines_out"), 3)

    def test_truncation(self):
        p = Pipeline(Config(max_line_bytes=300))
        out = next(p.process(["x" * 1000]))
        self.assertTrue(out.endswith(TRUNCATION_MARK))
        self.assertEqual(len(out.encode()), 300)


class ConfigTest(unittest.TestCase):
    def test_load(self):
        c = load_config(text="[clinlog]\nservice_name = adt\nmax_line_bytes = 1024\naudit_salt = s3\n")
        self.assertEqual(c, Config("adt", 1024, b"s3"))

    def test_defaults_and_validation(self):
        self.assertEqual(load_config(text=""), Config())
        with self.assertRaises(ValueError):
            load_config(text="[clinlog]\nmax_line_bytes = 10\n")


class MetricsTest(unittest.TestCase):
    def test_render(self):
        m = Metrics()
        m.inc("lines_in", format="json")
        m.inc("lines_in", 2, format="json")
        m.inc("lines_out")
        self.assertEqual(m.render(), 'clinlog_lines_in_total{format="json"} 3\nclinlog_lines_out_total 1\n')


class CliTest(unittest.TestCase):
    def test_sanitize(self):
        out = io.StringIO()
        rc = main(["sanitize"], stdin=io.StringIO("hello\nssn 000-12-3456\n"), stdout=out)
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue(), "hello\nssn [PHI:SSN]\n")

    def test_stats(self):
        out = io.StringIO()
        main(["stats"], stdin=io.StringIO("a=1 b=2\nplain\n"), stdout=out)
        self.assertIn('clinlog_lines_in_total{format="kv"} 1', out.getvalue())


if __name__ == "__main__":
    unittest.main()
