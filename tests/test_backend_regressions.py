import os
import sqlite3
import subprocess
import tempfile
import unittest
import gc
from pathlib import Path
from unittest.mock import Mock, patch

import app as app_module
import auth
import build_db
import embeddings as embeddings_module
import rag_engine
from auth import AuthManager
from database import Database


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"


class BackendRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_db_path = Path(self.temp_dir.name) / "ciqas-test.db"
        self.temp_db = Database(str(self.temp_db_path))
        self.client = app_module.app.test_client()

    def tearDown(self):
        self.client = None
        self.temp_db = None
        gc.collect()
        self.temp_dir.cleanup()

    def login_as_admin(self):
        with self.client.session_transaction() as session:
            session[AuthManager.SESSION_KEY] = {
                "user_id": "admin_001",
                "username": "202203010104",
                "role": "admin",
                "name": "系统管理员",
            }

    def test_non_stream_chat_returns_sources_instead_of_crashing(self):
        self.login_as_admin()
        qa_mock = Mock()
        qa_mock.get_answer.return_value = (
            "stub answer",
            [Mock(metadata={"source": "handbook.pdf"}, page_content="source excerpt")],
        )

        with patch.object(app_module, "db", self.temp_db), patch.object(
            auth, "db", self.temp_db
        ), patch.object(app_module, "qa_system", qa_mock):
            response = self.client.post(
                "/api/chat",
                json={"question": "test question", "stream": False},
            )
            conversation_id = response.get_json()["conversation_id"]
            detail_response = self.client.get(f"/api/conversations/{conversation_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["answer"], "stub answer")
        self.assertEqual(payload["sources"][0]["source"], "handbook.pdf")
        detail_payload = detail_response.get_json()
        self.assertEqual(detail_payload["messages"][1]["sources"][0]["source"], "handbook.pdf")

    def test_delete_conversation_cascades_messages(self):
        self.temp_db.create_user(
            user_id="student_test",
            username="student_test",
            password_hash="hash",
            salt="salt",
            role="student",
            name="Test User",
        )
        conversation_id = self.temp_db.create_conversation(user_id="student_test")
        self.temp_db.add_message(
            conversation_id,
            "user",
            "hello",
            user_id="student_test",
        )

        self.temp_db.delete_conversation(conversation_id, user_id="student_test")

        with sqlite3.connect(self.temp_db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            remaining = cursor.fetchone()[0]

        self.assertEqual(remaining, 0)

    def test_create_student_with_invalid_category_does_not_leave_partial_user(self):
        self.login_as_admin()

        with patch.object(app_module, "db", self.temp_db), patch.object(
            auth, "db", self.temp_db
        ):
            response = self.client.post(
                "/api/students",
                json={
                    "username": "20260001",
                    "name": "测试学生",
                    "password": "password",
                    "category_id": "cat_missing",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.temp_db.get_user_by_username("20260001"))

    def test_app_imports_even_when_embedding_config_is_missing(self):
        env = os.environ.copy()
        env["DEEPSEEK_API_KEY"] = ""
        env["SILICONFLOW_API_KEY"] = ""

        result = subprocess.run(
            [str(VENV_PYTHON), "-c", "import app; print('IMPORT_OK')"],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("IMPORT_OK", result.stdout)

    def test_default_admin_is_not_created_without_explicit_env_credentials(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "DEFAULT_ADMIN_USERNAME": "",
                "DEFAULT_ADMIN_PASSWORD": "",
                "DEFAULT_ADMIN_NAME": "",
            },
            clear=False,
        ):
            temp_db = Database(str(Path(temp_dir) / "no-default-admin.db"))
            admins = temp_db.list_users(role="admin")

        self.assertEqual(admins, [])

    def test_default_admin_can_be_bootstrapped_from_env(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "DEFAULT_ADMIN_USERNAME": "admin_bootstrap",
                "DEFAULT_ADMIN_PASSWORD": "bootstrap_secret",
                "DEFAULT_ADMIN_NAME": "Bootstrap Admin",
            },
            clear=False,
        ):
            temp_db = Database(str(Path(temp_dir) / "env-default-admin.db"))
            admins = temp_db.list_users(role="admin")

        self.assertEqual(len(admins), 1)
        self.assertEqual(admins[0]["username"], "admin_bootstrap")
        self.assertEqual(admins[0]["name"], "Bootstrap Admin")

    def test_api_login_required_returns_json_401(self):
        response = self.client.get("/api/conversations")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "未登录或会话已失效")

    def test_api_admin_required_returns_json_403(self):
        with self.client.session_transaction() as session:
            session[AuthManager.SESSION_KEY] = {
                "user_id": "student_001",
                "username": "student_001",
                "role": "student",
                "name": "普通学生",
            }

        response = self.client.get("/api/settings")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "您没有权限访问此功能")

    def test_student_category_description_is_persisted(self):
        self.login_as_admin()

        with patch.object(app_module, "db", self.temp_db), patch.object(
            auth, "db", self.temp_db
        ):
            create_response = self.client.post(
                "/api/student-categories",
                json={"name": "研究生", "description": "硕博学生"},
            )
            list_response = self.client.get("/api/student-categories")

        self.assertEqual(create_response.status_code, 200)
        categories = list_response.get_json()
        created = next(category for category in categories if category["name"] == "研究生")
        self.assertEqual(created["description"], "硕博学生")

    def test_embedding_batch_settings_are_initialized_and_validatable(self):
        self.assertEqual(self.temp_db.get_setting("embedding_batch_size", None), 20)
        self.assertEqual(self.temp_db.get_setting("embedding_max_workers", None), 4)
        self.assertEqual(app_module.Config.validate_setting("embedding_batch_size", 32), (True, None))
        self.assertEqual(app_module.Config.validate_setting("embedding_max_workers", 8), (True, None))

    def test_model_provider_settings_are_initialized_and_validatable(self):
        self.assertEqual(self.temp_db.get_setting("llm_provider", None), "deepseek")
        self.assertEqual(
            self.temp_db.get_setting("llm_base_url", None),
            app_module.Config.DEEPSEEK_API_BASE,
        )
        self.assertEqual(
            self.temp_db.get_setting("embedding_provider", None),
            "siliconflow",
        )
        self.assertEqual(
            self.temp_db.get_setting("embedding_base_url", None),
            app_module.Config.SILICONFLOW_BASE_URL,
        )
        self.assertEqual(
            app_module.Config.validate_setting("llm_provider", "openai_compatible"),
            (True, None),
        )
        self.assertEqual(
            app_module.Config.validate_setting("embedding_provider", "openai_compatible"),
            (True, None),
        )

        is_valid, error_message = app_module.Config.validate_setting("llm_provider", "unknown")
        self.assertFalse(is_valid)
        self.assertIn("必须是以下值之一", error_message)

    def test_settings_api_persists_model_provider_config_strings(self):
        self.login_as_admin()

        with patch.object(app_module, "db", self.temp_db), patch.object(
            auth, "db", self.temp_db
        ), patch.object(app_module, "get_qa_system", return_value=None), patch.object(
            app_module, "get_kb_builder", return_value=None
        ):
            response_1 = self.client.post(
                "/api/settings",
                json={"key": "llm_provider", "value": "openai_compatible"},
            )
            response_2 = self.client.post(
                "/api/settings",
                json={"key": "llm_base_url", "value": "http://localhost:1234/v1"},
            )
            response_3 = self.client.post(
                "/api/settings",
                json={"key": "embedding_model", "value": "text-embedding-local"},
            )
            settings_response = self.client.get("/api/settings")

        self.assertEqual(response_1.status_code, 200)
        self.assertEqual(response_2.status_code, 200)
        self.assertEqual(response_3.status_code, 200)

        payload = settings_response.get_json()
        settings_map = {
            item["setting_key"]: item["value"]
            for item in payload["settings"]
        }
        self.assertEqual(settings_map["llm_provider"], "openai_compatible")
        self.assertEqual(settings_map["llm_base_url"], "http://localhost:1234/v1")
        self.assertEqual(settings_map["embedding_model"], "text-embedding-local")


