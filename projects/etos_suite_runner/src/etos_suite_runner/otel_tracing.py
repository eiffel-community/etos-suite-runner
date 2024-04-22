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
import os

import opentelemetry
from opentelemetry.propagators.textmap import Getter, Setter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


LOGGER = logging.getLogger(__name__)


class EnvVarContextGetter(Getter):
    def get(self, carrier, key):
        value = os.getenv(carrier)
        if value is not None:
            pairs = value.split(',')
            for pair in pairs:
                k, v = pair.split('=', 1)
                if k == key:
                    return [v]
        return []

    def keys(self, carrier):
        value = os.getenv(carrier)
        if value is not None:
            return [pair.split('=')[0] for pair in value.split(',') if '=' in pair]
        return []

def get_current_context() -> opentelemetry.context.context.Context:
    """Get current context propagated via environment variable OTEL_CONTEXT."""
    LOGGER.info("Current OpenTelemetry context env: %s", os.environ.get("OTEL_CONTEXT"))
    propagator = TraceContextTextMapPropagator()
    ctx = propagator.extract(carrier="OTEL_CONTEXT", getter=EnvVarContextGetter())
    LOGGER.info("Current OpenTelemetry context %s", ctx)
    return ctx


def get_current_context_old() -> opentelemetry.context.context.Context:
    """Get current context (propagated via environment variable OTEL_CONTEXT)."""
    carrier = {}
    LOGGER.info("Current OpenTelemetry context env: %s", os.environ.get("OTEL_CONTEXT"))
    for kv in os.environ.get("OTEL_CONTEXT", "").split(","):
        if kv:
            k, v = kv.split("=", 1)
            carrier[k] = v
    ctx = opentelemetry.propagate.extract(carrier)
    LOGGER.info("Current OpenTelemetry context %s", ctx)
    return ctx
