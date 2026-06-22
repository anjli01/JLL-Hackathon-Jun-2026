# Codebase Architecture

This diagram maps out the directory structure and module responsibilities of the `ClimateNexus` codebase.

> [!TIP]
> **How to view in Draw.io:**
> Draw.io natively supports importing Mermaid code and will automatically arrange the boxes perfectly! 
> 1. Copy the code block below (starting from `graph TD`).
> 2. Open [Draw.io](https://app.diagrams.net/).
> 3. Go to **Arrange** -> **Insert** -> **Advanced** -> **Mermaid...**
> 4. Paste the code and click **Insert**.

```mermaid
graph TD
    %% Styling
    classDef module fill:#e3f2fd,stroke:#1565c0,stroke-width:2px;
    classDef file fill:#f5f5f5,stroke:#9e9e9e,stroke-width:1px;
    classDef dir fill:#fff8e1,stroke:#ffb300,stroke-width:2px;
    classDef root fill:#eceff1,stroke:#455a64,stroke-width:2px;

    %% Directories
    Root[Root Directory]:::root
    Src[📁 src/]:::dir
    Tests[📁 tests/]:::dir
    
    Root --> Src
    Root --> Tests
    
    %% API Module
    API[📁 src/api/]:::module
    Src --> API
    API --> Main[📄 main.py<br/>FastAPI Orchestrator]:::file
    API --> Models[📄 models.py<br/>Pydantic Schemas]:::file
    
    %% Ingestion Module
    Ingestion[📁 src/ingestion/<br/>Async HTTP Clients]:::module
    Src --> Ingestion
    Ingestion --> FEMA[📄 fema_client.py]:::file
    Ingestion --> NOAA[📄 noaa_client.py]:::file
    Ingestion --> USFS[📄 wildfire_client.py]:::file
    Ingestion --> Trans[📄 transition_client.py]:::file
    Ingestion --> Elev[📄 usgs_elevation_client.py]:::file
    Ingestion --> OSM[📄 osm_client.py]:::file
    Ingestion --> EPA[📄 epa_energy_star_client.py]:::file
    Ingestion --> Seismic[📄 usgs_seismic_client.py]:::file
    
    %% Database Module
    DB[📁 src/db/<br/>Persistence]:::module
    Src --> DB
    DB --> Schema[📄 schema.sql<br/>SQLite Schema]:::file
    DB --> Store[📄 feature_store.py<br/>Upsert Logic]:::file
    
    %% ML Module
    ML[📁 src/ml/<br/>Scoring Engine]:::module
    Src --> ML
    ML --> XGB[📄 xgboost_ensemble.py<br/>Risk Weighting]:::file
    ML --> SHAP[📄 explainer.py<br/>Feature Importance]:::file
    
    %% Tests
    Tests --> TestIngest[📄 test_ingestion.py<br/>Offline Mocks]:::file
    Tests --> TestML[📄 test_ml.py<br/>Bounds & Explainer]:::file
    
    %% Relationships
    Main -.->|Uses| Models
    Main -.->|Instantiates| Ingestion
    Main -.->|Writes to| Store
    Main -.->|Predicts with| XGB
    Main -.->|Explains with| SHAP
```
