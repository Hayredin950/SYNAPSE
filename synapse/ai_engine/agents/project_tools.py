"""
ai_engine.agents.project_tools
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Project scaffold generator for SYNAPSE ReAct agents.
Phase 5.3 — Project Builder (Week 15)

Templates implemented:
  1. django      — Django REST API (models, views, serializers, JWT auth, Docker, CI)
  2. fastapi      — FastAPI microservice (routes, schemas, SQLAlchemy, Docker, CI)
  3. nextjs       — Next.js 14 App Router (TypeScript, Tailwind, API client, auth store)
  4. datascience  — Python data science notebook project (Jupyter, pandas, sklearn, EDA)
  5. react_lib    — Reusable React component library (TypeScript, Storybook, Rollup, tests)

Each template returns a Dict[filename, content] that is packed into a .zip file.
"""

from __future__ import annotations

import io
import logging
import os
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
VALID_PROJECT_TYPES = ["django", "fastapi", "nextjs", "datascience", "react_lib"]

# SEC-06: Allowed feature flags per template — prevents injection of arbitrary
# strings into generated code via the features list.
_ALLOWED_FEATURES: Dict[str, frozenset] = {
    "django": frozenset(
        {
            "auth",
            "testing",
            "ci_cd",
            "payments",
            "stripe",
            "docker",
            "celery",
            "redis",
            "rest_framework",
            "graphql",
            "channels",
            "s3",
            "postgres",
            "admin",
            "api",
            "jwt",
        }
    ),
    "fastapi": frozenset(
        {
            "auth",
            "testing",
            "ci_cd",
            "jwt",
            "oauth2",
            "docker",
            "celery",
            "redis",
            "sqlalchemy",
            "postgres",
            "websockets",
            "prometheus",
            "sentry",
            "s3",
        }
    ),
    "nextjs": frozenset(
        {
            "auth",
            "testing",
            "ci_cd",
            "tailwind",
            "shadcn",
            "stripe",
            "sentry",
            "pwa",
            "i18n",
            "mdx",
            "prisma",
            "trpc",
            "zustand",
            "redux",
        }
    ),
    "datascience": frozenset(
        {
            "pytorch",
            "tensorflow",
            "sklearn",
            "xgboost",
            "plotly",
            "testing",
            "streamlit",
            "fastapi",
            "docker",
            "mlflow",
            "dvc",
            "ci_cd",
        }
    ),
    "react_lib": frozenset(
        {
            "typescript",
            "storybook",
            "jest",
            "vitest",
            "rollup",
            "testing",
            "vite",
            "tailwind",
            "emotion",
            "styled_components",
            "ci_cd",
        }
    ),
}


def _project_dir(user_id: str = "anonymous") -> Path:
    """Return the per-user project directory, creating it if needed.

    SEC-06: Sanitise user_id to prevent path traversal attacks.
    """
    import re as _re

    safe_user_id = _re.sub(r"[^a-zA-Z0-9_\-]", "_", str(user_id))
    if not safe_user_id or safe_user_id in ("", "_", "__"):
        safe_user_id = "anonymous"

    root = Path(os.environ.get("MEDIA_ROOT", "media")).resolve()
    d = root / "projects" / safe_user_id

    # Symlink-attack guard: ensure resolved path stays inside root
    try:
        d.resolve().relative_to(root)
    except ValueError:
        raise PermissionError(f"Resolved project path escapes media root: {d}")

    d.mkdir(parents=True, exist_ok=True)
    return d


def _rel_path(abs_path: Path) -> str:
    media_root = Path(os.environ.get("MEDIA_ROOT", "media"))
    try:
        return str(abs_path.relative_to(media_root))
    except ValueError:
        return str(abs_path)


def _pack_zip(files: Dict[str, str], zip_path: Path) -> int:
    """Write a dict of {filename: content} into a zip archive. Returns file size in bytes."""
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname, content in files.items():
            zf.writestr(fname, content)
    return zip_path.stat().st_size


# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------


