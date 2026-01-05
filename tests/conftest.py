import datetime
import logging

import pytest
import quasardb

from qdb_prometheus_exporter.stats import fetch_qdb_stats

logger = logging.getLogger(__name__)


def config():
    return {
        "uri": {"insecure": "qdb://127.0.0.1:2836", "secure": "qdb://127.0.0.1:2838"}
    }


conn_params = {
    "insecure": {
        "uri": "qdb://127.0.0.1:2836",
    },
    "secure": {
        "uri": "qdb://127.0.0.1:2838",
        "user_security_file": "user_private.key",
        "cluster_public_key_file": "cluster_public.key",
    },
}


@pytest.fixture(scope="module")
def qdbd_settings():
    return conn_params


@pytest.fixture(
    scope="module", params=list(conn_params.values()), ids=list(conn_params.keys())
)
def qdbd_conn_args(request):
    return request.param


@pytest.fixture(scope="module")
def qdbd_connection(qdbd_conn_args):
    conn = quasardb.Cluster(**qdbd_conn_args)
    conn.purge_all(datetime.timedelta(minutes=1))
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def stats(qdbd_conn_args):
    yield fetch_qdb_stats(qdbd_conn_args, None, None, logger)
