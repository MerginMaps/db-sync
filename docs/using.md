# Using DB Sync

## Useful command line options

- `config_file_name.yaml` The file name with path of yaml config can be provided. By default the `dbsync_daemon.py` loads `config.yaml` file.

- `--force-init` forces reinitialization of the sync. Drops dbsync schemas from database and the sync file and inits them all from scratch. This should be used to fix issues with dbsync init.

- `--single-run` instead of running the daemon indefinitely, performs just one single run. Such run consists of initialization, pull and push steps.

- `--skip-init` allows skipping the initialization of sync step. Should be only used if you know, what you are doing, otherwise issues are likely to occur.

- `--log-file` specify file to store log info into. If it is not set the log info will only be printed to the console.

- `--log-verbosity` use `errors` or `messages` to specify what should be logged. Default is `messages`.
