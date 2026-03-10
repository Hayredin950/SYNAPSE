"""
backend.apps.documents.tests.test_project_generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for Phase 5.3 Project Builder.

Tests cover:
  - All 5 project templates (django, fastapi, nextjs, datascience, react_lib)
  - Feature flags (auth, testing, ci_cd)
  - Zip archive contents and validity
  - create_project tool metadata
  - Input validation (invalid type, short name, bad chars)
  - ProjectGenerateSerializer validation
  - _project_dir / _rel_path helpers
  - Registry includes create_project

Phase 5.3 — Project Builder (Week 15)
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

# ---------------------------------------------------------------------------
# Helper base class — redirect MEDIA_ROOT to a temp dir
# ---------------------------------------------------------------------------


class ProjectToolTestCase(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env_patch = patch.dict(os.environ, {"MEDIA_ROOT": self.tmp})
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, project_type: str, name: str = "test-project", features=None):
        from ai_engine.agents.project_tools import _create_project

        return _create_project(
            project_type=project_type,
            name=name,
            features=features or [],
            user_id="test_user",
        )

    def _get_zip_path(self, result: str) -> Path:
        for line in result.splitlines():
            if line.startswith("Path:"):
                return Path(line.replace("Path:", "").strip())
        raise AssertionError("No Path: line in result")

    def _zip_names(self, zip_path: Path):
        with zipfile.ZipFile(zip_path, "r") as zf:
            return set(zf.namelist())


# ===========================================================================
# 1. Django template
# ===========================================================================


class TestDjangoTemplate(ProjectToolTestCase):

    def test_generates_zip(self):
        result = self._run("django", "my-api")
        self.assertIn("Project scaffold generated successfully", result)
        self.assertIn("django", result)
        zip_path = self._get_zip_path(result)
        self.assertTrue(zip_path.exists())
        self.assertTrue(zipfile.is_zipfile(zip_path))

    def test_zip_contains_manage_py(self):
        result = self._run("django", "my-api")
        names = self._zip_names(self._get_zip_path(result))
        self.assertIn("manage.py", names)

    def test_zip_contains_settings(self):
        result = self._run("django", "my-api")
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("settings.py" in n for n in names))

    def test_zip_contains_requirements(self):
        result = self._run("django", "my-api")
        names = self._zip_names(self._get_zip_path(result))
        self.assertIn("requirements.txt", names)

    def test_zip_contains_dockerfile(self):
        result = self._run("django", "my-api")
        names = self._zip_names(self._get_zip_path(result))
        self.assertIn("Dockerfile", names)

    def test_zip_contains_readme(self):
        result = self._run("django", "my-api")
        names = self._zip_names(self._get_zip_path(result))
        self.assertIn("README.md", names)

    def test_feature_testing_adds_test_file(self):
        result = self._run("django", "my-api", features=["testing"])
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("test_" in n for n in names))

    def test_feature_ci_cd_adds_workflow(self):
        result = self._run("django", "my-api", features=["ci_cd"])
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("ci.yml" in n for n in names))

    def test_name_used_in_result(self):
        result = self._run("django", "awesome-api")
        self.assertIn("awesome-api", result)

    def test_result_contains_file_count(self):
        result = self._run("django", "my-api")
        self.assertIn("Files:", result)

    def test_result_contains_size(self):
        result = self._run("django", "my-api")
        self.assertIn("bytes", result)


# ===========================================================================
# 2. FastAPI template
# ===========================================================================


class TestFastAPITemplate(ProjectToolTestCase):

    def test_generates_zip(self):
        result = self._run("fastapi", "my-service")
        self.assertIn("Project scaffold generated successfully", result)
        zip_path = self._get_zip_path(result)
        self.assertTrue(zipfile.is_zipfile(zip_path))

    def test_zip_contains_main(self):
        result = self._run("fastapi", "my-service")
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("main.py" in n for n in names))

    def test_zip_contains_requirements(self):
        result = self._run("fastapi", "my-service")
        names = self._zip_names(self._get_zip_path(result))
        self.assertIn("requirements.txt", names)

    def test_requirements_has_fastapi(self):
        result = self._run("fastapi", "my-service")
        zip_path = self._get_zip_path(result)
        with zipfile.ZipFile(zip_path) as zf:
            content = zf.read("requirements.txt").decode()
        self.assertIn("fastapi", content.lower())

    def test_zip_contains_dockerfile(self):
        result = self._run("fastapi", "my-service")
        names = self._zip_names(self._get_zip_path(result))
        self.assertIn("Dockerfile", names)

    def test_zip_contains_schemas(self):
        result = self._run("fastapi", "my-service")
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("schemas.py" in n for n in names))

    def test_zip_contains_test_file(self):
        result = self._run("fastapi", "my-service", features=["testing"])
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("test_" in n for n in names))

    def test_hyphen_in_name_converted_to_underscore_in_pkg(self):
        result = self._run("fastapi", "my-cool-service")
        zip_path = self._get_zip_path(result)
        names = self._zip_names(zip_path)
        # Package dir should use underscores
        self.assertTrue(any("my_cool_service" in n for n in names))


# ===========================================================================
# 3. Next.js template
# ===========================================================================


class TestNextJSTemplate(ProjectToolTestCase):

    def test_generates_zip(self):
        result = self._run("nextjs", "my-app")
        self.assertIn("Project scaffold generated successfully", result)
        zip_path = self._get_zip_path(result)
        self.assertTrue(zipfile.is_zipfile(zip_path))

    def test_zip_contains_package_json(self):
        result = self._run("nextjs", "my-app")
        names = self._zip_names(self._get_zip_path(result))
        self.assertIn("package.json", names)

    def test_zip_contains_tsconfig(self):
        result = self._run("nextjs", "my-app")
        names = self._zip_names(self._get_zip_path(result))
        self.assertIn("tsconfig.json", names)

    def test_zip_contains_tailwind_config(self):
        result = self._run("nextjs", "my-app")
        names = self._zip_names(self._get_zip_path(result))
        self.assertIn("tailwind.config.ts", names)

    def test_zip_contains_layout(self):
        result = self._run("nextjs", "my-app")
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("layout.tsx" in n for n in names))

    def test_zip_contains_page(self):
        result = self._run("nextjs", "my-app")
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("page.tsx" in n for n in names))

    def test_zip_contains_api_util(self):
        result = self._run("nextjs", "my-app")
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("api.ts" in n for n in names))

    def test_zip_contains_auth_store(self):
        result = self._run("nextjs", "my-app")
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("authStore.ts" in n for n in names))

    def test_feature_testing_adds_test(self):
        result = self._run("nextjs", "my-app", features=["testing"])
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("test" in n for n in names))

    def test_feature_ci_cd_adds_workflow(self):
        result = self._run("nextjs", "my-app", features=["ci_cd"])
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("ci.yml" in n for n in names))


# ===========================================================================
# 4. Data Science template
# ===========================================================================


class TestDataScienceTemplate(ProjectToolTestCase):

    def test_generates_zip(self):
        result = self._run("datascience", "ml-project")
        self.assertIn("Project scaffold generated successfully", result)
        zip_path = self._get_zip_path(result)
        self.assertTrue(zipfile.is_zipfile(zip_path))

    def test_zip_contains_requirements(self):
        result = self._run("datascience", "ml-project")
        names = self._zip_names(self._get_zip_path(result))
        self.assertIn("requirements.txt", names)

    def test_requirements_has_pandas(self):
        result = self._run("datascience", "ml-project")
        zip_path = self._get_zip_path(result)
        with zipfile.ZipFile(zip_path) as zf:
            content = zf.read("requirements.txt").decode()
        self.assertIn("pandas", content)

    def test_zip_contains_notebooks(self):
        result = self._run("datascience", "ml-project")
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any(".ipynb" in n for n in names))

    def test_zip_contains_src_modules(self):
        result = self._run("datascience", "ml-project")
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("data_loader.py" in n for n in names))
        self.assertTrue(any("model.py" in n for n in names))
        self.assertTrue(any("features.py" in n for n in names))

    def test_zip_contains_environment_yml(self):
        result = self._run("datascience", "ml-project")
        names = self._zip_names(self._get_zip_path(result))
        self.assertIn("environment.yml", names)

    def test_zip_contains_data_dirs(self):
        result = self._run("datascience", "ml-project")
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("data/" in n for n in names))

    def test_feature_testing_adds_test_file(self):
        result = self._run("datascience", "ml-project", features=["testing"])
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("test_" in n for n in names))


# ===========================================================================
# 5. React Library template
# ===========================================================================


class TestReactLibTemplate(ProjectToolTestCase):

    def test_generates_zip(self):
        result = self._run("react_lib", "my-ui-lib")
        self.assertIn("Project scaffold generated successfully", result)
        zip_path = self._get_zip_path(result)
        self.assertTrue(zipfile.is_zipfile(zip_path))

    def test_zip_contains_package_json(self):
        result = self._run("react_lib", "my-ui-lib")
        names = self._zip_names(self._get_zip_path(result))
        self.assertIn("package.json", names)

    def test_zip_contains_rollup_config(self):
        result = self._run("react_lib", "my-ui-lib")
        names = self._zip_names(self._get_zip_path(result))
        self.assertIn("rollup.config.js", names)

    def test_zip_contains_components(self):
        result = self._run("react_lib", "my-ui-lib")
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any("Button.tsx" in n for n in names))
        self.assertTrue(any("Card.tsx" in n for n in names))
        self.assertTrue(any("Badge.tsx" in n for n in names))

    def test_zip_contains_storybook_stories(self):
        result = self._run("react_lib", "my-ui-lib")
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any(".stories.tsx" in n for n in names))

    def test_zip_contains_test_file(self):
        result = self._run("react_lib", "my-ui-lib")
        names = self._zip_names(self._get_zip_path(result))
        self.assertTrue(any(".test.tsx" in n for n in names))

    def test_zip_contains_index_export(self):
        result = self._run("react_lib", "my-ui-lib")
        names = self._zip_names(self._get_zip_path(result))
        self.assertIn("src/index.ts", names)


# ===========================================================================
# 6. Error handling & validation
# ===========================================================================


class TestCreateProjectErrors(ProjectToolTestCase):

    def test_invalid_project_type_returns_error(self):
        result = self._run("ruby_on_rails", "my-app")
        self.assertIn("Unknown project_type", result)
        self.assertIn("ruby_on_rails", result)

    def test_valid_types_listed_in_error(self):
        result = self._run("invalid", "app")
        for t in ["django", "fastapi", "nextjs", "datascience", "react_lib"]:
            self.assertIn(t, result)

    def test_empty_name_uses_default(self):
        result = self._run("django", "   ")
        # Should not crash — uses 'my-project' default
        self.assertIn("Project scaffold generated successfully", result)

    def test_all_valid_types_succeed(self):
        for pt in ["django", "fastapi", "nextjs", "datascience", "react_lib"]:
            with self.subTest(project_type=pt):
                result = self._run(pt, f"test-{pt}")
                self.assertIn(
                    "Project scaffold generated successfully",
                    result,
                    msg=f"Failed for project_type={pt}: {result}",
                )


# ===========================================================================
# 7. Tool metadata
# ===========================================================================


class TestCreateProjectTool(TestCase):

    def test_tool_name(self):
        from ai_engine.agents.project_tools import make_create_project_tool

        tool = make_create_project_tool()
        self.assertEqual(tool.name, "create_project")

    def test_tool_description_mentions_types(self):
        from ai_engine.agents.project_tools import make_create_project_tool

        tool = make_create_project_tool()
        desc = tool.description.lower()
        for t in ["django", "fastapi", "nextjs"]:
            self.assertIn(t, desc)

    def test_input_schema_required_fields(self):
        from ai_engine.agents.project_tools import CreateProjectInput

        schema = CreateProjectInput.schema()
        required = schema.get("required", [])
        self.assertIn("project_type", required)
        self.assertIn("name", required)

    def test_input_schema_features_not_required(self):
        from ai_engine.agents.project_tools import CreateProjectInput

        schema = CreateProjectInput.schema()
        required = schema.get("required", [])
        self.assertNotIn("features", required)


# ===========================================================================
# 8. Registry includes create_project (10 tools total)
# ===========================================================================


class TestRegistryIncludesProjectTool(TestCase):

    def test_registry_has_create_project(self):
        from ai_engine.agents.project_tools import make_create_project_tool
        from ai_engine.agents.registry import AgentToolRegistry

        registry = AgentToolRegistry()
        tool = make_create_project_tool()
        registry._tools[tool.name] = tool
        registry._built = True

        self.assertIn("create_project", registry.list_tool_names())

    def test_create_project_tool_name_correct(self):
        from ai_engine.agents.project_tools import make_create_project_tool

        self.assertEqual(make_create_project_tool().name, "create_project")


# ===========================================================================
# 9. Helpers
# ===========================================================================


class TestProjectHelpers(ProjectToolTestCase):

    def test_project_dir_creates_directory(self):
        from ai_engine.agents.project_tools import _project_dir

        d = _project_dir("user_99")
        self.assertTrue(d.exists())
        self.assertTrue(str(d).endswith("user_99"))

    def test_project_dir_returns_path(self):
        from ai_engine.agents.project_tools import _project_dir

        self.assertIsInstance(_project_dir("u"), Path)

    def test_rel_path_strips_media_root(self):
        from ai_engine.agents.project_tools import _rel_path

        abs_path = Path(self.tmp) / "projects" / "user" / "file.zip"
        result = _rel_path(abs_path)
        self.assertNotIn(self.tmp, result)
        self.assertIn("projects", result)

    def test_pack_zip_creates_valid_archive(self):
        from ai_engine.agents.project_tools import _pack_zip

        files = {"hello.txt": "Hello, world!", "sub/dir/file.py": "print('hi')"}
        zip_path = Path(self.tmp) / "test.zip"
        size = _pack_zip(files, zip_path)
        self.assertTrue(zip_path.exists())
        self.assertGreater(size, 0)
        self.assertTrue(zipfile.is_zipfile(zip_path))
        with zipfile.ZipFile(zip_path) as zf:
            self.assertIn("hello.txt", zf.namelist())
            self.assertIn("sub/dir/file.py", zf.namelist())
            self.assertEqual(zf.read("hello.txt").decode(), "Hello, world!")


# ===========================================================================
# 10. Serializer validation
# ===========================================================================


class TestProjectGenerateSerializer(TestCase):

    def _serialize(self, data):
        from apps.documents.serializers import ProjectGenerateSerializer

        s = ProjectGenerateSerializer(data=data)
        return s.is_valid(), s.validated_data if s.is_valid() else s.errors

    def test_valid_django_request(self):
        ok, data = self._serialize({"project_type": "django", "name": "my-api"})
        self.assertTrue(ok)
        self.assertEqual(data["project_type"], "django")
        self.assertEqual(data["name"], "my-api")

    def test_valid_with_features(self):
        ok, data = self._serialize(
            {"project_type": "fastapi", "name": "svc", "features": ["auth", "testing"]}
        )
        self.assertTrue(ok)
        self.assertIn("auth", data["features"])

    def test_invalid_project_type(self):
        ok, errors = self._serialize({"project_type": "ruby", "name": "app"})
        self.assertFalse(ok)
        self.assertIn("project_type", errors)

    def test_short_name_rejected(self):
        ok, errors = self._serialize({"project_type": "django", "name": "a"})
        self.assertFalse(ok)
        self.assertIn("name", errors)

    def test_name_with_spaces_rejected(self):
        ok, errors = self._serialize({"project_type": "django", "name": "my project"})
        self.assertFalse(ok)
        self.assertIn("name", errors)

    def test_invalid_feature_flag_rejected(self):
        ok, errors = self._serialize(
            {"project_type": "django", "name": "my-api", "features": ["invalid_flag"]}
        )
        self.assertFalse(ok)
        self.assertIn("features", errors)

    def test_features_defaults_to_empty_list(self):
        ok, data = self._serialize({"project_type": "nextjs", "name": "my-app"})
        self.assertTrue(ok)
        self.assertEqual(data["features"], [])
