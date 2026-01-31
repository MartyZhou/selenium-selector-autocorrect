"""Unit tests for correction_tracker module."""

import pytest
from selenium_selector_autocorrect.correction_tracker import (
    CorrectionTracker,
    get_correction_tracker,
)


class TestCorrectionTracker:
    """Test CorrectionTracker class."""

    def test_tracker_initialization(self):
        """CorrectionTracker initializes with empty corrections."""
        tracker = CorrectionTracker()
        assert len(tracker.get_corrections()) == 0

    def test_record_correction(self):
        """CorrectionTracker records corrections."""
        tracker = CorrectionTracker()
        tracker.record_correction(
            original_by="id",
            original_value="old-id",
            corrected_by="css selector",
            corrected_value=".new-class",
            success=True,
        )
        corrections = tracker.get_corrections()
        assert len(corrections) == 1
        assert corrections[0]["original_by"] == "id"
        assert corrections[0]["success"] is True

    def test_get_successful_corrections(self):
        """CorrectionTracker filters successful corrections."""
        tracker = CorrectionTracker()
        tracker.record_correction("id", "old", "css", "new", success=True)
        tracker.record_correction("id", "old2", "css", "new2", success=False)
        successful = tracker.get_successful_corrections()
        assert len(successful) == 1
        assert successful[0]["success"] is True

    def test_clear_corrections(self):
        """CorrectionTracker can clear all corrections."""
        tracker = CorrectionTracker()
        tracker.record_correction("id", "old", "css", "new")
        tracker.clear_corrections()
        assert len(tracker.get_corrections()) == 0


class TestCorrectionTrackerModule:
    """Test module-level functions."""

    def test_get_correction_tracker_singleton(self):
        """get_correction_tracker returns singleton instance."""
        tracker1 = get_correction_tracker()
        tracker2 = get_correction_tracker()
        assert tracker1 is tracker2
