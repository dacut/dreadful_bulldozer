BEGIN;

CREATE TABLE dz_entity_domains(
    entity_domain TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL,
    CONSTRAINT pk_dz_ent_dom PRIMARY KEY (entity_domain));

INSERT INTO dz_entity_domains(entity_domain, display_name, description)
VALUES('dozer_user', 'Local Dozer user', 'Local Dozer user');

INSERT INTO dz_entity_domains(entity_domain, display_name, description)
VALUES('dozer_group', 'Local Dozer group', 'Local Dozer group');

INSERT INTO dz_entity_domains(entity_domain, display_name, description)
VALUES('auth_users', 'All authenticated users', 'All authenticated users');

INSERT INTO dz_entity_domains(entity_domain, display_name, description)
VALUES('users', 'All users', 'All users');

INSERT INTO dz_entity_domains(entity_domain, display_name, description)
VALUES('system', 'System', 'System');

CREATE TABLE dz_documents(
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_document_id INTEGER,
    document_type TEXT NOT NULL,
    document_name TEXT NOT NULL,
    owner_entity_domain TEXT NOT NULL,
    owner_entity_id TEXT,
    inherit_permissions TEXT,
    CONSTRAINT uk_dz_docs_name UNIQUE (document_name),
    CONSTRAINT fk_dz_docs_parent FOREIGN KEY (parent_document_id)
    REFERENCES dz_documents(document_id),
    CONSTRAINT fk_dz_docs_owner FOREIGN KEY (owner_entity_domain)
    REFERENCES dz_entity_domains(entity_domain),
    CONSTRAINT ck_dz_docs_type CHECK (document_type IN ('folder', 'notepage')),
    CONSTRAINT ck_dz_docs_inherit CHECK (inherit_permissions IN ('Y', 'N')));
CREATE INDEX i_dz_doc_name
ON dz_documents(document_name);

CREATE INDEX i_dz_doc_parent_id
ON dz_documents(parent_document_id, document_name);

INSERT INTO dz_documents(
    document_id, document_name, parent_document_id, owner_entity_domain,
    owner_entity_id, document_type, inherit_permissions)
VALUES(1, '', null, 'system', 'system', 'folder', 'N');

INSERT INTO dz_documents(
    document_id, document_name, parent_document_id, owner_entity_domain,
    owner_entity_id, document_type, inherit_permissions)
VALUES(2, 'tmp', 1, 'system', 'system', 'folder', 'N');

CREATE TABLE dz_document_permissions(
    document_id INTEGER NOT NULL,
    list_index INTEGER NOT NULL,
    entity_domain TEXT NOT NULL,
    entity_id TEXT,
    permissions TEXT,
    CONSTRAINT pk_dz_doc_perms PRIMARY KEY (document_id, list_index),
    CONSTRAINT uk_dz_doc_perms_docinfo UNIQUE (
        document_id, entity_domain, entity_id),
    CONSTRAINT fk_dz_doc_perm_docid FOREIGN KEY (document_id)
    REFERENCES dz_documents(document_id),
    CONSTRAINT fk_dz_doc_perm_dom FOREIGN KEY (entity_domain)
    REFERENCES dz_entity_domains(entity_domain));

INSERT INTO dz_document_permissions(document_id, list_index, entity_domain,
       entity_id, permissions)
VALUES(1, 0, 'users', null, 'LNS');

INSERT INTO dz_document_permissions(document_id, list_index, entity_domain,
       entity_id, permissions)
VALUES(2, 0, 'users', null, 'N');

CREATE TABLE dz_sessions(
    session_id INTEGER PRIMARY KEY,
    user_entity_domain TEXT NOT NULL,
    user_entity_id TEXT NOT NULL,
    established_time_utc INTEGER NOT NULL,
    last_ping_time_utc INTEGER NOT NULL,
    CONSTRAINT fk_ses_ent_dom FOREIGN KEY (user_entity_domain)
    REFERENCES dz_entity_domains(entity_domain));

CREATE INDEX i_dz_sess_time
ON dz_sessions(
    last_ping_time_utc ASC);

