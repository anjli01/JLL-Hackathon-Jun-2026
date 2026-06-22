"""
Unit tests for ingestion clients.

Tests mock the HTTP layer so they run fast and offline.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.ingestion.fema_client import FemaClient
from src.ingestion.noaa_client import NoaaClient
from src.ingestion.wildfire_client import WildfireClient
from src.ingestion.transition_client import TransitionClient
from src.ingestion.usgs_elevation_client import UsgsElevationClient
from src.ingestion.osm_client import OsmClient
from src.ingestion.epa_energy_star_client import EpaEnergyStarClient
from src.ingestion.usgs_seismic_client import UsgsSeismicClient


def _make_mock_response(json_data):
    """Create a mock httpx.Response whose .json() is synchronous (like real httpx)."""
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.json = Mock(return_value=json_data)
    return resp


# ── FEMA Client ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fema_client_parses_flood_zone():
    mock_response = {
        "features": [
            {"attributes": {"FLD_ZONE": "AE", "SFHA_TF": "T", "STATIC_BFE": 12.5}}
        ]
    }
    client = FemaClient()
    mock_get = AsyncMock(return_value=_make_mock_response(mock_response))
    with patch.object(client.client, "get", mock_get):
        res = await client.get_flood_risk(40.7128, -74.0060)
    assert res["flood_zone"] == "AE"
    assert res["is_sfha"] is True
    assert res["flood_risk_score"] == 80
    await client.close()


@pytest.mark.asyncio
async def test_fema_client_no_features():
    client = FemaClient()
    mock_get = AsyncMock(return_value=_make_mock_response({"features": []}))
    with patch.object(client.client, "get", mock_get):
        res = await client.get_flood_risk(39.0, -95.0)
    assert res["flood_zone"] == "X"
    assert res["is_sfha"] is False
    await client.close()


# ── NOAA Client (RCC-ACIS GridData) ──────────────────────────

@pytest.mark.asyncio
async def test_noaa_client_parses_acis_griddata():
    """Test the new ACIS GridData API response parsing (30-year normals)."""
    mock_acis_response = {
        "meta": {"lat": 40.71, "lon": -74.01, "elev": 10.0},
        "data": [
            ["1991", "58.2", "49.1", "4"],
            ["1992", "57.8", "48.5", "3"],
            ["1993", "58.5", "49.3", "5"],
            ["1994", "59.0", "49.8", "6"],
            ["1995", "58.1", "48.9", "4"],
            # Simulate 30 years with a smaller sample (still valid)
        ],
    }
    client = NoaaClient()
    mock_post = AsyncMock(return_value=_make_mock_response(mock_acis_response))
    with patch.object(client.client, "post", mock_post):
        res = await client.get_heat_risk(40.7128, -74.0060)

    assert res["heat_risk_score"] >= 0
    assert res["heat_risk_score"] <= 100
    assert res["projected_extreme_heat_days"] >= 0
    assert res["cooling_degree_days"] >= 0
    assert res["climate_normal_period"] == "1991-2020"
    # RCP projections should be populated
    assert res["rcp85_warming_f"] is not None
    assert res["rcp45_warming_f"] is not None
    await client.close()


@pytest.mark.asyncio
async def test_noaa_client_handles_missing_data():
    """ACIS returns 'M' for missing values; the client should handle gracefully."""
    mock_acis_response = {
        "meta": {"lat": 40.71, "lon": -74.01},
        "data": [
            ["1991", "M", "M", "M"],
            ["1992", "M", "M", "M"],
        ],
    }
    client = NoaaClient()
    mock_post = AsyncMock(return_value=_make_mock_response(mock_acis_response))
    with patch.object(client.client, "post", mock_post):
        res = await client.get_heat_risk(40.7128, -74.0060)

    # Should fall back to zero values
    assert res["heat_risk_score"] == 0
    assert res["projected_extreme_heat_days"] == 0
    await client.close()


@pytest.mark.asyncio
async def test_noaa_client_empty_response():
    """ACIS returns no data rows — should fall back gracefully."""
    client = NoaaClient()
    mock_post = AsyncMock(return_value=_make_mock_response({"data": []}))
    with patch.object(client.client, "post", mock_post):
        res = await client.get_heat_risk(40.7128, -74.0060)
    assert res["heat_risk_score"] == 0
    await client.close()


# ── Wildfire Client ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_wildfire_client_parses_burn_probability():
    client = WildfireClient()
    mock_get = AsyncMock(return_value=_make_mock_response({"value": "0.005"}))
    with patch.object(client.client, "get", mock_get):
        res = await client.get_wildfire_risk(34.0522, -118.2437)
    assert res["burn_probability"] == 0.005
    assert res["wildfire_risk_score"] == 25
    await client.close()


@pytest.mark.asyncio
async def test_wildfire_client_nodata():
    client = WildfireClient()
    mock_get = AsyncMock(return_value=_make_mock_response({"value": "NoData"}))
    with patch.object(client.client, "get", mock_get):
        res = await client.get_wildfire_risk(42.0, -80.0)
    assert res["wildfire_risk_score"] == 5
    await client.close()


# ── Transition Client ────────────────────────────────────────

@pytest.mark.asyncio
async def test_transition_client_matches_nyc():
    client = TransitionClient()
    res = await client.get_transition_risk(40.7128, -74.0060, "123 Broadway, New York, NY")
    assert "Local Law 97 (LL97)" in res["applicable_regulations"]
    assert res["compliance_gap_flag"] is True


@pytest.mark.asyncio
async def test_transition_client_no_regulation():
    client = TransitionClient()
    res = await client.get_transition_risk(35.0, -90.0, "123 Main St, Memphis, TN")
    assert res["applicable_regulations"] == []
    assert res["transition_risk_score"] == 20


# ── USGS Elevation Client ───────────────────────────────────

@pytest.mark.asyncio
async def test_elevation_client_parses_response():
    client = UsgsElevationClient()
    mock_get = AsyncMock(return_value=_make_mock_response({"value": 15.5}))
    with patch.object(client.client, "get", mock_get):
        res = await client.get_elevation(25.7617, -80.1918)  # Miami
    assert res["elevation_ft"] == 15.5
    assert res["low_lying_flag"] is True  # below 33 ft
    await client.close()


@pytest.mark.asyncio
async def test_elevation_client_high_ground():
    client = UsgsElevationClient()
    mock_get = AsyncMock(return_value=_make_mock_response({"value": 500.0}))
    with patch.object(client.client, "get", mock_get):
        res = await client.get_elevation(39.7392, -104.9903)  # Denver
    assert res["elevation_ft"] == 500.0
    assert res["low_lying_flag"] is False
    await client.close()


# ── OpenStreetMap Client ─────────────────────────────────────

@pytest.mark.asyncio
async def test_osm_client_finds_building():
    mock_response = {
        "elements": [
            {"type": "way", "id": 123, "tags": {"building": "commercial", "building:levels": "5"}},
            {"type": "way", "id": 124, "tags": {"building": "yes"}},
        ]
    }
    client = OsmClient()
    mock_post = AsyncMock(return_value=_make_mock_response(mock_response))
    with patch.object(client.client, "post", mock_post):
        with patch.object(client, "_get_land_use", return_value="commercial"):
            res = await client.get_building_info(40.7484, -73.9857)
    assert res["building_found"] is True
    assert res["building_type"] == "commercial"
    assert res["building_levels"] == 5
    assert res["nearby_buildings"] == 2
    await client.close()


@pytest.mark.asyncio
async def test_osm_client_no_building():
    client = OsmClient()
    mock_post = AsyncMock(return_value=_make_mock_response({"elements": []}))
    with patch.object(client.client, "post", mock_post):
        with patch.object(client, "_get_land_use", return_value=None):
            res = await client.get_building_info(36.0, -110.0)
    assert res["building_found"] is False
    assert res["nearby_buildings"] == 0
    await client.close()


# ── EPA ENERGY STAR Client (climate-zone-aware) ──────────────

@pytest.mark.asyncio
async def test_epa_client_office_climate_zone():
    """EPA client should return climate-zone-adjusted EUI for NYC (zone 5)."""
    client = EpaEnergyStarClient()
    # Mock the SODA API to fail so we exercise the climate-zone fallback
    mock_get = AsyncMock(side_effect=Exception("SODA unavailable"))
    with patch.object(client.client, "get", mock_get):
        res = await client.get_energy_benchmark(40.7128, -74.0060, "office")
    assert res["building_type_used"] == "office"
    assert res["national_median_eui"] == 92.9
    assert res["climate_zone"] == 5  # NYC → ASHRAE zone 5
    # Zone 5 multiplier = 1.10 → adjusted = 92.9 * 1.10 = 102.19 ≈ 102.2
    assert res["climate_adjusted_eui"] == 102.2
    assert res["energy_risk_flag"] is True  # 102.2 > 100
    assert res["data_source"] == "climate_zone_benchmark"
    await client.close()


@pytest.mark.asyncio
async def test_epa_client_hospital():
    """Hospital EUI is always high regardless of climate zone."""
    client = EpaEnergyStarClient()
    mock_get = AsyncMock(side_effect=Exception("SODA unavailable"))
    with patch.object(client.client, "get", mock_get):
        res = await client.get_energy_benchmark(40.7128, -74.0060, "hospital")
    assert res["building_type_used"] == "hospital"
    assert res["energy_risk_flag"] is True  # 389.5 * 1.10 > 100


@pytest.mark.asyncio
async def test_epa_client_soda_api_success():
    """If the SODA API returns data, it should be used over the fallback."""
    mock_soda_data = [
        {"energy_star_score": "75", "source_eui": "80.5"},
        {"energy_star_score": "65", "source_eui": "95.0"},
        {"energy_star_score": "80", "source_eui": "72.3"},
    ]
    client = EpaEnergyStarClient()
    mock_get = AsyncMock(return_value=_make_mock_response(mock_soda_data))
    with patch.object(client.client, "get", mock_get):
        res = await client.get_energy_benchmark(40.7128, -74.0060, "office")
    assert res["data_source"] == "energy_star_soda_api"
    assert res["energy_star_score_benchmark"] == 73  # mean(75, 65, 80) ≈ 73
    assert res["soda_sample_size"] == 3
    await client.close()


# ── USGS Seismic Client ─────────────────────────────────────

@pytest.mark.asyncio
async def test_seismic_client_high_risk():
    mock_response = {
        "response": {"data": {"sds": 1.2, "sd1": 0.55, "sdc": "D", "pgam": 0.6}}
    }
    client = UsgsSeismicClient()
    mock_get = AsyncMock(return_value=_make_mock_response(mock_response))
    with patch.object(client.client, "get", mock_get):
        res = await client.get_seismic_risk(34.05, -118.25)  # LA
    assert res["seismic_risk_score"] == 85  # SDS 1.2 → 85
    assert res["seismic_design_category"] == "D"
    await client.close()


@pytest.mark.asyncio
async def test_seismic_client_low_risk():
    mock_response = {
        "response": {"data": {"sds": 0.1, "sd1": 0.04, "sdc": "A", "pgam": 0.05}}
    }
    client = UsgsSeismicClient()
    mock_get = AsyncMock(return_value=_make_mock_response(mock_response))
    with patch.object(client.client, "get", mock_get):
        res = await client.get_seismic_risk(40.7128, -74.0060)  # NYC
    assert res["seismic_risk_score"] == 5  # SDS 0.1 → 5
    await client.close()
