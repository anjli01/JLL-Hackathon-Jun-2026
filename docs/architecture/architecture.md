# ClimateNexus Architecture

Here is the full architecture of the current implementation.

> [!TIP]
> **How to open this in Draw.io:**
> Draw.io natively supports importing Mermaid code and will automatically arrange the boxes perfectly for you! 
> 1. Copy the code block below (starting from `graph TD`).
> 2. Open [Draw.io](https://app.diagrams.net/).
> 3. In the top menu, go to **Arrange** -> **Insert** -> **Advanced** -> **Mermaid...**
> 4. Paste the code and click **Insert**.

```mermaid
graph TD
    %% Styling
    classDef client fill:#f9f9f9,stroke:#333,stroke-width:2px;
    classDef api fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef orchestrator fill:#ffecb3,stroke:#ffa000,stroke-width:2px;
    classDef external fill:#e8f5e9,stroke:#388e3c,stroke-width:2px;
    classDef offline fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px;
    classDef db fill:#cfd8dc,stroke:#455a64,stroke-width:2px;
    classDef ml fill:#ffe0b2,stroke:#f57c00,stroke-width:2px;

    %% Client Layer
    Client[Client / Swagger UI]:::client -->|GET /score| FastAPI(FastAPI Application):::api
    
    %% Geocoding
    FastAPI -->|1. Geocode Address| Nominatim[Nominatim Geocoder<br/>Extracts: lat, lon, state, county]:::external
    
    %% Orchestration
    Nominatim -->|2. Parallel Ingestion| Gather{{asyncio.gather<br/>Orchestrator}}:::orchestrator
    
    %% Real-time APIs
    subgraph "Real-Time External APIs (HTTP)"
        Gather --> FEMA[FEMA Client<br/>Flood Zones, SFHA]:::external
        Gather --> NOAA[NOAA Client<br/>Heat Projections]:::external
        Gather --> USFS[USFS Wildfire Client<br/>Burn Probability]:::external
        Gather --> Elevation[USGS Elevation Client<br/>Low-Lying Flag]:::external
        Gather --> Seismic[USGS Seismic Client<br/>Fault Risk]:::external
        Gather --> Transition[Transition Client<br/>Local Regulations]:::external
        Gather --> OSM[OpenStreetMap Client<br/>Building Context]:::external
        
        OSM -->|Sequential dependency:<br/>building_type| EPA[EPA Energy Star Client<br/>Median EUI]:::external
    end
    
    %% Aggregation
    FEMA & NOAA & USFS & Elevation & Seismic & Transition & EPA -->|3. Feature Dictionary| Dict(Feature Dictionary<br/>35+ fields):::orchestrator
    
    %% Feature Store
    Dict -->|4. Persist| FeatureStore[(Feature Store<br/>SQLite cache)]:::db
    
    %% ML & Explainer
    Dict -->|5. Scoring| ML[XGBoost Ensemble<br/>6-Hazard Weighting]:::ml
    ML -->|Composite Score| SHAP[SHAP Explainer<br/>Impact Values]:::ml
    
    %% Response
    SHAP -->|6. JSON Response| Response(RiskScoreResponse<br/>Score, Sub-scores, Features):::api
    Response --> Client
```
