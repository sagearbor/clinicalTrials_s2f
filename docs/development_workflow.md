Development Workflow DiagramThis diagram illustrates the cyclical development process for this agentic framework, showing the interaction between the developer, the AI agents, and the automated GitHub Actions.graph TD
    subgraph "Manual Steps"
        A[Developer decides to start work]
        B[Developer / Lead Agent runs AI agents (Codex) based on NEXT_ACTIONS.md]
    end

    subgraph "Automated GitHub Actions"
        C["(Action) Propose Next Actions"]
        D["(Action) Update Progress Report"]
    end

    subgraph "Repository Artifacts (State)"
        E[NEXT_ACTIONS.md]
        F[config/checklist.yml]
        G[PROGRESS_LOGS/new/]
        H[PROGRESS.md]
    end

    %% Define the workflow connections
    A -- triggers --> C;
    C -- runs --> script1(scripts/propose_next_tasks.py);
    script1 -- reads --> F;
    script1 -- writes to --> E;
    E -- informs --> B;
    B -- updates --> F;
    B -- writes new logs to --> G;
    G -- provides input for --> D;
    D -- runs --> script2(scripts/update_progress.py);
    script2 -- reads --> G;
    script2 -- reads --> F;
    script2 -- writes to --> H;
    H -- informs --> A;

    %% Styling
    classDef manual fill:#e6fffa,stroke:#00bfa5
    classDef action fill:#e3f2fd,stroke:#2196f3
    classDef state fill:#f3e5f5,stroke:#9c27b0
    
    class A,B manual;
    class C,D action;
    class E,F,G,H state;
