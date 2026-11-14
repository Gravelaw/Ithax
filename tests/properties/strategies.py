"""Hostile JSON values shared by the property tests (P6; #99): numbers at and beyond the
limits of a float, NaN and infinity, and strings that have caused findings before (a lone
surrogate, ``constructor``, path fragments)."""

from hypothesis import strategies as st

EXTREME_NUMBERS = st.one_of(
    st.integers(min_value=-(10**400), max_value=10**400),
    st.floats(allow_nan=True, allow_infinity=True),
    st.sampled_from([0, -1, 10**309, 1e308, -1e308, 5e-324]),
)
HOSTILE_STRINGS = st.one_of(
    st.text(max_size=20),
    st.sampled_from(["", "\ud800", "constructor", "__proto__", "..", "C:", "\\projects"]),
)
JSON_VALUES = st.recursive(
    st.none() | st.booleans() | EXTREME_NUMBERS | HOSTILE_STRINGS,
    lambda inner: st.lists(inner, max_size=4) | st.dictionaries(HOSTILE_STRINGS, inner, max_size=4),
    max_leaves=25,
)
