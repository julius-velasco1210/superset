-- Dummy data for the "Taylor Mobile POC" dashboard (made-up names, local POC only).
-- Load: docker exec -i superset-mobile-db-1 psql -U examples -d examples < poc/taylor_dummy_data.sql

BEGIN;

DROP TABLE IF EXISTS poc_emissions;
DROP TABLE IF EXISTS poc_assets;
DROP TABLE IF EXISTS poc_water;

CREATE TABLE poc_emissions (
    company      TEXT NOT NULL,
    division     TEXT NOT NULL,
    region       TEXT NOT NULL,
    scope        TEXT NOT NULL,
    year         INTEGER NOT NULL,
    emissions_kg DOUBLE PRECISION NOT NULL
);

CREATE TABLE poc_assets (
    asset_id TEXT PRIMARY KEY,
    company  TEXT NOT NULL
);

CREATE TABLE poc_water (
    company        TEXT NOT NULL,
    year           INTEGER NOT NULL,
    water_emission DOUBLE PRECISION NOT NULL,
    water_usage_m3 DOUBLE PRECISION NOT NULL
);

SELECT setseed(0.42);

-- One dominant company, mostly Scope 1, ~10% Singapore, one main division.
WITH
companies(company, cw) AS (VALUES
    ('Northwind Holdings', 1.00),
    ('Bluecrest Industries', 0.11),
    ('Harbor Supply Co', 0.02),
    ('Meridian Logistics', 0.005),
    ('Solace Energy Pte Ltd', 0.0001)),
divisions(division, dw) AS (VALUES
    ('Manufacturing', 0.88), ('Logistics', 0.095), ('Corporate', 0.025)),
regions(region, rw) AS (VALUES ('Rest of World', 0.90), ('Singapore', 0.10)),
scopes(scope, sw) AS (VALUES ('Scope 1', 0.90), ('Scope 2', 0.006), ('Scope 3', 0.094)),
years(year, yw) AS (
    SELECT y, 0.6 + (y - 2017) * 0.06 FROM generate_series(2017, 2026) AS y),
facilities(f) AS (SELECT generate_series(1, 3))
INSERT INTO poc_emissions
SELECT company, division, region, scope, year,
       round((12000000 * cw * dw * rw * sw * yw * (0.6 + random() * 0.8))::numeric, 2)
FROM companies, divisions, regions, scopes, years, facilities;

INSERT INTO poc_assets
SELECT 'AST-' || lpad(n::text, 4, '0'),
       (ARRAY['Northwind Holdings', 'Northwind Holdings', 'Northwind Holdings',
              'Bluecrest Industries', 'Bluecrest Industries', 'Harbor Supply Co',
              'Meridian Logistics', 'Solace Energy Pte Ltd'])[1 + (n % 8)]
FROM generate_series(1, 24) AS n;

WITH companies(company, ew, uw) AS (VALUES
    ('Bluecrest Industries', 1.0, 1.0),
    ('Harbor Supply Co', 1.6, 2.4),
    ('Meridian Logistics', 0.5, 0.8))
INSERT INTO poc_water
SELECT company, y,
       round((120 * ew * (0.7 + (y - 2017) * 0.08) * (0.7 + random() * 0.6))::numeric, 1),
       round((450 * uw * (0.7 + (y - 2017) * 0.08) * (0.7 + random() * 0.6))::numeric, 1)
FROM companies, generate_series(2017, 2026) AS y;

COMMIT;
