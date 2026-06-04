# SYNAPSE AI Agent Documentation Summary

## Executive Overview

This document consolidates the key technical details from `docs/13_AI_Agent_Spec.tex` and `docs/06_Implementation_Guide.tex`, focusing on LangChain ReAct agent architecture, tool registration, agent framework design, and Phase 5.1 implementation details.

---

## 1. LangChain ReAct Agent Architecture

### 1.1 ReAct Pattern Foundation

The SYNAPSE AI Agent layer is built on the **ReAct (Reasoning + Acting)** pattern, which combines large language models' reasoning capabilities with tool-based action execution through a structured, transparent loop.

**Core Loop - Four Sequential Stages:**

1. **Thought**: Agent reasons about current state, available tools, and optimal next steps (internal cognition)
2. **Action**: Agent selects a specific tool and constructs appropriate input parameters
3. **Observation**: Tool executes and returns structured feedback
4. **Repeat**: Agent evaluates observation against task goal and either continues or terminates with final answer

This transparent loop allows developers to inspect agent decision-making at each step, improving debugging and safety oversight.

### 1.2 Agent Loop Mechanics

```python
while not task_complete:
    thought = agent.reason(context, goal)
    action, tool_name, tool_input = agent.select_action(thought)
    observation = tools[tool_name].execute(tool_input)
    context = agent.update_context(observation)
    task_complete = agent.is_goal_reached(observation)
```

**Maintained Execution Context Includes:**
- Current task objective and subtasks
- Conversation history and memory
- Tool availability and constraints
- Token budget and cost limits
- Timeout tracking per tool and overall agent run

### 1.3 LangChain AgentExecutor Configuration

**Core Configuration Example:**

```python
from langchain.agents import AgentExecutor, create_react_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

executor = AgentExecutor.from_agent_and_tools(
    agent=agent,
    tools=tool_list,
    verbose=True,
    max_iterations=10,
    max_execution_time=300,
    early_stopping_method="force",
    return_intermediate_steps=True,
    handle_parsing_errors=True
)
```

**Critical AgentExecutor Parameters:**

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `max_iterations` | 10 | Maximum ReAct loop cycles per SYNAPSE spec |
| `max_execution_time` | 300s | Hard timeout for entire agent run |
| `early_stopping_method` | "force" | Handles max iterations or timeout |
| `return_intermediate_steps` | True | Captures all thought-action-observation records |
| `handle_parsing_errors` | True | Graceful error recovery for malformed output |
| `trim_intermediate_steps` | 5 | Memory optimization for long-running agents |

---

## 2. Tool Registration System

### 2.1 Standardized Tool Format

Tools must be registered with the AgentExecutor using LangChain's `StructuredTool` class:

```python
from langchain.tools import Tool, StructuredTool

tools = [
    StructuredTool.from_function(
        func=search_knowledge_base,
        name="search_knowledge_base",
        description="Search internal knowledge base",
        args_schema=SearchKnowledgeBaseInput,
    ),
    StructuredTool.from_function(
        func=generate_pdf,
        name="generate_pdf",
        description="Generate PDF documents",
        args_schema=GeneratePDFInput,
    ),
]
```

**Key Components:**
- `func`: Actual implementation function
- `name`: Unique tool identifier
- `description`: Human-readable tool description
- `args_schema`: Pydantic BaseModel defining input parameters

### 2.2 Tool Categories in SYNAPSE

#### Knowledge Base Tools
- **search_knowledge_base**: Semantic + keyword search via pgvector/PostgreSQL
- **fetch_articles**: Retrieve articles from arXiv, Medium, Hacker News (date range support)

#### Trend Analysis Tools
- **analyze_trends**: Technology adoption analysis across multiple metrics
- **get_technology_trend**: Real-time trend data from GitHub API and Google Trends

#### Document Generation Tools
- **generate_pdf**: ReportLab-based PDF creation with tables, charts, images
- **generate_ppt**: python-pptx PowerPoint presentations with multiple layouts
- **generate_word_doc**: python-docx Word documents with TOC and formatting

#### Project Creation Tools
- **create_project**: Bootstrap projects (Django REST, FastAPI, Next.js, React, Data Science)

#### Cloud Storage Tools
- **upload_to_drive**: Google Drive integration with folder organization

#### Code Search Tools
- Search repositories, analyze code patterns, retrieve snippets

### 2.3 Tool Input Schema Example

