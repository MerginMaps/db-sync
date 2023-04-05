import pytest

from dbsync import DbSyncError


def test_DbSyncError_password_print():
    password = "my_secret password 8417\\.*/"
    with pytest.raises(DbSyncError) as err:
        raise DbSyncError(f"string1 password=\"{password}\" string2")
    assert password not in str(err)
    assert DbSyncError.default_print_password in str(err)

    password = "my_secret password"
    with pytest.raises(DbSyncError) as err:
        raise DbSyncError(f"string1 password=\'{password}\' string2")
    assert password not in str(err)
    assert DbSyncError.default_print_password in str(err)

    password = "my_secret_password84189./+-"
    with pytest.raises(DbSyncError) as err:
        raise DbSyncError(f"string1 password={password} string2")
    assert password not in str(err)
    assert DbSyncError.default_print_password in str(err)