def _django_template(name: str, features: List[str]) -> Dict[str, str]:
    app = name.replace("-", "_").lower()
    auth_middleware = (
        "\n    'django.contrib.auth.middleware.AuthenticationMiddleware',"
        if "auth" in features
        else ""
    )
    test_file = (
        (
            f"tests/test_{app}.py",
            f"from django.test import TestCase\n\nclass {app.title()}Test(TestCase):\n    def test_placeholder(self):\n        self.assertTrue(True)\n",
        )
        if "testing" in features
        else None
    )

    files = {
        "manage.py": f"""#!/usr/bin/env python
import os, sys
def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{app}.settings')
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
if __name__ == '__main__':
    main()
""",
        f"{app}/settings.py": f"""from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'change-me-in-production'
DEBUG = True
ALLOWED_HOSTS = ['*']
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'corsheaders', 'api',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',{auth_middleware}
    'django.contrib.messages.middleware.MessageMiddleware',
]
ROOT_URLCONF = '{app}.urls'
DATABASES = {{'default': {{'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'db', 'USER': 'postgres', 'PASSWORD': 'postgres', 'HOST': 'localhost', 'PORT': '5432'}}}}
STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
REST_FRAMEWORK = {{'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication']}}
""",
        f"{app}/urls.py": f"""from django.contrib import admin
from django.urls import path, include
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('api.urls')),
]
""",
        f"{app}/__init__.py": "",
        "api/__init__.py": "",
        "api/models.py": """from django.db import models
import uuid

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True
""",
        "api/serializers.py": """from rest_framework import serializers

class ExampleSerializer(serializers.Serializer):
    message = serializers.CharField()
""",
        "api/views.py": """from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

class HealthView(APIView):
    permission_classes = []
    def get(self, request):
        return Response({'status': 'ok'})
""",
        "api/urls.py": """from django.urls import path
from .views import HealthView
urlpatterns = [
    path('health/', HealthView.as_view(), name='health'),
]
""",
        "requirements.txt": """Django==4.2
djangorestframework==3.14
djangorestframework-simplejwt==5.3
django-cors-headers==4.3
psycopg2-binary==2.9
python-decouple==3.8
gunicorn==21.2
""",
        "Dockerfile": f"""FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "{app}.wsgi:application", "--bind", "0.0.0.0:8000"]
""",
        "docker-compose.yml": f"""version: '3.8'
services:
  web:
    build: .
    ports: ['8000:8000']
    environment:
      - DEBUG=1
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/db
    depends_on: [db]
  db:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: db
    volumes: [pgdata:/var/lib/postgresql/data]
volumes:
  pgdata:
""",
        ".env.example": "SECRET_KEY=change-me\nDEBUG=True\nDATABASE_URL=postgresql://postgres:postgres@localhost/db\n",
        ".gitignore": "__pycache__/\n*.py[cod]\n*.egg-info/\n.env\n*.sqlite3\nstaticfiles/\nmediafiles/\n",
        "README.md": f"# {name}\n\nDjango REST API project generated by SYNAPSE AI.\n\n## Quick Start\n\n```bash\npip install -r requirements.txt\npython manage.py migrate\npython manage.py runserver\n```\n",
    }
    if test_file:
        files[test_file[0]] = test_file[1]
    if "ci_cd" in features:
        files[
            ".github/workflows/ci.yml"
        ] = """name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with: {python-version: '3.11'}
      - run: pip install -r requirements.txt
      - run: python manage.py test
"""
    return files


