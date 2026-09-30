import argparse
import datetime
import os

import pytest
from mergin import MerginClient

import dbsync
import dbsync_daemon
from config import config

from .conftest import DB_CONNINFO, TEST_DATA_DIR, init_sync_from_geopackage


class StopDaemon(Exception):
    """Raised from mocked sleep to break out of the infinite daemon loop"""


@pytest.fixture
def run_daemon(mocker):
    """Returns function running the daemon loop until it exits or sleeps `iterations` times.

    Sleeping is mocked, the function returns list of the requested sleep times and whether the daemon exited."""

    def run(
        iterations=100,
        force_init=False,
        skip_init=False,
        sleep_time=10,
        max_retries=10,
        send_notifications=False,
        on_sleep=None,
    ):
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)
            if on_sleep:
                on_sleep(len(sleeps))
            if len(sleeps) >= iterations:
                raise StopDaemon()

        mocker.patch("dbsync_daemon.time.sleep", side_effect=fake_sleep)
        args = argparse.Namespace(force_init=force_init, skip_init=skip_init)
        try:
            dbsync_daemon.run_daemon(args, sleep_time, max_retries, send_notifications)
        except StopDaemon:
            return sleeps, False
        except SystemExit:
            return sleeps, True

    return run


@pytest.fixture
def dbsync_mocks(mocker):
    """Mocks Mergin client creation, dbsync steps and notification emails"""
    mc = mocker.MagicMock()
    mc._auth_session = {"expire": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=12)}
    mocker.patch("dbsync_daemon.config").notification = {}
    return mocker.Mock(
        mc=mc,
        create_client=mocker.patch("dbsync.create_mergin_client", return_value=mc),
        clean=mocker.patch("dbsync.dbsync_clean"),
        init=mocker.patch("dbsync.dbsync_init"),
        pull=mocker.patch("dbsync.dbsync_pull"),
        push=mocker.patch("dbsync.dbsync_push"),
        send_email=mocker.patch("dbsync_daemon.send_email"),
    )


def test_retry_wait_time():
    """Wait time doubles with each consecutive failure, starting at sleep time and capped at MAX_RETRY_WAIT (or sleep time if longer)"""
    assert [dbsync_daemon.retry_wait_time(10, f) for f in range(1, 9)] == [10, 20, 40, 80, 160, 320, 600, 600]
    # sleep time longer than the max retry wait is respected
    assert dbsync_daemon.retry_wait_time(3600, 5) == 3600
    # no overflow with many failures
    assert dbsync_daemon.retry_wait_time(10, 10**6) == dbsync_daemon.MAX_RETRY_WAIT


def test_daemon_startup_is_retried(run_daemon, dbsync_mocks):
    """Failed login and init are retried in the same process with backoff: login is repeated only until it succeeds,
    --force-init cleaning is done only once and regular sleep time is used again once the sync succeeds"""
    dbsync_mocks.create_client.side_effect = [dbsync.DbSyncError("login failed")] * 2 + [dbsync_mocks.mc]
    dbsync_mocks.init.side_effect = [dbsync.DbSyncError("init failed")] * 2 + [None]

    sleeps, exited = run_daemon(iterations=6, force_init=True)

    assert not exited
    assert sleeps == [10, 20, 40, 80, 10, 10]
    assert dbsync_mocks.create_client.call_count == 3
    dbsync_mocks.clean.assert_called_once()
    assert dbsync_mocks.init.call_count == 3
    assert dbsync_mocks.pull.call_count == 2


def test_daemon_keeps_running_after_start(run_daemon, dbsync_mocks):
    """Sync errors after a successful start (e.g. server unavailable) never make the daemon exit, only back off.
    A single unexpected error does not stop it either. No new login is done in any case."""
    dbsync_mocks.pull.side_effect = (
        [None] + [dbsync.DbSyncError("server unavailable")] * 8 + [RuntimeError("boom")] + [None]
    )

    sleeps, exited = run_daemon(iterations=11, max_retries=2)

    assert not exited
    assert sleeps == [10, 10, 20, 40, 80, 160, 320, 600, 600, 600, 10]
    dbsync_mocks.create_client.assert_called_once()
    dbsync_mocks.init.assert_called_once()
    assert dbsync_mocks.push.call_count == 2


@pytest.mark.parametrize(
    "failing_step, errors, max_retries, expected_sleeps, expected_exit",
    [
        ("init", [dbsync.DbSyncError("init failed")] * 4, 3, [10, 20, 40], True),
        ("pull", [None] + [RuntimeError("boom")] * 3, 2, [10, 10, 20], True),
        ("create_client", dbsync.DbSyncError("login failed"), 0, [10, 20, 40, 80, 160, 320] + [600] * 14, False),
    ],
    ids=["startup-failures", "unexpected-errors", "never-exit"],
)
def test_daemon_gives_up_after_max_retries(
    run_daemon, dbsync_mocks, failing_step, errors, max_retries, expected_sleeps, expected_exit
):
    """Daemon exits after `max_retries` consecutive failed retries of the start or of unexpected errors
    (never with max_retries 0). Notification email is always sent when giving up, regardless of the minimal
    email interval."""
    getattr(dbsync_mocks, failing_step).side_effect = errors

    # daemon that should not exit is stopped after the expected number of sleeps
    iterations = 100 if expected_exit else len(expected_sleeps)
    sleeps, exited = run_daemon(iterations=iterations, max_retries=max_retries, send_notifications=True)

    assert exited == expected_exit
    assert sleeps == expected_sleeps
    if expected_exit:
        # first failure and giving up, the ones in between are suppressed by the minimal email interval
        assert dbsync_mocks.send_email.call_count == 2
        assert dbsync_mocks.send_email.call_args.args[0].startswith(f"Giving up after {max_retries} retries")
    else:
        dbsync_mocks.send_email.assert_called_once()


def test_daemon_recovers_from_init_failure(mc: MerginClient, run_daemon, mocker):
    """Integration test with real server and database: init fails on database connection for two attempts,
    the daemon retries without logging in again and continues syncing once the database connection is fixed."""
    init_sync_from_geopackage(mc, "test_daemon_recovery", os.path.join(TEST_DATA_DIR, "base.gpkg"))
    connection = dict(config.connections[0])
    config.update({"CONNECTIONS": [{**connection, "conn_info": DB_CONNINFO + " password=wrong"}]})

    def fix_db_connection(sleep_count):
        if sleep_count == 2:
            config.update({"CONNECTIONS": [connection]})

    login = mocker.spy(MerginClient, "login")
    pull = mocker.spy(dbsync, "dbsync_pull")

    sleeps, exited = run_daemon(iterations=4, max_retries=5, on_sleep=fix_db_connection)

    assert not exited
    assert sleeps == [10, 20, 10, 10]
    assert login.call_count == 1
    assert pull.call_count == 2