class RuntimeProviderConfigTests(unittest.TestCase):
    def test_qa_system_uses_openai_compatible_llm_provider(self):
        llm_provider_settings = {
            "provider": "openai_compatible",
            "base_url": "http://localhost:1234/v1",
            "api_key": "",
            "model": "qwen-local",
        }
        llm_sampling_settings = {
            "temperature": 0.3,
            "max_tokens": 2048,
            "top_p": 0.8,
            "frequency_penalty": 0.1,
            "presence_penalty": 0.2,
        }

        with patch.object(rag_engine, "create_embeddings_client", return_value=Mock()), patch.object(
            rag_engine, "ChatOpenAI"
        ) as chat_openai, patch.object(
            rag_engine, "ChatDeepSeek"
        ) as chat_deepseek, patch.object(
            rag_engine.Config, "get_llm_provider_settings", return_value=llm_provider_settings
        ), patch.object(
            rag_engine.Config, "get_llm_settings", return_value=llm_sampling_settings
        ), patch.object(
            rag_engine.QASystem, "_init_prompt"
        ), patch.object(
            rag_engine.QASystem, "_load_vector_store"
        ):
            rag_engine.QASystem(db_path="dummy-vector-db")

        chat_openai.assert_called_once()
        chat_deepseek.assert_not_called()
        kwargs = chat_openai.call_args.kwargs
        self.assertEqual(kwargs["model"], "qwen-local")
        self.assertEqual(kwargs["api_key"], "sk-local")
        self.assertEqual(kwargs["base_url"], "http://localhost:1234/v1")
        self.assertEqual(kwargs["temperature"], 0.3)

    def test_create_embeddings_client_uses_openai_compatible_provider(self):
        provider_settings = {
            "provider": "openai_compatible",
            "base_url": "http://localhost:1234/v1",
            "api_key": "",
            "model": "text-embedding-local",
        }

        with patch.object(
            embeddings_module.Config,
            "get_embedding_provider_settings",
            return_value=provider_settings,
        ), patch.object(
            embeddings_module.Config,
            "get_setting",
            side_effect=lambda key, default=None: {
                "embedding_batch_size": 32,
                "embedding_max_workers": 6,
            }.get(key, default),
        ), patch.object(
            embeddings_module, "OpenAIEmbeddings"
        ) as openai_embeddings:
            embeddings_module.create_embeddings_client()

        openai_embeddings.assert_called_once_with(
            model="text-embedding-local",
            api_key="sk-local",
            base_url="http://localhost:1234/v1",
            chunk_size=32,
            tiktoken_enabled=False,
        )


