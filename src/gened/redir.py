# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from urllib.parse import urljoin, urlparse

from flask import redirect, request, url_for
from werkzeug.wrappers.response import Response


def safe_redirect(target_url: str, default_endpoint: str) -> Response:
    """ Used for user-provided redirect URLs.  Redirect to the given URL if it
    is both not empty and is safe (within the current site) or to the default
    endpoint if not.

    Parameters
    ----------
    target_URL : str
      A user-provided redirect target URL.
    default_endpoint : str
      Flask's name for the endpoint to be used if the URL is unsafe.
    """
    ref_parse = urlparse(request.host_url)
    joined_url = urljoin(request.host_url, target_url)
    test_parse = urlparse(joined_url)
    is_safe = test_parse.scheme in ('http', 'https') and test_parse.netloc == ref_parse.netloc

    if target_url != "" and is_safe:
        return redirect(target_url)
    else:
        return redirect(url_for(default_endpoint))


def safe_redirect_next(default_endpoint: str) -> Response:
    """ Safely redirect to request.form['next'] or request.args['next'] if
    either exists and is safe.  Otherwise, redirect to the default endpoint.

    Parameters
    ----------
    default_endpoint : str
      Flask's name for the endpoint to be used if not using a given target.
    """
    if 'next' in request.form:
        return safe_redirect(request.form['next'], default_endpoint)
    elif 'next' in request.args:
        return safe_redirect(request.args['next'], default_endpoint)
    else:
        return redirect(url_for(default_endpoint))