```python
class SearchKnowledgeBaseInput(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(default=10, description="Max results")
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional filters (source, date_range, category)"
    )

class SearchResult(BaseModel):
    id: str
    title: str
    content: str
    relevance_score: float
    source: str
    metadata: Dict[str, Any]
```

---

## 3. Agent Framework Design

### 3.1 Five Specialized Agent Types

#### ResearchAgent
- **Purpose**: Autonomously search and synthesize multi-source information
- **Tools**: search_knowledge_base, fetch_articles, vector store retrieval
- **Tasks**: Technology landscape analysis, literature reviews, solution comparisons

#### DocumentAgent
- **Purpose**: Generate professional documents in multiple formats
- **Tools**: generate_pdf, generate_ppt, generate_word_doc, markdown generation
- **Tasks**: Quarterly trend reports, project proposals, training materials

#### TrendAgent
- **Purpose**: Analyze technology trends and adoption patterns
- **Tools**: analyze_trends, search_github, fetch_arxiv_papers, get_technology_trend
- **Tasks**: Emerging framework identification, adoption tracking, GitHub trends

#### ProjectAgent
- **Purpose**: Scaffold new software projects with complete structures
- **Tools**: create_project, file system operations
- **Tasks**: FastAPI microservices, Next.js applications, Django REST APIs

#### SchedulerAgent
- **Purpose**: Manage automation workflows and task orchestration
- **Tools**: Celery task scheduling, workflow orchestration
- **Tasks**: Weekly reports, scheduled research queries, agent chaining

### 3.2 Memory Management Systems

SYNAPSE implements four complementary memory strategies:

#### 1. ConversationBufferWindowMemory
- Stores last N conversation turns (default: 10)
- Lightweight, fast retrieval
- Suitable for short-term context
- TTL: 30 days in PostgreSQL

```python
from langchain.memory import ConversationBufferWindowMemory

memory = ConversationBufferWindowMemory(
    k=10,
    memory_key="chat_history",
    return_messages=True
)
```

#### 2. ConversationSummaryMemory
- Automatically summarizes conversation history
- Reduces context window usage by 70-80%
- Updated every 5 conversation turns
- Useful for long-running sessions

```python
from langchain.memory import ConversationSummaryMemory
from langchain_openai import ChatOpenAI

memory = ConversationSummaryMemory(
    llm=ChatOpenAI(model="gpt-3.5-turbo"),
    buffer="",
    memory_key="chat_summary"
)
```

#### 3. VectorStoreRetrieverMemory
- Semantic similarity-based retrieval of relevant past interactions
- Powered by pgvector
- Enables knowledge accumulation across sessions

```python
from langchain.memory import VectorStoreRetrieverMemory
from langchain_community.vectorstores import Chroma

vectorstore = Chroma(
    embedding_function=embeddings,
    collection_name="agent_memory"
)

memory = VectorStoreRetrieverMemory(
    vectorstore=vectorstore,
    memory_key="relevant_history",
    input_key="input"
)
```

#### 4. Entity Memory
- Tracks named entities (technologies, projects, concepts)
- Maintains entity graphs for relationship mapping
- Tracks mention frequency and temporal patterns
- Stored as JSON in PostgreSQL

### 3.3 Prompt Templates

#### System Prompt

```python
SYSTEM_PROMPT = """You are an AI agent in the SYNAPSE platform,
designed to autonomously execute complex multi-step tasks.
You have access to specialized tools for research, document
generation, trend analysis, and project scaffolding.

Guidelines:
1. Break complex tasks into logical subtasks
2. Use available tools to gather information
3. Cite sources for all information retrieved
4. Always validate data before using it
5. Respect user privacy and data security
6. Do not make assumptions without verification
7. Ask for clarification if task is ambiguous

Available tools: {tools}

Format your response as JSON with 'thought', 'action',
'action_input', and 'observation' fields."""
```

#### Human Prompt

```python
HUMAN_PROMPT = """Task: {task}

Current Date: {current_date}
User: {user_id}
Context: {context}

Previous steps taken:
{previous_steps}

Next steps to consider:
{next_steps_hint}"""
```

### 3.4 Output Parsing

```python
from langchain.agents.output_parsers import ReActJsonSingleInputOutputParser

parser = ReActJsonSingleInputOutputParser()
parsed_output = parser.parse(agent_response)

class ParsedOutput(BaseModel):
    thought: str
    action: str
    action_input: Dict[str, Any]
    observation: Optional[str]
    final_answer: Optional[str]
```