def _fastapi_template(name: str, features: List[str]) -> Dict[str, str]:
    """FastAPI microservice scaffold."""
    pkg = name.replace("-", "_").lower()
    files: Dict[str, str] = {
        f"{pkg}/__init__.py": "",
        f"{pkg}/main.py": f'''"""
{name} — FastAPI microservice generated by SYNAPSE AI.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from {pkg}.routers import health, items

app = FastAPI(title="{name}", version="0.1.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(items.router, prefix="/items", tags=["Items"])
''',
        f"{pkg}/routers/__init__.py": "",
        f"{pkg}/routers/health.py": """from fastapi import APIRouter
router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok"}
""",
        f"{pkg}/routers/items.py": """from fastapi import APIRouter, HTTPException
from typing import List
from {pkg}.schemas import ItemCreate, ItemRead
from {pkg}.database import get_db, SessionLocal
from {pkg} import models
from sqlalchemy.orm import Session
from fastapi import Depends

router = APIRouter()

@router.get("/", response_model=List[ItemRead])
async def list_items(db: Session = Depends(get_db)):
    return db.query(models.Item).all()

@router.post("/", response_model=ItemRead, status_code=201)
async def create_item(payload: ItemCreate, db: Session = Depends(get_db)):
    item = models.Item(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
""".replace(
            "{pkg}", pkg
        ),
        f"{pkg}/schemas.py": """from pydantic import BaseModel
from typing import Optional

class ItemBase(BaseModel):
    name: str
    description: Optional[str] = None

class ItemCreate(ItemBase):
    pass

class ItemRead(ItemBase):
    id: int
    class Config:
        from_attributes = True
""",
        f"{pkg}/models.py": """from sqlalchemy import Column, Integer, String, Text
from {pkg}.database import Base

class Item(Base):
    __tablename__ = "items"
    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
""".replace(
            "{pkg}", pkg
        ),
        f"{pkg}/database.py": """from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
""",
        "requirements.txt": "fastapi==0.111.0\nuvicorn[standard]==0.29.0\nsqlalchemy==2.0.30\nalembic==1.13.1\npydantic==2.7.1\npython-dotenv==1.0.1\nhttpx==0.27.0\n",
        "Dockerfile": f'FROM python:3.11-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nEXPOSE 8000\nCMD ["uvicorn", "{pkg}.main:app", "--host", "0.0.0.0", "--port", "8000"]\n',
        "docker-compose.yml": f'version: "3.8"\nservices:\n  api:\n    build: .\n    ports: ["8000:8000"]\n    environment:\n      - DATABASE_URL=sqlite:///./dev.db\n',
        ".env.example": "DATABASE_URL=sqlite:///./dev.db\nSECRET_KEY=change-me\n",
        ".gitignore": "__pycache__/\n*.py[cod]\n.env\n*.db\ndist/\n.venv/\n",
        "README.md": f"# {name}\n\nFastAPI microservice generated by SYNAPSE AI.\n\n## Quick Start\n\n```bash\npip install -r requirements.txt\nuvicorn {pkg}.main:app --reload\n```\n\nDocs available at http://localhost:8000/docs\n",
        f"tests/__init__.py": "",
        f"tests/test_health.py": f"""from fastapi.testclient import TestClient
from {pkg}.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {{"status": "ok"}}
""",
    }
    if "ci_cd" in features:
        files[".github/workflows/ci.yml"] = (
            "name: CI\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-python@v4\n        with: {python-version: '3.11'}\n      - run: pip install -r requirements.txt pytest httpx\n      - run: pytest\n"
        )
    return files


