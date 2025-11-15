import React, { useEffect, useRef } from "react";

export function ChatWindow({
  conversation,
  onSubmit,
  onClear,
  loading,
  resetting,
  error,
  useCaseLabel,
  sidebarOpen,
  onToggleSidebar,
}) {
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

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
          {conversation.length === 0 && (
            <div className="chat-empty">Start the conversation below</div>
          )}

          {conversation.map((msg, index) => (
            <div
              key={`${index}-${msg.isUser ? "user" : "assistant"}`}
              className={`chat-message ${msg.isUser ? "chat-message--user" : "chat-message--assistant"}`}
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
            className="chat-input"
            placeholder="Type your message…"
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
