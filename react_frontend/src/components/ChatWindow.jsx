import React, { useEffect, useRef } from "react";

export function ChatWindow({
  conversation,
  onSubmit,
  onClear,
  loading,
  resetting,
  error,
  useCaseLabel,
  useCase,
  sidebarOpen,
  onToggleSidebar,
  currentMood,
  userName,
  backendUrl,
}) {
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [conversation]);

  const handleSubmit = (event) => {
    event.preventDefault();
    const content = inputRef.current?.value ?? "";
    if (!content.trim() || loading || resetting) return;
    onSubmit(content.trim());
    inputRef.current.value = "";
    inputRef.current.focus();
  };

  const handleClear = () => {
    onClear();
    inputRef.current?.focus();
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${backendUrl || "http://localhost:8000"}/upload-file`, {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        console.log("File uploaded successfully:", result);
        // Optionally, you could add a message to the conversation or show a notification
        alert(`File "${result.filename}" uploaded successfully!`);
      } else {
        const error = await response.json();
        alert(`Upload failed: ${error.detail || "Unknown error"}`);
      }
    } catch (error) {
      console.error("Error uploading file:", error);
      alert("Error uploading file. Please try again.");
    } finally {
      // Reset the file input
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  // Get time-based medical greeting for patients
  const getMedicalGreeting = () => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) {
      return "Ready to start your healthy day?";
    } else if (hour >= 12 && hour < 17) {
      return "How's your wellness journey today?";
    } else if (hour >= 17 && hour < 21) {
      return "Time to check in on your health";
    } else {
      return "Rest well, your health matters";
    }
  };

  // Get time-based greeting for doctors
  const getDoctorGreeting = () => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) {
      return "Ready to manage your patients today?";
    } else if (hour >= 12 && hour < 17) {
      return "How can I assist with patient care?";
    } else if (hour >= 17 && hour < 21) {
      return "Time to review patient records";
    } else {
      return "Rest well, your patients are in good hands";
    }
  };

  // Get appropriate greeting based on use case
  const getGreeting = () => {
    if (useCase === "doctor_chatbot") {
      return getDoctorGreeting();
    }
    return getMedicalGreeting();
  };

  const showGreeting = conversation.length === 0 && userName;

  return (
    <section className="chat-pane">
      <div className="chat-box">
        <header className="chat-header">
          <div className="chat-header__left">
            <button
              type="button"
              className="chat-header__toggle"
              onClick={onToggleSidebar}
              aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
            >
              {sidebarOpen ? "◀" : "▶"}
            </button>
            <span className="chat-header__title">{useCaseLabel || "Conversation"}</span>
          </div>
          <button
            type="button"
            className="chat-header__clear"
            onClick={handleClear}
            disabled={loading || resetting}
          >
            {resetting ? "Clearing…" : "Clear"}
          </button>
        </header>

        <div className="chat-messages">
          {showGreeting && (
            <div className="chat-greeting">
              <div className="chat-greeting__line1">
                {useCase === "doctor_chatbot" ? "Hey Doc!!!" : `Hey ${userName}`}
              </div>
              <div className="chat-greeting__line2">{getGreeting()}</div>
            </div>
          )}

          {conversation.length === 0 && !showGreeting && (
            <div className="chat-empty">
              {useCase === "doctor_chatbot"
                ? "👋 Welcome to Doctor Assistant! How can I help you manage your patients today?"
                : "👋 Welcome to Medi-Mind! How can I help you with your health today?"}
            </div>
          )}

          {conversation.map((msg, index) => (
            <div
              key={`${index}-${msg.isUser ? "user" : "assistant"}`}
              className={`chat-message ${msg.isUser ? "chat-message--user" : "chat-message--assistant"} ${
                !msg.isUser && currentMood ? `chat-message--${currentMood}` : ""
              }`}
            >
              {msg.isUser ? (
                msg.text
              ) : (
                <span
                  dangerouslySetInnerHTML={{
                    __html: msg.rendered ?? "",
                  }}
                />
              )}
            </div>
          ))}

          {loading && <div className="chat-thinking">Thinking…</div>}
          <div ref={messagesEndRef} />
        </div>

        <form className="chat-form" onSubmit={handleSubmit}>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            className="chat-file-input"
            id="chat-file-upload"
            disabled={loading || resetting}
          />
          <label htmlFor="chat-file-upload" className="chat-file-button" title="Upload file">
            📎
          </label>
          <input
            className="chat-input"
            placeholder={
              useCase === "doctor_chatbot"
                ? "Search for patients, view records, or send emails…"
                : "Ask about your health, medications, symptoms, or medical records…"
            }
            disabled={resetting}
            ref={inputRef}
          />
          <button
            type="submit"
            className="chat-button"
            disabled={loading || resetting}
          >
            Send
          </button>
        </form>

        {error && <div className="chat-error">{error}</div>}
      </div>
    </section>
  );
}
