# KraberCode

A powerful CLI AI coding assistant with multi-model support and MCP integration.

## Features

- 🤖 **Multi-Model Support**: Compatible with OpenAI, Anthropic Claude, Google Gemini, Alibaba Qwen, and more
- 💬 **Intelligent Dialogue**: Multi-turn conversations with context management
- 🔧 **Code Operations**: Read, write, edit files; search code; execute commands
- 🔍 **Codebase Exploration**: Understand project structure, search patterns
- 🌐 **MCP Integration**: Extend capabilities through Model Context Protocol
- 🎨 **Rich CLI Experience**: Beautiful terminal output with syntax highlighting

## Installation

```bash
pip install krabercode
```

Or install from source:

```bash
git clone https://github.com/krabercode/krabercode
cd krabercode
pip install -e .
```

## Quick Start

```bash
# Initialize configuration (first time)
krabercode config --init

# Set your API key
krabercode config --set-key openai:sk-your-api-key

# Start interactive session
krabercode

# Or use the short alias
kc

# Ask a question
kc "How do I implement a binary search in Python?"
```

## Configuration

KraberCode uses configuration files located at `~/.krabercode/`:

| File | Purpose |
|------|---------|
| `config.yaml` | Model settings, output options, tool config |
| `secrets.yaml` | API keys for different providers |
| `mcp.yaml` | MCP server configurations |

### Initial Setup

```bash
# Create default configuration files
krabercode config --init

# View configuration paths
krabercode config --path

# Check API key status
krabercode config --keys
```

### Setting API Keys

**Method 1: Command Line**

```bash
# Set key for a provider
krabercode config --set-key openai:sk-xxxx
krabercode config --set-key anthropic:sk-ant-xxxx
krabercode config --set-key alibaba:sk-xxxx    # For Qwen models
krabercode config --set-key google:AIza-xxxx   # For Gemini

# Delete a key
krabercode config --delete-key openai
```

**Method 2: Edit Config File**

```bash
# Open secrets file in editor
krabercode config --edit
```

Or manually edit `~/.krabercode/secrets.yaml`:

```yaml
providers:
  openai:
    api_key: sk-your-openai-key
  anthropic:
    api_key: sk-ant-your-anthropic-key
  alibaba:
    api_key: your-dashscope-key      # For Qwen models
  google:
    api_key: your-google-api-key     # For Gemini
```

**Method 3: Environment Variables**

Environment variables take priority over config file:

```bash
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export DASHSCOPE_API_KEY="your-key"  # For Alibaba/Qwen
export GOOGLE_API_KEY="your-key"     # For Gemini
```

### Switching Models

```yaml
# In ~/.krabercode/config.yaml
model:
  provider: openai    # openai, anthropic, alibaba, google
  name: gpt-4o        # Model name
  temperature: 0.7    # 0.0 - 2.0
  max_tokens: 4096    # Response limit
  stream: true        # Enable streaming
```

Or via CLI:

```bash
krabercode --model gpt-4o --provider openai
```

## MCP Integration

KraberCode supports the Model Context Protocol (MCP) for extending tool capabilities.

Configure MCP servers in `~/.krabercode/mcp.yaml`:

```yaml
servers:
  filesystem:
    command: mcp-server-filesystem
    args: ["--path", "/path/to/project"]
  
  github:
    command: mcp-server-github
    env:
      GITHUB_TOKEN: your-token
```

## Commands

| Command | Description |
|---------|-------------|
| `kc` | Start interactive REPL |
| `kc "question"` | Ask a single question |
| `kc --model gpt-4` | Specify model |
| `kc config --init` | Initialize configuration |
| `kc config --keys` | Show API key status |
| `kc config --edit` | Edit secrets file |
| `kc tools -l` | List available tools |
| `kc --help` | Show help |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .

# Run type checker
mypy src/krabercode
```

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.