import logging

import click
import prometheus_client
import uvicorn
from fastapi import FastAPI
from prometheus_client import make_asgi_app
from prometheus_client.core import REGISTRY

from .collector import QdbStatsCollector


def _set_up_prometheus_metrics_app(
    conn_args, filter_include, filter_exclude, logger: logging.Logger
):
    metrics_app = make_asgi_app()
    # By default prometheus client will send metrics about the Python process itself. We want to forward QuasarDB metrics only
    REGISTRY.unregister(prometheus_client.GC_COLLECTOR)
    REGISTRY.unregister(prometheus_client.PLATFORM_COLLECTOR)
    REGISTRY.unregister(prometheus_client.PROCESS_COLLECTOR)
    REGISTRY.register(
        QdbStatsCollector(conn_args, filter_include, filter_exclude, logger)
    )
    return metrics_app


app = FastAPI(debug=False)


@app.get("/health")
def health():
    return {"status": "ok"}


def _parse_list(x):
    """
    Parses a comma-separated string into a list.
    """

    if x is None or not x.strip():
        return None

    return [token.strip() for token in x.split(",") if token.strip()]


@click.command()
@click.option("--cluster", default="qdb://127.0.0.1:2836", type=str)
@click.option("--cluster-public-key-file", default=None, type=str)
@click.option("--user-security-file", default=None, type=str)
@click.option(
    "--filter-include",
    default="",
    type=str,
    help="Optional comma-separated list of regex patterns to filter metrics. Only metrics that match at least one of the patterns will be reported.",
)
@click.option(
    "--filter-exclude",
    default="",
    type=str,
    help="Optional comma-separated list of regex patterns to filter metrics. Only metrics that contain none of the patterns will be reported.",
)
@click.option("--exporter-port", default=9000, type=int)
@click.option("--listen-address", default="127.0.0.1", type=str, help="Address on which the exporter will listen.")
def start_server(
    cluster: str,
    cluster_public_key_file: str,
    user_security_file: str,
    filter_include: str,
    filter_exclude: str,
    exporter_port: int,
    listen_address: str,
):
    conn_args = {
        "uri": cluster,
    }

    if cluster_public_key_file and user_security_file:
        conn_args["cluster_public_key_file"] = cluster_public_key_file
        conn_args["user_security_file"] = user_security_file

    logger = logging.getLogger("uvicorn.error")
    metrics_app = _set_up_prometheus_metrics_app(
        conn_args, _parse_list(filter_include), _parse_list(filter_exclude), logger
    )
    app.mount("/metrics", metrics_app)
    uvicorn.run(app, host=listen_address, port=exporter_port)


if __name__ == "__main__":
    start_server()
