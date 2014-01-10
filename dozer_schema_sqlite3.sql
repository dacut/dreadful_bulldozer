BEGIN;

-- Domain tables -------------------------------------------------------------
CREATE TABLE dz_user_domains(
    user_domain_id INTEGER PRIMARY KEY NOT NULL, -- AUTOINCREMENT
    display_name VARCHAR(32) NOT NULL,
    description VARCHAR(1000) NOT NULL,
    domain_config TEXT);

INSERT INTO dz_user_domains(user_domain_id, display_name, description)
VALUES(0, 'local', 'Locally defined users and groups');

CREATE TABLE dz_node_types(
    node_type_id INTEGER PRIMARY KEY NOT NULL, -- AUTOINCREMENT
    node_type_name VARCHAR(32) NOT NULL);

INSERT INTO dz_node_types(node_type_id, node_type_name)
VALUES(0, 'folder');

INSERT INTO dz_node_types(node_type_id, node_type_name)
VALUES(1, 'notepage');

INSERT INTO dz_node_types(node_type_id, node_type_name)
VALUES(2, 'note');

-- Users and groups ----------------------------------------------------------
CREATE TABLE dz_users(
    user_id INTEGER PRIMARY KEY NOT NULL, -- AUTOINCREMENT
    user_domain_id INTEGER NOT NULL,
    user_name VARCHAR(256),
    home_folder VARCHAR(256),
    display_name VARCHAR(256),
    password_pbkdf2 CHAR(256),
    is_group INTEGER NOT NULL,
    is_administrator INTEGER NOT NULL,
    UNIQUE (user_domain_id, user_name),
    FOREIGN KEY (user_domain_id) REFERENCES dz_user_domains(user_domain_id));

CREATE INDEX i_dz_usr_domname
ON dz_users(user_domain_id, user_name);

CREATE TABLE dz_local_group_members(
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    administrator INTEGER NOT NULL,
    PRIMARY KEY (group_id, user_id),
    FOREIGN KEY (group_id) REFERENCES dz_users(user_id),
    FOREIGN KEY (user_id) REFERENCES dz_users(user_id));
CREATE INDEX i_dz_lgm_user_group
ON dz_local_group_members(user_id, group_id);

-- Create the system user
INSERT INTO dz_users(user_id, user_domain_id, user_name, display_name,
                     password_pbkdf2, is_group, is_administrator)
VALUES(0, 0, 'system', 'System', NULL, 'N', 'Y');

-- Create the all_users catch-all group
INSERT INTO dz_users(user_id, user_domain_id, user_name, display_name,
                     password_pbkdf2, is_group, is_administrator)
VALUES(1, 0, 'all_users', 'All users', NULL, 'Y', 'N');

INSERT INTO dz_local_group_members(group_id, user_id, administrator)
VALUES(1, 0, 'Y');

-- Nodes ---------------------------------------------------------------------
CREATE TABLE dz_nodes(
    node_id INTEGER PRIMARY KEY NOT NULL, -- AUTOINCREMENT
    node_type_id INTEGER NOT NULL,
    parent_node_id INTEGER,
    node_name VARCHAR(64) NOT NULL,
    is_active INTEGER NOT NULL,
    inherit_permissions INTEGER NOT NULL,
    FOREIGN KEY (node_type_id) REFERENCES dz_node_types(node_type_id),
    FOREIGN KEY (parent_node_id) REFERENCES dz_nodes(node_id),
    UNIQUE (parent_node_id, node_name));
    
CREATE INDEX i_dz_node_parent_id
ON dz_nodes(parent_node_id, node_name);

CREATE TABLE dz_access_control_entries(
    node_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    permissions INTEGER NOT NULL,
    PRIMARY KEY (node_id, user_id),
    FOREIGN KEY (node_id) REFERENCES dz_nodes(node_id),
    FOREIGN KEY (user_id) REFERENCES dz_users(user_id));

CREATE INDEX i_dz_nperm_userid
ON dz_access_control_entries(user_id, node_id);

CREATE TABLE dz_note_display_prefs(
    node_id INTEGER NOT NULL,
    hashtag VARCHAR(256),
    width_um INTEGER,
    height_um INTEGER,
    background_color VARCHAR(32),
    font_family VARCHAR(256),
    font_size_millipt INTEGER,
    font_weight VARCHAR(32),
    font_slant VARCHAR(32),
    font_color VARCHAR(32),
    PRIMARY KEY (node_id, hashtag),
    FOREIGN KEY (node_id) REFERENCES dz_nodes(node_id));

-- Folders -------------------------------------------------------------------
CREATE TABLE dz_folders(
    node_id INTEGER PRIMARY KEY NOT NULL,
    FOREIGN KEY (node_id) REFERENCES dz_nodes(node_id));

-- Create the root folder.
INSERT INTO dz_nodes(node_id, node_type_id, parent_node_id, node_name,
                     is_active, inherit_permissions)
VALUES(0, 0, NULL, '', 1, 0);

INSERT INTO dz_folders(node_id)
VALUES(0);

