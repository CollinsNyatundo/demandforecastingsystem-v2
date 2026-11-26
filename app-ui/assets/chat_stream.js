window.UrbanFlow = window.UrbanFlow || {};

// Client-side session store memory & per-browser-tab session thread ID
window.UrbanFlow.chatHistory = [];
window.UrbanFlow.getThreadId = function () {
    const storageKey = "urbanflow-chat-thread-id";
    try {
        let tid = window.sessionStorage.getItem(storageKey);
        if (!tid) {
            tid = (window.crypto && typeof window.crypto.randomUUID === "function")
                ? `urbanflow-${window.crypto.randomUUID()}`
                : `urbanflow-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
            window.sessionStorage.setItem(storageKey, tid);
        }
        return tid;
    } catch (_e) {
        if (!window.UrbanFlow._fallbackThreadId) {
            window.UrbanFlow._fallbackThreadId = `urbanflow-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
        }
        return window.UrbanFlow._fallbackThreadId;
    }
};

window.UrbanFlow.streamChat = async function (message, initialHistory, pathname) {
    const chatContainer = document.getElementById("chat-messages");
    if (!chatContainer) return;

    if (window.UrbanFlow.chatHistory.length === 0 && initialHistory) {
        window.UrbanFlow.chatHistory = initialHistory;
    }

    // 1. Append User Bubble Visually
    const userRow = document.createElement("div");
    userRow.className = "chat-msg-row chat-msg-user";
    const userBubble = document.createElement("div");
    userBubble.className = "chat-bubble chat-bubble-user";
    userBubble.innerText = message;
    userRow.appendChild(userBubble);
    chatContainer.appendChild(userRow);

    // 2. Append AI Loading Bubble 
    const aiRow = document.createElement("div");
    aiRow.className = "chat-msg-row chat-msg-ai";
    const aiBubble = document.createElement("div");
    aiBubble.className = "chat-bubble chat-bubble-ai";
    aiBubble.innerHTML = `<i class="bi bi-robot me-2" style="color: #00e5ff; font-size: 0.85rem"></i><span class="small ai-stream-text"><span class="spinner-grow spinner-grow-sm text-info" role="status"></span></span>`;
    aiRow.appendChild(aiBubble);
    chatContainer.appendChild(aiRow);

    chatContainer.scrollTop = chatContainer.scrollHeight;
    const textTarget = aiBubble.querySelector(".ai-stream-text");

    // Push local user history
    window.UrbanFlow.chatHistory.push({ role: "user", content: message });

    try {
        // Construct the LangGraph V2 Streaming schema with per-session thread isolation
        const payload = {
            thread_id: window.UrbanFlow.getThreadId(),
            messages: window.UrbanFlow.chatHistory
        };

        const response = await fetch("/chat/stream", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            textTarget.innerText = "Error securely connecting to UrbanFlow orchestrator.";
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let finalReply = "";

        textTarget.innerText = ""; // Clear spinner once stream holds connection

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");

            // Re-assign the incomplete line back to buffer to parse on next chunk
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const dataStr = line.replace("data: ", "");
                    if (dataStr === "[DONE]") {
                        continue;
                    }

                    const eventObj = JSON.parse(dataStr);

                    // Route specifically for the model's message chunks over `astream_events` api
                    if (eventObj.event === "on_chat_model_stream") {
                        if (eventObj.data && eventObj.data.chunk && eventObj.data.chunk.content) {
                            // Extract AI tokens
                            const token = eventObj.data.chunk.content;
                            finalReply += token;

                            // Minimal markdown formatting for live stream
                            // Replace newlines with breaks
                            textTarget.innerHTML = finalReply.replace(/\n/g, "<br/>");
                            chatContainer.scrollTop = chatContainer.scrollHeight;
                        }
                    }
                }
            }
        }

        // Push local AI history
        window.UrbanFlow.chatHistory.push({ role: "assistant", content: finalReply });

    } catch (e) {
        console.error("Chat SSE Stream Execution Failed:", e);
        textTarget.innerText = "Fatal stream interruption.";
    }
};
