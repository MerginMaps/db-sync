import pytest

from dbsync import DbSyncError


@pytest.mark.parametrize("password", ['password=\"my_secret password 8417\\.\"',
                                      'password=\'my_secret password\'',
                                      "password=my_secret_password84189./+-"
                                      ])
def test_DbSyncError_password_print(password: str):
    host = "host=\"localhost\""
    user = "user=user"

    conn_string = f"{user} {password} {host}"

    with pytest.raises(DbSyncError) as err:
        raise DbSyncError(conn_string)
    assert password not in str(err)
    assert user in str(err)
    assert host in str(err)
    assert DbSyncError.default_print_password in str(err.value)
