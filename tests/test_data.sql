INSERT INTO users (username, password, is_admin, lti_id, lti_consumer)
VALUES
    -- testuser:testpassword
    ('testuser', 'pbkdf2:sha256:260000$sGEKFQJ2UbGkHl1i$97032d72ed006da449a04a9e636cd4baba6133b6df3c5cdba09ddb0465c5e812', false, null, null),
    -- testadmin:testadminpassword
    ('testadmin', 'pbkdf2:sha256:260000$kIcsNgDntNvCz7D0$3c517ee1ebd6402852e47e0ed16827e99a3144ca27024634e6ada8cd836028a4', true, null, null),
    ('ltiuser1', null, false, 'consumer_1234_me@consumer.domain', 'consumer'),
    ('ltiuser2', null, false, 'consumer_1234_me@consumer.domain', 'consumer');

