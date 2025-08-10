# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from tests.conftest import AppClient


def test_class_config_view(instructor: AppClient) -> None:
    response = instructor.get('/instructor/config/')
    assert response.status_code == 200

    # default instructor client is logged in with class '' active
    assert "Configure Class: USER001" in response.text
    for header in ("Access", "Language Model", "Contexts"):
        assert f"{header}</h2>" in response.text
