import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

# Tests never read or write the user's project store or installed model cache.
TEST_HOME = tempfile.TemporaryDirectory(prefix="aige-tests-")
os.environ["LOCALAPPDATA"] = TEST_HOME.name

import media_engine
import render_engine
import speech_engine
import gemini_director
from project_safety import contained_path, identifier, validate_director, write_json
from runtime import source_signature, worker_slot
from timeline_engine import compile_timeline, remap_dialogue, timeline_filter


def segment(start, end, action="keep", protected=False):
    return {"start_seconds": start, "end_seconds": end, "action": action, "protected_story": protected}


class SafetyTests(unittest.TestCase):
    def test_path_escape_and_identifier_rejected(self):
        for value in ("../other", "..", "C:\\file", "dlg/1", "a.wav", ""):
            with self.assertRaises(ValueError):
                identifier(value)
        with self.assertRaises(ValueError):
            contained_path(TEST_HOME.name, "..", "outside.mp4")

    def test_worker_serializes_operations(self):
        with worker_slot():
            with self.assertRaises(RuntimeError):
                with worker_slot():
                    pass

    def test_timeline_protection_and_coverage(self):
        for segments in ([segment(0, 1), segment(2, 4)], [segment(0, 4, "cut", True)], [segment(0, 4, "cut")]):
            with self.assertRaises(ValueError):
                compile_timeline(segments, 4)

    def test_shared_timeline_and_subtitle_mapping(self):
        timeline, duration = compile_timeline([segment(0, 1, "cut"), segment(1, 5, "compress"), segment(5, 7)], 7)
        self.assertEqual(duration, 3)
        line = {"start_seconds": 5.5, "end_seconds": 6.5, "english_rewrite": "Hello"}
        mapped = remap_dialogue([line], timeline)[0]
        self.assertEqual((mapped["start_seconds"], mapped["end_seconds"]), (1.5, 2.5))
        self.assertEqual(line["start_seconds"], 5.5)
        with self.assertRaises(ValueError):
            remap_dialogue([dict(line, start_seconds=4)], timeline)

    def test_director_cannot_invent_lines_or_cut_reactions(self):
        transcript = {"dialogue_lines": [{"id": "dlg-1", "start_seconds": 1, "end_seconds": 2, "timestamp": "00:00:01", "original_text": "hello"}]}
        output = {"story_segments": [segment(0, 3, "compress")], "english_lines": [{"line_id": "dlg-1", "english_rewrite": "Hello"}]}
        validated = validate_director(copy.deepcopy(output), transcript, 3)
        self.assertEqual(validated["story_segments"][0]["action"], "keep")
        output["english_lines"][0]["line_id"] = "invented"
        with self.assertRaises(ValueError):
            validate_director(output, transcript, 3)

    def test_silent_transcript_stays_empty(self):
        import numpy as np
        fake = SimpleNamespace(transcribe=lambda *args, **kwargs: (iter([]), SimpleNamespace(language="hi", language_probability=0)))
        with tempfile.TemporaryDirectory(dir=TEST_HOME.name) as directory:
            with patch.object(speech_engine, "WhisperModel", return_value=fake), patch.object(speech_engine, "load_audio_numpy", return_value=np.zeros(16000)):
                result = speech_engine.transcribe_audio_file("silence.wav", directory)
            self.assertEqual(result["lines"], [])
            self.assertEqual(result["language_confidence"], 0)

    def test_transcription_failure_is_not_success(self):
        import numpy as np
        fake = SimpleNamespace(transcribe=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("ASR failure")))
        with tempfile.TemporaryDirectory(dir=TEST_HOME.name) as directory:
            with patch.object(speech_engine, "WhisperModel", return_value=fake), patch.object(speech_engine, "load_audio_numpy", return_value=np.zeros(16000)):
                with self.assertRaisesRegex(RuntimeError, "ASR failure"):
                    speech_engine.transcribe_audio_file("silence.wav", directory)
            self.assertFalse(Path(directory, "transcript.json").exists())

    def test_missing_key_never_creates_a_fake_plan(self):
        with tempfile.TemporaryDirectory(dir=TEST_HOME.name) as directory:
            write_json(os.path.join(directory, "media.json"), {})
            write_json(os.path.join(directory, "transcript.json"), {"dialogue_lines": []})
            with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
                with self.assertRaises(ValueError):
                    gemini_director.analyze_session_with_gemini(directory)
            self.assertFalse(Path(directory, "edit_plan.json").exists())


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        from fastapi.testclient import TestClient
        cls.server = server
        cls.client = TestClient(server.app)
        cls.headers = {"X-Worker-Token": server.WORKER_TOKEN}

    def test_local_api_requires_authentication(self):
        self.assertEqual(self.client.get('/api/projects').status_code, 401)
        self.assertEqual(self.client.get('/api/projects', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/api/projects', headers={**self.headers, 'Origin': 'https://untrusted.example'}).status_code, 403)

    def test_path_traversal_is_rejected(self):
        result = self.client.get('/api/media/proxy-video', params={'project_id': '../escape'}, headers=self.headers)
        self.assertEqual(result.status_code, 400)

    def test_empty_store_does_not_invent_projects(self):
        self.assertEqual(self.client.get('/api/projects', headers=self.headers).json(), {"projects": []})

    def test_pipeline_reserves_worker_before_launching_thread(self):
        directory = Path(self.server.PROJECTS_BASE_DIR, "reservation_test")
        directory.mkdir()
        write_json(str(directory / "media.json"), {})
        try:
            with patch.object(self.server.threading, "Thread"):
                first = self.client.post('/api/pipeline/start', json={"project_id": "reservation_test"}, headers=self.headers)
                second = self.client.post('/api/pipeline/start', json={"project_id": "reservation_test"}, headers=self.headers)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 409)
        finally:
            self.server.WORKER_LOCK.release()
            for path in directory.iterdir():
                path.unlink()
            directory.rmdir()


class MediaIntegrationTests(unittest.TestCase):
    def test_failed_ffmpeg_is_reported(self):
        with self.assertRaises(RuntimeError):
            media_engine.run_ffmpeg(["-i", "missing-recording.mkv", "-f", "null", "-"])

    def test_no_audio_tracks_are_fabricated(self):
        with tempfile.TemporaryDirectory(dir=TEST_HOME.name) as directory:
            source = os.path.join(directory, "silent.mp4")
            media_engine.run_ffmpeg(["-y", "-f", "lavfi", "-i", "color=size=320x180:rate=30:duration=1", "-an", "-c:v", "libx264", source])
            self.assertEqual(media_engine.inspect_media(source)["audio_tracks"], [])

    def test_single_track_audio_extraction(self):
        with tempfile.TemporaryDirectory(dir=TEST_HOME.name) as directory:
            source = os.path.join(directory, "single_track.mp4")
            # Create a 1-second video with exactly 1 stereo audio track
            media_engine.run_ffmpeg([
                "-y", "-f", "lavfi", "-i", "color=size=320x180:rate=30:duration=1",
                "-f", "lavfi", "-i", "sine=frequency=1000:duration=1",
                "-c:v", "libx264", "-c:a", "aac", source
            ])
            inspection = media_engine.inspect_media(source)
            self.assertEqual(len(inspection["audio_tracks"]), 1)
            self.assertEqual(inspection["suggested_mapping"]["game_track"], 1)
            self.assertEqual(inspection["suggested_mapping"]["mic_track"], 1)
            
            # Extract streams using single track for both
            out_dir = os.path.join(directory, "extracted")
            result = media_engine.extract_audio_streams(source, out_dir, game_track=1, mic_track=1)
            self.assertTrue(os.path.isfile(result["game_audio_path"]))
            self.assertTrue(os.path.isfile(result["mic_audio_path"]))
            
            # Verify file sizes > 0
            self.assertGreater(os.path.getsize(result["game_audio_path"]), 0)
            self.assertGreater(os.path.getsize(result["mic_audio_path"]), 0)

    def test_real_cut_compress_export_and_subtitle_timing(self):
        with tempfile.TemporaryDirectory(dir=TEST_HOME.name) as directory:
            source = os.path.join(directory, "original.mp4")
            media_engine.run_ffmpeg(["-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=4", "-c:v", "libx264", source])
            for filename in ("game_audio.wav", "ai_voice_dub.wav"):
                media_engine.run_ffmpeg(["-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "4", os.path.join(directory, filename)])
            metadata = media_engine.inspect_media(source)
            original_signature = source_signature(source)
            write_json(os.path.join(directory, "media.json"), {"project_id": "test", "original_master": metadata, "source_signature": original_signature})
            write_json(os.path.join(directory, "edit_plan.json"), {"story_map": [segment(0, 1, "cut"), segment(1, 3, "compress"), segment(3, 4)]})
            write_json(os.path.join(directory, "english_lines.json"), [{"start_seconds": 3.1, "end_seconds": 3.8, "english_rewrite": "Hello, world!"}])
            encoder = {"args": ["-c:v", "libx264", "-preset", "ultrafast"], "desc": "CPU test", "codec": "libx264", "is_hw": False}
            with patch.object(render_engine, "probe_best_video_encoder", return_value=encoder):
                manifest = render_engine.render_master_video(directory, preset="YouTube 1080p60")
            result = media_engine.inspect_media(manifest["output_file"])
            self.assertAlmostEqual(result["duration_seconds"], 1.5, delta=0.12)
            self.assertEqual(result["resolution"], "1920x1080")
            self.assertEqual(source_signature(source), original_signature)
            self.assertIn('0:00:00.60,0:00:01.30', Path(directory, "master_subtitles.ass").read_text())
            with self.assertRaises(ValueError):
                render_engine.render_master_video(directory, output_filename="../escape.mp4")


if __name__ == '__main__':
    unittest.main()
