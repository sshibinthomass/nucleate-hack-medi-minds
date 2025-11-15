import React, { useEffect, useState } from "react";
import "./App.css";
import { MODEL_OPTIONS, USE_CASES } from "./constants";
import { Sidebar } from "./components/Sidebar";
import { ChatWindow } from "./components/ChatWindow";
import { Topbar } from "./components/Topbar";
import { WaterAnimation } from "./components/WaterAnimation";
import { MoodAnimation } from "./components/MoodAnimation";
import { escapeHtml, renderMarkdown } from "./utils/markdown";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export default function App() {
  const [conversation, setConversation] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [resetting, setResetting] = useState(false);
  const [sessionId, setSessionId] = useState("default");
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState(() => MODEL_OPTIONS.openai[0].value);
  const [useCase, setUseCase] = useState(() => USE_CASES[0]?.value ?? "mcp_chatbot");
  const [backendStatus, setBackendStatus] = useState("checking");
  const [backendStatusMessage, setBackendStatusMessage] = useState("Checking backend...");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [currentMood, setCurrentMood] = useState("");
  const [previousMood, setPreviousMood] = useState("");
  const [showWaterAnimation, setShowWaterAnimation] = useState(false);
  const [showMoodAnimation, setShowMoodAnimation] = useState(false);
  const [previousWaterIntake, setPreviousWaterIntake] = useState(0);
  const [userName, setUserName] = useState("");
  const [healthAlerts, setHealthAlerts] = useState([]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const existing = localStorage.getItem("chat_session_id");
    if (existing) {
      setSessionId(existing);
    } else {
      const id =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `session-${Date.now()}`;
      localStorage.setItem("chat_session_id", id);
      setSessionId(id);
    }
    
    // Set up global function for Sidebar to update health alerts
    window.setHealthAlerts = (alerts) => {
      setHealthAlerts(alerts);
    };
    
    return () => {
      delete window.setHealthAlerts;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    const checkBackend = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/health`, {
          method: "GET",
        });

        if (!response.ok) {
          throw new Error(`${response.status} ${response.statusText}`);
        }

        const data = await response.json().catch(() => ({}));

        if (!isMounted) return;
        setBackendStatus("online");
        setBackendStatusMessage(
          typeof data === "object" && data !== null
            ? data.status ?? "Online"
            : "Online"
        );
      } catch (err) {
        if (!isMounted) return;
        setBackendStatus("offline");
        setBackendStatusMessage(
          err instanceof Error ? err.message : "Unable to reach backend"
        );
      }
    };

    checkBackend();
    const interval = setInterval(checkBackend, 15000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Fetch current mood and water intake from backend and poll for updates
  useEffect(() => {
    const fetchPersonalData = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/personal-data`);
        if (response.ok) {
          const data = await response.json();
          const mood = data.mood || "";
          const validMoods = ["Happy", "Sad", "Surprised", "Angry"];
          const moodLower = validMoods.includes(mood)
            ? mood.toLowerCase()
            : "";
          
          // Set user name
          setUserName(data.user_name || "User");
          
          // Check if mood changed
          setPreviousMood((prev) => {
            if (prev && moodLower && prev !== moodLower) {
              setShowMoodAnimation(true);
            }
            return moodLower;
          });
          
          setCurrentMood(moodLower);
          
          // Check if water intake increased
          const currentWaterIntake = data.Water_Intake_cups || 0;
          setPreviousWaterIntake((prev) => {
            if (prev > 0 && currentWaterIntake > prev) {
              setShowWaterAnimation(true);
            }
            return currentWaterIntake;
          });
        }
      } catch (error) {
        console.error("Error fetching personal data:", error);
      }
    };

    // Initial fetch
    fetchPersonalData();

    // Poll for updates every 2 seconds to reflect changes from LLM
    const intervalId = setInterval(fetchPersonalData, 2000);

    // Cleanup interval on unmount
    return () => clearInterval(intervalId);
  }, [BACKEND_URL]);

  const handleProviderChange = (nextProvider) => {
    setProvider(nextProvider);
    const nextModel = MODEL_OPTIONS[nextProvider]?.[0]?.value ?? "";
    setModel(nextModel);
  };

  const handleModelChange = (nextModel) => {
    setModel(nextModel);
  };

  const resetConversation = async () => {
    setError("");
    setResetting(true);
    try {
      const res = await fetch(`${BACKEND_URL}/chat/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId || "default",
          use_case: useCase,
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || "Unable to clear conversation.");
      }
      setConversation([]);
    } catch (err) {
      setError(err.message || "Failed to clear conversation.");
    } finally {
      setResetting(false);
    }
  };

  const handleUseCaseChange = async (nextUseCase) => {
    if (nextUseCase === useCase) return;
    setUseCase(nextUseCase);
    await resetConversation();
  };

  async function handleSubmitMessage(content) {
    setError("");

    const trimmed = content.trim();
    if (!trimmed) return;

    const userMessage = {
      text: trimmed,
      rendered: escapeHtml(trimmed),
      isUser: true,
    };
    setConversation((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const response = await fetch(`${BACKEND_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          provider,
          selected_llm: model,
          use_case: useCase,
          session_id: sessionId || "default",
          health_alerts: healthAlerts.length > 0 ? healthAlerts : undefined,
        }),
      });

      const payload = await response
        .json()
        .catch(async () => ({ detail: await response.text() }));

      if (!response.ok) {
        const detail =
          typeof payload?.detail === "string"
            ? payload.detail
            : "Chatbot backend returned an error.";
        throw new Error(detail);
      }

      const botText = payload?.response ?? "No response";
      const rendered = renderMarkdown(botText);
      
      setConversation((prev) => [
        ...prev,
        { text: botText, rendered, isUser: false },
      ]);
    } catch (err) {
      let message = err.message || "Something went wrong";
      if (message.includes("Chatbot not initialized")) {
        message =
          "Chatbot service is not ready yet. Please ensure the backend is running with a valid GROQ_API_KEY.";
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  const availableModels = MODEL_OPTIONS[provider] ?? [];
  const activeUseCaseLabel =
    USE_CASES.find((option) => option.value === useCase)?.label || "Chat";

  return (
    <div className={`app ${sidebarOpen ? "app--sidebar-open" : "app--sidebar-closed"}`}>
      <Topbar backendUrl={BACKEND_URL} />
      
      <div className="app__main-content">
        {sidebarOpen && (
          <Sidebar
            provider={provider}
            model={model}
            models={availableModels}
            useCase={useCase}
            useCases={USE_CASES}
            onProviderChange={handleProviderChange}
            onModelChange={handleModelChange}
            onUseCaseChange={handleUseCaseChange}
            backendUrl={BACKEND_URL}
            backendStatus={backendStatus}
            backendStatusMessage={backendStatusMessage}
            onWaterIncrease={() => setShowWaterAnimation(true)}
          />
        )}

        <ChatWindow
          conversation={conversation}
          onSubmit={handleSubmitMessage}
          onClear={resetConversation}
          loading={loading}
          resetting={resetting}
          error={error}
          useCaseLabel={activeUseCaseLabel}
          useCase={useCase}
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          currentMood={currentMood}
          userName={userName}
          backendUrl={BACKEND_URL}
        />
      </div>

      <WaterAnimation
        show={showWaterAnimation}
        onComplete={() => setShowWaterAnimation(false)}
      />

      <MoodAnimation
        show={showMoodAnimation}
        mood={currentMood}
        onComplete={() => setShowMoodAnimation(false)}
      />
    </div>
  );
}


