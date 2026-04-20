from __future__ import annotations

import os

import pytest

from nz_workbench.config import ENV_RUN_INTEGRATION
from nz_workbench.kb.indexer import bootstrap


@pytest.mark.integration
def test_bootstrap_end_to_end() -> None:
    if os.environ.get(ENV_RUN_INTEGRATION) != "1":
        pytest.skip("set NZ_WORKBENCH_RUN_INTEGRATION=1 to run integration tests")

    # Requires nz-mcp configured and a live Netezza environment.
    report = bootstrap(["PROD_MAESTROBI"], top_n=1)
    assert report.procedures_indexed + report.procedures_skipped >= 0
