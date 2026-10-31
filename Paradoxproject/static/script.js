/**
 * VERITAS AI — Research Mode Frontend Application
 * Team PARADOX Hackathon
 */

(function () {
    "use strict";

    // View management
    function showDashboard() {
        dashboardView.classList.add("active");
        chatView.classList.remove("active");
        navDashboard.classList.add("active");
        navResearch.classList.remove("active");
        navFactCheck.classList.remove("active");
        navHistory.classList.remove("active");
        loadDashboardData();
    }

    function showChat() {
        dashboardView.classList.remove("active");
        chatView.classList.add("active");
    }

    // Load dashboard data
    async function loadDashboardData() {
        try {
            const res = await fetch("/api/conversations");
            const data = await res.json();
            if (data.success && data.conversations) {
                const convs = data.conversations;
                const researchCount = convs.filter(c => c.mode === "research").length;
                const factCount = convs.filter(c => c.mode === "fact_check").length;
                if (metricResearch) metricResearch.textContent = researchCount;
                if (metricFactCheck) metricFactCheck.textContent = factCount;
                
                // Update recent activity
                if (recentActivity) {
                    recentActivity.innerHTML = "";
                    convs.slice(0, 4).forEach(conv => {
                        const item = document.createElement("div");
                        item.style.cssText = "padding: 8px 0; border-bottom: 1px solid var(--border-subtle); font-size: 13px;";
                        const modeLabel = conv.mode === "fact_check" ? "Fact Check" : "Research";
                        item.innerHTML = `<div style="color: var(--text-primary);">${conv.title}</div><div style="color: var(--text-muted); font-size: 11px;">${modeLabel} • ${formatTimeShort(conv.updated_at)}</div>`;
                        recentActivity.appendChild(item);
                    });
                    if (convs.length === 0) {
                        recentActivity.innerHTML = '<p class="panel-empty">No recent activity</p>';
                    }
                }
            }
        } catch (err) {
            // Silent fail, show defaults
        }
    }

    // DOM Elements
    const sidebar = document.getElementById("sidebar");
    const sidebarBackdrop = document.getElementById("sidebarBackdrop");
    const hamburgerBtn = document.getElementById("hamburgerBtn");
    const mobileCloseBtn = document.getElementById("mobileCloseBtn");
    const sidebarNewBtn = document.getElementById("sidebarNewBtn");
    const conversationList = document.getElementById("conversationList");

    // Navigation
    const navDashboard = document.getElementById("navDashboard");
    const navResearch = document.getElementById("navResearch");
    const navFactCheck = document.getElementById("navFactCheck");
    const navHistory = document.getElementById("navHistory");

    // Views
    const dashboardView = document.getElementById("dashboardView");
    const chatView = document.getElementById("chatView");

    // Dashboard elements
    const metricResearch = document.getElementById("metricResearch");
    const metricFactCheck = document.getElementById("metricFactCheck");
    const recentActivity = document.getElementById("recentActivity");
    const panelActions = document.querySelectorAll(".panel-action");
    const featureCards = document.querySelectorAll(".feature-card");

    // Chat elements
    const backToDashboard = document.getElementById("backToDashboard");
    const chatTitle = document.getElementById("chatTitle");
    const chatTimestamp = document.getElementById("chatTimestamp");
    const modeBadge = document.getElementById("modeBadge");
    const modeToggleBtn = document.getElementById("modeToggleBtn");
    const errorBanner = document.getElementById("errorBanner");
    const errorBannerText = document.getElementById("errorBannerText");
    const errorDismissBtn = document.getElementById("errorDismissBtn");

    const chatStream = document.getElementById("chatStream");
    const messagesContainer = document.getElementById("messagesContainer");
    const loadingBubble = document.getElementById("loadingBubble");

    const promptInput = document.getElementById("promptInput");
    const sendBtn = document.getElementById("sendBtn");

    // =====================================================================
    // Initialization
    // =====================================================================
    function init() {
        bindEvents();
        loadDashboardData();
        loadConversations();
        showDashboard();
    }

    // Navigation event listeners
    if (navDashboard) {
        navDashboard.addEventListener("click", () => {
            showDashboard();
            renderSidebarConversations();
        });
    }
    if (navResearch) {
        navResearch.addEventListener("click", () => {
            currentMode = "research";
            showChat();
            if (modeBadge) {
                const dot = modeBadge.querySelector(".mode-dot");
                const text = modeBadge.querySelector(".mode-text");
                if (dot) dot.className = "mode-dot";
                if (text) text.textContent = "Research Mode";
            }
            if (modeToggleBtn) {
                const iconSvg = modeToggleBtn.querySelector(".mode-toggle-icon-svg");
                const txt = modeToggleBtn.querySelector(".mode-toggle-text");
                if (iconSvg) iconSvg.innerHTML = '<circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="2"/><line x1="21" y1="21" x2="16.65" y2="16.65" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>';
                if (txt) txt.textContent = "Verify";
            }
            if (promptInput) promptInput.placeholder = "Enter your research query...";
            createNewChat();
        });
    }
    if (navFactCheck) {
        navFactCheck.addEventListener("click", () => {
            currentMode = "fact_check";
            showChat();
            if (modeBadge) {
                const dot = modeBadge.querySelector(".mode-dot");
                const text = modeBadge.querySelector(".mode-text");
                if (dot) dot.className = "mode-dot mode-dot-verify";
                if (text) text.textContent = "Fact Verification Mode";
            }
            if (modeToggleBtn) {
                const iconSvg = modeToggleBtn.querySelector(".mode-toggle-icon-svg");
                const txt = modeToggleBtn.querySelector(".mode-toggle-text");
                if (iconSvg) iconSvg.innerHTML = '<circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="2"/><path d="M21 21L16.65 16.65" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M11 8V14M8 11H14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>';
                if (txt) txt.textContent = "Research";
            }
            if (promptInput) promptInput.placeholder = "Enter article or text to verify...";
            createNewChat();
        });
    }
    if (navHistory) {
        navHistory.addEventListener("click", () => {
            showDashboard();
            navDashboard.classList.remove("active");
            navResearch.classList.remove("active");
            navFactCheck.classList.remove("active");
            navHistory.classList.add("active");
        });
    }

    if (sidebarNewBtn) {
        sidebarNewBtn.addEventListener("click", () => {
            createNewChat();
            showChat();
        });
    }

    if (backToDashboard) {
        backToDashboard.addEventListener("click", showDashboard);
    }

    panelActions.forEach(btn => {
        btn.addEventListener("click", () => {
            const action = btn.getAttribute("data-action");
            if (action === "research") {
                currentMode = "research";
                showChat();
                if (modeBadge) {
                    const dot = modeBadge.querySelector(".mode-dot");
                    const text = modeBadge.querySelector(".mode-text");
                    if (dot) dot.className = "mode-dot";
                    if (text) text.textContent = "Research Mode";
                }
                if (modeToggleBtn) {
                    const iconSvg = modeToggleBtn.querySelector(".mode-toggle-icon-svg");
                    const txt = modeToggleBtn.querySelector(".mode-toggle-text");
                    if (iconSvg) iconSvg.innerHTML = '<circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="2"/><line x1="21" y1="21" x2="16.65" y2="16.65" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>';
                    if (txt) txt.textContent = "Verify";
                }
                if (promptInput) promptInput.placeholder = "Enter your research query...";
                createNewChat();
            } else if (action === "factcheck") {
                currentMode = "fact_check";
                showChat();
                if (modeBadge) {
                    const dot = modeBadge.querySelector(".mode-dot");
                    const text = modeBadge.querySelector(".mode-text");
                    if (dot) dot.className = "mode-dot mode-dot-verify";
                    if (text) text.textContent = "Fact Verification Mode";
                }
                if (modeToggleBtn) {
                    const iconSvg = modeToggleBtn.querySelector(".mode-toggle-icon-svg");
                    const txt = modeToggleBtn.querySelector(".mode-toggle-text");
                    if (iconSvg) iconSvg.innerHTML = '<circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="2"/><path d="M21 21L16.65 16.65" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M11 8V14M8 11H14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>';
                    if (txt) txt.textContent = "Research";
                }
                if (promptInput) promptInput.placeholder = "Enter article or text to verify...";
                createNewChat();
            }
        });
    });

    featureCards.forEach(card => {
        card.addEventListener("click", () => {
            const feature = card.getAttribute("data-feature");
            if (feature === "research") {
                currentMode = "research";
                showChat();
                if (modeBadge) {
                    const dot = modeBadge.querySelector(".mode-dot");
                    const text = modeBadge.querySelector(".mode-text");
                    if (dot) dot.className = "mode-dot";
                    if (text) text.textContent = "Research Mode";
                }
                if (modeToggleBtn) {
                    const iconSvg = modeToggleBtn.querySelector(".mode-toggle-icon-svg");
                    const txt = modeToggleBtn.querySelector(".mode-toggle-text");
                    if (iconSvg) iconSvg.innerHTML = '<circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="2"/><line x1="21" y1="21" x2="16.65" y2="16.65" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>';
                    if (txt) txt.textContent = "Verify";
                }
                if (promptInput) promptInput.placeholder = "Enter your research query...";
                createNewChat();
            } else if (feature === "factcheck") {
                currentMode = "fact_check";
                showChat();
                if (modeBadge) {
                    const dot = modeBadge.querySelector(".mode-dot");
                    const text = modeBadge.querySelector(".mode-text");
                    if (dot) dot.className = "mode-dot mode-dot-verify";
                    if (text) text.textContent = "Fact Verification Mode";
                }
                if (modeToggleBtn) {
                    const iconSvg = modeToggleBtn.querySelector(".mode-toggle-icon-svg");
                    const txt = modeToggleBtn.querySelector(".mode-toggle-text");
                    if (iconSvg) iconSvg.innerHTML = '<circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="2"/><path d="M21 21L16.65 16.65" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M11 8V14M8 11H14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>';
                    if (txt) txt.textContent = "Research";
                }
                if (promptInput) promptInput.placeholder = "Enter article or text to verify...";
                createNewChat();
            } else if (feature === "history") {
                showDashboard();
                navDashboard.classList.remove("active");
                navResearch.classList.remove("active");
                navFactCheck.classList.remove("active");
                navHistory.classList.add("active");
            }
        });
    });

        // Mode Toggle: Research <-> Fact Verification
        if (modeToggleBtn) {
            modeToggleBtn.addEventListener("click", () => {
                closeMobileSidebar();
                toggleMode();
            });
        }

        // Search Input with Debounce
        if (searchInput) {
            searchInput.addEventListener("input", (e) => {
                const query = e.target.value.trim();
                clearSearchBtn.style.display = query ? "block" : "none";

                clearTimeout(searchDebounceTimeout);
                searchDebounceTimeout = setTimeout(() => {
                    loadConversations(query);
                }, 250);
            });
        }

        if (clearSearchBtn) {
            clearSearchBtn.addEventListener("click", () => {
                searchInput.value = "";
                clearSearchBtn.style.display = "none";
                loadConversations();
            });
        }

        // Error Banner Dismiss
        if (errorDismissBtn) {
            errorDismissBtn.addEventListener("click", hideError);
        }

        // Welcome input handlers
        if (promptInputWelcome) {
            promptInputWelcome.addEventListener("input", () => {
                promptInputWelcome.style.height = "auto";
                promptInputWelcome.style.height = Math.min(promptInputWelcome.scrollHeight, 200) + "px";
            });

            promptInputWelcome.addEventListener("keydown", (e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (promptInputWelcome.value.trim()) {
                        if (promptInput) {
                            promptInput.value = promptInputWelcome.value;
                            promptInput.style.height = "auto";
                            promptInput.style.height = Math.min(promptInput.scrollHeight, 180) + "px";
                        }
                        promptInputWelcome.value = "";
                        promptInputWelcome.style.height = "auto";
                        sendMessage();
                    }
                }
            });
        }

        if (welcomeSendBtn) {
            welcomeSendBtn.addEventListener("click", () => {
                if (promptInputWelcome && promptInputWelcome.value.trim()) {
                    if (promptInput) {
                        promptInput.value = promptInputWelcome.value;
                        promptInput.style.height = "auto";
                        promptInput.style.height = Math.min(promptInput.scrollHeight, 180) + "px";
                    }
                    const val = promptInputWelcome.value;
                    promptInputWelcome.value = "";
                    promptInputWelcome.style.height = "auto";
                    sendMessage();
                }
            });
        }

        // Send Button
        if (sendBtn) {
            sendBtn.addEventListener("click", () => {
                sendMessage();
            });
        }

        // Prompt Starters
        document.querySelectorAll(".starter-card").forEach((card) => {
            card.addEventListener("click", () => {
                const promptText = card.getAttribute("data-prompt");
                if (promptText && promptInput) {
                    promptInput.value = promptText;
                    promptInput.focus();
                    promptInput.style.height = "auto";
                    promptInput.style.height = Math.min(promptInput.scrollHeight, 180) + "px";
                    sendMessage();
                }
            });
        });
    }

    function closeMobileSidebar() {
        sidebar.classList.remove("open");
        sidebarBackdrop.classList.remove("active");
    }

    /**
     * Toggle between Research Mode and Fact Verification Mode.
     * Updates UI state and resets the canvas for the new mode.
     */
    function toggleMode() {
        currentMode = currentMode === "research" ? "fact_check" : "research";

        const isFactCheck = currentMode === "fact_check";

        // Update mode badge
        if (modeBadge) {
            const dot = modeBadge.querySelector(".mode-dot");
            const text = modeBadge.querySelector(".mode-text");
            if (dot) dot.className = `mode-dot ${isFactCheck ? "mode-dot-verify" : ""}`;
            if (text) text.textContent = isFactCheck ? "Fact Verification Mode" : "Research Mode";
        }

        // Update mode toggle button icon
        if (modeToggleBtn) {
            const iconSvg = modeToggleBtn.querySelector(".mode-toggle-icon-svg");
            const txt = modeToggleBtn.querySelector(".mode-toggle-text");
            if (iconSvg) {
                iconSvg.innerHTML = isFactCheck 
                    ? '<circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="2"/><path d="M21 21L16.65 16.65" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M11 8V14M8 11H14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'
                    : '<circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="2"/><line x1="21" y1="21" x2="16.65" y2="16.65" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>';
            }
            if (txt) txt.textContent = isFactCheck ? "Research" : "Verify";
            modeToggleBtn.title = isFactCheck
                ? "Switch to Research Mode"
                : "Switch to Fact Verification Mode";
        }

        // Update input placeholder
        if (promptInput) {
            promptInput.placeholder = isFactCheck
                ? "Enter article or text to verify..."
                : "Enter your research query... (e.g. 'Compare deep learning and reinforcement learning')";
        }

        // Update new chat button text
        if (newChatBtn) {
            const btnText = newChatBtn.querySelector("span:last-child");
            if (btnText) {
                btnText.textContent = isFactCheck ? "New Fact Check" : "New Research";
            }
        }

        // Reset canvas for the new mode
        activeConversationId = null;
        resetChatCanvas();
        hideError();

        // Create a new conversation in the selected mode
        createNewChat();
    }

    // =====================================================================
    // Conversations Management (API Integration)
    // =====================================================================

    /**
     * Load conversations list from GET /api/conversations?search=...
     */
    async function loadConversations(searchQuery = "") {
        try {
            const url = searchQuery
                ? `/api/conversations?search=${encodeURIComponent(searchQuery)}`
                : "/api/conversations";

            const res = await fetch(url);
            const data = await res.json();

            if (!res.ok || !data.success) {
                showError(data.error || "Failed to load conversation history.");
                return;
            }

            conversations = data.conversations || [];
            renderSidebarConversations();
        } catch (err) {
            showError("Network error while loading conversations. Please check your connection.");
        }
    }

    /**
     * Safely render conversation list into the sidebar using DOM manipulation
     */
    function renderSidebarConversations() {
        conversationList.replaceChildren();

        if (conversations.length === 0) {
            const emptyEl = document.createElement("div");
            emptyEl.className = "empty-history";
            emptyEl.textContent = searchInput && searchInput.value
                ? "No matching conversations found."
                : "No conversations yet. Start a new one!";
            conversationList.appendChild(emptyEl);
            return;
        }

        conversations.forEach((conv) => {
            const item = document.createElement("div");
            item.className = "conversation-item";
            if (conv.id === activeConversationId) {
                item.classList.add("active");
            }
            item.setAttribute("data-id", String(conv.id));

            // Info container
            const infoDiv = document.createElement("div");
            infoDiv.className = "conv-info";

            const titleSpan = document.createElement("span");
            titleSpan.className = "conv-title";
            titleSpan.textContent = conv.title || "Untitled Research";

            const metaSpan = document.createElement("span");
            metaSpan.className = "conv-meta";
            metaSpan.textContent = conv.updated_at ? formatTimeShort(conv.updated_at) : "";

            infoDiv.appendChild(titleSpan);
            infoDiv.appendChild(metaSpan);

            // Delete button
            const deleteBtn = document.createElement("button");
            deleteBtn.className = "conv-delete-btn";
            deleteBtn.title = "Delete conversation";
            deleteBtn.setAttribute("aria-label", "Delete conversation");
            deleteBtn.textContent = "🗑️";

            deleteBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                handleDeleteConversation(conv.id, conv.title);
            });

            item.appendChild(infoDiv);
            item.appendChild(deleteBtn);

            item.addEventListener("click", () => {
                closeMobileSidebar();
                if (conv.id !== activeConversationId) {
                    selectConversation(conv.id);
                }
            });

            conversationList.appendChild(item);
        });
    }

    /**
     * Create a new research session via POST /api/conversations
     */
    async function createNewChat() {
        if (isProcessing) return;

        const isFactCheck = currentMode === "fact_check";

        try {
            const res = await fetch("/api/conversations", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    title: isFactCheck ? "New Fact Check Session" : "New Research Session",
                    mode: isFactCheck ? "fact_check" : "research"
                })
            });

            const data = await res.json();
            if (!res.ok || !data.success) {
                showError(data.error || "Could not create a new conversation.");
                return;
            }

            const newConv = data.conversation;
            activeConversationId = newConv.id;
            conversations.unshift(newConv);

            renderSidebarConversations();
            updateChatHeader(newConv.title, newConv.updated_at);
            resetChatCanvas();
            hideError();
            showChat();

            if (promptInput) {
                promptInput.value = "";
                promptInput.focus();
            }
        } catch (err) {
            showError("Network error while creating new chat. Please try again.");
        }
    }

    /**
     * Select and load a conversation thread via GET /api/conversations/<id>
     */
    async function selectConversation(convId) {
        if (isProcessing) return;

        activeConversationId = convId;
        renderSidebarConversations();

        try {
            const res = await fetch(`/api/conversations/${convId}`);
            const data = await res.json();

            if (!res.ok || !data.success) {
                showError(data.error || "Failed to load conversation details.");
                return;
            }

            const conv = data.conversation;
            
            // Sync current mode with the loaded conversation
            if (conv.mode) {
                currentMode = conv.mode;
                const isFactCheck = currentMode === "fact_check";
                
                // Update mode badge
                if (modeBadge) {
                    const dot = modeBadge.querySelector(".mode-dot");
                    const text = modeBadge.querySelector(".mode-text");
                    if (dot) dot.className = `mode-dot ${isFactCheck ? "mode-dot-verify" : ""}`;
                    if (text) text.textContent = isFactCheck ? "Fact Verification Mode" : "Research Mode";
                }
                
                // Update toggle button
                if (modeToggleBtn) {
                    const iconSvg = modeToggleBtn.querySelector(".mode-toggle-icon-svg");
                    const txt = modeToggleBtn.querySelector(".mode-toggle-text");
                    if (iconSvg) {
                        iconSvg.innerHTML = isFactCheck 
                            ? '<circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="2"/><path d="M21 21L16.65 16.65" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M11 8V14M8 11H14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'
                            : '<circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="2"/><line x1="21" y1="21" x2="16.65" y2="16.65" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>';
                    }
                    if (txt) txt.textContent = isFactCheck ? "Research" : "Verify";
                    modeToggleBtn.title = isFactCheck
                        ? "Switch to Research Mode"
                        : "Switch to Fact Verification Mode";
                }
                
                // Update input placeholder
                if (promptInput) {
                    promptInput.placeholder = isFactCheck
                        ? "Enter article or text to verify..."
                        : "Enter your research query... (e.g. 'Compare deep learning and reinforcement learning')";
                }
                
                // Update new chat button text
                if (newChatBtn) {
                    const btnText = newChatBtn.querySelector("span:last-child");
                    if (btnText) {
                        btnText.textContent = isFactCheck ? "New Fact Check" : "New Research";
                    }
                }
            }
            
            updateChatHeader(conv.title, conv.updated_at);

            messagesContainer.replaceChildren();

            const messages = conv.messages || [];
            if (messages.length === 0) {
                resetChatCanvas();
            } else {
                messages.forEach((msg) => {
                    renderMessageBubble(msg.role, msg.content, msg.created_at, msg.claims || null);
                });
                scrollChatToBottom();
            }

            hideError();
            if (promptInput) promptInput.focus();
            showChat();
        } catch (err) {
            showError("Failed to fetch conversation history. Please refresh.");
        }
    }

    /**
     * Delete conversation via DELETE /api/conversations/<id> with confirmation
     */
    async function handleDeleteConversation(convId, title) {
        const confirmMsg = `Are you sure you want to delete "${title || 'this conversation'}"?\nThis action cannot be undone.`;
        if (!window.confirm(confirmMsg)) {
            return;
        }

        try {
            const res = await fetch(`/api/conversations/${convId}`, {
                method: "DELETE"
            });
            const data = await res.json();

            if (!res.ok || !data.success) {
                showError(data.error || "Failed to delete conversation.");
                return;
            }

            // Remove from local list
            conversations = conversations.filter((c) => c.id !== convId);

            if (convId === activeConversationId) {
                if (conversations.length > 0) {
                    await selectConversation(conversations[0].id);
                } else {
                    await createNewChat();
                }
            } else {
                renderSidebarConversations();
            }
        } catch (err) {
            showError("Network error while deleting conversation.");
        }
    }

    // =====================================================================
    // Chat & Messaging (POST /api/chat)
    // =====================================================================

    /**
     * Send user message to POST /api/chat and display Gemini response
     */
    async function sendMessage() {
        if (isProcessing) return;

        const text = promptInput ? promptInput.value.trim() : "";
        if (!text) return;

        // Ensure active conversation exists
        if (!activeConversationId) {
            await createNewChat();
        }

        // Hide welcome state
        hideError();

        // 1. Immediately append user bubble to UI
        const nowFormatted = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        renderMessageBubble("user", text, nowFormatted);
        scrollChatToBottom();

        // Reset and lock input
        promptInput.value = "";
        promptInput.style.height = "auto";
        setProcessing(true);

        // Show Gemini loading indicator
        loadingBubble.style.display = "flex";
        scrollChatToBottom();

        try {
            const isFactCheck = currentMode === "fact_check";
            let data;

            if (isFactCheck) {
                // Fact Verification Mode: POST /api/fact-check
                const res = await fetch("/api/fact-check", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        conversation_id: activeConversationId,
                        article_text: text
                    })
                });
                data = await res.json();
                loadingBubble.style.display = "none";

                if (!res.ok || !data.success) {
                    const errorMsg = data.error || "Failed to verify article.";
                    showError(errorMsg);
                    renderErrorBubble(errorMsg);
                    return;
                }

                // 2. Render assistant summary bubble
                const assistantMsgId = data.assistant_message_id;
                if (data.summary) {
                    renderMessageBubble("assistant", data.summary, new Date().toISOString(), assistantMsgId);
                }

                // 3. Render claim cards
                if (data.claims && data.claims.length > 0) {
                    renderClaimsSection(data.claims, data.stats);
                }

                // 4. Auto-title first fact-check conversation
                const currentConv = conversations.find((c) => c.id === activeConversationId);
                if (currentConv && currentConv.title === "New Fact Check Session") {
                    const autoTitle = text.length > 40 ? text.slice(0, 37) + "..." : text;
                    currentConv.title = autoTitle;
                    updateChatHeader(autoTitle);
                }

                // Refresh sidebar ordering
                await loadConversations();
            } else {
                // Research Mode: POST /api/chat
                const res = await fetch("/api/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        conversation_id: activeConversationId,
                        prompt: text
                    })
                });
                data = await res.json();
                loadingBubble.style.display = "none";

                if (!res.ok || !data.success) {
                    const errorMsg = data.error || "Failed to generate research response.";
                    showError(errorMsg);
                    renderErrorBubble(errorMsg);
                    return;
                }

                // 2. Render Assistant response
                const assistantMsg = data.assistant_message;
                if (assistantMsg && assistantMsg.content) {
                    renderMessageBubble("assistant", assistantMsg.content, assistantMsg.created_at);
                }

                // 3. Auto-title first research conversation
                const currentConv = conversations.find((c) => c.id === activeConversationId);
                if (currentConv && (currentConv.title === "New Research Session" || currentConv.title === "New Conversation")) {
                    const autoTitle = text.length > 40 ? text.slice(0, 37) + "..." : text;
                    currentConv.title = autoTitle;
                    updateChatHeader(autoTitle);
                }

                // Refresh sidebar ordering to reflect updated_at
                await loadConversations();
            }

        } catch (err) {
            loadingBubble.style.display = "none";
            const netError = "Network error: Unable to reach VERITAS AI server. Please verify your connection.";
            showError(netError);
            renderErrorBubble(netError);
        } finally {
            setProcessing(false);
            scrollChatToBottom();
            if (promptInput) promptInput.focus();
        }
    }

    // =====================================================================
    // Safe DOM Rendering Helpers (Zero raw innerHTML injection)
    // =====================================================================

    /**
     * Safely constructs and appends a message row to messagesContainer
     * @param {string} role - "user" or "assistant"
     * @param {string} content - message text
     * @param {string} timestamp - ISO timestamp
     * @param {Array} claims - optional array of claim objects for fact-check messages
     */
    function renderMessageBubble(role, content, timestamp, claims = null) {
        const row = document.createElement("div");
        row.className = `message-row ${role === "user" ? "user-row" : "assistant-row"}`;

        // Assistant avatar
        if (role === "assistant") {
            const avatar = document.createElement("div");
            avatar.className = "avatar ai-avatar";
            avatar.textContent = "V";
            row.appendChild(avatar);
        }

        const bubble = document.createElement("div");
        bubble.className = `message-bubble ${role === "user" ? "user-bubble" : "assistant-bubble"}`;

        if (role === "user") {
            // Safe plain text for user messages
            const userP = document.createElement("p");
            userP.textContent = content;
            bubble.appendChild(userP);
        } else {
            // Format assistant text safely (paragraphs and code blocks)
            renderAssistantContent(bubble, content);
        }

        // Timestamp
        if (timestamp) {
            const timeSpan = document.createElement("div");
            timeSpan.className = "message-time";
            timeSpan.textContent = formatTimeShort(timestamp);
            bubble.appendChild(timeSpan);
        }

        row.appendChild(bubble);

        // User avatar
        if (role === "user") {
            const avatar = document.createElement("div");
            avatar.className = "avatar user-avatar";
            avatar.textContent = "U";
            row.appendChild(avatar);
        }

        messagesContainer.appendChild(row);

        // Render claim cards below assistant message if provided
        if (role === "assistant" && claims && claims.length > 0) {
            renderClaimsSection(claims, null);
        }
    }

    // =====================================================================
    // Fact Verification: Claim Card Rendering
    // =====================================================================

    /**
     * Render a section of claim cards below an assistant message.
     * @param {Array} claims - Array of claim objects from /api/fact-check
     * @param {Object|null} stats - Optional stats object for summary badge
     */
    function renderClaimsSection(claims, stats = null) {
        if (!claims || claims.length === 0) return;

        const section = document.createElement("div");
        section.className = "claims-section";

        // Summary stats bar
        if (stats) {
            const statsBar = document.createElement("div");
            statsBar.className = "claims-stats-bar";
            statsBar.innerHTML = `
                <span class="stat-item"><span class="stat-label">Total</span> <span class="stat-value">${stats.total || 0}</span></span>
                <span class="stat-item stat-supported"><span class="stat-label">Supported</span> <span class="stat-value">${stats.supported || 0}</span></span>
                <span class="stat-item stat-contradicted"><span class="stat-label">Contradicted</span> <span class="stat-value">${stats.contradicted || 0}</span></span>
                <span class="stat-item stat-unverified"><span class="stat-label">Unverified</span> <span class="stat-value">${stats.unverified || 0}</span></span>
            `;
            section.appendChild(statsBar);
        }

        claims.forEach((claim) => {
            section.appendChild(renderClaimCard(claim));
        });

        messagesContainer.appendChild(section);
        scrollChatToBottom();
    }

    /**
     * Render a single claim card with verdict, confidence, explanation, and evidence.
     * @param {Object} claim - Claim object with claim_text, verdict, confidence, explanation, evidence
     */
    function renderClaimCard(claim) {
        const card = document.createElement("div");
        card.className = "claim-card";

        const verdictClass = `verdict-${claim.verdict || "unverified"}`;
        const confidencePct = Math.round((claim.confidence || 0) * 100);

        // Verdict badge
        const verdictBadge = document.createElement("span");
        verdictBadge.className = `verdict-badge ${verdictClass}`;
        verdictBadge.textContent = (claim.verdict || "unverified").charAt(0).toUpperCase() + (claim.verdict || "unverified").slice(1);

        // Confidence score
        const confidenceEl = document.createElement("span");
        confidenceEl.className = "confidence-score";
        confidenceEl.textContent = `Confidence: ${confidencePct}%`;

        // Claim text
        const claimText = document.createElement("div");
        claimText.className = "claim-text";
        claimText.textContent = claim.claim_text || "";

        // Explanation
        const explanation = document.createElement("div");
        explanation.className = "claim-explanation";
        explanation.textContent = claim.explanation || "";

        // Evidence list
        const evidenceList = document.createElement("div");
        evidenceList.className = "evidence-list";

        const evidenceHeader = document.createElement("div");
        evidenceHeader.className = "evidence-header";
        evidenceHeader.textContent = "Evidence Sources";
        evidenceList.appendChild(evidenceHeader);

        if (claim.evidence && claim.evidence.length > 0) {
            claim.evidence.forEach((ev) => {
                evidenceList.appendChild(renderEvidenceItem(ev));
            });
        } else {
            const noEvidence = document.createElement("div");
            noEvidence.className = "evidence-item no-evidence";
            noEvidence.textContent = "No external evidence retrieved for this claim.";
            evidenceList.appendChild(noEvidence);
        }

        // Assemble card
        const headerRow = document.createElement("div");
        headerRow.className = "claim-header";
        headerRow.appendChild(verdictBadge);
        headerRow.appendChild(confidenceEl);

        card.appendChild(headerRow);
        card.appendChild(claimText);
        card.appendChild(explanation);
        card.appendChild(evidenceList);

        return card;
    }

    /**
     * Render a single evidence source item with clickable URL.
     * @param {Object} ev - Evidence object with source_title, source_url, evidence_snippet, evidence_stance
     */
    function renderEvidenceItem(ev) {
        const item = document.createElement("div");
        item.className = "evidence-item";

        const stanceClass = `stance-${ev.evidence_stance || "context"}`;
        const stanceBadge = document.createElement("span");
        stanceBadge.className = `evidence-stance ${stanceClass}`;
        stanceBadge.textContent = (ev.evidence_stance || "context").charAt(0).toUpperCase() + (ev.evidence_stance || "context").slice(1);

        const sourceTitle = document.createElement("div");
        sourceTitle.className = "evidence-title";

        const sourceUrl = ev.source_url || "";
        if (sourceUrl) {
            const link = document.createElement("a");
            link.href = sourceUrl;
            link.textContent = ev.source_title || "Untitled Source";
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.className = "evidence-link";
            sourceTitle.appendChild(link);
        } else {
            sourceTitle.textContent = ev.source_title || "Untitled Source";
        }

        const snippet = document.createElement("div");
        snippet.className = "evidence-snippet";
        snippet.textContent = ev.evidence_snippet || "";

        item.appendChild(stanceBadge);
        item.appendChild(sourceTitle);
        item.appendChild(snippet);

        return item;
    }

    /**
     * Parses assistant Markdown text safely.
     * Uses marked + DOMPurify when available, with a resilient safe DOM fallback.
     */
    function renderAssistantContent(container, rawText) {
        if (!rawText) return;

        // 1. Primary: marked.js + DOMPurify sanitization
        if (typeof marked !== "undefined" && typeof DOMPurify !== "undefined") {
            try {
                marked.setOptions({
                    gfm: true,
                    breaks: true
                });
                const dirtyHtml = marked.parse(rawText);
                const cleanHtml = DOMPurify.sanitize(dirtyHtml, {
                    ALLOWED_TAGS: [
                        "h1", "h2", "h3", "h4", "h5", "h6", "p", "br", "hr",
                        "strong", "b", "em", "i", "code", "pre", "ul", "ol", "li",
                        "blockquote", "table", "thead", "tbody", "tr", "th", "td",
                        "a", "span"
                    ],
                    ALLOWED_ATTR: ["href", "target", "rel", "class"]
                });
                container.innerHTML = cleanHtml;
                return;
            } catch (err) {
                console.warn("marked/DOMPurify parsing failed, using safe fallback:", err);
            }
        }

        // 2. Safe Fallback: Built-in safe DOM parser (zero raw innerHTML injection)
        renderSafeMarkdownFallback(container, rawText);
    }

    /**
     * Fallback parser that creates DOM elements safely
     */
    function renderSafeMarkdownFallback(container, rawText) {
        const parts = rawText.split(/(```[\w-]*\n[\s\S]*?```)/g);

        parts.forEach((part) => {
            if (part.startsWith("```") && part.endsWith("```")) {
                const match = part.match(/^```([\w-]*)\n([\s\S]*?)```$/);
                const lang = match ? match[1] : "";
                const codeBody = match ? match[2] : part.slice(3, -3);

                const pre = document.createElement("pre");
                const code = document.createElement("code");
                if (lang) {
                    code.className = `language-${lang}`;
                }
                code.textContent = codeBody.replace(/\n$/, "");
                pre.appendChild(code);
                container.appendChild(pre);
            } else if (part.trim()) {
                parseMarkdownBlocks(container, part);
            }
        });
    }

    function parseMarkdownBlocks(container, text) {
        const lines = text.split("\n");
        let currentList = null;
        let currentListType = null;
        let currentParaLines = [];

        function flushPara() {
            if (currentParaLines.length > 0) {
                const p = document.createElement("p");
                renderInlineText(p, currentParaLines.join(" "));
                container.appendChild(p);
                currentParaLines = [];
            }
        }

        function flushList() {
            if (currentList) {
                container.appendChild(currentList);
                currentList = null;
                currentListType = null;
            }
        }

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const trimmed = line.trim();

            if (!trimmed) {
                flushPara();
                flushList();
                continue;
            }

            // Headings (#, ##, ###, ####)
            const headingMatch = trimmed.match(/^(#{1,4})\s+(.*)$/);
            if (headingMatch) {
                flushPara();
                flushList();
                const level = headingMatch[1].length;
                const h = document.createElement(`h${level}`);
                renderInlineText(h, headingMatch[2]);
                container.appendChild(h);
                continue;
            }

            // Blockquote (> text)
            if (trimmed.startsWith(">")) {
                flushPara();
                flushList();
                const bq = document.createElement("blockquote");
                renderInlineText(bq, trimmed.slice(1).trim());
                container.appendChild(bq);
                continue;
            }

            // Unordered list (- item or * item)
            const ulMatch = trimmed.match(/^[-*]\s+(.*)$/);
            if (ulMatch) {
                flushPara();
                if (currentListType !== "ul") {
                    flushList();
                    currentList = document.createElement("ul");
                    currentListType = "ul";
                }
                const li = document.createElement("li");
                renderInlineText(li, ulMatch[1]);
                currentList.appendChild(li);
                continue;
            }

            // Ordered list (1. item, 2. item)
            const olMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
            if (olMatch) {
                flushPara();
                if (currentListType !== "ol") {
                    flushList();
                    currentList = document.createElement("ol");
                    currentListType = "ol";
                }
                const li = document.createElement("li");
                renderInlineText(li, olMatch[2]);
                currentList.appendChild(li);
                continue;
            }

            // Regular paragraph line
            flushList();
            currentParaLines.push(trimmed);
        }

        flushPara();
        flushList();
    }

    function renderInlineText(container, text) {
        if (!text) return;

        // Matches **bold**, *italic*, `inline code`
        const tokenRegex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
        let lastIdx = 0;
        let match;

        while ((match = tokenRegex.exec(text)) !== null) {
            if (match.index > lastIdx) {
                container.appendChild(document.createTextNode(text.slice(lastIdx, match.index)));
            }

            const token = match[0];
            if (token.startsWith("**") && token.endsWith("**")) {
                const strong = document.createElement("strong");
                strong.textContent = token.slice(2, -2);
                container.appendChild(strong);
            } else if (token.startsWith("`") && token.endsWith("`")) {
                const code = document.createElement("code");
                code.textContent = token.slice(1, -1);
                container.appendChild(code);
            } else if (token.startsWith("*") && token.endsWith("*")) {
                const em = document.createElement("em");
                em.textContent = token.slice(1, -1);
                container.appendChild(em);
            }

            lastIdx = match.index + token.length;
        }

        if (lastIdx < text.length) {
            container.appendChild(document.createTextNode(text.slice(lastIdx)));
        }
    }

    /**
     * Displays an inline error message bubble in the chat stream
     */
    function renderErrorBubble(errMsg) {
        const row = document.createElement("div");
        row.className = "message-row assistant-row";

        const avatar = document.createElement("div");
        avatar.className = "avatar ai-avatar";
        avatar.style.background = "#EF4444";
        avatar.textContent = "!";
        row.appendChild(avatar);

        const bubble = document.createElement("div");
        bubble.className = "message-bubble assistant-bubble";
        bubble.style.borderColor = "rgba(239, 68, 68, 0.4)";
        bubble.style.backgroundColor = "rgba(239, 68, 68, 0.1)";

        const p = document.createElement("p");
        p.style.color = "#FCA5A5";
        p.textContent = `Error: ${errMsg}`;
        bubble.appendChild(p);

        row.appendChild(bubble);
        messagesContainer.appendChild(row);
    }

    // =====================================================================
    // UI Helpers & State Updates
    // =====================================================================

    function setProcessing(processing) {
        isProcessing = processing;
        if (sendBtn) sendBtn.disabled = processing;
        if (promptInput) promptInput.disabled = processing;
    }

    function resetChatCanvas() {
        messagesContainer.replaceChildren();
        loadingBubble.style.display = "none";
    }

    function updateChatHeader(title, timestamp) {
        if (chatTitle) {
            chatTitle.textContent = title || "New Research Session";
        }
        if (chatTimestamp) {
            chatTimestamp.textContent = timestamp ? `Active: ${formatTimeShort(timestamp)}` : "";
        }
    }

    function scrollChatToBottom() {
        chatStream.scrollTop = chatStream.scrollHeight;
    }

    function showError(msg) {
        if (errorBanner && errorBannerText) {
            errorBannerText.textContent = msg;
            errorBanner.style.display = "flex";
        }
    }

    function hideError() {
        if (errorBanner) {
            errorBanner.style.display = "none";
        }
    }

    function formatTimeShort(dateStr) {
        if (!dateStr) return "";
        try {
            const d = new Date(dateStr.replace(" ", "T"));
            if (isNaN(d.getTime())) return dateStr;
            return d.toLocaleDateString([], { month: "short", day: "numeric" }) +
                " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        } catch {
            return dateStr;
        }
    }

    // Launch application on DOM ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
