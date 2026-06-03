# 🧠 SYNAPSE: AI-Powered Technology Intelligence Monorepo

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Monorepo](https://img.shields.io/badge/Structure-Monorepo-blueviolet.svg)](https://turbo.build/)
[![AI Engine](https://img.shields.io/badge/AI-Engine-FF6F61.svg)](synapse/ai_engine)
[![Backend](https://img.shields.io/badge/Backend-Django%20%2F%20FastAPI-092E20.svg)](synapse/backend)
[![Frontend](https://img.shields.io/badge/Frontend-Next.js%20%2F%20React-000000.svg)](synapse/frontend)

SYNAPSE is an enterprise-grade, FAANG-style technology intelligence platform. It leverages autonomous AI agents, semantic search, and real-time data pipelines to collect, analyze, and surface high-value insights from across the technical landscape (GitHub, ArXiv, HN, etc.).

## 🏗️ Monorepo Architecture

This repository is structured as a unified monorepo containing all components of the SYNAPSE ecosystem:

### 核心组件 (Core Components)
- **`synapse/`**: The primary application suite.
  - **`ai_engine/`**: LangChain-powered RAG pipeline, autonomous agents, and NLP services.
  - **`backend/`**: Scalable Django REST & FastAPI services handling business logic, orchestration, and integrations.
  - **`frontend/`**: Modern Next.js dashboard with real-time visualizations and command palette.
- **`lib/`**: Shared libraries and packages used across the ecosystem.
  - `api-spec/`: OpenAPI specifications and Orval configurations.
  - `db/`: Centralized database schemas (Drizzle/PostgreSQL).
- **`artifacts/`**: Supporting services and sandbox environments.
  - `api-server/`: Lightweight TS-based utility API.
  - `mockup-sandbox/`: Rapid prototyping environment for UI components.

## 🚀 Key Technologies

| Layer | Stack |
|-------|-------|
| **AI/ML** | LangChain, OpenAI (GPT-4), Whisper, spaCy, HuggingFace |
| **Backend** | Python 3.11, Django 4.2, FastAPI, Celery, Redis |
| **Frontend** | TypeScript, Next.js 14, React 18, TailwindCSS, Framer Motion |
| **Database** | PostgreSQL (pgvector), Redis, S3 |
| **DevOps** | Docker, GitHub Actions, AWS, Prometheus, Grafana |

## 🌟 Professional Features

- **Autonomous Research Agents**: Plan-and-execute agents that synthesize multi-source data into cited reports.
- **Semantic Intelligence**: Hybrid search (BM25 + Vector) across papers, repositories, and articles.
- **Automation Marketplace**: A hub for installing and sharing no-code automation workflows.
- **Knowledge Graph**: Interactive, entity-extracted graph visualization of technical concepts.
- **Enterprise Security**: MFA, Scoped API Keys, Audit Logs, and PII Redaction.

## 🛠️ Getting Started

Detailed setup instructions for each component can be found in their respective directories:

1.  **Full System**: See [synapse/README.md](synapse/README.md) for Docker-based deployment.
2.  **AI Engine**: Explore [synapse/ai_engine/README.md](synapse/ai_engine/README.md).
3.  **Developer Portal**: Interactive API docs at `http://localhost:8000/api/schema/swagger-ui/`.

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Author
**Hayredin Mohammed**
- GitHub: [@HayreBuilds](https://github.com/HayreBuilds)
