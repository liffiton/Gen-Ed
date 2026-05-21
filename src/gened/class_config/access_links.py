# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import base64
import datetime as dt
from dataclasses import dataclass
from hashlib import blake2b
from secrets import compare_digest, token_urlsafe
from sqlite3 import Row
from typing import Literal, Self

from flask import url_for

from gened.db import get_db
from gened.tz import date_is_past


class InvalidLinkKeyError(Exception):
    def __init__(self, key: str):
        super().__init__(f"Invalid link key: {key}")


def v2_generate_new_key() -> str:
    """ Generate a new, unique, unguessable link key.
    (Currently on version 2 of this feature.)
    """
    db = get_db()
    while True:
        link_key_secret = token_urlsafe(10)
        link_key = f"v2.{link_key_secret}"
        match_row = db.execute("SELECT 1 FROM classes_user WHERE link_key=?", [link_key]).fetchone()
        is_unique = not match_row
        if is_unique:
            break

    return link_key


def v2_get_hash(key: str, counter: int | None = None) -> str:
    if not key.startswith("v2."):
        raise InvalidLinkKeyError(key)

    secret = key[3:]
    if counter is not None:
        secret += f":{counter}"
    # 9 bytes provides plenty of entropy and an unpadded base64 encoding
    hash_bytes = blake2b(secret.encode(), digest_size=9).digest()
    return base64.urlsafe_b64encode(hash_bytes).decode()


def v2_check_hash(key: str, received: str, counter: int | None = None) -> bool:
    if not key.startswith("v2."):
        # only v2 uses hashes; do not hash otherwise
        return False
    correct = v2_get_hash(key, counter)
    return compare_digest(correct, received)


@dataclass(frozen=True, kw_only=True)
class AccessLink:
    class_id: int
    class_name: str
    key: str
    reg_expires: dt.date
    anon_login: bool

    @property
    def reg_state(self) -> Literal['disabled', 'enabled', 'date']:
        if date_is_past(self.reg_expires):
            return 'disabled'  # disabled or expired
        elif self.reg_expires == dt.date.max:
            return 'enabled'  # enabled w/ no expiration
        else:
            return 'date'  # will expire at some set date

    def get_url(self, *, counter: int | None = None, external: bool = True) -> str:
        if self.key.startswith("v1."):
            ident = self.key[3:]
            return url_for("classes.access_class_v1", class_ident=ident, _external=external)
        elif self.key.startswith("v2."):
            hash_val = v2_get_hash(self.key, counter)
            return url_for("classes.access_class_v2", counter=counter, class_id=self.class_id, hash_val=hash_val, _external=external)
        else:
            raise InvalidLinkKeyError(self.key)

    @classmethod
    def from_row(cls, row: Row) -> Self:
        """ Instantiate an AccessLink instance from an SQLite row.
        Row must be for a user-created class.
        """
        return cls(
            class_id = row['id'],
            class_name = row['name'],
            key = row['link_key'],
            reg_expires = row['link_reg_expires'],
            anon_login = row['link_anon_login'],
        )
