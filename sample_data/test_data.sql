CREATE SCHEMA sync_data;
ALTER SCHEMA sync_data OWNER TO postgres;

CREATE TABLE sync_data.points (
    fid integer NOT NULL,
    name text,
    rating integer,
    geom public.geometry(Point,4326)
);
ALTER TABLE sync_data.points OWNER TO postgres;

CREATE SEQUENCE sync_data.points_fid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE sync_data.points_fid_seq OWNER TO postgres;
ALTER SEQUENCE sync_data.points_fid_seq OWNED BY sync_data.points.fid;
ALTER TABLE ONLY sync_data.points ALTER COLUMN fid SET DEFAULT nextval('sync_data.points_fid_seq'::regclass);

COPY sync_data.points (fid, name, rating, geom) FROM stdin;
2	Paris	2	0101000020E610000093FF8BF8A6490340F5879EB1286D4840
3	Bratislava	3	0101000020E61000000FB2156A2B20314049D26EAB33134840
1	London	1	0101000020E6100000512DC3E0B94EBCBF218340C214C14940
\.

SELECT pg_catalog.setval('sync_data.points_fid_seq', 3, true);
ALTER TABLE ONLY sync_data.points
    ADD CONSTRAINT points_pkey PRIMARY KEY (fid);
