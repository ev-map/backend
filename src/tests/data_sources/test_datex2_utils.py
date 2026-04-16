from evmap_backend.data_sources.datex2.parser.utils import find_common_part


class TestFindCommonPart:
    def test_returns_none_for_empty_input(self):
        assert find_common_part([]) is None

    def test_returns_none_for_all_empty_strings(self):
        assert find_common_part(["", "", ""]) is None

    def test_single_string_long_enough(self):
        assert find_common_part(["hello world"]) == "hello world"

    def test_single_string_too_short(self):
        assert find_common_part(["hi"]) is None

    def test_single_string_exactly_min_length(self):
        assert find_common_part(["abcde"]) == "abcde"

    def test_identical_strings(self):
        assert (
            find_common_part(["charging station", "charging station"])
            == "charging station"
        )

    def test_common_prefix(self):
        result = find_common_part(["charging station A", "charging station B"])
        assert result == "charging station"

    def test_common_suffix(self):
        result = find_common_part(["A - Main Street", "B - Main Street"])
        assert result == "- Main Street"

    def test_common_substring_in_middle(self):
        result = find_common_part(["XX EV Charger 01", "YY EV Charger 02"])
        assert "EV Charger" in result

    def test_no_common_substring_above_min_length(self):
        assert find_common_part(["abcde", "fghij"]) is None

    def test_common_part_shorter_than_min_length(self):
        assert find_common_part(["abc123", "xyz123"]) is None

    def test_custom_min_length(self):
        assert find_common_part(["abc12", "xyz12"], min_length=2) == "12"

    def test_custom_min_length_no_match(self):
        assert find_common_part(["abc", "xyz"], min_length=2) is None

    def test_returns_longest_common_substring(self):
        result = find_common_part(
            [
                "EV Fast Charger Alpha",
                "EV Fast Charger Beta",
                "EV Fast Charger Gamma",
            ]
        )
        assert result == "EV Fast Charger"

    def test_multiple_strings_with_varying_lengths(self):
        result = find_common_part(
            [
                "SuperCharger Berlin 01",
                "SuperCharger Berlin 02",
                "SuperCharger Berlin 03",
            ]
        )
        assert result == "SuperCharger Berlin 0"

    def test_accepts_any_iterable(self):
        result = find_common_part(iter(["hello world", "hello world!"]))
        assert result == "hello world"

    def test_strips_whitespace_from_result(self):
        result = find_common_part(["Station A", "Station B"])
        assert result == "Station"

    def test_returns_none_when_only_short_common_part(self):
        assert find_common_part(["ax", "bx"]) is None

    def test_min_length_one(self):
        assert find_common_part(["ax", "bx"], min_length=1) == "x"