CREATE TABLE dz_document_revisions(
    document_id INTEGER NOT NULL,
    revision_id INTEGER NOT NULL,
    delta_to_previous TEXT,
    editor_entity_domain TEXT NOT NULL,
    editor_entity_id TEXT NOT NULL,
    edit_time_utc INTEGER NOT NULL,
    CONSTRAINT pk_dz_doc_rev PRIMARY KEY (document_id, revision_id));

CREATE TABLE dz_session_documents(
    session_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    revision_id INTEGER NOT NULL,
    CONSTRAINT pk_dz_ses_doc PRIMARY KEY (session_id, document_id),
    CONSTRAINT fk_dz_ses_doc_ses_id FOREIGN KEY (session_id)
    REFERENCES dz_sessions(session_id),
    CONSTRAINT fk_dz_ses_doc_doc_rev FOREIGN KEY (document_id, revision_id)
    REFERENCES dz_document_revisions(document_id, revision_id));

CREATE TABLE dz_document_display_prefs(
    document_id INTEGER NOT NULL,
    width_pixels INTEGER,
    height_pixels INTEGER,
    background_color TEXT,
    font_family TEXT,
    font_size_millipt INTEGER,
    font_weight TEXT,
    font_slant TEXT,
    font_color TEXT,
    CONSTRAINT pk_dz_doc_disp_prefs PRIMARY KEY (document_id),
    CONSTRAINT fk_dz_doc_disp_prefs_doc_id FOREIGN KEY (document_id)
    REFERENCES dz_documents(document_id));

CREATE TABLE dz_document_hashtag_prefs(
    document_id INTEGER NOT NULL,
    list_index INTEGER NOT NULL,
    hashtag TEXT NOT NULL,
    background_color TEXT,
    font_family TEXT,
    font_size_millipt INTEGER,
    font_weight TEXT,
    font_slant TEXT,
    font_color TEXT,
    CONSTRAINT pk_dz_doc_ht_prefs PRIMARY KEY (document_id, list_index),
    CONSTRAINT uk_dz_doc_ht_prefs UNIQUE (document_id, hashtag),
    CONSTRAINT fk_dz_doc_ht_prefs_doc_id FOREIGN KEY (document_id)
    REFERENCES dz_documents(document_id));

CREATE TABLE dz_notes(
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    contents_markdown TEXT,
    x_pos_pixels INTEGER,
    y_pos_pixels INTEGER,
    width_pixels INTEGER,
    height_pixels INTEGER,
    background_color TEXT,
    font_family TEXT,
    font_size_millipt INTEGER,
    font_weight TEXT,
    font_slant TEXT,
    font_color TEXT,
    CONSTRAINT fk_dz_notes_doc_id FOREIGN KEY (document_id)
    REFERENCES dz_documents(document_id));

CREATE INDEX i_dz_note_doc_id
ON dz_notes(document_id);


CREATE TABLE dz_note_hashtags(
    note_id INTEGER NOT NULL,
    hashtag TEXT NOT NULL,
    CONSTRAINT pk_dz_note_ht PRIMARY KEY (note_id, hashtag),
    CONSTRAINT fk_dz_note_ht_note_id FOREIGN KEY (note_id)
    REFERENCES dz_notes(note_id));

CREATE TABLE dz_local_users(
    username TEXT PRIMARY KEY,
    password_pbkdf2 TEXT NOT NULL);

CREATE TABLE dz_local_groups(
    groupname TEXT PRIMARY KEY);

CREATE TABLE dz_local_group_members(
    groupname TEXT NOT NULL,
    username TEXT NOT NULL,
    CONSTRAINT pk_dz_loc_grp_mem PRIMARY KEY (groupname, username),
    CONSTRAINT fk_dz_loc_grp_mem_grp FOREIGN KEY (groupname)
    REFERENCES dz_local_groups(groupname),
    CONSTRAINT fk_dz_loc_grp_mem_user FOREIGN KEY (username)
    REFERENCES dz_local_users(username));

CREATE INDEX i_dz_loc_grp_mem_user
ON dz_local_group_members(username, groupname);

COMMIT;

