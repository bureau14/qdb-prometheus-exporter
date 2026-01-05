import logging
from typing import Generator

import quasardb.stats as qdbst
from prometheus_client.core import (
    CounterMetricFamily,
    GaugeMetricFamily,
    InfoMetricFamily,
)
from prometheus_client.registry import Collector

from .stats import fetch_qdb_stats


class QdbStatsCollector(Collector):
    def __init__(
        self,
        qdb_conn_args: dict,
        filter_include: list[str] | None,
        filter_exclude: list[str] | None,
        logger: logging.Logger,
    ):
        self.qdb_conn_args = qdb_conn_args
        self.filter_include = filter_include
        self.filter_exclude = filter_exclude
        self.logger = logger

        self.qdbst_types_to_prometheus_types: dict[
            qdbst.Type, type[GaugeMetricFamily | CounterMetricFamily | InfoMetricFamily]
        ] = {
            qdbst.Type.GAUGE: GaugeMetricFamily,
            qdbst.Type.ACCUMULATOR: CounterMetricFamily,
            qdbst.Type.LABEL: InfoMetricFamily,
        }

    def _parse_metric(
        self, labels: dict[str, str], metric_name: str, metric_info: dict
    ) -> GaugeMetricFamily | CounterMetricFamily | InfoMetricFamily | None:
        """
        Converts entry from QuasarDB statistics dictionary to Prometheus Metric.
        """
        metric_type = self.qdbst_types_to_prometheus_types.get(
            metric_info["type"], None
        )

        if metric_type is None:
            self.logger.error(
                "Unknown metric type for metric '%s': %s",
                metric_name,
                str(metric_info["type"]),
            )
            return None

        # Prometheus will add suffixes based on metric type (_total for counters, _info for info metrics, no suffix for gauges), units are also added as suffixes for gauges
        # e.g. metric with name `async_pipelines.pulled.total_count` will be transformed by Prometheus client internally to `async_pipelines_pulled_total_count_total`
        # We want to drop "total" and "count" from the name to avoid duplication
        # We also want to replace `.` with `_` to conform to OpenMetrics naming conventions (which Prometheus uses)
        # This means that stats names will differ slightly from the ones stored in QuasarDB, but will be consistent with Prometheus conventions
        metric_name = metric_name.replace(".", "_")
        metric_name = (
            metric_name.replace("total", "")
            .replace("_ns", "")
            .replace("count", "")
            .replace("__", "_")
            .rstrip("_")
        )

        # Info metrics dont have units in Prometheus, metric creation is different from others
        #
        # value for `documentation` is required by Prometheus but not available from QuasarDB stats module itself, we set it to an empty string
        if metric_type is InfoMetricFamily:
            metric = metric_type(
                name=metric_name,
                documentation="",
                labels=list(labels.keys()),
            )
            metric.add_metric(
                list(labels.values()), {"value": str(metric_info["value"])}
            )
        else:
            metric = metric_type(
                name=metric_name,
                documentation="",
                unit=metric_info["unit"].name.lower(),
                labels=list(labels.keys()),
            )
            metric.add_metric(list(labels.values()), metric_info["value"])
        return metric

    def _parse_metrics(
        self, qdb_metrics: dict
    ) -> Generator[
        GaugeMetricFamily | CounterMetricFamily | InfoMetricFamily | None, None, None
    ]:
        """
        Yields Prometheus metrics parsed from QuasarDB statistics dictionary.
        """
        for endpoint, metric_types in qdb_metrics.items():
            for metric_name, metric_info in metric_types["cumulative"].items():
                labels = {"endpoint": endpoint, "stat_type": "cumulative"}
                yield self._parse_metric(labels, metric_name, metric_info)

            for user_id, metrics in metric_types["by_uid"].items():
                for metric_name, metric_info in metrics.items():
                    labels = {
                        "endpoint": endpoint,
                        "stat_type": "by_uid",
                        "user_id": f"{user_id}",
                    }
                    yield self._parse_metric(labels, metric_name, metric_info)

    def collect(self):
        """
        Method called by Prometheus to collect metrics.
        Yields Prometheus metrics collected from QuasarDB.
        """

        try:
            stats = fetch_qdb_stats(
                self.qdb_conn_args,
                self.filter_include,
                self.filter_exclude,
                self.logger,
            )
            for metric in self._parse_metrics(stats):
                yield metric
        except Exception:
            self.logger.exception("Failed to collect metrics")