def _nextjs_template(name: str, features: List[str]) -> Dict[str, str]:
    """Next.js 14 App Router scaffold with TypeScript and Tailwind."""
    files: Dict[str, str] = {
        "package.json": f'{{"name": "{name.lower()}", "version": "0.1.0", "private": true, "scripts": {{"dev": "next dev", "build": "next build", "start": "next start", "lint": "next lint", "test": "jest --passWithNoTests"}}, "dependencies": {{"next": "14.2.3", "react": "^18", "react-dom": "^18", "axios": "^1.7.2", "zustand": "^4.5.2", "lucide-react": "^0.379.0"}}, "devDependencies": {{"typescript": "^5", "@types/node": "^20", "@types/react": "^18", "@types/react-dom": "^18", "tailwindcss": "^3.4.1", "postcss": "^8", "autoprefixer": "^10", "eslint": "^8", "eslint-config-next": "14.2.3", "jest": "^29", "@testing-library/react": "^15", "@testing-library/jest-dom": "^6"}}}}',
        "tsconfig.json": '{"compilerOptions": {"target": "es5", "lib": ["dom", "dom.iterable", "esnext"], "allowJs": true, "skipLibCheck": true, "strict": true, "noEmit": true, "esModuleInterop": true, "module": "esnext", "moduleResolution": "bundler", "resolveJsonModule": true, "isolatedModules": true, "jsx": "preserve", "incremental": true, "plugins": [{"name": "next"}], "paths": {"@/*": ["./src/*"]}}, "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"], "exclude": ["node_modules"]}',
        "next.config.mjs": "/** @type {import('next').NextConfig} */\nconst nextConfig = {};\nexport default nextConfig;\n",
        "tailwind.config.ts": 'import type { Config } from "tailwindcss";\nconst config: Config = { content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"], theme: { extend: { colors: { primary: "#4F46E5", secondary: "#06B6D4", accent: "#8B5CF6" } } }, plugins: [] };\nexport default config;\n',
        "postcss.config.js": "module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } };\n",
        ".env.local.example": "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1\n",
        ".gitignore": "node_modules/\n.next/\nout/\nbuild/\n.env.local\n*.tsbuildinfo\n",
        f"README.md": f"# {name}\n\nNext.js 14 app generated by SYNAPSE AI.\n\n## Quick Start\n\n```bash\nnpm install\nnpm run dev\n```\n\nOpen http://localhost:3000\n",
        "src/app/layout.tsx": f'import type {{ Metadata }} from "next";\nimport "./globals.css";\nexport const metadata: Metadata = {{ title: "{name}", description: "Generated by SYNAPSE AI" }};\nexport default function RootLayout({{ children }}: {{ children: React.ReactNode }}) {{\n  return (<html lang="en"><body>{{children}}</body></html>);\n}}\n',
        "src/app/globals.css": "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n",
        "src/app/page.tsx": f'export default function HomePage() {{\n  return (\n    <main className="flex min-h-screen flex-col items-center justify-center p-24">\n      <h1 className="text-4xl font-bold text-primary">{name}</h1>\n      <p className="mt-4 text-gray-600">Generated by SYNAPSE AI</p>\n    </main>\n  );\n}}\n',
        "src/utils/api.ts": 'import axios from "axios";\nconst api = axios.create({ baseURL: process.env.NEXT_PUBLIC_API_URL || "/api", headers: { "Content-Type": "application/json" } });\napi.interceptors.request.use((config) => { const token = localStorage.getItem("access_token"); if (token) config.headers.Authorization = `Bearer ${token}`; return config; });\nexport default api;\n',
        "src/store/authStore.ts": 'import { create } from "zustand";\ninterface AuthState { user: null | { id: string; email: string }; token: string | null; login: (user: AuthState["user"], token: string) => void; logout: () => void; }\nexport const useAuthStore = create<AuthState>((set) => ({ user: null, token: null, login: (user, token) => { localStorage.setItem("access_token", token); set({ user, token }); }, logout: () => { localStorage.removeItem("access_token"); set({ user: null, token: null }); } }));\n',
        "src/types/index.ts": "export interface User { id: string; email: string; username: string; }\nexport interface ApiError { detail: string; }\nexport interface PaginatedResponse<T> { count: number; next: string | null; previous: string | null; results: T[]; }\n",
    }
    if "testing" in features:
        files["src/__tests__/page.test.tsx"] = (
            'import { render, screen } from "@testing-library/react";\nimport HomePage from "../app/page";\ndescribe("HomePage", () => { it("renders heading", () => { render(<HomePage />); expect(screen.getByRole("heading")).toBeInTheDocument(); }); });\n'
        )
    if "ci_cd" in features:
        files[".github/workflows/ci.yml"] = (
            "name: CI\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-node@v4\n        with: {node-version: '20'}\n      - run: npm ci\n      - run: npm run lint\n      - run: npm test\n      - run: npm run build\n"
        )
    return files