### 3.5 Streaming and Callbacks

```python
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

class CustomAgentCallback(StreamingStdOutCallbackHandler):
    def on_agent_action(self, action, **kwargs):
        print(f"Agent Action: {action.tool}")
        print(f"Input: {action.tool_input}")
    
    def on_agent_finish(self, finish, **kwargs):
        print(f"Final Answer: {finish.output}")

executor = AgentExecutor(
    agent=agent,
    tools=tools,
    callbacks=[CustomAgentCallback()],
)
```

---

## 4. RAG (Retrieval-Augmented Generation) Pipeline

### 4.1 ConversationalRetrievalChain

```python
from langchain.chains import ConversationalRetrievalChain
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import Chroma

retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5}
)

qa_chain = ConversationalRetrievalChain.from_llm(
    llm=ChatOpenAI(model="gpt-4", temperature=0.3),
    retriever=retriever,
    memory=memory,
    return_source_documents=True,
    verbose=True
)

result = qa_chain({"question": query})
```

### 4.2 Vector Store Configuration (pgvector)

```python
from langchain_community.vectorstores.pgvector import PGVector

vectorstore = PGVector.from_documents(
    documents=docs,
    embedding=embeddings,
    connection_string=db_url,
    collection_name="synapse_knowledge",
    pre_delete_collection=False
)

retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5}
)

# MMR (Maximal Marginal Relevance) retrieval for diversity
retriever_mmr = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 5, "fetch_k": 20}
)
```

### 4.3 Document Loaders

```python
from langchain_community.document_loaders import (
    PDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
    WebBaseLoader,
    GitHubRepositoryLoader
)

pdf_loader = PDFLoader("document.pdf")
docs = pdf_loader.load()

web_loader = WebBaseLoader("https://example.com/docs")
web_docs = web_loader.load()

github_loader = GitHubRepositoryLoader(
    repo_owner="torvalds",
    repo_name="linux"
)
```

### 4.4 Text Splitting Strategy

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", " ", ""],
    length_function=len
)

chunks = splitter.split_documents(documents)
```

**Configuration Notes:**
- Chunk size: 1000 characters (optimal for semantic search)
- Chunk overlap: 200 characters (maintains context continuity)
- Separators: Hierarchical breakdown by paragraph, line, word
- Metadata: Source, page number, chunk index preserved

### 4.5 Retrieval Strategies

**Similarity Search:**
```python
results = vectorstore.similarity_search(
    query="machine learning frameworks",
    k=5
)
```

**Maximal Marginal Relevance (MMR):**
```python
results = vectorstore.max_marginal_relevance_search(
    query="python web frameworks",
    k=5,
    fetch_k=20,
    lambda_mult=0.5
)
```

### 4.6 Source Citation System

```python
class CitedAnswer(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float

def format_with_citations(result):
    answer = result["answer"]
    sources = result["source_documents"]
    
    citations = []
    for i, doc in enumerate(sources, 1):
        citations.append({
            "number": i,
            "source": doc.metadata.get("source"),
            "page": doc.metadata.get("page"),
            "excerpt": doc.page_content[:100]
        })
    
    return CitedAnswer(
        answer=answer,
        sources=citations,
        confidence=0.95
    )
```

---

## 5. Token Counting and Cost Tracking

```python
from tiktoken import encoding_for_model

class CostTracker:
    def __init__(self, model="gpt-4"):
        self.model = model
        self.encoder = encoding_for_model("gpt-4")
        self.input_cost_per_1k = 0.03
        self.output_cost_per_1k = 0.06
    
    def estimate_tokens(self, text):
        return len(self.encoder.encode(text))
    
    def calculate_cost(self, input_tokens, output_tokens):
        input_cost = (input_tokens / 1000) * self.input_cost_per_1k
        output_cost = (output_tokens / 1000) * self.output_cost_per_1k
        return input_cost + output_cost

tracker = CostTracker()
result = executor.invoke({"input": task})
total_cost = tracker.calculate_cost(
    result["input_tokens"],
    result["output_tokens"]
)
```

---

## 6. Agent Safety and Constraints

### 6.1 Tool Use Validation

```python
class ToolValidator:
    def __init__(self):
        self.dangerous_tools = [
            'delete_database',
            'modify_system_config',
            'access_production'
        ]
    
    def validate_tool_call(self, tool_name, tool_input, user_tier):
        # Check dangerous tools
        if tool_name in self.dangerous_tools:
            if user_tier != 'admin':
                raise PermissionError(f"User cannot call {tool_name}")
        
        # Validate input parameters
        if not self.validate_schema(tool_input):
            raise ValueError("Invalid tool input schema")
        
        # Check resource limits
        if not self.check_resource_limits(tool_name, user_tier):
            raise ResourceError("Resource limit exceeded")
        
        return True
```

### 6.2 Output Sanitization

```python
import re

class OutputSanitizer:
    SENSITIVE_PATTERNS = [
        r'(password|api_key|secret)["\']?\s*[:=]\s*["\']?([^"\'\s]+)',
        r'(token|Bearer)\s+([A-Za-z0-9\-._]+)',
        r'(email|email_address).*?([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+)',
        r'(phone|telephone)["\']?\s*[:=]\s*([0-9\-\+\(\)\s]+)'
    ]
    
    @staticmethod
    def sanitize(text):
        sanitized = text
        for pattern in OutputSanitizer.SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, r'\1: [REDACTED]', sanitized, flags=re.IGNORECASE)
        return sanitized
