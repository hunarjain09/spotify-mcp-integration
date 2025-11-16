# Architecture Documentation

This document provides detailed architectural diagrams and explanations of the Spotify MCP Integration system.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Sync Workflow Sequence](#sync-workflow-sequence)
3. [Component Interactions](#component-interactions)
4. [Data Flow](#data-flow)
5. [Activity Execution Flow](#activity-execution-flow)
6. [Deployment Architecture](#deployment-architecture)

---

## System Architecture

High-level overview of the system components and their relationships.

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

## Sync Workflow Sequence

Detailed sequence diagram showing the complete flow of a song sync request.

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

Production deployment setup with Docker containers.

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

---

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Client** | iOS Shortcuts | User interface for syncing |
| **API** | FastAPI | REST API endpoints |
| **Orchestration** | Temporal | Durable workflow execution |
| **Integration** | MCP (Model Context Protocol) | Spotify API wrapper |
| **AI** | OpenAI GPT-4 / Anthropic Claude | Track disambiguation |
| **Matching** | RapidFuzz | Fuzzy string matching |
| **Database** | PostgreSQL | Temporal workflow state |
| **HTTP Client** | HTTPX | Async HTTP requests |
| **Spotify Client** | Spotipy | Spotify API SDK |

---

## Key Design Decisions

### 1. Fire-and-Forget Architecture
- **Why**: Instant response to iOS users, no waiting for completion
- **How**: Temporal workflows run asynchronously after API returns 202 Accepted
- **Benefit**: Better UX, resilient to network issues

### 2. Temporal for Orchestration
- **Why**: Need durable, reliable workflow execution with retries
- **How**: Workflows persist state, survive worker restarts
- **Benefit**: Automatic retries, progress tracking, failure recovery

### 3. MCP for Spotify Integration
- **Why**: Standardized protocol for API tool calling
- **How**: MCP server exposes Spotify operations as callable tools
- **Benefit**: Clean separation, easy to mock/test, swappable implementations

### 4. Swappable AI Providers
- **Why**: Not all users have access to same AI services
- **How**: Abstract AI interface with multiple implementations
- **Benefit**: Flexibility, cost optimization, fallback options

### 5. ISRC Priority Matching
- **Why**: Most accurate way to match tracks across services
- **How**: Check ISRC first, fall back to fuzzy matching
- **Benefit**: Higher accuracy, fewer false positives

---

## Related Documentation

- [SETUP.md](./SETUP.md) - Local development setup
- [TESTING.md](./TESTING.md) - Testing guide
- [README.md](./README.md) - Project overview and quick start
- [docs/ios-shortcuts-setup.md](./docs/ios-shortcuts-setup.md) - iOS integration guide
