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
"""Tests for the OpenTelemetry context propagation of the ETOS suite runner."""

import os
import threading
from unittest import TestCase, mock

from opentelemetry import baggage, trace

from etos_suite_runner.lib.otel_tracing import get_current_context
from etos_suite_runner.lib.runner import SuiteRunner

TRACE_ID = "aaaabbbbccccddddeeeeffff00001111"
SPAN_ID = "1234567890abcdef"
TRACEPARENT = f"00-{TRACE_ID}-{SPAN_ID}-01"


class TestOpenTelemetryContext(TestCase):
    """Test the extraction of the OpenTelemetry context from environment variables."""

    def test_context_from_traceparent(self):
        """Test that the parent span is extracted from the TRACEPARENT environment variable.

        Approval criteria:
            - The span context shall have the trace and span IDs of the TRACEPARENT.
            - The baggage shall be extracted from the BAGGAGE environment variable.

        Test steps:
            1. Get the current context with TRACEPARENT and BAGGAGE set.
            2. Verify that the span context and baggage are extracted.
        """
        environment = {"TRACEPARENT": TRACEPARENT, "BAGGAGE": "testrun_id=abc"}
        with mock.patch.dict(os.environ, environment):
            ctx = get_current_context()
        span_context = trace.get_current_span(ctx).get_span_context()
        self.assertTrue(span_context.is_valid)
        self.assertTrue(span_context.is_remote)
        self.assertEqual(span_context.trace_id, int(TRACE_ID, 16))
        self.assertEqual(span_context.span_id, int(SPAN_ID, 16))
        self.assertEqual(baggage.get_baggage("testrun_id", ctx), "abc")

    def test_context_from_deprecated_otel_context(self):
        """Test that the parent span is extracted from the deprecated OTEL_CONTEXT variable.

        Approval criteria:
            - The span context shall have the trace and span IDs of the OTEL_CONTEXT traceparent.

        Test steps:
            1. Get the current context with OTEL_CONTEXT set.
            2. Verify that the span context is extracted.
        """
        environment = {"OTEL_CONTEXT": f"traceparent={TRACEPARENT}"}
        with mock.patch.dict(os.environ, environment):
            os.environ.pop("TRACEPARENT", None)
            ctx = get_current_context()
        span_context = trace.get_current_span(ctx).get_span_context()
        self.assertTrue(span_context.is_valid)
        self.assertEqual(span_context.trace_id, int(TRACE_ID, 16))

    def test_no_context(self):
        """Test that no parent span is extracted when no trace context is set.

        Approval criteria:
            - The span context shall be invalid.

        Test steps:
            1. Get the current context without TRACEPARENT or OTEL_CONTEXT set.
            2. Verify that the span context is invalid.
        """
        with mock.patch.dict(os.environ, {}):
            os.environ.pop("TRACEPARENT", None)
            os.environ.pop("OTEL_CONTEXT", None)
            ctx = get_current_context()
        self.assertFalse(trace.get_current_span(ctx).get_span_context().is_valid)


class TestSuiteRunnerContext(TestCase):
    """Test the OpenTelemetry context in the suite runner thread pool."""

    def test_run_attaches_suite_context(self):
        """Test that a test suite is started and finished within its OpenTelemetry context.

        Approval criteria:
            - The test suite shall be started, finished and released within the context of the
              carrier given to the test suite, also when running in a separate thread.

        Test steps:
            1. Run a test suite with a trace context carrier in a separate thread.
            2. Verify that start, finish and release were called within the trace context.
        """
        span_contexts = {}

        def record(name):
            """Record the current span context for a test suite method."""

            def _record(*_):
                """Store the current span context."""
                span_contexts[name] = trace.get_current_span().get_span_context()
                return ("PASSED", "SUCCESSFUL", "")

            return _record

        test_suite = mock.MagicMock()
        test_suite.otel_context_carrier = {"traceparent": TRACEPARENT}
        test_suite.start.side_effect = record("start")
        test_suite.results.side_effect = record("results")
        test_suite.finish.side_effect = record("finish")
        test_suite.release_all.side_effect = record("release_all")

        runner = SuiteRunner(mock.MagicMock(), mock.MagicMock())
        thread = threading.Thread(target=runner.run, args=(test_suite,))
        thread.start()
        thread.join()

        self.assertEqual(set(span_contexts), {"start", "results", "finish", "release_all"})
        for name, span_context in span_contexts.items():
            self.assertEqual(span_context.trace_id, int(TRACE_ID, 16), name)
            self.assertEqual(span_context.span_id, int(SPAN_ID, 16), name)
