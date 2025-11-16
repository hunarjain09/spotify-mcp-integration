# Architecture Documentation

This document provides detailed architectural diagrams and explanations of the Spotify MCP Integration system.

## Table of Contents

1. [Execution Modes Overview](#execution-modes-overview)
2. [System Architecture (Temporal Mode)](#system-architecture-temporal-mode)
3. [System Architecture (Standalone Mode)](#system-architecture-standalone-mode)
4. [Sync Workflow Sequence](#sync-workflow-sequence)
5. [Component Interactions](#component-interactions)
6. [Data Flow](#data-flow)
7. [Activity Execution Flow](#activity-execution-flow)
8. [Deployment Architecture](#deployment-architecture)

---

## Execution Modes Overview

The system supports **two execution modes** controlled by the `USE_TEMPORAL` environment variable:

### 🏢 Temporal Mode (`USE_TEMPORAL=true`)

**Architecture**: Distributed, durable workflow orchestration
**Best for**: Production, high reliability, distributed processing

**Key Components**:
- Temporal Server (workflow orchestration engine)
- PostgreSQL (state persistence)
- Temporal Worker (executes workflows & activities)
- FastAPI Server (HTTP endpoints)
- MCP Client/Server (Spotify integration)

**Features**:
- ✅ Durable execution (survives server restarts)
- ✅ Advanced retry policies with exponential backoff
- ✅ Distributed processing across multiple workers
- ✅ Real-time progress tracking via queries
- ✅ Complete workflow history and replay
- ✅ Automatic state management

### ⚡ Standalone Mode (`USE_TEMPORAL=false`)

**Architecture**: Direct, synchronous execution
**Best for**: Development, testing, simple deployments

**Key Components**:
- FastAPI Server (HTTP endpoints + workflow execution)
- MCP Client/Server (Spotify integration)
- In-memory state storage

**Features**:
- ✅ Simple deployment (no infrastructure)
- ✅ Lower resource usage
- ✅ Faster startup time
- ✅ Identical API endpoints
- ⚠️ In-memory state only (lost on restart)
- ⚠️ Basic retry logic
- ⚠️ Single-server execution

**📖 For detailed comparison, see [docs/EXECUTION_MODES.md](./docs/EXECUTION_MODES.md)**

---

## System Architecture (Temporal Mode)

High-level overview when `USE_TEMPORAL=true` (production mode).

```mermaid
graph TB
    subgraph "Client Layer"
        iOS[iOS Shortcuts App]
        User[User]
    end

    subgraph "API Layer"
        FastAPI[FastAPI Server<br/>Port 8000]
        Health[/api/v1/health]
        Sync[/api/v1/sync]
        Status[/api/v1/sync/:id]
        Cancel[/api/v1/sync/:id/cancel]
    end

    subgraph "Workflow Orchestration"
        Temporal[Temporal Server<br/>Port 7233]
        Worker[Temporal Worker]
        Workflow[MusicSyncWorkflow]
    end

    subgraph "Activities"
        Search[Spotify Search Activity]
        Fuzzy[Fuzzy Matcher Activity]
        AI[AI Disambiguator Activity]
        Playlist[Playlist Manager Activity]
    end

    subgraph "Integration Layer"
        MCP[MCP Client]
        MCPServer[MCP Spotify Server]
    end

    subgraph "External Services"
        SpotifyAPI[Spotify Web API]
        OpenAI[OpenAI API / GPT-4]
        Claude[Anthropic Claude API]
    end

    subgraph "Data Storage"
        PostgreSQL[(PostgreSQL<br/>Temporal DB)]
    end

    User -->|Share Song| iOS
    iOS -->|HTTP POST| FastAPI
    FastAPI -->|Start Workflow| Temporal
    Temporal -->|Execute| Worker
    Worker -->|Run| Workflow

    Workflow -->|1. Search| Search
    Workflow -->|2. Match| Fuzzy
    Workflow -->|3. Disambiguate| AI
    Workflow -->|4. Add to Playlist| Playlist

    Search -->|Call Tool| MCP
    AI -->|Call Tool| MCP
    Playlist -->|Call Tool| MCP

    MCP -->|MCP Protocol| MCPServer
    MCPServer -->|HTTPS| SpotifyAPI

    AI -.->|Provider: langchain| OpenAI
    AI -.->|Provider: claude| Claude

    Temporal -->|Store State| PostgreSQL

    FastAPI -.->|Query Progress| Temporal
    iOS -.->|Poll Status| Status

    classDef client fill:#e1f5ff,stroke:#01579b
    classDef api fill:#fff3e0,stroke:#e65100
    classDef workflow fill:#f3e5f5,stroke:#4a148c
    classDef activity fill:#e8f5e9,stroke:#1b5e20
    classDef integration fill:#fff9c4,stroke:#f57f17
    classDef external fill:#fce4ec,stroke:#880e4f
    classDef storage fill:#e0f2f1,stroke:#004d40

    class iOS,User client
    class FastAPI,Health,Sync,Status,Cancel api
    class Temporal,Worker,Workflow workflow
    class Search,Fuzzy,AI,Playlist activity
    class MCP,MCPServer integration
    class SpotifyAPI,OpenAI,Claude external
    class PostgreSQL storage
```

---

## System Architecture (Standalone Mode)

Simplified architecture when `USE_TEMPORAL=false` (development/simple deployments).

```mermaid
graph TB
    subgraph "Client Layer"
        iOS[iOS Shortcuts App]
        User[User]
    end

    subgraph "API Layer"
        FastAPI[FastAPI Server<br/>Port 8000<br/>+ Workflow Executor]
        Health[/api/v1/health]
        Sync[/api/v1/sync]
        Status[/api/v1/sync/:id]
    end

    subgraph "Execution Layer"
        Executor[Standalone Executor<br/>In-Memory State]
        Search[Search Function]
        Fuzzy[Fuzzy Match Function]
        AI[AI Disambiguate Function]
        Playlist[Playlist Function]
    end

    subgraph "Integration Layer"
        MCP[MCP Client]
        MCPServer[MCP Spotify Server]
    end

    subgraph "External Services"
        SpotifyAPI[Spotify Web API]
        OpenAI[OpenAI API / GPT-4]
        Claude[Anthropic Claude API]
    end

    User -->|Share Song| iOS
    iOS -->|HTTP POST| FastAPI
    FastAPI -->|Execute Directly| Executor

    Executor -->|1. Search| Search
    Executor -->|2. Match| Fuzzy
    Executor -->|3. Disambiguate| AI
    Executor -->|4. Add to Playlist| Playlist

    Search -->|Call Tool| MCP
    AI -->|Call Tool| MCP
    Playlist -->|Call Tool| MCP

    MCP -->|MCP Protocol| MCPServer
    MCPServer -->|HTTPS| SpotifyAPI

    AI -.->|Provider: langchain| OpenAI
    AI -.->|Provider: claude| Claude

    iOS -.->|Poll Status| Status
    FastAPI -.->|Query State| Executor

    classDef client fill:#e1f5ff,stroke:#01579b
    classDef api fill:#fff3e0,stroke:#e65100
    classDef executor fill:#e8f5e9,stroke:#1b5e20
    classDef integration fill:#fff9c4,stroke:#f57f17
    classDef external fill:#fce4ec,stroke:#880e4f

    class iOS,User client
    class FastAPI,Health,Sync,Status api
    class Executor,Search,Fuzzy,AI,Playlist executor
    class MCP,MCPServer integration
    class SpotifyAPI,OpenAI,Claude external
```

**Key Differences from Temporal Mode:**
- ❌ No Temporal Server (no workflow orchestration)
- ❌ No PostgreSQL (no persistent state storage)
- ❌ No Worker process (execution happens in FastAPI)
- ✅ Simpler deployment (2 components vs 5+)
- ✅ Lower resource usage
- ⚠️ State stored in-memory (lost on restart)

---

## Sync Workflow Sequence

Detailed sequence diagram showing the complete flow of a song sync request (Temporal Mode).

```mermaid
sequenceDiagram
    participant User
    participant iOS as iOS Shortcuts
    participant API as FastAPI Server
    participant Temporal as Temporal Server
    participant Worker as Temporal Worker
    participant Workflow as MusicSyncWorkflow
    participant Search as Spotify Search
    participant Fuzzy as Fuzzy Matcher
    participant AI as AI Disambiguator
    participant Playlist as Playlist Manager
    participant MCP as MCP Client
    participant Spotify as Spotify API

    User->>iOS: Share song from Apple Music
    iOS->>iOS: Extract metadata<br/>(title, artist, album)

    iOS->>+API: POST /api/v1/sync<br/>{track_name, artist, playlist_id}
    API->>API: Generate workflow_id
    API->>+Temporal: Start workflow<br/>MusicSyncWorkflow.run()
    Temporal->>Temporal: Create workflow instance
    Temporal-->>-API: Workflow started
    API-->>-iOS: 202 Accepted<br/>{workflow_id, status_url}

    iOS->>iOS: Show success message
    iOS->>User: "Sync started!"

    Note over Temporal,Worker: Fire-and-forget - workflow runs asynchronously

    Temporal->>+Worker: Execute workflow
    Worker->>+Workflow: run(WorkflowInput)

    Workflow->>Workflow: Update progress:<br/>"Starting sync"

    rect rgb(230, 245, 255)
        Note over Workflow,Spotify: Step 1: Search Spotify
        Workflow->>+Search: search_spotify(metadata)
        Search->>+MCP: search_track(query)
        MCP->>+Spotify: GET /search?q=track:... artist:...
        Spotify-->>-MCP: {tracks: [...]}
        MCP-->>-Search: List[Track]
        Search-->>-Workflow: List[SpotifyTrackResult]
        Workflow->>Workflow: Update progress:<br/>"Found X candidates"
    end

    rect rgb(255, 243, 230)
        Note over Workflow,Fuzzy: Step 2: Fuzzy Matching
        Workflow->>+Fuzzy: fuzzy_match_tracks(metadata, results)
        Fuzzy->>Fuzzy: Check ISRC exact match
        alt ISRC Match Found
            Fuzzy->>Fuzzy: Return perfect match (1.0)
        else No ISRC Match
            Fuzzy->>Fuzzy: Calculate fuzzy scores<br/>(title 50%, artist 35%, album 15%)
            Fuzzy->>Fuzzy: Sort by combined score
        end
        Fuzzy-->>-Workflow: MatchResult {confidence, track}
        Workflow->>Workflow: Update progress:<br/>"Matching complete"
    end

    alt Confidence >= Threshold (e.g., 0.85)
        Workflow->>Workflow: Match found!
    else Confidence < Threshold AND use_ai_disambiguation
        rect rgb(243, 229, 245)
            Note over Workflow,AI: Step 3: AI Disambiguation
            Workflow->>+AI: disambiguate_with_ai(metadata, candidates)
            AI->>AI: Build prompt with<br/>original + candidates
            alt Provider = langchain
                AI->>OpenAI: ChatCompletion<br/>(GPT-4)
                OpenAI-->>AI: Selected track + reasoning
            else Provider = claude
                AI->>Claude: Messages API<br/>(Claude 3.5 Sonnet)
                Claude-->>AI: Selected track + reasoning
            end
            AI->>AI: Parse JSON response
            AI-->>-Workflow: MatchResult {track, reasoning}
            Workflow->>Workflow: Update progress:<br/>"AI disambiguation complete"
        end
    else Low confidence AND AI disabled
        Workflow->>Workflow: No match found
    end

    alt Match Found
        rect rgb(232, 245, 233)
            Note over Workflow,Playlist: Step 4: Add to Playlist
            Workflow->>+Playlist: add_track_to_playlist(track_id, playlist_id)
            Playlist->>+MCP: add_track_to_playlist(track_id, playlist_id)
            MCP->>+Spotify: POST /playlists/{id}/tracks
            Spotify-->>-MCP: {snapshot_id}
            MCP-->>-Playlist: Success

            Playlist->>+MCP: verify_track_added(track_id, playlist_id)
            MCP->>+Spotify: GET /playlists/{id}/tracks
            Spotify-->>-MCP: {items: [...]}
            MCP-->>-Playlist: Verified
            Playlist-->>-Workflow: Success

            Workflow->>Workflow: Update progress:<br/>"Track added successfully"
        end
    end

    Workflow->>Workflow: Calculate execution time
    Workflow-->>-Worker: WorkflowResult {success, message, track_id}
    Worker-->>-Temporal: Result stored

    Note over iOS,API: User can poll for status
    iOS->>+API: GET /api/v1/sync/{workflow_id}
    API->>+Temporal: Query workflow status
    Temporal-->>-API: WorkflowResult
    API-->>-iOS: 200 OK {status: "completed", result: {...}}
    iOS->>User: "✓ Added to playlist!"
```

---

## Component Interactions

How different components interact with each other.

```mermaid
graph LR
    subgraph "External Clients"
        A[iOS Shortcuts]
        B[CLI/API Client]
    end

    subgraph "API Server Process"
        C[FastAPI App]
        D[CORS Middleware]
        E[Request Validators]
        F[Temporal Client]
    end

    subgraph "Worker Process"
        G[Temporal Worker]
        H[Workflow Executor]
        I[Activity Pool]
    end

    subgraph "Workflow Logic"
        J[MusicSyncWorkflow]
        K[Progress Queries]
        L[Error Handlers]
    end

    subgraph "Activity Implementations"
        M[spotify_search.py]
        N[fuzzy_matcher.py]
        O[ai_disambiguator.py]
        P[playlist_manager.py]
    end

    subgraph "Shared Libraries"
        Q[Data Models]
        R[Config/Settings]
        S[MCP Client Wrapper]
    end

    subgraph "MCP Server Process"
        T[MCP Server]
        U[Spotify Tools]
        V[Spotipy Client]
    end

    A -->|HTTP| D
    B -->|HTTP| D
    D --> C
    C --> E
    E --> F
    F -->|gRPC| G

    G --> H
    H --> J
    J --> I

    I --> M
    I --> N
    I --> O
    I --> P

    M --> S
    O --> S
    P --> S

    S -->|MCP Protocol| T
    T --> U
    U --> V

    J --> K
    J --> L

    M --> Q
    N --> Q
    O --> Q
    P --> Q

    C --> R
    G --> R
    T --> R

    classDef client fill:#e1f5ff
    classDef api fill:#fff3e0
    classDef worker fill:#f3e5f5
    classDef workflow fill:#e8f5e9
    classDef activity fill:#fff9c4
    classDef shared fill:#fce4ec
    classDef mcp fill:#e0f2f1

    class A,B client
    class C,D,E,F api
    class G,H,I worker
    class J,K,L workflow
    class M,N,O,P activity
    class Q,R,S shared
    class T,U,V mcp
```

---

## Data Flow

How data flows through the system from request to completion.

```mermaid
flowchart TD
    Start([User shares song from Apple Music]) --> Extract[Extract song metadata]
    Extract --> Request{Create sync request}

    Request -->|track_name, artist, album, playlist_id| Validate[Validate request]

    Validate -->|Valid| GenerateID[Generate unique workflow_id]
    Validate -->|Invalid| Error1[Return 422 Validation Error]

    GenerateID --> CreateInput[Create WorkflowInput]
    CreateInput --> StartWF[Start Temporal Workflow]

    StartWF --> Return[Return 202 Accepted]
    Return --> EndUser([User sees: 'Sync started!'])

    StartWF --> WFStart[Workflow begins execution]

    WFStart --> SearchSpotify[Search Spotify via MCP]
    SearchSpotify --> Results{Found tracks?}

    Results -->|Yes| ParseResults[Parse to SpotifyTrackResult list]
    Results -->|No| NoMatch[Return: No matches found]

    ParseResults --> FuzzyMatch[Fuzzy matching algorithm]

    FuzzyMatch --> CheckISRC{ISRC available?}
    CheckISRC -->|Yes, matches| PerfectMatch[Perfect match - Score: 1.0]
    CheckISRC -->|No/Different| CalculateScore[Calculate weighted score<br/>Title: 50%, Artist: 35%, Album: 15%]

    CalculateScore --> BestScore[Select highest scoring track]
    PerfectMatch --> BestScore

    BestScore --> ThresholdCheck{Score >= threshold?}

    ThresholdCheck -->|Yes| MatchFound[Match found!]
    ThresholdCheck -->|No| AICheck{AI enabled?}

    AICheck -->|Yes| AIDisambiguate[AI Disambiguator]
    AICheck -->|No| NoMatch

    AIDisambiguate --> ProviderCheck{AI Provider?}

    ProviderCheck -->|langchain| CallOpenAI[Call OpenAI GPT-4]
    ProviderCheck -->|claude| CallClaude[Call Anthropic Claude]

    CallOpenAI --> ParseAI[Parse AI response]
    CallClaude --> ParseAI

    ParseAI --> AIResult{AI selected track?}
    AIResult -->|Yes| MatchFound
    AIResult -->|No| NoMatch

    MatchFound --> AddToPlaylist[Add track to Spotify playlist]

    AddToPlaylist --> Verify[Verify track was added]
    Verify --> VerifyResult{Verified?}

    VerifyResult -->|Yes| Success[Return success result]
    VerifyResult -->|No| Retry{Retry count < max?}

    Retry -->|Yes| AddToPlaylist
    Retry -->|No| Failure[Return failure result]

    Success --> StoreResult[(Store in Temporal)]
    Failure --> StoreResult
    NoMatch --> StoreResult

    StoreResult --> Complete([Workflow complete])

    Complete -.-> Poll[User polls status endpoint]
    Poll --> ReturnStatus[Return workflow status & result]
    ReturnStatus --> ShowUser([User sees: 'Added to playlist!'])

    style Start fill:#e1f5ff
    style EndUser fill:#c8e6c9
    style ShowUser fill:#c8e6c9
    style Error1 fill:#ffcdd2
    style NoMatch fill:#ffe0b2
    style Failure fill:#ffcdd2
    style Success fill:#c8e6c9
    style Complete fill:#e1f5ff
```

---

## Activity Execution Flow

Detailed flow of how activities are executed within the Temporal workflow.

```mermaid
stateDiagram-v2
    [*] --> WorkflowStarted: Workflow instance created

    WorkflowStarted --> SearchActivity: Execute search activity

    state SearchActivity {
        [*] --> BuildQuery: Build search query from metadata
        BuildQuery --> CallMCP: Call MCP search_track tool
        CallMCP --> MCPRequest: MCP makes Spotify API request
        MCPRequest --> ParseResponse: Parse Spotify response
        ParseResponse --> ReturnTracks: Return List[SpotifyTrackResult]
        ReturnTracks --> [*]

        state error_handling <<choice>>
        MCPRequest --> error_handling: On error
        error_handling --> RateLimit: 429 Rate Limit
        error_handling --> APIError: 4xx/5xx Error
        error_handling --> MCPError: MCP Tool Error

        RateLimit --> WaitRetry: Wait retry_after seconds
        WaitRetry --> CallMCP

        APIError --> Retry: Retry with backoff
        Retry --> CallMCP

        MCPError --> [*]: Non-retryable error
    }

    SearchActivity --> CheckResults: Activity complete

    CheckResults --> FuzzyMatchActivity: Has results
    CheckResults --> NoMatchState: No results

    state FuzzyMatchActivity {
        [*] --> IterateTracks: For each candidate
        IterateTracks --> CheckISRC: Check ISRC match

        state isrc_check <<choice>>
        CheckISRC --> isrc_check
        isrc_check --> ISRCMatch: ISRCs match
        isrc_check --> CalculateScores: No ISRC match

        ISRCMatch --> SetPerfectScore: Set score = 1.0

        CalculateScores --> TitleScore: fuzz.ratio(title) * 0.5
        TitleScore --> ArtistScore: fuzz.ratio(artist) * 0.35
        ArtistScore --> AlbumScore: fuzz.ratio(album) * 0.15
        AlbumScore --> CombinedScore: Sum weighted scores

        SetPerfectScore --> StoreScore
        CombinedScore --> StoreScore: Store FuzzyMatchScore

        StoreScore --> MoreTracks: More tracks?
        MoreTracks --> IterateTracks: Yes
        MoreTracks --> SelectBest: No

        SelectBest --> [*]: Return highest score
    }

    FuzzyMatchActivity --> EvaluateMatch: Activity complete

    state EvaluateMatch <<choice>>
    EvaluateMatch --> HighConfidence: Score >= threshold
    EvaluateMatch --> LowConfidence: Score < threshold

    HighConfidence --> AddToPlaylistActivity

    LowConfidence --> AIEnabledCheck: Check use_ai_disambiguation

    state AIEnabledCheck <<choice>>
    AIEnabledCheck --> AIActivity: Enabled
    AIEnabledCheck --> NoMatchState: Disabled

    state AIActivity {
        [*] --> BuildPrompt: Build disambiguation prompt
        BuildPrompt --> SelectProvider: Check AI_PROVIDER setting

        state provider_choice <<choice>>
        SelectProvider --> provider_choice
        provider_choice --> UseLangchain: Provider = langchain
        provider_choice --> UseClaude: Provider = claude

        UseLangchain --> CallOpenAI: OpenAI GPT-4 API
        UseClaude --> CallClaudeAPI: Anthropic Claude API

        CallOpenAI --> ParseJSON
        CallClaudeAPI --> ParseJSON: Parse JSON response

        ParseJSON --> ValidateResponse: Validate track selection
        ValidateResponse --> [*]: Return selected track
    }

    AIActivity --> AIResult: Activity complete

    state AIResult <<choice>>
    AIResult --> AddToPlaylistActivity: Track selected
    AIResult --> NoMatchState: No selection

    state AddToPlaylistActivity {
        [*] --> AddTrack: Call MCP add_track_to_playlist
        AddTrack --> WaitForAdd: Wait for Spotify response
        WaitForAdd --> VerifyAdd: Call verify_track_added
        VerifyAdd --> CheckPlaylist: Check playlist tracks

        state verify_check <<choice>>
        CheckPlaylist --> verify_check
        verify_check --> Verified: Track found in playlist
        verify_check --> NotVerified: Track not found

        NotVerified --> RetryAdd: Retry count < max
        RetryAdd --> AddTrack

        Verified --> [*]: Success
    }

    AddToPlaylistActivity --> SuccessState
    NoMatchState --> FailureState

    SuccessState --> CalculateMetrics: Calculate execution time
    FailureState --> CalculateMetrics

    CalculateMetrics --> ReturnResult: Create WorkflowResult
    ReturnResult --> [*]: Workflow complete

    note right of SearchActivity
        Retries: 3 attempts
        Timeout: 60s
        Backoff: Exponential
    end note

    note right of AIActivity
        Swappable providers:
        - Langchain (OpenAI)
        - Claude SDK (Anthropic)
    end note

    note right of AddToPlaylistActivity
        Includes verification
        to ensure track was
        actually added
    end note
```

---

## Deployment Architecture

### Temporal Mode Deployment (Production)

Production deployment setup with distributed Temporal infrastructure.

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[Nginx / CloudFlare]
    end

    subgraph "Application Tier"
        API1[FastAPI Instance 1<br/>:8000]
        API2[FastAPI Instance 2<br/>:8000]
        API3[FastAPI Instance 3<br/>:8000]

        Worker1[Temporal Worker 1]
        Worker2[Temporal Worker 2]
        Worker3[Temporal Worker 3]
    end

    subgraph "Temporal Cloud / Self-Hosted"
        TemporalCluster[Temporal Server Cluster]
        TemporalUI[Temporal Web UI<br/>:8080]
    end

    subgraph "Data Tier"
        PG[(PostgreSQL<br/>Temporal State)]
        Redis[(Redis<br/>Cache - Optional)]
    end

    subgraph "External Services"
        SpotifyAPI[Spotify Web API]
        OpenAIAPI[OpenAI API]
        ClaudeAPI[Anthropic API]
    end

    subgraph "Monitoring"
        Prometheus[Prometheus]
        Grafana[Grafana Dashboards]
        Logs[Centralized Logging]
    end

    Internet([Internet]) --> LB
    LB --> API1
    LB --> API2
    LB --> API3

    API1 --> TemporalCluster
    API2 --> TemporalCluster
    API3 --> TemporalCluster

    Worker1 --> TemporalCluster
    Worker2 --> TemporalCluster
    Worker3 --> TemporalCluster

    TemporalCluster --> PG
    TemporalCluster --> TemporalUI

    API1 -.-> Redis
    API2 -.-> Redis
    API3 -.-> Redis

    Worker1 --> SpotifyAPI
    Worker2 --> SpotifyAPI
    Worker3 --> SpotifyAPI

    Worker1 -.-> OpenAIAPI
    Worker2 -.-> ClaudeAPI
    Worker3 -.-> OpenAIAPI

    API1 --> Prometheus
    API2 --> Prometheus
    API3 --> Prometheus
    Worker1 --> Prometheus
    Worker2 --> Prometheus
    Worker3 --> Prometheus

    Prometheus --> Grafana

    API1 --> Logs
    API2 --> Logs
    API3 --> Logs
    Worker1 --> Logs
    Worker2 --> Logs
    Worker3 --> Logs

    classDef lb fill:#e3f2fd,stroke:#1565c0
    classDef app fill:#fff3e0,stroke:#e65100
    classDef temporal fill:#f3e5f5,stroke:#4a148c
    classDef data fill:#e0f2f1,stroke:#004d40
    classDef external fill:#fce4ec,stroke:#880e4f
    classDef monitoring fill:#fff9c4,stroke:#f57f17

    class LB lb
    class API1,API2,API3,Worker1,Worker2,Worker3 app
    class TemporalCluster,TemporalUI temporal
    class PG,Redis data
    class SpotifyAPI,OpenAIAPI,ClaudeAPI external
    class Prometheus,Grafana,Logs monitoring
```

### Standalone Mode Deployment (Simplified)

Lightweight deployment without Temporal infrastructure.

```mermaid
graph TB
    subgraph "Load Balancer (Optional)"
        LB[Nginx / CloudFlare]
    end

    subgraph "Application Tier"
        API1[FastAPI Instance 1<br/>:8000<br/>+ Workflow Executor]
        API2[FastAPI Instance 2<br/>:8000<br/>+ Workflow Executor]
    end

    subgraph "External Services"
        SpotifyAPI[Spotify Web API]
        OpenAIAPI[OpenAI API]
        ClaudeAPI[Anthropic API]
    end

    subgraph "Monitoring (Optional)"
        Logs[Logging Service]
    end

    Internet([Internet]) --> LB
    LB --> API1
    LB --> API2

    API1 --> SpotifyAPI
    API2 --> SpotifyAPI

    API1 -.-> OpenAIAPI
    API2 -.-> ClaudeAPI

    API1 --> Logs
    API2 --> Logs

    classDef lb fill:#e3f2fd,stroke:#1565c0
    classDef app fill:#fff3e0,stroke:#e65100
    classDef external fill:#fce4ec,stroke:#880e4f
    classDef monitoring fill:#fff9c4,stroke:#f57f17

    class LB lb
    class API1,API2 app
    class SpotifyAPI,OpenAIAPI,ClaudeAPI external
    class Logs monitoring
```

**Deployment Mode Comparison:**

| Aspect | Temporal Mode | Standalone Mode |
|--------|---------------|-----------------|
| **Components** | 7+ (API, Worker, Temporal, PostgreSQL, etc.) | 1-2 (FastAPI only) |
| **Scaling** | Horizontal (multiple workers) | Horizontal (stateless API) |
| **State Storage** | PostgreSQL (persistent) | In-memory (ephemeral) |
| **Cost** | Higher ($200-400/month) | Lower ($10-50/month) |
| **Complexity** | High (orchestration layer) | Low (direct execution) |
| **Reliability** | High (durable workflows) | Medium (best-effort) |
| **Best For** | Production, high traffic | Development, low traffic |

---

## Technology Stack Summary

| Layer | Technology | Purpose | Required In |
|-------|-----------|---------|-------------|
| **Client** | iOS Shortcuts | User interface for syncing | Both modes |
| **API** | FastAPI | REST API endpoints | Both modes |
| **Orchestration** | Temporal | Durable workflow execution | Temporal mode only |
| **Executor** | Standalone Executor | Direct workflow execution | Standalone mode only |
| **Integration** | MCP (Model Context Protocol) | Spotify API wrapper | Both modes |
| **AI** | OpenAI GPT-4 / Anthropic Claude | Track disambiguation | Both modes |
| **Matching** | RapidFuzz | Fuzzy string matching | Both modes |
| **Database** | PostgreSQL | Temporal workflow state | Temporal mode only |
| **HTTP Client** | HTTPX | Async HTTP requests | Both modes |
| **Spotify Client** | Spotipy | Spotify API SDK | Both modes |

---

## Key Design Decisions

### 1. Dual Execution Modes
- **Why**: Different deployment scenarios have different requirements
- **How**: `USE_TEMPORAL` flag toggles between Temporal orchestration and direct execution
- **Benefit**: Simple deployments don't need complex infrastructure, but can scale up when needed
- **Trade-off**: In standalone mode, lose durability and advanced retry capabilities

### 2. Fire-and-Forget Architecture
- **Why**: Instant response to iOS users, no waiting for completion
- **How**: Workflows run asynchronously after API returns 202 Accepted
- **Benefit**: Better UX, resilient to network issues
- **Implementation**: Temporal workflows (temporal mode) or asyncio tasks (standalone mode)

### 3. Temporal for Orchestration (Optional)
- **Why**: Need durable, reliable workflow execution with retries for production
- **How**: Workflows persist state, survive worker restarts
- **Benefit**: Automatic retries, progress tracking, failure recovery
- **When**: Enable with `USE_TEMPORAL=true` for production deployments

### 4. Standalone Executor (Alternative)
- **Why**: Not all deployments need Temporal's complexity
- **How**: Direct async execution with in-memory state and basic retry logic
- **Benefit**: Simple deployment, lower resource usage, faster development
- **When**: Enable with `USE_TEMPORAL=false` for development or simple deployments

### 5. MCP for Spotify Integration
- **Why**: Standardized protocol for API tool calling
- **How**: MCP server exposes Spotify operations as callable tools
- **Benefit**: Clean separation, easy to mock/test, swappable implementations
- **Note**: Works identically in both execution modes

### 6. Swappable AI Providers
- **Why**: Not all users have access to same AI services
- **How**: Abstract AI interface with multiple implementations (Langchain/OpenAI or Claude SDK)
- **Benefit**: Flexibility, cost optimization, fallback options
- **Note**: Both providers work in both execution modes

### 7. ISRC Priority Matching
- **Why**: Most accurate way to match tracks across services
- **How**: Check ISRC first, fall back to fuzzy matching
- **Benefit**: Higher accuracy, fewer false positives
- **Note**: Same matching logic in both execution modes

---

## Related Documentation

- [README.md](./README.md) - Project overview and quick start
- [docs/EXECUTION_MODES.md](./docs/EXECUTION_MODES.md) - **Detailed comparison of Temporal vs Standalone modes**
- [SETUP.md](./SETUP.md) - Local development setup (both modes)
- [TESTING.md](./TESTING.md) - Testing guide
- [docs/ios-shortcuts-setup.md](./docs/ios-shortcuts-setup.md) - iOS integration guide
