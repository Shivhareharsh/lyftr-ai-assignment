import { useState } from "react";
import "./App.css";

const API_URL =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000";

function App() {
  const [sessionId, setSessionId] = useState(
    () => `session-${Date.now()}`
  );

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const sendMessage = async () => {
    const text = input.trim();

    if (!text || loading) return;

    const userMessage = {
      role: "user",
      content: text,
    };

    setMessages((previous) => [
      ...previous,
      userMessage,
    ]);

    setInput("");
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            session_id: sessionId,
            message: text,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            `Request failed with status ${response.status}`
        );
      }

      const assistantMessage = {
        role: "assistant",
        content: data.reply,
        metadata: data.metadata,
      };

      setMessages((previous) => [
        ...previous,
        assistantMessage,
      ]);
    } catch (err) {
      const errorText =
        err instanceof Error
          ? err.message
          : "Something went wrong";

      setError(errorText);

      setMessages((previous) => [
        ...previous,
        {
          role: "error",
          content: errorText,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (event) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      sendMessage();
    }
  };

  const clearConversation = () => {
    setMessages([]);
    setInput("");
    setError("");

    setSessionId(
      `session-${Date.now()}`
    );
  };

  const latestAssistantMessage = [
    ...messages,
  ]
    .reverse()
    .find(
      (message) =>
        message.role === "assistant"
    );

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Lyftr AI Chatbot</h1>

          <p>
            Multi-turn AI chat with caching and
            automatic API key failover
          </p>
        </div>

        <div className="status">
          <span className="status-dot" />
          API Connected
        </div>
      </header>

      <main className="layout">
        <section className="chat-panel">
          <div className="chat-topbar">
            <div>
              <span className="label">
                Session
              </span>

              <span className="session-id">
                {sessionId}
              </span>
            </div>

            <button
              className="clear-button"
              onClick={clearConversation}
              type="button"
            >
              Clear conversation
            </button>
          </div>

          <div className="messages">
            {messages.length === 0 && (
              <div className="empty-state">
                <div className="bot-icon">
                  AI
                </div>

                <h2>
                  Start a conversation
                </h2>

                <p>
                  Ask anything. Your conversation
                  history is stored by the backend.
                </p>
              </div>
            )}

            {messages.map(
              (message, index) => {
                if (
                  message.role === "error"
                ) {
                  return (
                    <div
                      className="chat-error"
                      key={index}
                    >
                      <strong>
                        Request failed
                      </strong>

                      <span>
                        {message.content}
                      </span>
                    </div>
                  );
                }

                if (
                  message.role === "assistant"
                ) {
                  return (
                    <AssistantMessage
                      key={index}
                      message={message}
                    />
                  );
                }

                return (
                  <div
                    key={index}
                    className="message-row user"
                  >
                    <div className="message">
                      <div className="message-role">
                        You
                      </div>

                      <div className="message-content">
                        {message.content}
                      </div>
                    </div>
                  </div>
                );
              }
            )}

            {loading && (
              <div className="message-row assistant">
                <div className="message">
                  <div className="message-role">
                    Assistant
                  </div>

                  <div className="typing">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <div className="composer">
            <textarea
              data-testid="chat-input"
              value={input}
              onChange={(event) =>
                setInput(
                  event.target.value
                )
              }
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              rows={1}
            />

            <button
              data-testid="send-button"
              className="send-button"
              onClick={sendMessage}
              disabled={
                loading ||
                !input.trim()
              }
              type="button"
            >
              {loading
                ? "Sending..."
                : "Send"}
            </button>
          </div>
        </section>

        <aside className="metadata-panel">
          <h2>
            Latest Response
          </h2>

          {!latestAssistantMessage ? (
            <div className="metadata-empty">
              Send a message to see inference
              details.
            </div>
          ) : (
            <MetadataList
              metadata={
                latestAssistantMessage.metadata
              }
            />
          )}

          <div className="features">
            <h3>
              Backend features
            </h3>

            <div>
              ✓ Multi-turn SQLite history
            </div>

            <div>
              ✓ Response caching
            </div>

            <div>
              ✓ Automatic key failover
            </div>

            <div>
              ✓ Per-request token tracking
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}


function AssistantMessage({
  message,
}) {
  const metadata =
    message.metadata || {};

  return (
    <div
      className="message-row assistant"
      data-testid="assistant-message"
    >
      <div className="message assistant-card">
        <div className="message-role">
          Assistant
        </div>

        <div className="message-content">
          {message.content}
        </div>

        <div className="reply-metadata">
          <div className="reply-meta-item">
            <span>Source</span>

            <strong
              data-testid="meta-source"
            >
              {
                metadata.resolution_source
              }
            </strong>
          </div>

          <div className="reply-meta-item">
            <span>Model</span>

            <strong
              data-testid="meta-model"
            >
              {metadata.model}
            </strong>
          </div>

          <div className="reply-meta-item">
            <span>Latency</span>

            <strong
              data-testid="meta-latency"
            >
              {metadata.latency_ms} ms
            </strong>
          </div>

          <div className="reply-meta-item">
            <span>Input tokens</span>

            <strong
              data-testid="meta-input-tokens"
            >
              {metadata.input_tokens}
            </strong>
          </div>

          <div className="reply-meta-item">
            <span>Output tokens</span>

            <strong
              data-testid="meta-output-tokens"
            >
              {metadata.output_tokens}
            </strong>
          </div>

          <div className="reply-meta-item">
            <span>Key</span>

            <strong>
              {metadata.key_id ??
                "cache"}
            </strong>
          </div>

          <div className="reply-meta-item">
            <span>Fallbacks</span>

            <strong>
              {
                metadata.fallback_attempts
              }
            </strong>
          </div>
        </div>
      </div>
    </div>
  );
}


function MetadataList({
  metadata,
}) {
  if (!metadata) return null;

  return (
    <div className="metadata-list">
      <MetadataItem
        label="Resolution"
        value={
          metadata.resolution_source
        }
      />

      <MetadataItem
        label="Model"
        value={metadata.model}
      />

      <MetadataItem
        label="Latency"
        value={`${metadata.latency_ms} ms`}
      />

      <MetadataItem
        label="Input tokens"
        value={metadata.input_tokens}
      />

      <MetadataItem
        label="Output tokens"
        value={metadata.output_tokens}
      />

      <MetadataItem
        label="API key"
        value={
          metadata.key_id ??
          "Cache"
        }
      />

      <MetadataItem
        label="Fallback attempts"
        value={
          metadata.fallback_attempts
        }
      />
    </div>
  );
}


function MetadataItem({
  label,
  value,
}) {
  return (
    <div className="metadata-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}


export default App;