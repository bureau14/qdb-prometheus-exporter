# qdb-prometheus-exporter

Exporter for QuasarDB metrics to Prometheus monitoring system.

## Installation

Currently, the exporter is not published to PyPI. You need to [build](#build-and-test-locally) it from source.

## Usage

### Running the exporter

#### Arguments

- `--cluster`: QuasarDB cluster URI. Default: `qdb://127.0.0.1:2836`
- `--cluster-public-key-file`: Path to cluster security file for secure clusters.
- `--user-security-file`: Path to user security file for secure clusters.
- `--filter-include`: Optional comma-separated list of regex patterns to filter metrics. Only metrics that match at least one of the patterns will be reported.
- `--filter-exclude`: Optional comma-separated list of regex patterns to filter metrics. Only metrics that contain none of the patterns will be reported.
- `--exporter-port`: Port on which the Prometheus exporter will listen. Default: `9000`

#### Insecure QuasarDB cluster configuration

```bash
qdb-prometheus-exporter --cluster qdb://127.0.0.1:2836
```

#### Secure QuasarDB cluster configuration

```bash
qdb-prometheus-exporter --cluster qdb://127.0.0.1:2836 --cluster-public-key-file /path/to/cluster_public_key.pem --user-security-file /path/to/user_security_file.key
```

### Connecting Prometheus to the exporter

This is example Prometheus server configuration to connect to the exporter running on `localhost:9000`:

```yaml
global:
  scrape_interval: 60s

scrape_configs:
  - job_name: "quasardb-cluster"
    static_configs:
      - targets: ["localhost:9000"]
```

### Gathering OS level metrics from QuasarDB server

For gathering OS level metrics from QuasarDB server, you can install and configure [`node_exporter`](https://github.com/prometheus/node_exporter) (on linux and other \*nix systems) or [`windows_exporter`](https://github.com/prometheus-community/windows_exporter) (on Windows) on the same host where QuasarDB server is running. Then, you can configure Prometheus to scrape metrics from the exporter as well.

```yaml
global:
  scrape_interval: 60s

scrape_configs:
  - job_name: "quasardb-cluster"
    static_configs:
      - targets: ["localhost:9000"]
  - job_name: "quasardb-cluster-os-metrics"
    static_configs:
      - targets: ["localhost:9182"]
```

## Naming Convention

Prometheus exporter transforms QuasarDB statistics names into Prometheus metric names to comply with OpenMetrics conventions:

- Dots (`.`) in QuasarDB statistic names are replaced with underscores (`_`).
- Units of measurement are appended as suffixes to the metric names (if not already present).
- Metric types are indicated by specific suffixes (`_total`, `_info`, etc.).

### Examples

| QuasarDB Statistic                   | Metric Type | Prometheus Metric Name               | Note                                                            |
| :----------------------------------- | :---------- | :----------------------------------- | :-------------------------------------------------------------- |
| `check.online`                       | Gauge       | `check_online_none`                  | Added unit (`none`)                                             |
| `network.partitions_count`           | Counter     | `network_partitions_count`           | No changes needed                                               |
| `requests.in_bytes`                  | Counter     | `requests_in_bytes_total`            | No changes needed                                               |
| `async_pipelines.pulled.total_bytes` | Counter     | `async_pipelines_pulled_bytes_total` | `total` removed, `_total` suffix appended                       |
| `perf.direct_get.ns`                 | Counter     | `perf_direct_get_nanoseconds_total`  | `_ns` removed, `_nanoseconds` unit and `_total` suffix appended |

Full list of QuasarDB metrics can be found in [QuasarDB documentation](https://doc.quasar.ai/master/administration/observability/metrics_reference.html#metrics-reference).

## Build and test locally

### Prerequisites

- Python >= 3.9

The instructions below have been verified to work on:

- Linux (Ubuntu, Debian)
- Windows 11

### QuasarDB tarball extraction

All QuasarDB APIs assume QuasarDB and associated utilities are extracted into the `qdb/` subdirectory.

Extract QuasarDB C API, utilities and server into qdb/

```
mkdir qdb
cd qdb
tar xf <archives>
cd ..
```

### QuasarDB Python API extraction

You should provide QuasarDB Python API wheel compatible with your platform to `qdb/` directory.

### Launch services

Use the scripts from the qdb-test-setup submodule to start and stop background services. These scripts are used across all QuasarDB API and tools projects:

```
$ scripts/tests/setup/start-services.sh

<.. snip ..>

qdbd secure and insecure were started properly.
```

## Run tests

Invoke the scripts that our continuous integration system uses directly:

```
$ bash scripts/teamcity/10.test.sh

<.. snip a lot ..>

========================================================================================= 650 passed, 0 skipped, 40 warnings in 87.43s (0:01:27) ==========================================================================================
$

```

This does the following out of the box:

- Create a virtualenv;
- Install dev requirements in virtualenv;
- Build the .whl file;
- Install the .whl file in virtualenv;
- Invoke pytest on the entire repository in the `tests/` subdirectory.

All arguments passed to this `10.test.sh` script are passed directly to pytest. For example, to enable verbose output and test a single file, you can use this:
