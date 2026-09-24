import copy
import json
from pathlib import Path
import unittest

from validate_story_contract import validate


class StoryContractTests(unittest.TestCase):
    def setUp(self):
        template = Path(__file__).resolve().parents[1] / "assets" / "templates" / "分集叙事契约.json"
        self.data = json.loads(template.read_text(encoding="utf-8-sig"))
        self.data["template_only"] = False

    def test_valid_declared_structure(self):
        self.assertEqual([], validate(self.data)[0])

    def test_nonfinite_boolean_and_negative_voice_times(self):
        for value in (float("nan"), float("inf"), True, -1, 181):
            with self.subTest(value=value):
                data = copy.deepcopy(self.data)
                data["voice_landings"][0]["at_seconds"] = value
                self.assertTrue(validate(data)[0])

    def test_duration_change_invalidates_reversal(self):
        self.data["duration_seconds"] = 200
        self.assertTrue(any("反转过早" in x for x in validate(self.data)[0]))

    def test_late_first_voice(self):
        self.data["voice_landings"][0]["at_seconds"] = 4
        self.assertTrue(validate(self.data)[0])

    def test_negative_pressure_start(self):
        self.data["pressure_payoff"]["pressure_start_seconds"] = -1
        self.assertTrue(validate(self.data)[0])

    def test_empty_silence_list_does_not_prove_actual_sound(self):
        self.data["silence_segments"] = []
        errors, warnings = validate(self.data)
        self.assertEqual([], errors)
        self.assertTrue(any("空静默列表" in x for x in warnings))

    def test_malformed_shape_fails(self):
        for key in ("hook", "reversal", "voice_landings", "beats", "silence_segments"):
            data = copy.deepcopy(self.data)
            data[key] = "bad"
            self.assertTrue(validate(data)[0])
        self.assertTrue(validate([])[0])


if __name__ == "__main__":
    unittest.main()
