-- SQLite schema for caching property climate features

CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT UNIQUE NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS property_features (
    property_id INTEGER PRIMARY KEY,
    -- Flood Features (FEMA NFHL)
    flood_risk_score INTEGER,
    flood_zone TEXT,
    is_sfha BOOLEAN,
    base_flood_elevation REAL,
    -- Heat Features (NOAA NWS)
    heat_risk_score INTEGER,
    projected_extreme_heat_days INTEGER,
    cooling_degree_days INTEGER,
    -- Wildfire Features (USFS)
    wildfire_risk_score INTEGER,
    burn_probability REAL,
    distance_to_wui_miles REAL,
    -- Transition Risk Features
    transition_risk_score INTEGER,
    applicable_regulations TEXT,  -- JSON-encoded list
    compliance_gap_flag BOOLEAN,
    -- Elevation Features (USGS EPQS)
    elevation_ft REAL,
    elevation_m REAL,
    low_lying_flag BOOLEAN,
    -- Building Context (OpenStreetMap)
    building_type TEXT,
    building_levels INTEGER,
    building_found BOOLEAN,
    land_use TEXT,
    nearby_buildings INTEGER,
    -- Energy Benchmark (EPA ENERGY STAR)
    energy_star_score_benchmark INTEGER,
    national_median_eui REAL,
    building_type_used TEXT,
    energy_risk_flag BOOLEAN,
    -- Seismic Risk (USGS Design Maps)
    seismic_risk_score INTEGER,
    sds REAL,
    sd1 REAL,
    seismic_design_category TEXT,
    pga REAL,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(property_id) REFERENCES properties(id)
);
