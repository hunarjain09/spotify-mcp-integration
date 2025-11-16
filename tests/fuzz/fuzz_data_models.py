"""Fuzz testing for core data models."""

import sys
from typing import List, Dict, Any

from models.data_models import SongMetadata, WorkflowInput, SpotifyTrackResult
from tests.fuzz.fuzz_generators import FuzzGenerator


class DataModelFuzzer:
    """Fuzz test data models."""

    def __init__(self):
        self.generator = FuzzGenerator()
        self.bugs_found = []

    def fuzz_song_metadata(self) -> List[Dict[str, Any]]:
        """Fuzz test SongMetadata model."""
        print("\n" + "=" * 60)
        print("FUZZING: SongMetadata Model")
        print("=" * 60)

        bugs = []
        test_count = 0

        # Test 1: Edge case strings in metadata
        print("\n[TEST 1] Edge case music strings...")
        for edge_case in self.generator.edge_case_strings():
            test_count += 1
            try:
                metadata = SongMetadata(
                    title=edge_case,
                    artist=edge_case,
                    album=edge_case,
                )
                # Test search query generation
                query = metadata.to_search_query()

                # Check for potential Spotify API issues
                if len(query) > 1000:
                    bugs.append({
                        "test": "search_query length",
                        "input": edge_case[:50],
                        "issue": f"Search query too long: {len(query)} chars (Spotify API limit might be hit)",
                        "severity": "MEDIUM",
                    })

            except Exception as e:
                bugs.append({
                    "test": "SongMetadata crash",
                    "input": repr(edge_case),
                    "issue": f"Crash on valid music metadata: {type(e).__name__}: {str(e)}",
                    "severity": "HIGH",
                })

        # Test 2: Null/None values
        print(f"[TEST 2] Null/None album values...")
        test_count += 1
        try:
            metadata = SongMetadata(title="Test", artist="Artist", album=None)
            query = metadata.to_search_query()
            # Should handle None gracefully
            if "None" in query or "null" in query.lower():
                bugs.append({
                    "test": "None handling",
                    "input": "album=None",
                    "issue": f"None value leaking into search query: {query}",
                    "severity": "MEDIUM",
                })
        except Exception as e:
            bugs.append({
                "test": "None handling crash",
                "input": "album=None",
                "issue": f"Crash on None album: {type(e).__name__}: {str(e)}",
                "severity": "HIGH",
            })

        # Test 3: Extreme duration values
        print(f"[TEST 3] Extreme duration values...")
        for duration in self.generator.extreme_numbers():
            test_count += 1
            try:
                metadata = SongMetadata(
                    title="Test",
                    artist="Artist",
                    duration_ms=duration,
                )
                # Check for unrealistic durations
                if isinstance(duration, (int, float)) and (duration < 0 or duration > 3600000):
                    bugs.append({
                        "test": "duration validation",
                        "input": str(duration),
                        "issue": f"Unrealistic duration accepted: {duration}ms",
                        "severity": "LOW",
                    })
            except Exception as e:
                if not isinstance(duration, (int, float)):
                    # Expected to fail on inf/nan
                    pass
                else:
                    bugs.append({
                        "test": "duration crash",
                        "input": str(duration),
                        "issue": f"Crash on duration: {type(e).__name__}: {str(e)}",
                        "severity": "MEDIUM",
                    })

        # Test 4: ISRC edge cases
        print(f"[TEST 4] ISRC code edge cases...")
        isrc_tests = [
            "",
            "INVALID",
            "USRC17607839",  # Valid format
            "us-rc1-76-07839",  # With dashes
            "12345",
            "A" * 100,
            None,
        ]
        for isrc in isrc_tests:
            test_count += 1
            try:
                metadata = SongMetadata(
                    title="Test",
                    artist="Artist",
                    isrc=isrc,
                )
            except Exception as e:
                bugs.append({
                    "test": "ISRC crash",
                    "input": repr(isrc),
                    "issue": f"Crash on ISRC: {type(e).__name__}: {str(e)}",
                    "severity": "MEDIUM",
                })

        print(f"\nTests run: {test_count}, Bugs found: {len(bugs)}")
        return bugs

    def fuzz_workflow_input(self) -> List[Dict[str, Any]]:
        """Fuzz test WorkflowInput validation."""
        print("\n" + "=" * 60)
        print("FUZZING: WorkflowInput Model")
        print("=" * 60)

        bugs = []
        test_count = 0

        # Test 1: Invalid match thresholds
        print("\n[TEST 1] Invalid match thresholds...")
        for threshold in [-1, -0.1, 1.1, 2.0, 999, float('inf'), float('nan')]:
            test_count += 1
            try:
                workflow_input = WorkflowInput(
                    song_metadata=SongMetadata(title="Test", artist="Artist"),
                    playlist_id="37i9dQZF1DXcBWIGoYBM5M",
                    user_id="test_user",
                    match_threshold=threshold,
                )
                bugs.append({
                    "test": "match_threshold validation",
                    "input": str(threshold),
                    "issue": f"Invalid threshold accepted: {threshold}",
                    "severity": "HIGH",
                })
            except ValueError as e:
                # Expected - should raise ValueError
                if "threshold" not in str(e).lower():
                    bugs.append({
                        "test": "match_threshold error message",
                        "input": str(threshold),
                        "issue": f"Unclear error message: {str(e)}",
                        "severity": "LOW",
                    })
            except Exception as e:
                bugs.append({
                    "test": "match_threshold crash",
                    "input": str(threshold),
                    "issue": f"Unexpected error: {type(e).__name__}: {str(e)}",
                    "severity": "HIGH",
                })

        # Test 2: Empty/invalid playlist IDs
        print(f"[TEST 2] Invalid playlist IDs...")
        for invalid_id in self.generator.invalid_spotify_ids():
            test_count += 1
            try:
                workflow_input = WorkflowInput(
                    song_metadata=SongMetadata(title="Test", artist="Artist"),
                    playlist_id=invalid_id,
                    user_id="test_user",
                )
                if not invalid_id or invalid_id.strip() == "":
                    bugs.append({
                        "test": "playlist_id validation",
                        "input": repr(invalid_id),
                        "issue": "Empty playlist ID accepted",
                        "severity": "HIGH",
                    })
            except ValueError:
                # Expected - should raise ValueError
                pass
            except Exception as e:
                bugs.append({
                    "test": "playlist_id crash",
                    "input": repr(invalid_id),
                    "issue": f"Unexpected error: {type(e).__name__}: {str(e)}",
                    "severity": "MEDIUM",
                })

        # Test 3: Malicious user IDs
        print(f"[TEST 3] Malicious user IDs...")
        for malicious in self.generator.malicious_strings()[:20]:  # Sample
            test_count += 1
            try:
                workflow_input = WorkflowInput(
                    song_metadata=SongMetadata(title="Test", artist="Artist"),
                    playlist_id="37i9dQZF1DXcBWIGoYBM5M",
                    user_id=malicious,
                )
                # Check if it could cause issues in logging/workflow IDs
            except Exception as e:
                bugs.append({
                    "test": "user_id crash",
                    "input": repr(malicious),
                    "issue": f"Crash on user_id: {type(e).__name__}: {str(e)}",
                    "severity": "MEDIUM",
                })

        print(f"\nTests run: {test_count}, Bugs found: {len(bugs)}")
        return bugs

    def fuzz_spotify_track_result(self) -> List[Dict[str, Any]]:
        """Fuzz test SpotifyTrackResult."""
        print("\n" + "=" * 60)
        print("FUZZING: SpotifyTrackResult Model")
        print("=" * 60)

        bugs = []
        test_count = 0

        # Test 1: Extreme popularity values
        print("\n[TEST 1] Extreme popularity values...")
        for popularity in [-1, -100, 101, 999, 2**31]:
            test_count += 1
            try:
                track = SpotifyTrackResult(
                    track_id="test_id",
                    track_name="Test",
                    artist_name="Artist",
                    album_name="Album",
                    spotify_uri="spotify:track:test",
                    duration_ms=200000,
                    popularity=popularity,
                    release_date="2023-01-01",
                )
                # Spotify popularity should be 0-100
                if popularity < 0 or popularity > 100:
                    bugs.append({
                        "test": "popularity validation",
                        "input": str(popularity),
                        "issue": f"Invalid popularity accepted: {popularity} (should be 0-100)",
                        "severity": "LOW",
                    })
            except Exception as e:
                bugs.append({
                    "test": "popularity crash",
                    "input": str(popularity),
                    "issue": f"Crash: {type(e).__name__}: {str(e)}",
                    "severity": "LOW",
                })

        # Test 2: Invalid release dates
        print(f"[TEST 2] Invalid release dates...")
        invalid_dates = [
            "",
            "not-a-date",
            "2023-13-01",  # Invalid month
            "2023-01-32",  # Invalid day
            "0000-00-00",
            "9999-99-99",
            "01/01/2023",  # Wrong format
        ]
        for date in invalid_dates:
            test_count += 1
            try:
                track = SpotifyTrackResult(
                    track_id="test_id",
                    track_name="Test",
                    artist_name="Artist",
                    album_name="Album",
                    spotify_uri="spotify:track:test",
                    duration_ms=200000,
                    popularity=50,
                    release_date=date,
                )
                # No crash is OK, but should handle gracefully later
            except Exception as e:
                bugs.append({
                    "test": "release_date crash",
                    "input": date,
                    "issue": f"Crash: {type(e).__name__}: {str(e)}",
                    "severity": "LOW",
                })

        print(f"\nTests run: {test_count}, Bugs found: {len(bugs)}")
        return bugs


def run_fuzz_tests():
    """Run all data model fuzz tests."""
    fuzzer = DataModelFuzzer()
    all_bugs = []

    all_bugs.extend(fuzzer.fuzz_song_metadata())
    all_bugs.extend(fuzzer.fuzz_workflow_input())
    all_bugs.extend(fuzzer.fuzz_spotify_track_result())

    return all_bugs


if __name__ == "__main__":
    print("\n🔥 DATA MODEL FUZZ TESTING 🔥\n")
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
