# Medi-Mind

A personal medical assistant application with a React frontend and FastAPI backend, designed to help users manage their medical details and health information. Supports multiple LLM providers (Groq, OpenAI, Gemini, and Ollama) and includes comprehensive health tracking, patient management, and intelligent medical assistance features.

## Project Goal

Medi-Mind aims to revolutionize personal healthcare management by providing an intelligent, AI-powered medical assistant that helps both patients and healthcare professionals. The project focuses on:

- **Personalized Health Management**: Enable users to track, monitor, and understand their health metrics in real-time through an intuitive interface
- **Intelligent Medical Assistance**: Provide context-aware medical guidance that interprets all queries through a health and wellness lens
- **Healthcare Professional Support**: Empower doctors and medical staff with advanced patient management tools and analytics
- **Seamless Integration**: Integrate multiple LLM providers and tools to create a comprehensive health ecosystem
- **Data-Driven Insights**: Transform raw health data into actionable insights through visualization and intelligent analysis

The platform bridges the gap between patients and healthcare providers by offering dual use cases: a personal medical assistant for patients and a professional assistant for healthcare providers, all powered by advanced AI and modern web technologies.

## Team Members

- **Shibin Thomas**
- **Manan Jignesh Shah**
- **Elison Jusufati**

## Features

- Multiple LLM provider support (Groq, OpenAI, Gemini, Ollama)
- Real-time health dashboard (steps, calories, heart rate, blood oxygen, water intake, mood, sleep, energy)
- Interactive health tracking and management
- Dual use cases: Medical Assistant for patients and Doctor Assistant for healthcare providers
- Email integration with Gmail
- Weather and date context integration
- Patient management and analytics (Doctor Assistant)
- Health metrics visualization with interactive charts

## Prerequisites

- **Python 3.13+** (for backend)
- **Node.js 18+** and **npm** (for frontend)
- **Git** (for cloning the repository)
- **API Keys** for at least one LLM provider:
  - Groq API key: [console.groq.com](https://console.groq.com/)
  - OpenAI API key: [platform.openai.com](https://platform.openai.com/)
  - Google Gemini API key: [makersuite.google.com](https://makersuite.google.com/)

## Environment Setup

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd nucleate-hack-medi-minds
```

### Step 2: Backend Setup

```bash
cd backend
```

**Install dependencies using uv (recommended):**

```bash
uv sync
```

**Or using pip:**

```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate   # On Windows
pip install -e .
```

**Configure environment variables:**

```bash
cp example.env .env
# Edit .env and add your API keys:
# OPENAI_API_KEY=sk-your-key-here
# GROQ_API_KEY=gsk_your-key-here
# GEMINI_API_KEY=your-key-here
```

**Gmail Integration (Optional):**

1. Place your Gmail OAuth credentials file (`client_secret*.json`) in the `backend` directory
2. The first time you use email features, you'll be prompted to authenticate via OAuth

### Step 3: Frontend Setup

```bash
cd ../react_frontend
npm install
```

## Instructions to Run the Code

### Step 1: Start the Backend Server

Open a terminal and navigate to the backend directory:

```bash
cd backend
```

**If using uv:**

```bash
uv run uvicorn main:app --reload --port 8000
```

**If using pip:**

```bash
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate   # On Windows
python -m uvicorn main:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`

### Step 2: Start the Frontend Development Server

Open a **new** terminal (keep the backend running) and navigate to the frontend directory:

```bash
cd react_frontend
npm run dev
```

The frontend will be available at `http://localhost:5173`

### Step 3: Access the Application

1. Open your web browser and navigate to `http://localhost:5173`
2. Select a use case (Medical Assistant or Doctor Assistant)
3. Choose an LLM provider and model
4. Start chatting!

### Troubleshooting

- **Port 8000 already in use**: Change the port: `--port 8001`
- **Module not found errors**: Ensure dependencies are installed with `uv sync` or `pip install -e .`
- **API key errors**: Verify your `.env` file contains valid API keys
- **Cannot connect to backend**: Verify backend is running on port 8000

### Stopping the Application

- Press `Ctrl+C` in both terminal windows to stop the backend and frontend servers