```

### 6.3 Cost Limits and Timeout Handling

```python
class ExecutionLimiter:
    def __init__(self, max_tokens_per_task=10000, timeout_per_tool=30, 
                 timeout_per_run=300):
        self.max_tokens = max_tokens_per_task
        self.tool_timeout = timeout_per_tool
        self.run_timeout = timeout_per_run
        self.token_counter = CostTracker()
    
    def check_token_budget(self, tokens_used):
        if tokens_used > self.max_tokens:
            raise TokenLimitExceeded(f"Exceeded {self.max_tokens} token limit")
        return True
    
    def enforce_tool_timeout(self, tool_name, func, args):
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Tool {tool_name} exceeded {self.tool_timeout}s")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.tool_timeout)
        
        try:
            result = func(*args)
            signal.alarm(0)
            return result
        except Exception as e:
            signal.alarm(0)
            raise
```

### 6.4 Rate Limiting

```python
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self):
        self.user_limits = {
            'free': {'requests_per_hour': 10, 'tokens_per_day': 5000},
            'pro': {'requests_per_hour': 100, 'tokens_per_day': 100000},
            'enterprise': {'requests_per_hour': 1000, 'tokens_per_day': 1000000}
        }
        self.request_tracker = {}
    
    def is_allowed(self, user_id, user_tier):
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        if user_id not in self.request_tracker:
            self.request_tracker[user_id] = []
        
        # Clean old requests
        self.request_tracker[user_id] = [
            req_time for req_time in self.request_tracker[user_id]
            if req_time > hour_ago
        ]
        
        limit = self.user_limits[user_tier]['requests_per_hour']
        
        if len(self.request_tracker[user_id]) >= limit:
            return False
        
        self.request_tracker[user_id].append(now)
        return True
```

### 6.5 Dangerous Action Confirmation

```python
class ConfirmationRequester:
    DANGEROUS_ACTIONS = {
        'delete_project': 'permanent deletion',
        'reset_database': 'complete data reset',
        'modify_access_control': 'security settings change',
        'deploy_to_production': 'production deployment'
    }
    
    @staticmethod
    def requires_confirmation(action_name):
        return action_name in ConfirmationRequester.DANGEROUS_ACTIONS
    
    @staticmethod
    def get_confirmation_prompt(action_name):
        risk = ConfirmationRequester.DANGEROUS_ACTIONS.get(action_name)
        return f"This action will result in {risk}. Please confirm (yes/no): "
```

---

## 7. Phase 5.1 Implementation Details

### 7.1 Implementation Guide: Agentic AI Setup

**File Location:** `ai_service/agent.py`

```python
from langchain.agents import Tool, initialize_agent, AgentType
from langchain.chat_models import ChatOpenAI
from langchain.callbacks import StreamingStdOutCallbackHandler
import os

class SynapseAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            model_name="gpt-3.5-turbo",
            streaming=True,
            callbacks=[StreamingStdOutCallbackHandler()]
        )
        self.tools = self._setup_tools()
        self.agent = initialize_agent(
            self.tools,
            self.llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True
        )
    
    def _setup_tools(self):
        """Setup agent tools"""
        tools = [
            Tool(
                name="Search Knowledge Base",
                func=self.search_kb,
                description="Search the knowledge base for articles and papers"
            ),
            Tool(
                name="Generate PDF Report",
                func=self.generate_pdf,
                description="Generate a PDF report with findings"
            ),
            Tool(
                name="Create Project",
                func=self.create_project,
                description="Create a new project in the system"
            ),
        ]
        return tools
    
    def search_kb(self, query: str) -> str:
        """Search knowledge base"""
        # Implementation
        return "Results from knowledge base"
    
    def generate_pdf(self, title: str, content: str) -> str:
        """Generate PDF using ReportLab"""
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        
        filename = f"reports/{title}.pdf"
        c = canvas.Canvas(filename, pagesize=letter)
        c.drawString(100, 750, title)
        c.drawString(100, 730, content)
        c.save()
        return f"PDF generated: {filename}"
    
    def create_project(self, name: str, description: str) -> str:
        """Create project"""
        return f"Project '{name}' created successfully"
    
    def run(self, user_input: str) -> str:
        """Run agent"""
        return self.agent.run(user_input)
```

### 7.2 Key Dependencies

```
langchain==0.1.0
langchain-openai==0.0.5
langchain-community==0.0.10
langgraph==0.0.8
reportlab==4.0.9
python-pptx==0.6.21
python-docx==0.8.11
chromadb==0.4.21
tiktoken==0.5.2
```

### 7.3 Agent Type Configuration

Agent type selection via `AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION`:
- Structured output format
- Chat-based conversation style
- Zero-shot reasoning (no training examples needed)
- ReAct pattern implementation
- Detailed action descriptions

---

## 8. Key Integration Points

### 8.1 Database Integration
- PostgreSQL with pgvector for semantic search
- Vector embeddings stored in PostgreSQL
- Conversation and memory state persistence
- Entity tracking and relationship management

### 8.2 LLM Integration
- OpenAI ChatOpenAI (gpt-3.5-turbo, gpt-4)
- Streaming support for real-time output
- Token counting and cost tracking
- Temperature control for consistency (0.3 for RAG)

### 8.3 External APIs
- arXiv API for academic papers
- GitHub API for repository data
- Google Trends for trend analysis
- Medium API for articles
- Hacker News for news feeds

### 8.4 Document Generation
- ReportLab for PDF generation with tables, charts, images
- python-pptx for PowerPoint presentations
- python-docx for Word documents
- Markdown generation for documentation

### 8.5 File Storage
- PostgreSQL large object storage for generated documents
- Google Drive integration for cloud storage
- Local file system for temporary storage

---

## 9. Best Practices

1. **Tool Descriptions**: Provide detailed, specific descriptions for better agent tool selection
2. **Input Validation**: Use Pydantic schemas for all tool inputs
3. **Error Handling**: Implement graceful error recovery in tool implementations
4. **Timeout Management**: Set appropriate timeouts per tool and overall run
5. **Memory Management**: Use appropriate memory strategy based on use case
6. **Token Budget**: Monitor token usage and implement early stopping
7. **Source Citation**: Always include source attribution in RAG responses
8. **Safety First**: Validate all tool calls and sanitize outputs
9. **Monitoring**: Log all agent actions for debugging and auditing

---

## 10. Architecture Diagram

```
User Query
    ↓
AgentExecutor
    ↓
    ├─→ LLM (ChatOpenAI) → ReAct Reasoning
    │
    ├─→ Tool Registry
    │   ├─ Search Knowledge Base
    │   ├─ Fetch Articles
    │   ├─ Analyze Trends
    │   ├─ Generate Documents
    │   ├─ Create Projects
    │   └─ Cloud Storage
    │
    ├─→ Memory Systems
    │   ├─ Conversation Buffer
    │   ├─ Summary Memory
    │   ├─ Vector Store (pgvector)
    │   └─ Entity Tracking
    │
    ├─→ RAG Pipeline
    │   ├─ Document Loaders
    │   ├─ Text Splitters
    │   ├─ Vector Store Retrieval
    │   └─ Citation System
    │
    └─→ Safety Layer
        ├─ Input Validation
        ├─ Cost Tracking
        ├─ Rate Limiting
        ├─ Timeout Enforcement
        └─ Output Sanitization
            ↓
        Final Answer with Citations
```

---

## Document Metadata

- **Specification Document**: SYNAPSE AI Agent Specification (Version 1.0)
- **Implementation Guide**: SYNAPSE Implementation Guide
- **Focus Areas**: LangChain ReAct, Tool Registration, Agent Framework, Phase 5.1
- **Last Updated**: As per documentation timestamps
- **Framework**: LangChain 0.1.x with OpenAI integration
