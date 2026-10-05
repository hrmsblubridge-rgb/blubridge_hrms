"""Tests for payroll leave-code mapping (HR mapping shipped 2026-05-07).

Verifies _leave_code_for_status helper produces the correct abbreviations
for every (leave_type, leave_split) combination.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import server  # noqa: E402


@pytest.mark.parametrize("leave_type,leave_split,expected", [
    # Pre-Planned bucket
    ("Preplanned", "Full Day", "PF"),
    ("Pre-Planned", "Full Day", "PF"),
    ("preplanned", "First Half", "PH"),
    ("Pre-planned", "Second Half", "PH"),
    # Sick bucket
    ("Sick", "Full Day", "SF"),
    ("Sick Leave", "Full Day", "SF"),
    ("sick", "First Half", "SH"),
    ("Sick", "Second Half", "SH"),
    # Emergency bucket
    ("Emergency", "Full Day", "EF"),
    ("Emergency Leave", "Full Day", "EF"),
    ("emergency", "First Half", "EH"),
    ("Emergency", "Second Half", "EH"),
    # Optional Holiday — single code regardless of split
    ("Optional", "Full Day", "OH"),
    ("Optional", "First Half", "OH"),
    ("Optional", "Second Half", "OH"),
    # Paid Leave bucket (everything else)
    ("Earned", "Full Day", "PA"),
    ("Casual", "Full Day", "PA"),
    ("Annual", "Full Day", "PA"),
    ("Maternity", "Full Day", "PA"),
    ("Paternity", "Full Day", "PA"),
    ("Bereavement", "Full Day", "PA"),
    ("General Leave", "Full Day", "PA"),
    ("Earned", "First Half", "PP"),
    ("Casual", "Second Half", "PP"),
    ("Annual", "First Half", "PP"),
    # Edge: empty / None
    ("", "Full Day", "PA"),
    (None, "Full Day", "PA"),
])
def test_leave_code_mapping(leave_type, leave_split, expected):
    assert server._leave_code_for_status(leave_type, leave_split) == expected