def _datascience_template(name: str, features: List[str]) -> Dict[str, str]:
    """Python data science project scaffold with Jupyter, pandas, sklearn."""
    pkg = name.replace("-", "_").lower()
    files: Dict[str, str] = {
        "requirements.txt": "numpy==1.26.4\npandas==2.2.2\nmatplotlib==3.8.4\nseaborn==0.13.2\nscikit-learn==1.4.2\njupyterlab==4.2.1\nipykernel==6.29.4\npython-dotenv==1.0.1\nopenpyxl==3.1.2\n",
        "environment.yml": f"name: {pkg}\nchannels:\n  - conda-forge\ndependencies:\n  - python=3.11\n  - numpy\n  - pandas\n  - matplotlib\n  - seaborn\n  - scikit-learn\n  - jupyterlab\n  - ipykernel\n  - pip\n",
        ".gitignore": "__pycache__/\n*.py[cod]\n.env\n.ipynb_checkpoints/\ndata/raw/\nmodels/*.pkl\n.venv/\ndist/\n",
        f"README.md": f"# {name}\n\nData science project generated by SYNAPSE AI.\n\n## Quick Start\n\n```bash\npip install -r requirements.txt\njupyter lab\n```\n\n## Project Structure\n\n```\n{pkg}/\n  data/        # raw and processed data\n  notebooks/   # Jupyter notebooks\n  src/         # reusable modules\n  models/      # saved model artifacts\n  reports/     # generated figures and reports\n```\n",
        "src/__init__.py": "",
        "src/data_loader.py": f'"""\nData loading utilities for {name}.\n"""\nimport pandas as pd\nfrom pathlib import Path\n\nDATA_DIR = Path(__file__).parent.parent / "data"\n\n\ndef load_csv(filename: str, **kwargs) -> pd.DataFrame:\n    """Load a CSV file from the data/raw directory."""\n    path = DATA_DIR / "raw" / filename\n    return pd.read_csv(path, **kwargs)\n\n\ndef save_processed(df: pd.DataFrame, filename: str) -> None:\n    """Save a processed DataFrame to data/processed."""\n    out_dir = DATA_DIR / "processed"\n    out_dir.mkdir(parents=True, exist_ok=True)\n    df.to_csv(out_dir / filename, index=False)\n',
        "src/features.py": '"""\nFeature engineering utilities.\n"""\nimport pandas as pd\nimport numpy as np\nfrom sklearn.preprocessing import StandardScaler, LabelEncoder\n\n\ndef encode_categoricals(df: pd.DataFrame, cols: list) -> pd.DataFrame:\n    """Label-encode categorical columns in-place."""\n    df = df.copy()\n    le = LabelEncoder()\n    for col in cols:\n        if col in df.columns:\n            df[col] = le.fit_transform(df[col].astype(str))\n    return df\n\n\ndef scale_numerics(df: pd.DataFrame, cols: list) -> pd.DataFrame:\n    """Standard-scale numeric columns."""\n    df = df.copy()\n    scaler = StandardScaler()\n    df[cols] = scaler.fit_transform(df[cols])\n    return df\n',
        "src/model.py": '"""\nModel training and evaluation.\n"""\nfrom sklearn.ensemble import RandomForestClassifier\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.metrics import classification_report, accuracy_score\nimport pandas as pd\nimport pickle\nfrom pathlib import Path\n\n\ndef train(X: pd.DataFrame, y: pd.Series, test_size: float = 0.2, random_state: int = 42):\n    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=random_state)\n    clf = RandomForestClassifier(n_estimators=100, random_state=random_state)\n    clf.fit(X_train, y_train)\n    y_pred = clf.predict(X_test)\n    print(classification_report(y_test, y_pred))\n    return clf, accuracy_score(y_test, y_pred)\n\n\ndef save_model(model, path: str = "models/model.pkl") -> None:\n    Path(path).parent.mkdir(parents=True, exist_ok=True)\n    with open(path, "wb") as f:\n        pickle.dump(model, f)\n\n\ndef load_model(path: str = "models/model.pkl"):\n    with open(path, "rb") as f:\n        return pickle.load(f)\n',
        "notebooks/01_eda.ipynb": '{"nbformat": 4, "nbformat_minor": 5, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python", "version": "3.11.0"}}, "cells": [{"cell_type": "markdown", "metadata": {}, "source": ["# Exploratory Data Analysis\\n"]}, {"cell_type": "code", "execution_count": null, "metadata": {}, "outputs": [], "source": ["import pandas as pd\\nimport matplotlib.pyplot as plt\\nimport seaborn as sns\\nfrom src.data_loader import load_csv\\n\\nsns.set_theme(style=\\"whitegrid\\")\\n%matplotlib inline\\n"]}, {"cell_type": "code", "execution_count": null, "metadata": {}, "outputs": [], "source": ["# df = load_csv(\\"your_data.csv\\")\\n# df.head()\\n"]}]}',
        "notebooks/02_model.ipynb": '{"nbformat": 4, "nbformat_minor": 5, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python", "version": "3.11.0"}}, "cells": [{"cell_type": "markdown", "metadata": {}, "source": ["# Model Training\\n"]}, {"cell_type": "code", "execution_count": null, "metadata": {}, "outputs": [], "source": ["from src.model import train, save_model\\nfrom src.features import encode_categoricals, scale_numerics\\nprint(\\"Ready to train model\\")\\n"]}]}',
        "data/raw/.gitkeep": "",
        "data/processed/.gitkeep": "",
        "models/.gitkeep": "",
        "reports/.gitkeep": "",
    }
    if "testing" in features:
        files["tests/__init__.py"] = ""
        files["tests/test_features.py"] = (
            'import pandas as pd\nimport pytest\nfrom src.features import encode_categoricals, scale_numerics\n\ndef test_encode_categoricals():\n    df = pd.DataFrame({"cat": ["a", "b", "a"]})\n    result = encode_categoricals(df, ["cat"])\n    assert result["cat"].dtype in [int, "int64", "int32"]\n\ndef test_scale_numerics():\n    df = pd.DataFrame({"num": [1.0, 2.0, 3.0]})\n    result = scale_numerics(df, ["num"])\n    assert abs(result["num"].mean()) < 1e-9\n'
        )
    return files


