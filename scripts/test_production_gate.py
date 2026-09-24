"""Offline regression checks of the record gate, not synthetic artistic acceptance."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from validate_production_gate import MEDIA, REQUIRED, required_checks, validate


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        # Bytes are fixture placeholders. The checker deliberately does not decode media.
        (self.base / "fixture.bin").write_bytes(b"offline evidence fixture")
        self.current = {"project": "test", "episode": "1", "source_revision": "r1",
                        "dependencies": {"baseline": {"version": "b1", "adoption": "accepted"},
                                         "visual_contract": {"version": "style1", "adoption": "accepted"}}}
        self.data = self.record()

    def record(self, stage="assets", phase="accept"):
        return {"schema_version": 1, "template_only": False, "project": "test", "episode": "1",
                "source_revision": "r1", "stage": stage, "phase": phase, "targets": ["C1", "C2"],
                "dependencies": {"baseline": "b1", "visual_contract": "style1"}, "blockers": [],
                "visual_contract": {"version": "style1", "medium": "2D animation",
                                    "shape_language": "adult natural proportions",
                                    "line_and_material": "clean contours, cel shading",
                                    "light_and_color": "muted palette, soft shadows",
                                    "exclude": "photography, 3D renders", "decision_evidence": "note"},
                "evidence": [{"id": "note", "uri": "fixture.bin", "version": "n1", "kind": "record"}] +
                            [{"id": c, "uri": "fixture.bin", "version": "v1", "kind": sorted(MEDIA[stage])[0]}
                             for c in ("C1", "C2")],
                "checks": {k: {"status": "pass", "evidence": ["note"], "findings": "fixture observation"}
                           for k in required_checks(stage, phase)},
                "results": [{"target": c, "version": "v1", "artifact": c,
                             "inspection": {"status": "pass", "evidence": [c], "findings": "fixture observation"}}
                            for c in ("C1", "C2")]}

    def errors(self):
        return validate(self.data, self.current, self.base)

    def test_valid_all_stages_and_phases(self):
        for stage in REQUIRED:
            for phase in ("prepare", "accept"):
                with self.subTest(stage=stage, phase=phase):
                    self.assertEqual([], validate(self.record(stage, phase), self.current, self.base))

    def test_every_required_check_is_enforced(self):
        for stage in REQUIRED:
            for phase in ("prepare", "accept"):
                for key in required_checks(stage, phase):
                    with self.subTest(stage=stage, phase=phase, missing=key):
                        data = self.record(stage, phase)
                        del data["checks"][key]
                        self.assertTrue(validate(data, self.current, self.base))

    def test_original_failure_no_visual_preflight(self):
        self.data = self.record("assets", "prepare")
        del self.data["checks"]["visual_contract"]
        self.assertTrue(self.errors())

    def test_empty_style_cannot_hide_behind_pass_label(self):
        for key in ("medium", "shape_language", "line_and_material", "light_and_color", "exclude"):
            with self.subTest(key=key):
                self.data = self.record()
                self.data["visual_contract"][key] = ""
                self.assertTrue(self.errors())

    def test_style_version_change_invalidates_approval(self):
        self.data["visual_contract"]["version"] = "style2"
        self.assertTrue(self.errors())

    def test_success_logs_are_not_images(self):
        for evidence in self.data["evidence"]:
            evidence["kind"] = "record"
        self.assertTrue(self.errors())

    def test_one_inspected_character_does_not_cover_three(self):
        self.data["targets"].append("C3")
        self.assertTrue(self.errors())

    def test_no_cross_character_review(self):
        del self.data["checks"]["style_consistency"]
        self.assertTrue(self.errors())

    def test_missing_storyboard_continuity(self):
        self.data = self.record("storyboards", "accept")
        del self.data["checks"]["spatial_continuity"]
        self.assertTrue(self.errors())

    def test_prompt_scope_not_checked(self):
        self.data = self.record("storyboards", "prepare")
        self.data["checks"]["prompt_scope"]["status"] = "pending"
        self.assertTrue(self.errors())

    def test_new_generated_version_does_not_inherit_acceptance(self):
        self.data["results"][0]["version"] = "v2"
        self.assertTrue(self.errors())

    def test_changed_source_revision(self):
        self.current["source_revision"] = "r2"
        self.assertTrue(self.errors())

    def test_new_script_can_prepare_without_faking_revision(self):
        self.data = self.record("script", "prepare")
        self.data["source_revision"] = None
        self.current["source_revision"] = None
        self.assertEqual([], self.errors())
        self.data = self.record("script", "accept")
        self.data["source_revision"] = None
        self.assertTrue(self.errors())

    def test_visual_adoption_requires_actual_revision(self):
        self.data["source_revision"] = None
        self.current["source_revision"] = None
        self.assertTrue(self.errors())

    def test_changed_dependency_version(self):
        self.current["dependencies"]["baseline"]["version"] = "b2"
        self.assertTrue(self.errors())

    def test_current_is_not_adopted(self):
        self.current["dependencies"]["baseline"]["adoption"] = "current"
        self.assertTrue(self.errors())

    def test_empty_dependencies(self):
        self.data["dependencies"] = {}
        self.assertTrue(self.errors())

    def test_video_cover_is_not_full_video(self):
        self.data = self.record("video", "accept")
        self.data["evidence"][1]["kind"] = "image"
        self.assertTrue(self.errors())

    def test_no_actual_sound_review(self):
        self.data = self.record("audio", "accept")
        self.data["checks"]["timing_sound"]["status"] = "pending"
        self.assertTrue(self.errors())

    def test_failed_item_blocks_batch(self):
        self.data["results"][1]["inspection"]["status"] = "fail"
        self.assertTrue(self.errors())

    def test_unknown_evidence(self):
        self.data["checks"]["actual_review"]["evidence"] = ["not-found"]
        self.assertTrue(self.errors())

    def test_missing_local_evidence(self):
        self.data["evidence"][0]["uri"] = "missing.json"
        self.assertTrue(self.errors())

    def test_no_specific_findings(self):
        self.data["checks"]["actual_review"]["findings"] = " "
        self.assertTrue(self.errors())

    def test_unresolved_blocker(self):
        self.data["blockers"] = ["wrong costume"]
        self.assertTrue(self.errors())

    def test_duplicate_results(self):
        self.data["results"][1] = copy.deepcopy(self.data["results"][0])
        self.assertTrue(self.errors())

    def test_template_fails(self):
        self.data["template_only"] = True
        self.assertTrue(self.errors())

    def test_wrong_project(self):
        self.current["project"] = "another"
        self.assertTrue(self.errors())

    def test_malformed_shapes_fail_without_crashing(self):
        for key in ("evidence", "checks", "results", "targets", "dependencies", "stage", "phase"):
            for bad in (None, 3, [], {}):
                with self.subTest(key=key, bad=bad):
                    data = copy.deepcopy(self.data)
                    data[key] = bad
                    self.assertTrue(validate(data, self.current, self.base))
        self.assertTrue(validate([], self.current, self.base))

    def test_cli_relative_files_and_failure_exit(self):
        script = Path(__file__).with_name("validate_production_gate.py")
        record, current = self.base / "record.json", self.base / "current.json"
        current.write_text(json.dumps(self.current), encoding="utf-8")
        for expected, change in ((0, False), (1, True)):
            self.data["template_only"] = change
            record.write_text(json.dumps(self.data), encoding="utf-8-sig")
            result = subprocess.run([sys.executable, str(script), str(record), "--current", str(current)],
                                    capture_output=True)
            self.assertEqual(expected, result.returncode, result.stderr)
        record.write_text("{bad json", encoding="utf-8")
        result = subprocess.run([sys.executable, str(script), str(record), "--current", str(current)],
                                capture_output=True)
        self.assertEqual(2, result.returncode)


if __name__ == "__main__":
    unittest.main()
