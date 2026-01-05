import copy
import logging
import random
import re
import uuid

import quasardb
import quasardb.stats as qdbst


def _do_filter_metrics(metrics: dict, fn):
    return {key: metrics[key] for key in metrics if fn(key)}


def _do_filter(stats: dict, fn):
    """
    Performs actual filtering of stats, keeping only those where fn(name) equals True
    """

    for node_id in stats:
        for group_id in stats[node_id]:
            if group_id == "cumulative":
                stats[node_id][group_id] = _do_filter_metrics(
                    stats[node_id][group_id], fn
                )
            elif group_id == "by_uid":
                for uid in stats[node_id][group_id]:
                    stats[node_id][group_id][uid] = _do_filter_metrics(
                        stats[node_id][group_id][uid], fn
                    )
            else:
                raise RuntimeError(
                    "Internal error: unrecognized stats group id: {}".format(group_id)
                )
    return stats


def filter_stats(stats: dict, include: list[str] | None, exclude: list[str] | None, logger: logging.Logger):
    logger.info("Filtering stats based on include/exclude filters")
    stats_ = copy.deepcopy(stats)

    if include is not None:
        # Returns `true` if any of the `include` patterns is found in the metric name.
        def _filter_include(metric_name):
            return any(
                pattern for pattern in include if re.search(pattern, metric_name)
            )

        stats_ = _do_filter(stats_, _filter_include)

    if exclude is not None:
        # Returns `false` if any of the `exclude` patterns is found in the metric name.
        def _filter_exclude(metric_name):
            return not any(
                pattern for pattern in exclude if re.search(pattern, metric_name)
            )

        stats_ = _do_filter(stats_, _filter_exclude)

    return stats_


def _check_node_online(conn: quasardb.Cluster, logger: logging.Logger):
    logger.info("Checking node online")

    ret = {}

    for endpoint in conn.endpoints():
        ret[endpoint] = 0  # pessimistic
        node = conn.node(endpoint)
        entry = node.integer("$qdb.statistics.startup_epoch")  # entry always exists

        try:
            entry.get()
            ret[endpoint] = 1
        except quasardb.Error as e:
            logger.error("[%s] Failed to read sample entry: %s", endpoint, str(e))

    return ret


def _check_node_writable(conn: quasardb.Cluster, logger: logging.Logger):
    logger.info("Checking node writable")
    key = f"_qdb_write_check_{uuid.uuid4().hex}"  # almost zero chance of collision
    value = random.randint(-9223372036854775808, 9223372036854775807)
    ret = {}

    for endpoint in conn.endpoints():
        ret[endpoint] = 0  # pessimistic
        node = conn.node(endpoint)
        entry = node.integer(key)

        try:
            entry.put(value)
            if entry.get() == value:
                ret[endpoint] = 1
        except quasardb.Error as e:
            logger.error("[%s] Failed to put/get test entry '%s': %s", endpoint, key, e)
        finally:
            try:
                entry.remove()
            except quasardb.AliasNotFoundError as e:
                logger.error(
                    "[%s] Failed to put/get test entry '%s': %s", endpoint, key, e
                )
            except quasardb.Error as e:
                logger.error(
                    "[%s] Failed to clean up test entry '%s': %s", endpoint, key, e
                )

    return ret


def _get_base_qdb_metrics(conn: quasardb.Cluster, logger: logging.Logger):
    """
    Returns basic QuasarDB metrics such as node online and writable status.
    Those metrics are most commonly used to determine QuasarDB cluster health.
    """
    logger.info("Getting base QuasarDB metrics")
    ret = {endpoint: {"cumulative": {}, "by_uid": {}} for endpoint in conn.endpoints()}
    online_stats = _check_node_online(conn, logger)
    writable_stats = _check_node_writable(conn, logger)

    for endpoint in conn.endpoints():
        ret[endpoint]["cumulative"]["check.online"] = {
            "value": online_stats.get(endpoint, 0),
            "type": qdbst.Type.GAUGE,
            "unit": qdbst.Unit.NONE,
        }
        ret[endpoint]["cumulative"]["node.writable"] = {
            "value": writable_stats.get(endpoint, 0),
            "type": qdbst.Type.GAUGE,
            "unit": qdbst.Unit.NONE,
        }

    return ret


def fetch_qdb_stats(
    qdb_conn_args: dict,
    include: list[str] | None,
    exclude: list[str] | None,
    logger: logging.Logger,
):
    base_stats, node_stats = {}, {}
    logger.info("Getting QuasarDB connection")
    try:
        with quasardb.Cluster(**qdb_conn_args) as conn:
            base_stats = _get_base_qdb_metrics(conn, logger)
            node_stats = qdbst.by_node(conn)
    except Exception as e:
        logger.error("Failed to fetch stats from QuasarDB: %s", str(e))
        raise

    # Merge base_stats into node_stats
    combined_stats = node_stats
    for endpoint, data in base_stats.items():
        if endpoint not in combined_stats:
            combined_stats[endpoint] = data
        else:
            if "cumulative" in data:
                combined_stats[endpoint].setdefault("cumulative", {}).update(
                    data["cumulative"]
                )
            if "by_uid" in data:
                combined_stats[endpoint].setdefault("by_uid", {}).update(data["by_uid"])

    return filter_stats(combined_stats, include, exclude, logger)
