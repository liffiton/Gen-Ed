-- SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
--
-- SPDX-License-Identifier: AGPL-3.0-only

BEGIN;

-- Create experiments table
CREATE TABLE experiments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT
);

-- Create experiment_class table
CREATE TABLE experiment_class (
    experiment_id   INTEGER NOT NULL,
    class_id        INTEGER NOT NULL,
    PRIMARY KEY (experiment_id, class_id),
    FOREIGN KEY (experiment_id) REFERENCES experiments (id),
    FOREIGN KEY (class_id) REFERENCES classes (id)
);

-- Create indexes for experiment_class table
CREATE INDEX exp_crs_experiment_idx ON experiment_class(experiment_id);
CREATE INDEX exp_crs_class_idx ON experiment_class(class_id);

COMMIT;