def _react_lib_template(name: str, features: List[str]) -> Dict[str, str]:
    """Reusable React component library scaffold with TypeScript and Storybook."""
    pkg = name.replace("-", "_").lower()
    files: Dict[str, str] = {
        "package.json": f'{{"name": "{name.lower()}", "version": "0.1.0", "description": "React component library generated by SYNAPSE AI", "main": "dist/index.js", "module": "dist/index.esm.js", "types": "dist/index.d.ts", "scripts": {{"build": "rollup -c", "dev": "rollup -c -w", "test": "jest --passWithNoTests", "storybook": "storybook dev -p 6006", "build-storybook": "storybook build"}}, "peerDependencies": {{"react": ">=18", "react-dom": ">=18"}}, "devDependencies": {{"react": "^18", "react-dom": "^18", "typescript": "^5", "@types/react": "^18", "@types/react-dom": "^18", "rollup": "^4", "@rollup/plugin-typescript": "^11", "rollup-plugin-dts": "^6", "jest": "^29", "@testing-library/react": "^15", "@testing-library/jest-dom": "^6", "@storybook/react": "^8", "@storybook/addon-essentials": "^8"}}}}',
        "tsconfig.json": '{"compilerOptions": {"target": "ES2017", "module": "ESNext", "lib": ["ES2017", "DOM"], "jsx": "react", "declaration": true, "declarationDir": "dist", "outDir": "dist", "moduleResolution": "node", "strict": true, "esModuleInterop": true, "skipLibCheck": true}, "include": ["src"], "exclude": ["node_modules", "dist"]}',
        "rollup.config.js": 'import typescript from "@rollup/plugin-typescript";\nimport dts from "rollup-plugin-dts";\nconst config = [\n  { input: "src/index.ts", output: [{ file: "dist/index.js", format: "cjs", sourcemap: true }, { file: "dist/index.esm.js", format: "esm", sourcemap: true }], plugins: [typescript()], external: ["react", "react-dom"] },\n  { input: "src/index.ts", output: [{ file: "dist/index.d.ts", format: "esm" }], plugins: [dts()] },\n];\nexport default config;\n',
        ".gitignore": "node_modules/\ndist/\n.storybook-out/\n",
        f"README.md": f'# {name}\n\nReact component library generated by SYNAPSE AI.\n\n## Quick Start\n\n```bash\nnpm install\nnpm run build\n```\n\n## Usage\n\n```tsx\nimport {{ Button }} from "{name.lower()}";\n\n<Button variant="primary" onClick={{() => console.log("clicked")}}>Click me</Button>\n```\n\n## Storybook\n\n```bash\nnpm run storybook\n```\n',
        "src/index.ts": "export { Button } from './components/Button';\nexport { Card } from './components/Card';\nexport { Badge } from './components/Badge';\n",
        "src/components/Button.tsx": 'import React from "react";\n\nexport interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {\n  variant?: "primary" | "secondary" | "ghost" | "destructive";\n  size?: "sm" | "md" | "lg";\n  children: React.ReactNode;\n}\n\nconst variantStyles: Record<string, string> = {\n  primary: "background:#4F46E5;color:#fff;",\n  secondary: "background:#06B6D4;color:#fff;",\n  ghost: "background:transparent;border:1px solid #4F46E5;color:#4F46E5;",\n  destructive: "background:#EF4444;color:#fff;",\n};\n\nconst sizeStyles: Record<string, string> = {\n  sm: "padding:4px 10px;font-size:12px;",\n  md: "padding:8px 16px;font-size:14px;",\n  lg: "padding:12px 24px;font-size:16px;",\n};\n\nexport const Button: React.FC<ButtonProps> = ({ variant = "primary", size = "md", children, style, ...props }) => (\n  <button style={{ ...(Object.fromEntries(variantStyles[variant].split(";").filter(Boolean).map(s => s.split(":") as [string,string]))), ...(Object.fromEntries(sizeStyles[size].split(";").filter(Boolean).map(s => s.split(":") as [string,string]))), borderRadius: 6, cursor: "pointer", border: "none", ...style }} {...props}>\n    {children}\n  </button>\n);\n',
        "src/components/Card.tsx": 'import React from "react";\n\nexport interface CardProps { children: React.ReactNode; className?: string; style?: React.CSSProperties; }\n\nexport const Card: React.FC<CardProps> = ({ children, style }) => (\n  <div style={{ background: "#fff", borderRadius: 8, boxShadow: "0 2px 8px rgba(0,0,0,0.08)", padding: 20, ...style }}>\n    {children}\n  </div>\n);\n',
        "src/components/Badge.tsx": 'import React from "react";\n\nexport interface BadgeProps { label: string; color?: string; bg?: string; }\n\nexport const Badge: React.FC<BadgeProps> = ({ label, color = "#4F46E5", bg = "#EEF2FF" }) => (\n  <span style={{ display: "inline-block", padding: "2px 10px", borderRadius: 12, fontSize: 12, fontWeight: 600, color, background: bg }}>{label}</span>\n);\n',
        "src/components/Button.stories.tsx": 'import type { Meta, StoryObj } from "@storybook/react";\nimport { Button } from "./Button";\nconst meta: Meta<typeof Button> = { title: "Components/Button", component: Button };\nexport default meta;\ntype Story = StoryObj<typeof Button>;\nexport const Primary: Story = { args: { children: "Button", variant: "primary" } };\nexport const Secondary: Story = { args: { children: "Button", variant: "secondary" } };\n',
        "src/components/Button.test.tsx": 'import React from "react";\nimport { render, screen, fireEvent } from "@testing-library/react";\nimport "@testing-library/jest-dom";\nimport { Button } from "./Button";\n\ndescribe("Button", () => {\n  it("renders children", () => {\n    render(<Button>Click me</Button>);\n    expect(screen.getByText("Click me")).toBeInTheDocument();\n  });\n  it("calls onClick", () => {\n    const fn = jest.fn();\n    render(<Button onClick={fn}>Go</Button>);\n    fireEvent.click(screen.getByText("Go"));\n    expect(fn).toHaveBeenCalledTimes(1);\n  });\n});\n',
    }
    return files


