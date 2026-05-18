### Storage

1 Process - 1 Pool
1 Pool - N Databases
1 Repo - 1 Database
1 Database - N Connections
1 Pool - 1 Eventbus

### Model

Similarity as Python Pydantic model for Object (Node/Edge) of Graph => Model for in-memory graph

### Schema

Similarity as ORM --> It define the real Schema inside Database => Schema for physic graph

### Adpater

Giống Repository

### Luồng

ingestion pipeline
-> tạo KnowledgeGraph trong RAM
-> KuzuAdapter.connect() ==> KuzuPool
-> KuzuAdapter.create_schema() ==> Schema
-> KuzuAdapter.load_graph(graph, csv_dir)
-> graph được ghi vào KuzuDB
