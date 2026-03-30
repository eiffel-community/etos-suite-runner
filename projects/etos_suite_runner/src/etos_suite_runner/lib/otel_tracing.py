#!/usr/bin/env python
# Copyright Axis Communications AB.
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
# -*- coding: utf-8 -*-
"""OpenTelemetry-related code."""

import logging

import opentelemetry
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.propagators._envcarrier import EnvironmentGetter
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

LOGGER = logging.getLogger(__name__)


class OpenTelemetryBase:
    """Base functionality for OpenTelemetry data collection."""

    # pylint: disable=too-few-public-methods
    @staticmethod
    def _record_exception(exc) -> None:
        """Record the given exception to the current OpenTelemetry span."""
        span = opentelemetry.trace.get_current_span()
        span.set_attribute("error.type", exc.__class__.__name__)
        span.record_exception(exc)
        span.set_status(opentelemetry.trace.Status(opentelemetry.trace.StatusCode.ERROR))


def get_current_context() -> opentelemetry.context.context.Context:
    """Get current context propagated via environment variables."""
    propagator = CompositePropagator(
        (
            TraceContextTextMapPropagator(),
            W3CBaggagePropagator(),
        )
    )
    return propagator.extract(carrier={}, getter=EnvironmentGetter())
