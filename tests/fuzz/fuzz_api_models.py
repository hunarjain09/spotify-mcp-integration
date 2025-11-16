"""Fuzz testing for API models."""

import sys
from typing import List, Dict, Any
from pydantic import ValidationError

from api.models import SyncSongRequest
from tests.fuzz.fuzz_generators import FuzzGenerator


class APIModelFuzzer:
    """Fuzz test API models with malicious inputs."""

    def __init__(self):
        self.generator = FuzzGenerator()
        self.bugs_found = []

    def fuzz_sync_song_request(self) -> List[Dict[str, Any]]:
        """Fuzz test SyncSongRequest model."""
        print("\n" + "=" * 60)
        print("FUZZING: SyncSongRequest Model")
        print("=" * 60)

        bugs = []
        test_count = 0
        crash_count = 0

        # Test 1: Malicious strings in track_name
        print("\n[TEST 1] Malicious strings in track_name...")
        for malicious in self.generator.malicious_strings():
            test_count += 1
            try:
                request = SyncSongRequest(
                    track_name=malicious,
                    artist="Test Artist",
                    playlist_id="37i9dQZF1DXcBWIGoYBM5M",
                )
                # Should have been rejected!
                if malicious.strip() == "":
                    bugs.append({
                        "test": "track_name validation",
                        "input": repr(malicious),
                        "issue": "Empty/whitespace track_name accepted",
                        "severity": "MEDIUM",
                    })
                elif len(malicious) > 1000:
                    bugs.append({
                        "test": "track_name length",
                        "input": f"String of length {len(malicious)}",
                        "issue": "Extremely long track_name accepted (DoS risk)",
                        "severity": "HIGH",
                    })
            except ValidationError:
                # Expected - validation should reject bad inputs
                pass
            except Exception as e:
                crash_count += 1
                bugs.append({
                    "test": "track_name crash",
                    "input": repr(malicious),
                    "issue": f"Unexpected crash: {type(e).__name__}: {str(e)}",
                    "severity": "CRITICAL",
                })

        # Test 2: Malicious strings in artist
        print(f"[TEST 2] Malicious strings in artist...")
        for malicious in self.generator.malicious_strings():
            test_count += 1
            try:
                request = SyncSongRequest(
                    track_name="Test Song",
                    artist=malicious,
                    playlist_id="37i9dQZF1DXcBWIGoYBM5M",
                )
                if malicious.strip() == "":
                    bugs.append({
                        "test": "artist validation",
                        "input": repr(malicious),
                        "issue": "Empty/whitespace artist accepted",
                        "severity": "MEDIUM",
                    })
            except ValidationError:
                pass
            except Exception as e:
                crash_count += 1
                bugs.append({
                    "test": "artist crash",
                    "input": repr(malicious),
                    "issue": f"Unexpected crash: {type(e).__name__}: {str(e)}",
                    "severity": "CRITICAL",
                })

        # Test 3: Invalid playlist IDs
        print(f"[TEST 3] Invalid playlist IDs...")
        for invalid_id in self.generator.invalid_spotify_ids():
            test_count += 1
            try:
                request = SyncSongRequest(
                    track_name="Test Song",
                    artist="Test Artist",
                    playlist_id=invalid_id,
                )
                bugs.append({
                    "test": "playlist_id validation",
                    "input": repr(invalid_id),
                    "issue": f"Invalid playlist ID accepted: {invalid_id}",
                    "severity": "HIGH",
                })
            except ValidationError:
                # Expected - should reject invalid IDs
                pass
            except Exception as e:
                crash_count += 1
                bugs.append({
                    "test": "playlist_id crash",
                    "input": repr(invalid_id),
                    "issue": f"Unexpected crash: {type(e).__name__}: {str(e)}",
                    "severity": "CRITICAL",
                })

        # Test 4: Extreme match thresholds
        print(f"[TEST 4] Extreme match thresholds...")
        for threshold in [-1, -100, 1.1, 2.0, 999, float('inf'), float('-inf'), float('nan')]:
            test_count += 1
            try:
                request = SyncSongRequest(
                    track_name="Test Song",
                    artist="Test Artist",
                    playlist_id="37i9dQZF1DXcBWIGoYBM5M",
                    match_threshold=threshold,
                )
                if threshold < 0 or threshold > 1:
                    bugs.append({
                        "test": "match_threshold validation",
                        "input": str(threshold),
                        "issue": f"Invalid threshold accepted: {threshold}",
                        "severity": "MEDIUM",
                    })
            except ValidationError:
                # Expected for out of range
                pass
            except Exception as e:
                crash_count += 1
                bugs.append({
                    "test": "match_threshold crash",
                    "input": str(threshold),
                    "issue": f"Unexpected crash: {type(e).__name__}: {str(e)}",
                    "severity": "CRITICAL",
                })

        # Test 5: Unicode edge cases
        print(f"[TEST 5] Unicode edge cases...")
        for _ in range(10):
            test_count += 1
            unicode_string = self.generator.random_unicode_string(100)
            try:
                request = SyncSongRequest(
                    track_name=unicode_string,
                    artist=unicode_string,
                    playlist_id="37i9dQZF1DXcBWIGoYBM5M",
                )
                # Check if it serializes properly
                request.model_dump_json()
            except ValidationError:
                pass
            except Exception as e:
                crash_count += 1
                bugs.append({
                    "test": "Unicode handling",
                    "input": repr(unicode_string[:50]),
                    "issue": f"Unicode crash: {type(e).__name__}: {str(e)}",
                    "severity": "HIGH",
                })

        # Test 6: Type confusion
        print(f"[TEST 6] Type confusion attacks...")
        type_confusion_tests = [
            {"track_name": ["list", "instead"], "artist": "Test", "playlist_id": "37i9dQZF1DXcBWIGoYBM5M"},
            {"track_name": {"dict": "value"}, "artist": "Test", "playlist_id": "37i9dQZF1DXcBWIGoYBM5M"},
            {"track_name": 12345, "artist": "Test", "playlist_id": "37i9dQZF1DXcBWIGoYBM5M"},
            {"track_name": None, "artist": "Test", "playlist_id": "37i9dQZF1DXcBWIGoYBM5M"},
            {"track_name": True, "artist": "Test", "playlist_id": "37i9dQZF1DXcBWIGoYBM5M"},
        ]

        for bad_input in type_confusion_tests:
            test_count += 1
            try:
                request = SyncSongRequest(**bad_input)
                # Type coercion might work, check if it makes sense
                if not isinstance(request.track_name, str):
                    bugs.append({
                        "test": "Type validation",
                        "input": str(bad_input),
                        "issue": f"Type coercion accepted: {type(request.track_name)}",
                        "severity": "LOW",
                    })
            except ValidationError:
                # Expected - should reject wrong types
                pass
            except Exception as e:
                crash_count += 1
                bugs.append({
                    "test": "Type confusion crash",
                    "input": str(bad_input),
                    "issue": f"Unexpected crash: {type(e).__name__}: {str(e)}",
                    "severity": "CRITICAL",
                })

        # Summary
        print("\n" + "-" * 60)
        print(f"Tests run: {test_count}")
        print(f"Bugs found: {len(bugs)}")
        print(f"Crashes: {crash_count}")
        print("-" * 60)

        return bugs


def run_fuzz_tests():
    """Run all API model fuzz tests."""
    fuzzer = APIModelFuzzer()
    all_bugs = []

    all_bugs.extend(fuzzer.fuzz_sync_song_request())

    return all_bugs


if __name__ == "__main__":
    print("\n🔥 API MODEL FUZZ TESTING 🔥\n")
    bugs = run_fuzz_tests()

    print("\n" + "=" * 60)
    print(f"TOTAL BUGS FOUND: {len(bugs)}")
    print("=" * 60)

    if bugs:
        for i, bug in enumerate(bugs, 1):
            print(f"\n[BUG #{i}] {bug['severity']}")
            print(f"Test: {bug['test']}")
            print(f"Input: {bug['input']}")
            print(f"Issue: {bug['issue']}")

        sys.exit(1)
    else:
        print("\n✅ No bugs found!")
        sys.exit(0)
