"""
Tests for KraberCode agent module.
"""

import pytest

from krabercode.agent.context import ContextManager
from krabercode.agent.executor import AgentExecutor
from krabercode.agent.history import HistoryManager
from krabercode.agent.planner import TaskPlanner
from krabercode.agent.system_prompt import get_default_system_prompt
from krabercode.cli.output import OutputManager
from krabercode.config.settings import Settings
from krabercode.config.storage import ConfigStorage
from krabercode.llm.base import LLMResponse, LLMStreamChunk
from krabercode.llm.messages import ToolCall
from krabercode.tools.base import ToolRegistry, ToolResult


class DummyToolRegistry(ToolRegistry):
    async def execute(self, name: str, **kwargs):
        return ToolResult(success=True, output=f"ran {name}")

    def get_all_definitions(self):
        return []


class DummyLLMClient:
    def __init__(self, response: LLMResponse):
        self._response = response

    async def complete(self, messages, tools=None, **kwargs):
        return self._response

    async def stream(self, messages, tools=None, **kwargs):
        if False:
            yield

    async def count_tokens(self, messages):
        return 0

    @property
    def model_name(self):
        return "dummy-model"

    @property
    def provider_name(self):
        return "dummy-provider"


class StreamLLMClient:
    def __init__(self, chunks: list[LLMStreamChunk]):
        self._chunks = chunks

    async def complete(self, messages, tools=None, **kwargs):
        return LLMResponse(content="", model="m", provider="p")

    async def stream(self, messages, tools=None, **kwargs):
        for chunk in self._chunks:
            yield chunk

    async def count_tokens(self, messages):
        return 0

    @property
    def model_name(self):
        return "stream-model"

    @property
    def provider_name(self):
        return "stream-provider"


class TestContextManager:
    """Test context manager."""

    def test_context_creation(self):
        """Test creating context manager."""
        context = ContextManager()
        assert context.max_tokens > 0

    def test_add_message(self):
        """Test adding messages."""
        context = ContextManager()
        context.add_message("user", "Hello")
        context.add_message("assistant", "Hi there")

        assert len(context.conversation_history) == 2

    def test_add_message_with_metadata(self):
        """Test adding message metadata."""
        context = ContextManager()
        context.add_message("tool", "done", tool_call_id="abc", name="read_file")

        assert context.conversation_history[0]["tool_call_id"] == "abc"
        assert context.conversation_history[0]["name"] == "read_file"

    def test_get_messages(self):
        """Test getting messages for LLM."""
        context = ContextManager()
        context.set_system_prompt("Test prompt")
        context.add_message("user", "Hello")

        messages = context.get_messages()
        assert len(messages) >= 2

    def test_token_estimation(self):
        """Test token estimation."""
        context = ContextManager()
        context.add_message("user", "This is a test message")

        tokens = context.estimate_tokens()
        assert tokens > 0

    def test_truncation(self):
        """Test history truncation."""
        context = ContextManager(max_tokens=100)

        # Add many messages
        for i in range(100):
            context.add_message("user", f"Message {i}" * 10)

        context.truncate_history()
        assert context.estimate_tokens() <= 100


class TestTaskPlanner:
    """Test task planner."""

    def test_planner_creation(self):
        """Test creating task planner."""
        planner = TaskPlanner()
        assert len(planner.tasks) == 0

    def test_create_plan(self):
        """Test creating a plan."""
        planner = TaskPlanner()
        tasks = planner.create_plan("1. Create file\n2. Edit file\n3. Run tests")

        assert len(tasks) >= 1

    def test_task_status(self):
        """Test task status management."""
        planner = TaskPlanner()
        planner.add_task("Test task")

        next_task = planner.get_next_task()
        assert next_task is not None
        assert next_task["status"] == "pending"

        planner.mark_in_progress(next_task["id"])
        task = planner.get_next_task()
        assert task["status"] == "in_progress"

    def test_status_summary(self):
        """Test status summary."""
        planner = TaskPlanner()
        planner.add_task("Task 1")
        planner.add_task("Task 2")
        planner.mark_completed("1")

        summary = planner.get_status_summary()
        assert "completed" in summary.lower()


class TestHistoryManager:
    """Test history manager."""

    def test_history_creation(self, temp_dir):
        """Test creating history manager."""
        history_file = temp_dir / "history.json"
        manager = HistoryManager(history_file)
        assert manager.history_file == history_file

    def test_add_entry(self, temp_dir):
        """Test adding history entry."""
        history_file = temp_dir / "history.json"
        manager = HistoryManager(history_file)

        manager.add_entry("user", "Test message")
        assert len(manager.entries) == 1

    def test_save_and_load(self, temp_dir):
        """Test saving and loading history."""
        history_file = temp_dir / "history.json"
        manager = HistoryManager(history_file)

        manager.add_entry("user", "Message 1")
        manager.add_entry("assistant", "Response 1")

        # Create new manager to load
        manager2 = HistoryManager(history_file)
        assert len(manager2.entries) == 2

    def test_search_history(self, temp_dir):
        """Test searching history."""
        history_file = temp_dir / "history.json"
        manager = HistoryManager(history_file)

        manager.add_entry("user", "Hello world")
        manager.add_entry("assistant", "Hi there")

        results = manager.search_history("hello")
        assert len(results) == 1