# ---------------------------------------------------------------------------
# Main create_project function
# ---------------------------------------------------------------------------

TEMPLATE_MAP = {
    "django": _django_template,
    "fastapi": _fastapi_template,
    "nextjs": _nextjs_template,
    "datascience": _datascience_template,
    "react_lib": _react_lib_template,
}


class CreateProjectInput(BaseModel):
    project_type: str = Field(
        ...,
        description=(
            "Type of project to generate. One of: "
            "'django' (Django REST API), "
            "'fastapi' (FastAPI microservice), "
            "'nextjs' (Next.js 14 app), "
            "'datascience' (Python data science project), "
            "'react_lib' (React component library)."
        ),
    )
    name: str = Field(
        ...,
        description=(
            "Project name used for directory names, package names, and README titles. "
            "Use kebab-case (e.g. 'my-api', 'data-explorer')."
        ),
    )
    features: List[str] = Field(
        default_factory=list,
        description=(
            "Optional list of feature flags. Common values: "
            "'auth' (add auth middleware/JWT setup), "
            "'testing' (add test files), "
            "'ci_cd' (add GitHub Actions CI workflow). "
            "Example: ['auth', 'testing', 'ci_cd']"
        ),
    )
    description: str = Field(
        default="",
        description=(
            "Optional free-text description of what the project should do. "
            "Included verbatim in the generated README.md under the 'About' section."
        ),
    )
    user_id: str = Field(
        default="anonymous", description="User ID for file storage path."
    )


