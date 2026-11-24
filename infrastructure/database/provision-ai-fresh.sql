\getenv ai_user AI_DB_USER
\getenv ai_password AI_DB_PASSWORD
\getenv ai_db POSTGRES_DB
CREATE ROLE :"ai_user" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD :'ai_password';
-- vector is installed by the administrator before unprivileged AI Flyway runs.
CREATE EXTENSION IF NOT EXISTS vector;
ALTER DATABASE :"ai_db" OWNER TO :"ai_user";
REVOKE ALL ON DATABASE :"ai_db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"ai_db" TO :"ai_user";
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
