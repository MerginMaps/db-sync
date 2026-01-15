pyinstaller ../dbsync_daemon.py ^
	-c ^
	--noconfirm ^
	--add-binary="./windows_binaries/geodiff.exe;lib" ^
	--hidden-import dynaconf ^
	--collect-all mergin ^
	--clean ^
	-F