class FakeEmbeddings:
    pass


class FakeSplitter:
    def split_documents(self, docs):
        return docs


class FakeVectorStore:
    STORES = {}

    def __init__(self, db_path, docs):
        self.db_path = db_path
        self.docs = list(docs)
        self.docstore = type("DocStore", (), {"_dict": {str(i): doc for i, doc in enumerate(self.docs)}})()

    @classmethod
    def from_documents(cls, docs, embeddings):
        return cls(None, docs)

    @classmethod
    def load_local(cls, db_path, embeddings, allow_dangerous_deserialization=True):
        stored_docs = cls.STORES.get(str(db_path), [])
        return cls(str(db_path), stored_docs)

    def add_documents(self, docs):
        self.docs.extend(docs)
        self.docstore = type("DocStore", (), {"_dict": {str(i): doc for i, doc in enumerate(self.docs)}})()

    def save_local(self, db_path):
        path = Path(db_path)
        path.mkdir(parents=True, exist_ok=True)
        (path / "index.faiss").write_text("fake-index", encoding="utf-8")
        cls = type(self)
        cls.STORES[str(path)] = list(self.docs)
        self.db_path = str(path)


class KnowledgeBaseRegressionTests(unittest.TestCase):
    def test_process_documents_replaces_existing_document_with_same_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "vector-db"
            uploads_dir = Path(temp_dir) / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)
            file_path = uploads_dir / "policy.txt"
            file_path.write_text("v1", encoding="utf-8")

            FakeVectorStore.STORES.clear()

            with patch.object(build_db, "create_embeddings_client", return_value=FakeEmbeddings()), patch.object(
                build_db, "FAISS", FakeVectorStore
            ):
                builder = build_db.KnowledgeBaseBuilder(str(db_path))
                builder.text_splitter = FakeSplitter()

                first_doc = Mock(page_content="old content", metadata={"source": str(file_path)})
                second_doc = Mock(page_content="new content", metadata={"source": str(file_path)})

                with patch.object(builder, "load_document", side_effect=[[first_doc], [second_doc]]):
                    first_count = builder.process_documents([str(file_path)], category="other")
                    second_count = builder.process_documents([str(file_path)], category="other")

            self.assertEqual(first_count, 1)
            self.assertEqual(second_count, 1)
            stored_docs = FakeVectorStore.STORES[str(db_path)]
            self.assertEqual(len(stored_docs), 1)
            self.assertEqual(stored_docs[0].page_content, "new content")


if __name__ == "__main__":
    unittest.main()
