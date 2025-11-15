# Medi-Mind

A personal medical assistant application with a React frontend and FastAPI backend, designed to help users manage their medical details and health information. Supports multiple LLM providers (Groq, OpenAI, Gemini, and Ollama).

## Features

- 🤖 Multiple LLM provider support (Groq, OpenAI, Gemini, Ollama)
- 💬 Interactive chat interface with markdown rendering
- 🎯 Medical assistant features for managing health information
- 🔄 Session-based conversation history management
- 📱 Responsive UI with collapsible sidebar
- 🎨 Modern, clean design

## Prerequisites

- **Python 3.13+** (for backend)
- **Node.js 18+** and **npm** (for frontend)
- **API Keys** for at least one LLM provider:
  - Groq API key
  - OpenAI API key
  - Google Gemini API key
  - (Optional) Ollama running locally

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd nucleate-hack-medi-minds
```

### 2. Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Install dependencies using `uv` (recommended) or `pip`:

**Using uv (recommended):**

```bash
uv sync
```

**Using pip:**

```bash
pip install -e .
```

Set up environment variables:

```bash
# Copy the example.env file
cp example.env .env

# Edit .env and add your API keys
# OPENAI_API_KEY=sk-your-key-here
# GROQ_API_KEY=gsk_your-key-here
# GEMINI_API_KEY=your-key-here
# OLLAMA_BASE_URL=http://localhost:11434 (optional)
```

### 3. Frontend Setup

Navigate to the frontend directory:

```bash
cd ../react_frontend
```

Install dependencies:

```bash
npm install
```

## Running the Application

### Start the Backend

From the `backend` directory:

```bash
# Using uv
uv run uvicorn main:app --reload --port 8000

# Or using python directly
python -m uvicorn main:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`

### Start the Frontend

From the `react_frontend` directory:

```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Project Structure

```
Medi-Mind/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── configurations.py       # Configuration settings
│   ├── example.env             # Environment variables template
│   ├── pyproject.toml          # Python dependencies
│   └── langgraph_agent/
│       ├── graphs/             # LangGraph graph definitions
│       ├── llms/               # LLM provider implementations
│       ├── nodes/              # Graph nodes
│       ├── states/             # State definitions
│       └── tools/              # Available tools
├── react_frontend/
│   ├── src/
│   │   ├── App.jsx             # Main React component
│   │   ├── App.css             # Styles
│   │   ├── components/         # React components
│   │   ├── constants.js        # Constants and configurations
│   │   └── utils/              # Utility functions
│   ├── package.json            # Node.js dependencies
│   └── vite.config.js          # Vite configuration
└── README.md                   # This file
```

## Usage

1. **Select a Use Case**: Choose from the dropdown (e.g., Medical Assistant, Health Tracker)
2. **Choose a Provider**: Select your preferred LLM provider (Groq, OpenAI, Gemini, or Ollama)
3. **Select a Model**: Pick a specific model from the selected provider
4. **Start Chatting**: Type your message and press Enter or click Send
5. **Clear Conversation**: Use the red "Clear" button to reset the conversation history

## API Endpoints

- `GET /health` - Health check endpoint
- `POST /chat` - Send a chat message
- `POST /chat/reset` - Reset conversation history

## Development

### Backend Development

The backend uses FastAPI with LangGraph for building stateful, multi-actor applications with LLMs.

### Frontend Development

The frontend is built with React and Vite for fast development and hot module replacement.

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]
