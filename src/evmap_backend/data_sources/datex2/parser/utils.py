from typing import Iterable, Optional


def find_common_part(strings: Iterable[str], min_length=5) -> Optional[str]:
    """
    For a given list of strings, find the longest common substring (located anywhere within the string)
    in the given list of strings.

    Only substrings with at least min_length characters are considered.
    """
    string_list = [s for s in strings if s]
    if len(string_list) == 0:
        return None
    if len(string_list) == 1:
        return string_list[0] if len(string_list[0]) >= min_length else None

    # Use the shortest string as the base for generating candidate substrings
    base = min(string_list, key=len)

    # Try substrings from longest to shortest
    for length in range(len(base), min_length - 1, -1):
        for start in range(len(base) - length + 1):
            candidate = base[start : start + length]
            if all(candidate in s for s in string_list):
                return candidate.strip()

    return None
