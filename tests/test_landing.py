# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

def test_landing(client):
    '''Make sure we get the landing page from a basic root path request.'''
    response = client.get('/')
    assert "Automated Teaching Assistant" in response.text
