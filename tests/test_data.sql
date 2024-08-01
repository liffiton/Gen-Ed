-- SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

INSERT INTO consumers (id, lti_consumer, lti_secret, openai_key, model_id)
VALUES
    (1, 'consumer.domain', 'seecrits1', 'keeeez1', 1),
    (2, 'consumer.otherdomain', 'seecrits2', 'keeeez2', 2);

INSERT INTO classes (id, name, enabled)
VALUES
    (1, 'LERN101', 1),
    (2, 'USER001', 1),
    (3, 'USER002', 1),
    (4, 'USER003', 1);

INSERT INTO contexts (id, name, class_id, class_order, available, config)
VALUES
    (1, 'default', 1, 0, '0001-01-01', '{"tools": "Python\r\nC++\r\nOCaml", "avoid": "sum()\r\neval()\r\nzfill()\r\n+=\r\n"}'),
    (2, 'default', 2, 0, '0001-01-01', '{"tools": "Python", "avoid": ""}'),
    (3, 'default', 3, 0, '0001-01-01', '{"tools": "Python", "avoid": ""}'),
    (4, 'default', 4, 0, '0001-01-01', '{"tools": "Python", "avoid": ""}'),
    -- contexts for testuser's class:
    (5, 'default1', 2, 0, '0001-01-01', '{"tools": "Python", "avoid": ""}'),
    (6, 'default2', 2, 1, '0001-01-01', '{"tools": "Python", "avoid": ""}'),
    (7, 'default3', 2, 2, '0001-01-01', '{"tools": "Python", "avoid": ""}');

INSERT INTO classes_lti (class_id, lti_consumer_id, lti_context_id)
VALUES
    (1, 1, 'ctx_id');

INSERT INTO users (id, auth_provider, full_name, email, auth_name, is_admin, is_tester, query_tokens)
VALUES
    -- provider 1 = local
    (11, 1, null, null, 'testuser', false, true, 0),  -- testuser
    (12, 1, null, null, 'testadmin', true, true, 0),  -- testadmin
    (13, 1, null, 'instructor@example.com', 'testinstructor', false, true, 0),  -- testinstructor
    (14, 1, null, 'user2@example.com', 'testuser2', false, false, 0),  -- testuser2
    -- provider 2 = lti
    (21, 2, null, 'ltiuser1@domain.edu', null, false, false, 0),
    (22, 2, null, 'ltiuser2@domain.edu', null, false, false, 0),
    (23, 2, null, 'ltiuser3@domain.edu', null, false, false, 0);

INSERT INTO classes_user (class_id, openai_key, link_ident, link_reg_expires, creator_user_id, model_id)
VALUES
    (2, 'nope', 'reg_disabled', '0001-01-01', 11, 1),
    (3, 'nope', 'reg_expired', '2023-01-01', 11, 2),
    (4, 'nope', 'reg_enabled', '9999-12-31', 11, 2);

INSERT INTO auth_local (user_id, username, password)
VALUES
    -- Generate with werkzeug.security.generate_password_hash("password")
    -- testuser:testpassword
    (11, 'testuser', 'pbkdf2:sha256:260000$sGEKFQJ2UbGkHl1i$97032d72ed006da449a04a9e636cd4baba6133b6df3c5cdba09ddb0465c5e812'),
    -- testadmin:testadminpassword
    (12, 'testadmin', 'pbkdf2:sha256:260000$kIcsNgDntNvCz7D0$3c517ee1ebd6402852e47e0ed16827e99a3144ca27024634e6ada8cd836028a4'),
    -- testinstructor:testinstructorpassword
    (13, 'testinstructor', 'scrypt:32768:8:1$7rbBwwiV9lXPVVsz$721c41bdea527a131442f371d66e690bcfb51dad30857951f439a075fce01b3c4a9ddc84999480ebf42d25ad1d06d9d5420c1ca34fc8c273c0fe0671129759a6'),
    -- testuser2:testuser2password
    (14, 'testuser2', 'scrypt:32768:8:1$x6JpBekAfzh3gHMo$dc53d5e24c325a9917f9718bf3d822283f664bd9004a5f9c57621d75535566bccc2a587e75c37a1f87ab4dae9bd0f34d718b3abdcb88a2a3251acf028d0b28a8');

INSERT INTO auth_external (user_id, auth_provider, ext_id)
VALUES
    -- provider 2 = lti
    (21, 2, 'domain.edu_1234_ltiuser1@domain.edu'),
    (22, 2, 'domain.edu_5678_ltiuser2@domain.edu'),
    (23, 2, 'domain.edu_ABCD_ltiuser3@domain.edu');

INSERT INTO roles (id, user_id, class_id, role)
VALUES
    (1, 21, 1, 'student'), -- ltiuser1
    (2, 22, 1, 'student'), -- ltiuser2
    (3, 23, 1, 'instructor'), -- ltiuser3 is an instructor
    -- testuser, testadmin, and testinstructor are in class 2 -- but not testuser2
    (4, 11, 2, 'instructor'), -- testuser created the class
    (5, 12, 2, 'student'), -- testadmin is a student
    (6, 13, 2, 'student'); -- testinstructor is a student

INSERT INTO context_strings (id, ctx_str)
VALUES (1, 'context 1'), (2, 'context 2');

INSERT INTO queries (id, context_name, context_string_id, code, error, issue, response_json, response_text, helpful, user_id, role_id)
VALUES
    (1, 'ctx1', 1, 'code1', '', '', '{}', '{"main": "response1"}', 0, 21, 1),
    (2, 'ctx2', 2, 'code2', '', '', '{}', '{"main": "response2"}', 0, 22, 2),
    (3, 'ctx1', 1, 'code3', '', '', '{}', '{"main": "response3"}', 0, 21, 1),
    (4, 'ctx2', 2, 'code4', '', '', '{}', '{"main": "response4"}', 0, 23, 3);

INSERT INTO demo_links (id, name, enabled, expiration, tokens, uses)
VALUES
    (1, 'test_valid', 1, '2199-12-31', 3, 0),
    (2, 'test_disabled', 0, '2199-12-31', 10, 0),
    (3, 'test_expired', 1, '2000-01-01', 10, 0);

INSERT INTO chats (id, topic, context_name, context_string_id, chat_json, user_id, role_id)
VALUES
    (1, 'topic1', 'ctx1', 1, '[{"role": "user", "content": "user_msg_1"}, {"role": "assistant", "content": "assistant_msg_1"}]', 11, 4), -- testuser(instructor)
    (2, 'topic2', 'ctx2', 2, '[{"role": "user", "content": "user_msg_2"}, {"role": "assistant", "content": "assistant_msg_2"}]', 12, 5), -- testadmin(student)
    (3, 'topic3', 'ctx1', 1, '[{"role": "user", "content": "user_msg_3"}, {"role": "assistant", "content": "assistant_msg_3"}]', 14, NULL); -- testuser2

INSERT INTO experiments(id, name, description)
VALUES
    (1, 'chats_experiment', 'Experimental tutor chats feature.');

INSERT INTO experiment_class(experiment_id, class_id)
VALUES
    (1, 2);  -- experiment active in class 2 (where the test chats are registered (via roles 4, 5))
