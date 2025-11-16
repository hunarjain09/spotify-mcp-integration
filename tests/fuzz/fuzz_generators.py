"""Generators for creating fuzz test inputs."""

import random
import string
from typing import Any, List


class FuzzGenerator:
    """Generate various types of fuzz test inputs."""

    @staticmethod
    def malicious_strings() -> List[str]:
        """Generate strings that commonly break parsers."""
        return [
            # Empty and whitespace
            "",
            " ",
            "   ",
            "\t",
            "\n",
            "\r\n",
            "\0",

            # SQL Injection patterns
            "'; DROP TABLE songs;--",
            "' OR '1'='1",
            "admin'--",
            "1' UNION SELECT NULL--",

            # XSS patterns
            "<script>alert('XSS')</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
            "';alert(String.fromCharCode(88,83,83))//",

            # Path traversal
            "../../etc/passwd",
            "..\\..\\windows\\system32",
            "%2e%2e%2f",

            # Command injection
            "; ls -la",
            "| whoami",
            "`id`",
            "$(whoami)",

            # Unicode and special chars
            "你好世界",
            "🎵🎶🎧",
            "𝕿𝖊𝖘𝖙",
            "\u0000",
            "\ufeff",  # Zero-width no-break space

            # Format string bugs
            "%s%s%s%s%s",
            "%x%x%x%x",
            "{0}{1}{2}",

            # Very long strings
            "A" * 10000,
            "Test " * 1000,

            # Special JSON/XML chars
            '{"key": "value"}',
            "<xml>test</xml>",
            "\\n\\r\\t",

            # Null bytes and control chars
            "test\x00test",
            "\x01\x02\x03",

            # Mixed encodings
            "café",
            "naïve",
            "Björk",

            # Case variations
            "TeSt",
            "TEST",
            "test",

            # Numbers as strings
            "12345",
            "0",
            "-1",
            "3.14159",
            "1e308",

            # Boolean-like strings
            "true",
            "false",
            "null",
            "undefined",
            "NaN",
        ]

    @staticmethod
    def extreme_numbers() -> List[Any]:
        """Generate extreme numeric values."""
        return [
            # Integers
            0,
            -1,
            1,
            2**31 - 1,  # Max 32-bit int
            -(2**31),   # Min 32-bit int
            2**63 - 1,  # Max 64-bit int
            -(2**63),   # Min 64-bit int
            2**128,     # Very large

            # Floats
            0.0,
            -0.0,
            0.00000001,
            -0.00000001,
            1e308,      # Near max float
            -1e308,
            1e-308,     # Near min float
            float('inf'),
            float('-inf'),
            float('nan'),

            # Edge cases
            1.0000000000000001,  # Floating point precision
            0.1 + 0.2,           # Classic floating point bug
        ]

    @staticmethod
    def edge_case_strings() -> List[str]:
        """Generate edge case strings for music metadata."""
        return [
            # Single character
            "a",
            "A",
            "1",
            "!",

            # Extremely long artist names
            "The International Submarine Band feat. Gram Parsons and The Flying Burrito Brothers",

            # Songs with special formatting
            "Song Title (feat. Artist2)",
            "Song Title [Remix]",
            "Song Title - Remastered 2023",
            "Song Title (Live at Venue)",
            "Song Title / Song Title 2",

            # Articles and grammar
            "The Beatles",
            "Beatles",
            "A Song",
            "An Album",

            # Punctuation heavy
            "Don't Stop Believin'",
            "Ain't No Mountain High Enough",
            "What's Going On?",
            "Money (That's What I Want)",

            # Accented characters
            "Cœur de pirate",
            "Sigur Rós",
            "Mötley Crüe",

            # Same name different artists
            "Coldplay",  # Band and song name conflicts

            # Version numbers
            "Song v2.0",
            "Album (Deluxe Edition)",

            # Spacing variations
            "SongName",
            "Song  Name",  # Double space
            " Song Name",  # Leading space
            "Song Name ",  # Trailing space
        ]

    @staticmethod
    def invalid_spotify_ids() -> List[str]:
        """Generate invalid Spotify playlist/track IDs."""
        return [
            # Wrong length
            "abc",
            "a" * 21,
            "a" * 23,
            "a" * 100,

            # Invalid characters
            "spotify:track:abc123",  # Contains colons
            "37i9dQZF1DXcBWIGoYBM5_",  # Underscore
            "37i9dQZF1DXcBWIGoYBM5-",  # Dash
            "37i9dQZF1DXcBWIGoYBM5!",  # Special char

            # Empty/whitespace
            "",
            " " * 22,

            # Case sensitivity issues
            "ABCDEFGHIJKLMNOPQRSTUV",
            "abcdefghijklmnopqrstuv",

            # SQL injection attempts
            "'; DROP TABLE playlists",

            # Path traversal
            "../../../etc/passwd",
        ]

    @staticmethod
    def random_string(min_length: int = 1, max_length: int = 100) -> str:
        """Generate random string."""
        length = random.randint(min_length, max_length)
        chars = string.ascii_letters + string.digits + string.punctuation + " "
        return ''.join(random.choice(chars) for _ in range(length))

    @staticmethod
    def random_unicode_string(length: int = 50) -> str:
        """Generate random Unicode string."""
        # Random Unicode code points from various ranges
        chars = []
        for _ in range(length):
            # Mix of ASCII, Latin-1, emoji, CJK, etc.
            ranges = [
                (0x20, 0x7E),      # ASCII printable
                (0xA0, 0xFF),      # Latin-1 supplement
                (0x1F600, 0x1F64F),  # Emoticons
                (0x4E00, 0x9FFF),  # CJK
            ]
            start, end = random.choice(ranges)
            chars.append(chr(random.randint(start, end)))
        return ''.join(chars)
