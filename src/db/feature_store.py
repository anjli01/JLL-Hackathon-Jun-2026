import json
import sqlite3
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class FeatureStore:
    """Manages reading/writing property features to SQLite cache."""

    def __init__(self, db_path: str = "data/climate_nexus.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        if not os.path.exists(schema_path):
            logger.warning("Schema file not found at %s", schema_path)
            return

        with sqlite3.connect(self.db_path) as conn:
            with open(schema_path, "r") as f:
                conn.executescript(f.read())
            conn.commit()

    def get_property(self, address: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached property data by address."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM properties WHERE address = ?", (address,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    # Default cache TTL: entries older than this are considered stale
    CACHE_TTL_HOURS = 24

    def get_property_features(
        self, address: str, max_age_hours: float | None = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached features for a property.

        Returns None if no cache entry exists or if the entry is older
        than *max_age_hours* (defaults to ``CACHE_TTL_HOURS``).
        """
        ttl = max_age_hours if max_age_hours is not None else self.CACHE_TTL_HOURS

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT pf.* FROM property_features pf
                JOIN properties p ON p.id = pf.property_id
                WHERE p.address = ?
                """,
                (address,),
            )
            row = cursor.fetchone()
            if row:
                result = dict(row)

                # ---- TTL check ----
                updated_at = result.get("updated_at")
                if updated_at and ttl > 0:
                    from datetime import datetime, timedelta, timezone

                    try:
                        # SQLite stores as 'YYYY-MM-DD HH:MM:SS' (UTC)
                        cached_time = datetime.strptime(
                            updated_at, "%Y-%m-%d %H:%M:%S"
                        ).replace(tzinfo=timezone.utc)
                        if datetime.now(timezone.utc) - cached_time > timedelta(hours=ttl):
                            logger.info(
                                "Cache expired for '%s' (age > %dh) — will re-fetch",
                                address,
                                ttl,
                            )
                            return None
                    except (ValueError, TypeError):
                        pass  # Can't parse timestamp — treat as valid

                # Deserialize JSON-encoded list
                if result.get("applicable_regulations"):
                    result["applicable_regulations"] = json.loads(
                        result["applicable_regulations"]
                    )
                return result
        return None

    def purge_stale(self, max_age_hours: float | None = None) -> int:
        """Delete cache entries older than *max_age_hours*. Returns count deleted."""
        ttl = max_age_hours if max_age_hours is not None else self.CACHE_TTL_HOURS
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM property_features
                WHERE updated_at < datetime('now', ? || ' hours')
                """,
                (f"-{ttl}",),
            )
            deleted = cursor.rowcount
            conn.commit()
            if deleted:
                logger.info("Purged %d stale cache entries (older than %dh)", deleted, ttl)
            return deleted

    def save_property_features(
        self, address: str, lat: float, lon: float, features: Dict[str, Any]
    ):
        """Persist property features to the SQLite cache."""
        # Serialize list fields to JSON for storage
        applicable_regs = features.get("applicable_regulations", [])
        if isinstance(applicable_regs, list):
            applicable_regs_json = json.dumps(applicable_regs)
        else:
            applicable_regs_json = str(applicable_regs)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Insert or ignore property
            cursor.execute(
                "INSERT OR IGNORE INTO properties (address, latitude, longitude) VALUES (?, ?, ?)",
                (address, lat, lon),
            )

            # Get property ID
            cursor.execute("SELECT id FROM properties WHERE address = ?", (address,))
            prop_id = cursor.fetchone()[0]

            # Upsert features
            cursor.execute(
                """
                INSERT OR REPLACE INTO property_features (
                    property_id,
                    flood_risk_score, flood_zone, is_sfha, base_flood_elevation,
                    heat_risk_score, projected_extreme_heat_days, cooling_degree_days,
                    wildfire_risk_score, burn_probability, distance_to_wui_miles,
                    transition_risk_score, applicable_regulations, compliance_gap_flag,
                    elevation_ft, elevation_m, low_lying_flag,
                    building_type, building_levels, building_found, land_use, nearby_buildings,
                    energy_star_score_benchmark, national_median_eui, building_type_used, energy_risk_flag,
                    seismic_risk_score, sds, sd1, seismic_design_category, pga
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prop_id,
                    # Flood
                    features.get("flood_risk_score"),
                    features.get("flood_zone"),
                    features.get("is_sfha"),
                    features.get("base_flood_elevation"),
                    # Heat
                    features.get("heat_risk_score"),
                    features.get("projected_extreme_heat_days"),
                    features.get("cooling_degree_days"),
                    # Wildfire
                    features.get("wildfire_risk_score"),
                    features.get("burn_probability"),
                    features.get("distance_to_wui_miles"),
                    # Transition
                    features.get("transition_risk_score"),
                    applicable_regs_json,
                    features.get("compliance_gap_flag"),
                    # Elevation
                    features.get("elevation_ft"),
                    features.get("elevation_m"),
                    features.get("low_lying_flag"),
                    # Building (OSM)
                    features.get("building_type"),
                    features.get("building_levels"),
                    features.get("building_found"),
                    features.get("land_use"),
                    features.get("nearby_buildings"),
                    # Energy (EPA)
                    features.get("energy_star_score_benchmark"),
                    features.get("national_median_eui"),
                    features.get("building_type_used"),
                    features.get("energy_risk_flag"),
                    # Seismic
                    features.get("seismic_risk_score"),
                    features.get("sds"),
                    features.get("sd1"),
                    features.get("seismic_design_category"),
                    features.get("pga"),
                ),
            )
            conn.commit()
            logger.info("Saved features for property '%s' (id=%s)", address, prop_id)
