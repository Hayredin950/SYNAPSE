<div align="center">

<img src="docs/assets/synapse-logo.png" alt="SYNAPSE Logo" height="400">

# 🚀 SYNAPSE
**FAANG-Grade Tech Intelligence & RAG Platform**

[![GitHub license](https://img.shields.io/github/license/Hayredin950/SYNAPSE)](https://github.com/Hayredin950/SYNAPSE/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/Hayredin950/SYNAPSE)](https://github.com/Hayredin950/SYNAPSE/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Hayredin950/SYNAPSE)](https://github.com/Hayredin950/SYNAPSE/network/members)
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=flat&logo=django&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=flat&logo=langchain&logoColor=white)

---

</div>

## ✨ Key Features

### 🧠 AI Agent System
- **ReAct Pattern**: Reasoning + Acting loop with full transparency
- **5 Specialized Agents**: Research, Document, Trend, Project, and Scheduler agents
- **Tool Registry**: Search, document generation, trend analysis, project scaffolding, and more
- **Memory Systems**: 4-layer memory (buffer, summary, vector, entity)

### 🔍 RAG & Knowledge Management
- **pgvector Integration**: Semantic search with PostgreSQL
- **Document Loaders**: PDF, web, GitHub, and more
- **Source Citation**: Full reference tracking for all generated content
- **Text Splitting**: Smart chunking with 200-character overlap

### 📊 Trend & Intelligence
- **arXiv Integration**: Academic paper search and analysis
- **GitHub API**: Real-time repository trend data
- **Google Trends**: Technology adoption tracking
- **Hacker News & Medium**: News and article aggregation

### 📝 Document Generation
- **PDF Reports**: ReportLab-based with tables, charts, images
- **PowerPoint Presentations**: Multiple layout support
- **Word Documents**: Professional formatting with TOC
- **Markdown Generation**: Documentation and guides

### 🛠️ Project Scaffolding
- **Django REST API**: Complete backend templates
- **FastAPI Microservices**: Modern async setup
- **Next.js & React**: Frontend applications
- **Data Science Projects**: Jupyter notebook templates

### 🔒 Security & Safety
- **Tool Validation**: Input schema checks
- **Rate Limiting**: Per-user request limits
- **Cost Tracking**: Token and budget management
- **Output Sanitization**: Redaction of sensitive data

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|---------------|
| **Backend** | Django REST Framework, PostgreSQL, pgvector |
| **AI/ML** | LangChain, OpenAI GPT-3.5/4, tiktoken |
| **Vector Store** | pgvector (PostgreSQL extension) |
| **Task Queue** | Celery |
| **Frontend** | Next.js, React, Tailwind CSS |
| **Document Gen** | ReportLab, python-pptx, python-docx |
| **Testing** | pytest |
| **CI/CD** | GitHub Actions |

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- PostgreSQL 15+ with pgvector
- Node.js 18+ (for frontend)

### Installation
```bash
# Clone the repository
git clone https://github.com/Hayredin950/SYNAPSE.git
cd SYNAPSE

# Set up backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set up PostgreSQL
# Make sure pgvector extension is installed
# Update DATABASE_URL in .env

# Run migrations
python manage.py migrate

# Start the backend
python manage.py runserver

# Set up frontend (in new terminal)
cd frontend
npm install
npm run dev
```

### Configuration
Create a `.env` file:
```env
# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/synapse

# API Keys
GITHUB_API_KEY=your_github_api_key
GOOGLE_API_KEY=your_google_api_key

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
```

## 📂 Project Structure
```
SYNAPSE/
├── ai_engine/              # AI and agent systems
│   ├── agents/            # Research, document, trend agents
│   ├── embeddings/        # Embedding generation
│   ├── middleware/        # Safety, rate limiting, moderation
│   ├── nlp/               # NLP processing pipelines
│   └── rag/               # RAG and vector store logic
├── backend/               # Django backend
│   ├── apps/              # Core, articles, agents, automation, billing, documents
│   └── ...
├── frontend/              # Next.js frontend
│   ├── src/
│   └── ...
├── scraper/               # Web scrapers for data collection
│   ├── spiders/           # arXiv, GitHub, HackerNews, Twitter, YouTube
│   └── ...
├── docs/                  # Project documentation
│   └── ...
├── tests/                 # Test suite
└── ...
```

## 🎯 Usage Examples

### Research Agent
```python
from ai_engine.agents.research_agent import ResearchAgent

agent = ResearchAgent()
result = agent.execute({
    "task": "Analyze the current state of AI agent frameworks",
    "user_id": "user_123"
})
print(result["final_answer"])
```

### RAG Query
```python
from ai_engine.rag.pipeline import RAGPipeline

pipeline = RAGPipeline()
result = pipeline.query("What are the best practices for LLM safety?")
print(f"Answer: {result['answer']}")
print("\nSources:")
for source in result['sources']:
    print(f"  {source['source']}: {source['excerpt']}")
```

## 📊 Architecture Overview
```
┌─────────────┐    ┌───────────────┐    ┌───────────────┐
│  Frontend   │    │  Backend API  │    │   PostgreSQL   │
│  (Next.js)  │────│  (Django)     │────│ (with pgvector)│
└─────────────┘    └───────────────┘    └───────────────┘
                          │
                          ▼
                  ┌───────────────┐
                  │  AI Engine    │
                  │ (LangChain)   │
                  └───────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ Research │    │ Document │    │  Trend   │
    │  Agent   │    │  Agent   │    │  Agent   │
    └──────────┘    └──────────┘    └──────────┘
```

## 📚 Documentation

- **DOCUMENTATION_SUMMARY.md**: Complete AI agent and RAG documentation
- **WHATS_NEW.md**: Release notes and change history
- **DEPLOYMENT.md**: Production deployment guide
- **TASKS.md**: Project task list and milestones

## 🌟 Highlights
- **Production-Grade**: FAANG-level architecture and code quality
- **Full-Stack**: Complete backend + frontend implementation
- **AI-First**: Built around LangChain and OpenAI
- **Open-Source**: MIT licensed, community-driven
- **Well-Documented**: Comprehensive technical and user guides

## 📄 License
MIT © [Hayredin950](https://github.com/Hayredin950)

## 📞 Contact
- GitHub: [Hayredin950](https://github.com/Hayredin950)
- Profile: [hayredin.vercel.app](https://hayredin.vercel.app/)

---

<div align="center">
Made with ❤️ by Hayredin950
</div>