class TestSystemPrompt:
    """Test system prompt generation."""

    def test_default_prompt(self):
        """Test default prompt."""
        prompt = get_default_system_prompt()
        assert len(prompt) > 0
        assert "KraberCode" in prompt

    def test_prompt_contains_tools(self):
        """Test prompt mentions tools."""
        prompt = get_default_system_prompt()
        assert "read_file" in prompt
        assert "write_file" in prompt


class TestAgentExecutorProtocol:
    def _make_executor(self, temp_dir, llm_response: LLMResponse | None = None, llm_client=None):
        settings = Settings()
        settings.model.stream = False
        settings.output.show_tokens = False
        storage = ConfigStorage(config_dir=temp_dir)
        output = OutputManager(settings=settings.output)
        tool_registry = DummyToolRegistry()

        client = llm_client or DummyLLMClient(
            llm_response or LLMResponse(content="ok", model="m", provider="p")
        )

        return AgentExecutor(
            settings=settings,
            storage=storage,
            output=output,
            llm_client=client,
            tool_registry=tool_registry,
        )

    @pytest.mark.asyncio
    async def test_execute_does_not_duplicate_last_user_message(self, temp_dir):
        executor = self._make_executor(temp_dir)
        conversation = [{"role": "user", "content": "hello"}]

        await executor.execute("hello", conversation=conversation)

        user_messages = [
            m for m in executor.context.conversation_history if m.get("role") == "user"
        ]
        assert len(user_messages) == 1

    @pytest.mark.asyncio
    async def test_execute_tools_records_tool_message_with_call_id(self, temp_dir):
        executor = self._make_executor(temp_dir)
        tc = ToolCall(id="call_1", name="read_file", arguments={"path": "a"})

        await executor._execute_tools([tc])

        tool_messages = [
            m for m in executor.context.conversation_history if m.get("role") == "tool"
        ]
        assert len(tool_messages) == 1
        assert tool_messages[0]["tool_call_id"] == "call_1"
        assert tool_messages[0]["name"] == "read_file"

    @pytest.mark.asyncio
    async def test_agent_loop_stores_assistant_tool_calls(self, temp_dir):
        response = LLMResponse(
            content="",
            model="m",
            provider="p",
            tool_calls=[ToolCall(id="call_2", name="grep", arguments={"pattern": "x"})],
        )
        executor = self._make_executor(temp_dir, llm_response=response)

        async def no_op_execute_tools(tool_calls):
            return None

        executor._execute_tools = no_op_execute_tools  # type: ignore[method-assign]
        await executor.execute("run tool")

        assistant_msgs = [
            m
            for m in executor.context.conversation_history
            if m.get("role") == "assistant" and m.get("tool_calls")
        ]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0]["tool_calls"][0].id == "call_2"

    def test_build_messages_preserves_tool_role_and_id(self, temp_dir):
        executor = self._make_executor(temp_dir)
        executor.context.conversation_history = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_3",
                        "type": "function",
                        "function": {"name": "glob", "arguments": "{\"pattern\": \"*.py\"}"},
                    }
                ],
            },
            {
                "role": "tool",
                "content": "result",
                "tool_call_id": "call_3",
                "name": "glob",
            },
        ]

        messages = executor._build_messages()
        assert messages[0].role.value == "system"
        assert messages[1].role.value == "assistant"
        assert messages[1].tool_calls[0].id == "call_3"
        assert messages[1].tool_calls[0].arguments == {"pattern": "*.py"}
        assert messages[2].role.value == "tool"
        assert messages[2].tool_call_id == "call_3"

    @pytest.mark.asyncio
    async def test_stream_response_collects_tokens_and_tool_calls(self, temp_dir):
        chunks = [
            LLMStreamChunk(content="Hi", input_tokens=11, output_tokens=5),
            LLMStreamChunk(tool_call=ToolCall(id="call_4", name="read_file", arguments={}), finish_reason="tool_calls", input_tokens=11, output_tokens=7),
        ]
        settings = Settings()
        settings.model.stream = True
        settings.output.show_tokens = False
        storage = ConfigStorage(config_dir=temp_dir)
        output = OutputManager(settings=settings.output)

        executor = AgentExecutor(
            settings=settings,
            storage=storage,
            output=output,
            llm_client=StreamLLMClient(chunks),
            tool_registry=DummyToolRegistry(),
        )

        response = await executor._stream_response([], [])

        assert response is not None
        assert response.content == "Hi"
        assert response.input_tokens == 11
        assert response.output_tokens == 7
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].id == "call_4"