-- Grant all access to the system user.
-- 511 == 0x1ff == all permissions
INSERT INTO dz_access_control_entries(node_id, user_id, permissions)
VALUES(0, 0, 511);

-- Grant read, list, navigate access to everyone.
-- 50 == 0x32 == PERM_LIST_CONTENTS | PERM_NAVIGATE | PERM_READ_DOCUMENT
INSERT INTO dz_access_control_entries(node_id, user_id, permissions)
VALUES(0, 1, 50);

-- Create the /home folder.
INSERT INTO dz_nodes(node_id, node_type_id, parent_node_id, node_name,
                     is_active, inherit_permissions)
VALUES(1, 0, 0, 'home', 1, 1);

INSERT INTO dz_folders(node_id)
VALUES(1);

-- Notepages -----------------------------------------------------------------
CREATE TABLE dz_notepages(
    node_id INTEGER PRIMARY KEY NOT NULL,
    current_revision_id_sha256 CHAR(64),
    snap_to_grid INTEGER,
    grid_x_um INTEGER,
    grid_y_um INTEGER,
    grid_x_subdivisions INTEGER,
    grid_y_subdivisions INTEGER,
    FOREIGN KEY (node_id) REFERENCES dz_nodes(node_id),
    CHECK (grid_x_um IS NULL OR grid_x_um > 0),
    CHECK (grid_y_um IS NULL OR grid_y_um > 0),
    CHECK (grid_x_subdivisions IS NULL OR grid_x_subdivisions > 0),
    CHECK (grid_y_subdivisions IS NULL OR grid_y_subdivisions > 0));

CREATE TABLE dz_notepage_guides(
    node_id INTEGER PRIMARY KEY NOT NULL,
    orientation CHAR(1) NOT NULL,
    position_um INTEGER NOT NULL,
    FOREIGN KEY (node_id) REFERENCES dz_notepages(node_id),
    CHECK (orientation IN ('H', 'V')));

CREATE TABLE dz_notepage_revisions(
    node_id INTEGER NOT NULL,
    revision_id_sha256 CHAR(64) NOT NULL,
    previous_revision_id_sha256 CHAR(64),
    delta_to_previous TEXT,
    editor_user_id INTEGER NOT NULL,
    edit_time_utc TIMESTAMP(3),
    PRIMARY KEY (node_id, revision_id_sha256),
    UNIQUE (node_id, previous_revision_id_sha256),
    FOREIGN KEY (node_id) REFERENCES dz_notepages(node_id),
    FOREIGN KEY (previous_revision_id_sha256)
      REFERENCES dz_notepage_revisions(revision_id_sha256));

CREATE INDEX i_dz_nprev_prev
ON dz_notepage_revisions(node_id, previous_revision_id_sha256);

-- Notes ---------------------------------------------------------------------
CREATE TABLE dz_notes(
    node_id INTEGER PRIMARY KEY NOT NULL,
    contents_markdown TEXT,
    contents_hash_sha256 CHAR(64),
    x_pos_um INTEGER NOT NULL,
    y_pos_um INTEGER NOT NULL,
    width_um INTEGER NOT NULL,
    height_um INTEGER NOT NULL,
    z_index INTEGER NOT NULL,
    FOREIGN KEY (node_id) REFERENCES dz_nodes(node_id));

CREATE TABLE dz_note_hashtags(
    node_id INTEGER NOT NULL,
    hashtag VARCHAR(256) NOT NULL,
    PRIMARY KEY (node_id, hashtag),
    FOREIGN KEY (node_id) REFERENCES dz_notes(node_id));

-- Sessions ------------------------------------------------------------------
CREATE TABLE dz_sessions(
    session_id CHAR(64) PRIMARY KEY NOT NULL,
    user_id INTEGER NOT NULL,
    established_time_utc TIMESTAMP(3) NOT NULL,
    last_ping_time_utc TIMESTAMP(3) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES dz_users(user_id));
CREATE INDEX i_dz_sess_uid
ON dz_sessions(user_id, last_ping_time_utc DESC);

CREATE TABLE dz_session_secrets(
    session_secret_id INTEGER PRIMARY KEY NOT NULL,
    secret_key_base64 CHAR(44) NOT NULL,
    valid_from_utc TIMESTAMP NOT NULL,
    accept_until_utc TIMESTAMP);
CREATE INDEX i_dz_ssec_valid
ON dz_session_secrets(valid_from_utc DESC);

CREATE TABLE dz_session_notepages(
    session_id CHAR(64) NOT NULL,
    node_id INTEGER NOT NULL,
    revision_id_sha256 CHAR(64) NOT NULL,
    listener_ipv4 VARCHAR(15),
    listener_ipv6 VARCHAR(45),
    listener_port INTEGER,
    PRIMARY KEY (session_id, node_id),
    FOREIGN KEY (session_id) REFERENCES dz_sessions(session_id),
    FOREIGN KEY (node_id, revision_id_sha256)
      REFERENCES dz_notepage_revisions(node_id, revision_id_sha256));
CREATE INDEX i_dz_sessnp_node_id
ON dz_session_notpages(node_id);

COMMIT;
