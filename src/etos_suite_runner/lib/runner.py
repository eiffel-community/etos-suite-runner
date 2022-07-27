# Copyright 2020-2022 Axis Communications AB.
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
"""ETOS suite runner executor."""
import logging
import time
from multiprocessing.pool import ThreadPool

from etos_suite_runner.lib.result_handler import ResultHandler
from etos_suite_runner.lib.executor import Executor
from etos_suite_runner.lib.exceptions import EnvironmentProviderException
from etos_suite_runner.lib.graphql import (
    request_environment_defined,
)


class SuiteRunner:  # pylint:disable=too-few-public-methods
    """Test suite runner.

    Splits test suites into sub suites based on number of products available.
    Starts ETOS test runner (ETR) and sends out a test suite finished.
    """

    lock = Lock()
    environment_provider_done = False
    error = False
    logger = logging.getLogger("ESR - Runner")

    def __init__(self, params, etos, context):
        """Initialize.

        :param params: Parameters object for this suite runner.
        :type params: :obj:`etos_suite_runner.lib.esr_parameters.ESRParameters`
        :param etos: ETOS library object.
        :type etos: :obj:`etos_lib.etos.ETOS`
        :param context: Context which triggered the runner.
        :type context: str
        """
        self.params = params
        self.etos = etos
        self.context = context
        self.sub_suites = {}

    def _release_environment(self, task_id):
        """Release an environment from the environment provider.

        :param task_id: Task ID to release.
        :type task_id: str
        """
        wait_generator = self.etos.http.wait_for_request(
            self.etos.debug.environment_provider, params={"release": task_id}
        )
        for response in wait_generator:
            if response:
                break

    def _run_etr(self, environment):
        """Trigger an instance of ETR.

        :param environment: Environment which to execute in.
        :type environment: dict
        """
        uri = environment["data"]["uri"]
        json_header = {"Accept": "application/json"}
        json_response = self.etos.http.wait_for_request(
            uri,
            headers=json_header,
        )
        suite = {}
        for suite in json_response:
            break
        else:
            raise Exception("Could not download sub suite instructions")

        executor = Executor(self.etos)
        executor.run_tests(suite)

    def _environments(self, suite_name):
        """Get environments for a specific test suite.

        :param suite_name: Since environment defined events have a name starting with 'suite_name'
                           we will use this as a part of getting the environments.
        :type suite_name: str
        :return: Test suite environments.
        :rtype: iterator
        """
        yielded = []
        status = {
            "status": "FAILURE",
            "error": "Couldn't collect any error information",
        }
        timeout = time.time() + self.etos.config.get("WAIT_FOR_ENVIRONMENT_TIMEOUT")
        while time.time() < timeout:
            time.sleep(1)
            status = self.params.environment_status
            self.logger.info(status)
            for environment in request_environment_defined(self.etos, self.context):
                if not environment["data"]["name"].startswith(suite_name):
                    continue
                if environment["meta"]["id"] in yielded:
                    continue
                yielded.append(environment["meta"]["id"])
                yield environment
            if status["status"] != "PENDING":
                break
        if status["status"] == "FAILURE":
            raise EnvironmentProviderException(
                status["error"], self.etos.config.get("task_id")
            )

    def start_sub_suites(self, suite):
        """Start up all sub suites within a TERCC suite.

        :param suite: TERCC suite to start up sub suites from.
        :type suite: dict
        """
        suite_name = suite.get("name")
        self.etos.events.send_announcement_published(
            "[ESR] Starting tests.",
            "Starting test suites on all checked out IUTs.",
            "MINOR",
            {"CONTEXT": self.context},
        )
        self.logger.info("Starting sub suites for %r", suite_name)
        started = []
        for environment in self._environments(suite_name):
            started.append(environment)

            self.logger.info("Triggering sub suite %r", environment["data"]["name"])
            self._run_etr(environment)
            self.logger.info("%r Triggered", environment["data"]["name"])
            time.sleep(1)
        self.etos.config.set("nbr_of_suites", len(started))
        self.logger.info("All %d sub suites for %r started", len(started), suite_name)

        self.etos.events.send_announcement_published(
            "[ESR] Waiting.",
            "Waiting for test suites to finish",
            "MINOR",
            {"CONTEXT": self.context},
        )
        return started

    def start_suite(self, suite):
        """Send test suite events and launch test runners.

        :param suite: Test suite to start.
        :type suite: dict
        """
        suite_name = suite.get("name")
        self.logger.info("Starting %s.", suite_name)

        categories = ["Regression test suite"]
        if self.params.product:
            categories.append(self.params.product)
        test_suite_started = self.etos.events.send_test_suite_started(
            suite_name,
            {"CONTEXT": self.context},
            categories=categories,
            types=["FUNCTIONAL"],
        )

        # TODO: This will conflict whenever we run more than one suite which
        # is not supported yet.
        self.etos.config.set("test_suite_started", test_suite_started.json)

        verdict = "INCONCLUSIVE"
        conclusion = "INCONCLUSIVE"
        description = ""

        result_handler = ResultHandler(self.etos, test_suite_started)
        try:
            self.start_sub_suites(suite)
            self.logger.info("Wait for test results.")
            self.result_handler.wait_for_test_suite_finished()
            verdict, conclusion, description = self.result_handler.test_results()
            time.sleep(5)
        except Exception as exc:
            conclusion = "FAILED"
            description = str(exc)
            raise
        finally:
            self.etos.events.send_test_suite_finished(
                test_suite_started,
                {"CONTEXT": self.context},
                outcome={
                    "verdict": verdict,
                    "conclusion": conclusion,
                    "description": description,
                },
            )

            # TODO: This should be released using the environment defined ID
            # when that is supported.
            task_id = self.etos.config.get("task_id")
            self.logger.info("Release test environment.")
            if task_id is not None:
                self._release_environment(task_id)
        self.logger.info("Test suite finished.")

    def start_suites_and_wait(self):
        """Get environments and start all test suites."""
        with ThreadPool() as pool:
            pool.map(self.start_suite, self.params.test_suite)
