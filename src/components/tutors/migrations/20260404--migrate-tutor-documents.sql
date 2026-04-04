-- SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

-- Migrate tutor config from single document to documents array
-- Old schema: { ..., "document_filename": "string", "document_text": "string", ... }
-- New schema: { ..., "documents": [{"filename": "string", "text": "string", "use_in": ["setup"]}], ... }

UPDATE tutors SET config = (
    SELECT
        -- Remove old fields and add new documents array
        json_remove(
            json_set(
                cfg,
                '$.documents',
                -- Build documents array
                CASE 
                    -- If old document fields exist and have content, transform them
                    WHEN doc_filename IS NOT NULL 
                         AND doc_filename != ''
                         AND doc_text IS NOT NULL
                         AND doc_text != ''
                    THEN json_array(
                        json_object(
                            'filename', doc_filename,
                            'text', doc_text,
                            'use_in', json_array('setup')
                         )
                    )
                    -- Otherwise, empty array
                    ELSE json_array()
                END
            ),
            '$.document_filename',
            '$.document_text'
        )
        AS new_config
    FROM (
        SELECT
            config AS cfg,
            json_extract(config, '$.document_filename') AS doc_filename,
            json_extract(config, '$.document_text') AS doc_text
        FROM tutors AS ttrs
        WHERE ttrs.rowid = tutors.rowid
    )
);

COMMIT;
