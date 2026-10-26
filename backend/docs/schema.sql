-- DigiPass PostgreSQL schema (reference).
--
-- Generated from the SQLAlchemy models in backend/app/models/ with:
--     python -c "see backend/docs/README note"
--
-- It reproduces the schema the previous Prisma `db push` created, including
-- the five enum type names, so the FastAPI backend maps onto an existing
-- DigiPass database without any migration.
--
-- The application never runs this file: `CREATE_TABLES_ON_STARTUP` only emits
-- CREATE TABLE IF NOT EXISTS. Keep it as documentation / for provisioning a
-- fresh database.

CREATE TYPE "PassType" AS ENUM ('leave', 'market', 'other');

CREATE TYPE "PassStatus" AS ENUM ('pending', 'approved', 'rejected');

CREATE TYPE "LogAction" AS ENUM ('checked_in', 'checked_out', 'scan');

CREATE TYPE "StudentStatus" AS ENUM ('out', 'in', 'market');

CREATE TYPE "Role" AS ENUM ('student', 'warden', 'guard', 'admin', 'other');

CREATE TABLE users (
	id VARCHAR(25) NOT NULL, 
	password VARCHAR(255) NOT NULL, 
	first_name VARCHAR(20) NOT NULL, 
	last_name VARCHAR(20) NOT NULL, 
	role "Role" NOT NULL, 
	contact_details VARCHAR(50), 
	parent_email VARCHAR(100), 
	photo_url TEXT, 
	parents_phone VARCHAR(10), 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE leave_pass (
	pass_id SERIAL NOT NULL, 
	college_id VARCHAR(25) NOT NULL, 
	pass_type "PassType" NOT NULL, 
	leave_start DATE NOT NULL, 
	leave_end DATE NOT NULL, 
	pass_status "PassStatus" NOT NULL, 
	request_time TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	is_extension BOOLEAN NOT NULL, 
	remark TEXT, 
	PRIMARY KEY (pass_id), 
	FOREIGN KEY(college_id) REFERENCES users (id)
);

CREATE INDEX college_id ON leave_pass (college_id);

CREATE TABLE logs (
	scan_id SERIAL NOT NULL, 
	pass_id INTEGER NOT NULL, 
	staff_id VARCHAR(25) NOT NULL, 
	action "LogAction" NOT NULL, 
	student_status "StudentStatus" NOT NULL, 
	scan_time TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (scan_id), 
	FOREIGN KEY(pass_id) REFERENCES leave_pass (pass_id), 
	FOREIGN KEY(staff_id) REFERENCES users (id)
);

CREATE INDEX pass_id ON logs (pass_id);

CREATE INDEX staff_id ON logs (staff_id);
