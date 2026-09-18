#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  --set=agent_password="$AGENT_DB_PASSWORD" --set=commerce_password="$COMMERCE_DB_PASSWORD" <<'SQL'
CREATE USER cf_agent PASSWORD :'agent_password';
CREATE USER cf_commerce PASSWORD :'commerce_password';
CREATE DATABASE cf_agent_v2 OWNER cf_agent;
CREATE DATABASE cf_commerce_v2 OWNER cf_commerce;
REVOKE CONNECT ON DATABASE cf_agent_v2 FROM PUBLIC;
REVOKE CONNECT ON DATABASE cf_commerce_v2 FROM PUBLIC;
GRANT CONNECT ON DATABASE cf_agent_v2 TO cf_agent;
GRANT CONNECT ON DATABASE cf_commerce_v2 TO cf_commerce;
SQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname cf_agent_v2 -c 'CREATE EXTENSION vector;'
