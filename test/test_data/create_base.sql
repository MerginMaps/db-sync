SET standard_conforming_strings = OFF;

CREATE SCHEMA IF NOT EXISTS test_init_from_db_main;

DROP TABLE IF EXISTS "test_init_from_db_main"."simple" CASCADE;

CREATE TABLE "test_init_from_db_main"."simple" ( "ogc_fid" SERIAL, CONSTRAINT "base_pk" PRIMARY KEY ("ogc_fid") );

SELECT AddGeometryColumn('test_init_from_db_main','simple','wkb_geometry',4326,'POINT',2);
ALTER TABLE "test_init_from_db_main"."simple" ADD COLUMN "fid" NUMERIC(20,0);
ALTER TABLE "test_init_from_db_main"."simple" ADD COLUMN "name" VARCHAR;
ALTER TABLE "test_init_from_db_main"."simple" ADD COLUMN "rating" NUMERIC(10,0);

INSERT INTO "test_init_from_db_main"."simple" ("wkb_geometry" , "fid", "name", "rating") VALUES ('0101000020E61000001E78CBA1366CF1BF70E6AAC83981DD3F', 1, 'feature1', 1);
INSERT INTO "test_init_from_db_main"."simple" ("wkb_geometry" , "fid", "name", "rating") VALUES ('0101000020E6100000F0431AAFE449D7BFF874B615E6FDE13F', 2, 'feature2', 2);
INSERT INTO "test_init_from_db_main"."simple" ("wkb_geometry" , "fid", "name", "rating") VALUES ('0101000020E61000009CB92A724E60E7BFE0FDF1F774B6A53F', 3, 'feature3', 3);

