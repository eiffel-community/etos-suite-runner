# Copyright 2020-2021 Axis Communications AB.
#
# For a full list of individual contributors, please see the commit history.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""ETOS suite runner module."""
import logging
import os
from importlib.metadata import PackageNotFoundError, version

from etos_lib.logging.logger import setup_logging
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import (
    DEPLOYMENT_ENVIRONMENT,
    SERVICE_NAME,
    SERVICE_VERSION,
    OTELResourceDetector,
    ProcessResourceDetector,
    Resource,
    get_aggregated_resources,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

try:
    VERSION = version("etos_suite_runner")
except PackageNotFoundError:
    VERSION = "Unknown"

DEV = os.getenv("DEV", "false").lower() == "true"
ENVIRONMENT = "development" if DEV else "production"
os.environ["ENVIRONMENT_PROVIDER_DISABLE_LOGGING"] = "true"

LOGGER = logging.getLogger(__name__)

# Setting OTEL_COLLECTOR_HOST will override the default OTEL collector endpoint.
# This is needed because Suite Runner uses the cluster-level OpenTelemetry collector
# instead of a sidecar collector.
if os.getenv("OTEL_COLLECTOR_HOST"):
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = os.getenv("OTEL_COLLECTOR_HOST")
elif "OTEL_EXPORTER_OTLP_ENDPOINT" in os.environ:
    LOGGER.debug("Environment variable OTEL_EXPORTER_OTLP_ENDPOINT not used.")
    LOGGER.debug("To specify an OpenTelemetry collector host use OTEL_COLLECTOR_HOST.")
    del os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"]


if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    OTEL_RESOURCE = Resource.create(
        {
            SERVICE_NAME: "etos-suite-runner",
            SERVICE_VERSION: VERSION,
            DEPLOYMENT_ENVIRONMENT: ENVIRONMENT,
        },
    )

    OTEL_RESOURCE = get_aggregated_resources(
        [OTELResourceDetector(), ProcessResourceDetector()],
    ).merge(OTEL_RESOURCE)
    LOGGER.info(
        "Using OpenTelemetry collector: %s",
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
    )
    PROVIDER = TracerProvider(resource=OTEL_RESOURCE)
    EXPORTER = OTLPSpanExporter()
    PROCESSOR = BatchSpanProcessor(EXPORTER)
    PROVIDER.add_span_processor(PROCESSOR)
    trace.set_tracer_provider(PROVIDER)
    setup_logging("ETOS Suite Runner", VERSION, ENVIRONMENT, OTEL_RESOURCE)
else:
    setup_logging("ETOS Suite Runner", VERSION, ENVIRONMENT)
    LOGGER.info("OpenTelemetry not enabled. OTEL_COLLECTOR_HOST not set.")
