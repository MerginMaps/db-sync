# Development information

Information related to development of DB Sync.

## Running Tests

To run automatic tests:

```bash
cd mergin-db-sync
export TEST_DB_CONNINFO=<conninfo>          # connection info for DB
export TEST_MERGIN_URL=<url>                # testing server
export TEST_API_USERNAME=<username>
export TEST_API_PASSWORD=<pwd>
export TEST_API_WORKSPACE=<workspace>
pytest-3 test/
```

## Running the sync daemon in tmux

If we SSH somewhere and want to leave the daemon (`dbsync_daemon.py`) running there
even after logging out, we can use `tmux` utility. After starting SSH session, run
`tmux` which will start new terminal session where you can start the script
(`python3 dbsync_daemon.py`) and then with `Ctrl-B` followed by `d` leave the script
running in a detached tmux session. Logging out will not affect the daemon. At some
point later one can run `tmux attach` to bring the session back to the foreground.

## Releasing new version

1. Update `version.py` and `CHANGELOG.md`
2. Tag the new version in git repo
3. Build and upload the new container (both with the new version tag and as the latest tag)

```bash
docker build --no-cache -t lutraconsulting/mergin-db-sync .
docker tag lutraconsulting/mergin-db-sync lutraconsulting/mergin-db-sync:1.0.3
docker push lutraconsulting/mergin-db-sync:1.0.3
docker push lutraconsulting/mergin-db-sync:latest
```
