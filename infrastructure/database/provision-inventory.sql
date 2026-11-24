\getenv inventory_db INVENTORY_DB
\getenv inventory_user INVENTORY_DB_USER
\getenv inventory_password INVENTORY_DB_PASSWORD

-- Refuse to adopt privileged roles or databases owned by anyone else.
SELECT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = :'inventory_user'
    AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR NOT rolcanlogin
         OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member = pg_roles.oid))
) OR EXISTS (
    SELECT 1 FROM pg_database WHERE datname = :'inventory_db'
    AND pg_get_userbyid(datdba) <> :'inventory_user'
) AS unsafe \gset
\if :unsafe
    DO $$ BEGIN
        RAISE EXCEPTION 'Refusing existing role privileges or database ownership; operator review required.';
    END $$;
\endif

SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
              :'inventory_user', :'inventory_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'inventory_user') \gexec
-- Existing role passwords are deliberately NOT reset on rerun.
SELECT format('CREATE DATABASE %I OWNER %I', :'inventory_db', :'inventory_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'inventory_db') \gexec
REVOKE ALL ON DATABASE :"inventory_db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"inventory_db" TO :"inventory_user";
