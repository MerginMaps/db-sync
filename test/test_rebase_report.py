import logging

import dbsync


def test_lost_field_updates_by_row_key(caplog, mocker):
    """A row deleted in the database (ours) that the server's changeset (theirs) updates is reported
    before the rebase drops it; other combinations are silent"""
    ours = [
        {"table": "t", "type": "delete", "changes": [{"column": 0, "old": 631}, {"column": 1, "old": "x"}]},
        {"table": "t", "type": "update", "changes": [{"column": 0, "old": 5}, {"column": 1, "old": "a", "new": "b"}]},
    ]
    theirs = [
        {
            "table": "t",
            "type": "update",
            "changes": [{"column": 0, "old": 631}, {"column": 1, "old": "x", "new": "field"}],
        },
        {"table": "t", "type": "update", "changes": [{"column": 0, "old": 7}, {"column": 1, "old": "q", "new": "r"}]},
        {"table": "u", "type": "update", "changes": [{"column": 0, "old": 631}, {"column": 1, "old": 1, "new": 2}]},
    ]
    assert dbsync._lost_field_updates(ours, theirs) == [("t", {0: 631}, [(1, "field")])]
    assert dbsync._lost_field_updates([], theirs) == []

    mocker.patch("dbsync._geodiff_list_changes_details", side_effect=[ours, theirs])
    with caplog.at_level(logging.WARNING):
        dbsync._report_lost_field_updates("base2our", "base2their")
    assert [r.message for r in caplog.records] == [
        "field update lost: table t row (column 0 = 631) was deleted in the database; "
        "the update from Mergin Maps (column 1: 'field') is dropped with the row"
    ]
