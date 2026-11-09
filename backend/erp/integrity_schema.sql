CREATE TABLE IF NOT EXISTS erp_integrity_genesis(id INTEGER PRIMARY KEY CHECK(id=1),signature TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS erp_integrity(seq INTEGER PRIMARY KEY,document_id TEXT UNIQUE NOT NULL REFERENCES erp_documents(id),previous_signature TEXT NOT NULL,signature TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS erp_no_update_integrity BEFORE UPDATE ON erp_integrity BEGIN SELECT RAISE(ABORT,'Audit chain is append-only'); END;
CREATE TRIGGER IF NOT EXISTS erp_no_delete_integrity BEFORE DELETE ON erp_integrity BEGIN SELECT RAISE(ABORT,'Audit chain is append-only'); END;
CREATE TRIGGER IF NOT EXISTS erp_no_update_genesis BEFORE UPDATE ON erp_integrity_genesis BEGIN SELECT RAISE(ABORT,'Integrity baseline is immutable'); END;
CREATE TRIGGER IF NOT EXISTS erp_no_delete_genesis BEFORE DELETE ON erp_integrity_genesis BEGIN SELECT RAISE(ABORT,'Integrity baseline is immutable'); END;
