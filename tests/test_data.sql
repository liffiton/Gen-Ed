INSERT INTO consumers (id, lti_consumer, lti_secret, openai_key)
VALUES
    (1, 'consumer.domain', 'seecrits1', 'keeeez1'),
    (2, 'consumer.otherdomain', 'seecrits2', 'keeeez2');

INSERT INTO classes (id, name, enabled, config)
VALUES
    (1, 'LERN101', 1, '{"default_lang": "python", "avoid": "sum()\r\neval()\r\nzfill()\r\n+=\r\n"}');

INSERT INTO classes_lti (class_id, lti_consumer_id, lti_context_id)
VALUES
    (1, 1, 'ctx_id');

INSERT INTO users (id, auth_provider, full_name, email, auth_name, is_admin, is_tester, query_tokens)
VALUES
    -- provider 1 = local
    (11, 1, null, 'testuser', null, false, true, 0),  -- testuser
    (12, 1, null, 'testadmin', null, true, true, 0),  -- testadmin
    -- provider 2 = lti
    (13, 2, null, 'ltiuser1@domain.edu', null, false, false, 0),
    (14, 2, null, 'ltiuser2@domain.edu', null, false, false, 0),
    (15, 2, null, 'ltiuser3@domain.edu', null, false, false, 0);

INSERT INTO auth_local (user_id, username, password)
VALUES
    -- testuser:testpassword
    (11, 'testuser', 'pbkdf2:sha256:260000$sGEKFQJ2UbGkHl1i$97032d72ed006da449a04a9e636cd4baba6133b6df3c5cdba09ddb0465c5e812'),
    -- testadmin:testadminpassword
    (12, 'testadmin', 'pbkdf2:sha256:260000$kIcsNgDntNvCz7D0$3c517ee1ebd6402852e47e0ed16827e99a3144ca27024634e6ada8cd836028a4');

INSERT INTO auth_external (user_id, auth_provider, ext_id)
VALUES
    -- provider 2 = lti
    (13, 2, 'domain.edu_1234_ltiuser1@domain.edu'),
    (14, 2, 'domain.edu_5678_ltiuser2@domain.edu'),
    (15, 2, 'domain.edu_ABCD_ltiuser3@domain.edu');

INSERT INTO roles (id, user_id, class_id, role)
VALUES
    (1, 13, 1, 'student'), -- ltiuser1
    (2, 14, 1, 'student'), -- ltiuser2
    (3, 15, 1, 'instructor'); -- ltiuser3 is an instructor

INSERT INTO queries (id, language, code, error, issue, response_json, response_text, helpful, user_id, role_id)
VALUES
    (1, 'python', 'code1', '', '', '{}', '{"main": "response1"}', 0, 13, 1),
    (2, 'python', 'code2', '', '', '{}', '{"main": "response2"}', 0, 14, 2),
    (3, 'python', 'code3', '', '', '{}', '{"main": "response3"}', 0, 13, 1),
    (4, 'python', 'code4', '', '', '{}', '{"main": "response4"}', 0, 15, 3);

INSERT INTO demo_links (id, name, enabled, expiration, tokens, uses)
VALUES
    (1, 'test_valid', 1, '2199-12-31', 3, 0),
    (2, 'test_disabled', 0, '2199-12-31', 10, 0),
    (3, 'test_expired', 1, '2000-01-01', 10, 0);

INSERT INTO tutor_chats (id, topic, context, chat_json, user_id, role_id)
VALUES
    (1, 'topic1', 'context1', '[{"role": "user", "content": "user_msg_1"}, {"role": "assistant", "content": "assistant_msg_1"}]', 11, NULL),
    (2, 'topic2', 'context2', '[{"role": "user", "content": "user_msg_2"}, {"role": "assistant", "content": "assistant_msg_2"}]', 12, NULL);