def _create_project(
    project_type: str,
    name: str,
    features: Optional[List[str]] = None,
    description: str = "",
    user_id: str = "anonymous",
) -> str:
    """Generate a project scaffold and return it as a downloadable .zip file."""
    try:
        if features is None:
            features = []

        project_type = project_type.lower().strip()
        if project_type not in TEMPLATE_MAP:
            return (
                f"Unknown project_type '{project_type}'. "
                f"Valid types: {', '.join(VALID_PROJECT_TYPES)}"
            )

        # SEC-06: Validate and sanitise feature flags
        import re as _re

        allowed = _ALLOWED_FEATURES.get(project_type, frozenset())
        invalid = [f for f in features if f not in allowed]
        if invalid:
            return (
                f"Invalid feature(s) for '{project_type}': {invalid}. "
                f"Allowed: {sorted(allowed)}"
            )

        # Sanitise project name — must start with letter, alphanumeric/hyphens/underscores only
        name = name.strip() or "my-project"
        if not _re.match(r"^[a-zA-Z][a-zA-Z0-9_\-]{0,63}$", name):
            return (
                "Project name must start with a letter, contain only alphanumeric "
                "characters, hyphens or underscores, and be 1–64 characters long."
            )

        # Build the template file dict
        template_fn = TEMPLATE_MAP[project_type]
        files = template_fn(name, features)

        # Inject user description into README if provided
        if description and description.strip():
            readme_key = next(
                (k for k in files if k.lower().endswith("readme.md")), None
            )
            if readme_key:
                about_block = f"\n## About\n\n{description.strip()}\n"
                # Insert after the first heading line (# Project Name)
                lines = files[readme_key].splitlines(keepends=True)
                insert_at = 1  # default: right after title
                for i, line in enumerate(lines):
                    if line.startswith("## "):
                        insert_at = i  # insert before the first existing section
                        break
                lines.insert(insert_at, about_block)
                files[readme_key] = "".join(lines)

        # Pack into a zip archive
        safe_name = name.replace(" ", "_")[:50]
        zip_name = f"{safe_name}_{uuid.uuid4().hex[:8]}.zip"
        zip_path = _project_dir(user_id) / zip_name
        file_size = _pack_zip(files, zip_path)
        rel = _rel_path(zip_path)

        file_list = "\n".join(f"  {f}" for f in sorted(files.keys()))

        return (
            f"Project scaffold generated successfully.\n"
            f"Type: {project_type}\n"
            f"Name: {name}\n"
            f"Features: {', '.join(features) if features else 'none'}\n"
            f"Description: {description[:100] + '…' if len(description) > 100 else description or 'none'}\n"
            f"Files: {len(files)}\n"
            f"File: {rel}\n"
            f"Size: {file_size:,} bytes\n"
            f"Path: {str(zip_path)}\n"
            f"\nIncluded files:\n{file_list}"
        )

    except Exception as exc:
        logger.error("create_project failed: %s", exc)
        return f"Project generation failed: {exc}"


def make_create_project_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_create_project,
        name="create_project",
        description=(
            "Generate a complete project scaffold as a downloadable .zip file. "
            "Supports: 'django' (Django REST API with DRF + JWT), "
            "'fastapi' (FastAPI microservice with SQLAlchemy), "
            "'nextjs' (Next.js 14 app with TypeScript + Tailwind), "
            "'datascience' (Python project with Jupyter + pandas + sklearn), "
            "'react_lib' (React component library with Storybook). "
            "Optional features: 'auth', 'testing', 'ci_cd'. "
            "Returns the file path of the generated .zip archive."
        ),
        args_schema=CreateProjectInput,
        return_direct=False,
    )
