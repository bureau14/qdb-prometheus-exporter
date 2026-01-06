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
import re


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

        self.suffix_regex = re.compile(r"(^|_)(total|count|ns)(?=_|$)")

    def _conform_qdb_name_to_prometheus_name(self, name: str) -> str:
        """
        Converts QuasarDB statistic name to OpenMetrics/Prometheus compliant name.
        """
        # Prometheus will add suffixes based on metric type (_total for counters, _info for info metrics, no suffix for gauges), units are also added as suffixes for gauges
        # e.g. metric with name `async_pipelines.pulled.total_count` will be transformed by Prometheus client internally to `async_pipelines_pulled_total_count_total`
        # we want to avoid redundant suffixes in the final metric name. this will result is slightly different names compared to native QuasarDB stats, but is more compliant with Prometheus conventions.

        # 1. Replace dots with underscores to conform to OpenMetrics hierarchy convention
        name = name.replace(".", "_")
        # 2. Remove suffixes that will be added by Prometheus
        #    - total : Prometheus counter convention
        #    - count : histogram / summary aggregation
        #    - ns    : unit suffix (units belong in metadata, not names)
        name = self.suffix_regex.sub("", name)
        return name

    def _parse_qdb_statistics_entry(
        self, labels: dict[str, str], metric_name: str, metric_info: dict
    ) -> GaugeMetricFamily | CounterMetricFamily | InfoMetricFamily | None:
        """
        Converts single statistic from QuasarDB to Prometheus Metric.
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

        metric_name = self._conform_qdb_name_to_prometheus_name(metric_name)

        # Info metrics dont have units in Prometheus, metric creation is different from others
        #
        # value for `documentation` is required by Prometheus but not available from QuasarDB stats module itself, we set it to an empty string
        metric_kwargs = {
            "name": metric_name,
            "documentation": "",
            "labels": list(labels.keys()),
        }
        add_metric_kwargs = {
            "labels": list(labels.values()),
            "value": metric_info["value"],
        }

        # depending on metric type, adjust metric creation parameters
        if metric_type is InfoMetricFamily:
            add_metric_kwargs["value"] = {"value": metric_info["value"]}
        else:
            metric_kwargs["unit"] = metric_info["unit"].name.lower()

        metric = metric_type(**metric_kwargs)
        metric.add_metric(**add_metric_kwargs)
        return metric

    def _parse_qdb_statistics(
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
                yield self._parse_qdb_statistics_entry(labels, metric_name, metric_info)

            for user_id, metrics in metric_types["by_uid"].items():
                for metric_name, metric_info in metrics.items():
                    labels = {
                        "endpoint": endpoint,
                        "stat_type": "by_uid",
                        "user_id": f"{user_id}",
                    }
                    yield self._parse_qdb_statistics_entry(
                        labels, metric_name, metric_info
                    )

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
            for metric in self._parse_qdb_statistics(stats):
                yield metric
        except Exception:
            self.logger.exception("Failed to collect metrics")
