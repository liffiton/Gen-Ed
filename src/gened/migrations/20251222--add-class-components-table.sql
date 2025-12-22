-- SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

PRAGMA foreign_keys = OFF;

BEGIN;


-- Enable/disable components per-class (if no row here, use default state for the component)
CREATE TABLE class_components (
    class_id INTEGER NOT NULL,
    component_name TEXT NOT NULL,
    enabled BOOLEAN NOT NULL CHECK (enabled IN (0, 1)),
    created DATETIME DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (class_id, component_name),
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
);

-- Override default component enable to disable tutors by default in any
-- existing classes that were not in the chats_experiment experiment
INSERT INTO class_components (class_id, component_name, enabled)
SELECT classes.id, 'tutors', 0
FROM classes
WHERE classes.id NOT IN (
    SELECT class_id
    FROM experiment_class
    JOIN experiments ON experiment_class.experiment_id=experiments.id
    WHERE experiments.name='chats_experiment'
);


COMMIT;

PRAGMA foreign_keys = ON;
