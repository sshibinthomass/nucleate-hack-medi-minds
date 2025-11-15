import React from "react";

export function Sidebar({
  provider,
  model,
  models,
  useCase,
  useCases,
  onProviderChange,
  onModelChange,
  onUseCaseChange,
  backendUrl,
  backendStatus,
  backendStatusMessage,
}) {
  const activeUseCaseLabel =
    useCases.find((option) => option.value === useCase)?.label || "Chat";

  const statusLabel = (() => {
    switch (backendStatus) {
      case "online":
        return "Backend Online";
      case "offline":
        return "Backend Offline";
      case "checking":
      default:
        return "Checking Backend";
    }
  })();

  return (
    <aside className="sidebar">
      <h1 className="sidebar__title">{activeUseCaseLabel}</h1>
      <div className="sidebar__form">
        <label className="sidebar__label">
          Use Case
          <select
            value={useCase}
            onChange={(event) => onUseCaseChange(event.target.value)}
            className="sidebar__select"
          >
            {useCases.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="sidebar__label">
          Provider
          <select
            value={provider}
            onChange={(event) => onProviderChange(event.target.value)}
            className="sidebar__select"
          >
            <option value="groq">Groq</option>
            <option value="openai">OpenAI</option>
            <option value="gemini">Gemini</option>
            <option value="ollama">Ollama</option>
          </select>
        </label>

        <label className="sidebar__label">
          Model
          <select
            value={model}
            onChange={(event) => onModelChange(event.target.value)}
            className="sidebar__select"
          >
            {models.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="sidebar__footer">
        <span className={`sidebar__status sidebar__status--${backendStatus}`}>
          <span className="sidebar__status-indicator" />
          {statusLabel}
        </span>
        <div className="sidebar__backend-url">
          <code>{backendUrl}</code>
        </div>
        {backendStatusMessage && (
          <div className="sidebar__footer-message">{backendStatusMessage}</div>
        )}
      </div>
    </aside>
  );
}
