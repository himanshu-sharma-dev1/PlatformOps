(function () {
    'use strict';
    /* global DOMPurify, marked, TextDecoder , requestAnimationFrame  */

    //  Configuration
    const API_ENDPOINT = '/yantraAgent/api/query/';
    const FOLLOW_UP_ENDPOINT = '/yantraAgent/api/follow-up/';
    const HISTORY_ENDPOINT = '/yantraAgent/api/history/';
    const SIDEBAR_HISTORY_ENDPOINT = '/yantraAgent/api/sidebar-history/';

    //  State
    let activeQuestionId = null;
    let isProcessing = false;
    let analysisMode = false;
    let currentStepsContainer = null;

    //  DOM References
    const $ = function (sel) {
        return document.querySelector(sel);
    };

    const dom = {
        sidebar: $('#agent-sidebar'),
        sidebarOverlay: $('#sidebar-overlay'),
        sidebarToggle: $('#sidebar-toggle'),
        convList: $('#conv-list'),
        convSearch: $('#conv-search'),
        newChatSidebar: $('#new-chat-sidebar-btn'),
        newChatHeader: $('#new-chat-header-btn'),
        chat: $('#agent-chat'),
        welcome: $('#agent-welcome'),
        messages: $('#agent-messages'),
        input: $('#chat-input'),
        sendBtn: $('#send-btn'),
        analysisBtn: $('#analysis-btn'),
        statusDot: $('#status-dot'),
        agentStatus: $('#agent-status'),
    };

    //  Utilities
    function escapeHtml (text) {
        const el = document.createElement('div');
        el.textContent = text;
        return el.innerHTML;
    }

    //  Sidebar Module
    function toggleSidebar () {
        const isOpen = dom.sidebar.classList.toggle('open');
        dom.sidebarOverlay.classList.toggle('active', isOpen);
    }

    function closeSidebar () {
        dom.sidebar.classList.remove('open');
        dom.sidebarOverlay.classList.remove('active');
    }

    function loadConversation (questionId) {
        // Clear current messages
        dom.messages.innerHTML = '';
        dom.welcome.style.display = 'none';
        dom.messages.style.display = 'flex';

        // Show loading indicator
        setAgentThinking(true);
        activeQuestionId = questionId;

        fetch(HISTORY_ENDPOINT + encodeURIComponent(questionId) + '/')
            .then(function (res) {
                if (!res.ok) throw new Error('Failed to load conversation');
                return res.json();
            })
            .then(function (data) {
                setAgentThinking(false);
                dom.messages.innerHTML = '';
                if (!data.question && !data.response) {
                    appendMessageDOM(
                        'No conversation history found.',
                        false,
                        false,
                    );
                    return;
                }
                if (data.question) {
                    appendMessageDOM(data.question, true, false);
                }
                if (data.response) {
                    appendMessageDOM(
                        data.response,
                        false,
                        false,
                        '',
                        data.sql_query || '',
                    );
                }
                scrollToBottom();
            })
            .catch(function (err) {
                setAgentThinking(false);
                appendMessageDOM(
                    'Failed to load conversation: ' + err.message,
                    false,
                );
            });
    }
    window.handleHistoryClick = function (event) {
        const anchor = event.target.closest('a');
        if (!anchor) return;
        event.preventDefault();
        if (isProcessing) return;
        const convItem = anchor.closest('.conv-item');
        if (!convItem) return;
        const queryIdEl = convItem.querySelector('.queryId');
        if (!queryIdEl) return;

        const questionId = queryIdEl.textContent.trim();
        if (!questionId) return;
        // Mark as active
        dom.convList.querySelectorAll('.conv-item').forEach(function (el) {
            el.classList.remove('active');
        });
        convItem.classList.add('active');

        loadConversation(questionId);
        closeSidebar();
    };

    //  Sidebar search filter
    function filterSidebar (query) {
        const items = dom.convList.querySelectorAll('.conv-item');
        const search = (query || '').toLowerCase();
        items.forEach(function (item) {
            const title = item.querySelector('.conv-item-title');
            const text = title ? title.textContent.toLowerCase() : '';
            item.style.display =
                !search || text.indexOf(search) !== -1 ? '' : 'none';
        });
    }

    //  Conversation Module
    function startNewChat () {
        if (isProcessing) return; // Block new chat while processing
        activeQuestionId = null;
        currentStepsContainer = null;
        dom.messages.innerHTML = '';
        dom.messages.style.display = 'none';
        dom.welcome.style.display = '';
        dom.convList.querySelectorAll('.conv-item').forEach(function (el) {
            el.classList.remove('active');
        });
        closeSidebar();
        dom.input.focus();
    }

    //  Message Rendering
    const botAvatarSvg =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
        '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>' +
        '<line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/>' +
        '<line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/>' +
        '<line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/>' +
        '<line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>' +
        '</svg>';

    const sqlIconSvg =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
        '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>' +
        '</svg>';

    const copySvg =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
        '<rect x="9" y="9" width="13" height="13" rx="2"/>' +
        '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>' +
        '</svg>';

    const checkSvg =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
        '<polyline points="20 6 9 17 4 12"/>' +
        '</svg>';

    const thumbsUpSvg =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
        '<path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/>' +
        '<path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>' +
        '</svg>';

    const thumbsDownSvg =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
        '<path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/>' +
        '<path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>' +
        '</svg>';

    //  SQL popup card
    function showSqlPopup (sqlText) {
        // Remove existing popup if any
        const existing = document.getElementById('sql-popup-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = 'sql-popup-overlay';
        overlay.className = 'sql-popup-overlay';
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) overlay.remove();
        });

        const card = document.createElement('div');
        card.className = 'sql-popup-card';
        card.innerHTML =
            '<div class="sql-popup-header">' +
            '<span class="sql-popup-title">' +
            sqlIconSvg +
            ' SQL Query</span>' +
            '<button class="sql-popup-close" title="Close">' +
            '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>' +
            '</button>' +
            '</div>' +
            '<pre class="sql-popup-code"><code>' +
            escapeHtml(sqlText) +
            '</code></pre>';

        card.querySelector('.sql-popup-close').addEventListener(
            'click',
            function () {
                overlay.remove();
            },
        );

        overlay.appendChild(card);
        document.body.appendChild(overlay);
    }

    function appendMessageDOM (text, isUser, animate, followUpText, sqlQuery) {
        if (animate === undefined) animate = true;
        if (!sqlQuery) sqlQuery = '';

        if (dom.welcome.style.display !== 'none') {
            dom.welcome.style.display = 'none';
            dom.messages.style.display = 'flex';
        }

        const msg = document.createElement('div');
        msg.className = 'message message-' + (isUser ? 'user' : 'bot');
        if (!animate) msg.style.animation = 'none';

        const formattedText = isUser
            ? escapeHtml(text)
            : DOMPurify.sanitize(marked.parse(text));

        let toolbar = '';
        if (!isUser) {
            toolbar =
                '<div class="message-toolbar message-toolbar-visible">' +
                '<button class="toolbar-btn copy-btn" title="Copy">' +
                copySvg +
                '</button>' +
                '<button class="toolbar-btn thumbs-up-btn" title="Good response">' +
                thumbsUpSvg +
                '</button>' +
                '<button class="toolbar-btn thumbs-down-btn" title="Bad response">' +
                thumbsDownSvg +
                '</button>' +
                (sqlQuery
                    ? '<button class="toolbar-btn show-sql-btn" title="View SQL Query">' +
                      sqlIconSvg +
                      '</button>'
                    : '') +
                '</div>';
        }

        msg.innerHTML =
            '<div class="message-avatar">' +
            botAvatarSvg +
            '</div>' +
            '<div class="message-content">' +
            '<div class="message-bubble">' +
            formattedText +
            '</div>' +
            toolbar +
            '</div>';

        msg.querySelectorAll('.message-bubble table').forEach(function (table) {
            const wrapper = document.createElement('div');
            wrapper.className = 'table-scroll-wrapper';
            table.parentNode.insertBefore(wrapper, table);
            wrapper.appendChild(table);
        });

        // Inject follow-up chips inside the bubble
        if (!isUser && followUpText) {
            const parsed = parseFollowUp(followUpText);
            if (parsed) {
                const bubble = msg.querySelector('.message-bubble');
                const followUpDiv = document.createElement('div');
                followUpDiv.className = 'follow-up-section';

                const heading = document.createElement('p');
                heading.className = 'follow-up-heading';
                heading.textContent = 'Follow up Questions:';
                followUpDiv.appendChild(heading);

                const chipWrap = document.createElement('div');
                chipWrap.className = 'follow-up-chips';

                parsed.questions.forEach(function (q) {
                    const chip = document.createElement('button');
                    chip.className = 'follow-up-chip';
                    chip.textContent = q;
                    chip.addEventListener('click', function () {
                        sendMessage(q);
                    });
                    chipWrap.appendChild(chip);
                });

                followUpDiv.appendChild(chipWrap);
                bubble.appendChild(followUpDiv);
            }
        }

        if (!isUser) {
            bindToolbarEvents(msg, sqlQuery);
        }

        dom.messages.appendChild(msg);
        if (!isUser) {
            scrollToMessage(msg);
        } else {
            scrollToBottom();
        }
    }

    function bindToolbarEvents (msgEl, sqlQuery) {
        const copyBtn = msgEl.querySelector('.copy-btn');
        const thumbsUp = msgEl.querySelector('.thumbs-up-btn');
        const thumbsDown = msgEl.querySelector('.thumbs-down-btn');
        const sqlBtn = msgEl.querySelector('.show-sql-btn');

        if (copyBtn) {
            const rawText = msgEl.querySelector('.message-bubble').textContent;
            copyBtn.addEventListener('click', function () {
                navigator.clipboard.writeText(rawText).then(function () {
                    copyBtn.innerHTML = checkSvg;
                    setTimeout(function () {
                        copyBtn.innerHTML = copySvg;
                    }, 2000);
                });
            });
        }

        if (thumbsUp) {
            thumbsUp.addEventListener('click', function () {
                thumbsUp.classList.toggle('active');
                thumbsDown.classList.remove('active');
            });
        }

        if (thumbsDown) {
            thumbsDown.addEventListener('click', function () {
                thumbsDown.classList.toggle('active');
                thumbsUp.classList.remove('active');
            });
        }

        if (sqlBtn && sqlQuery) {
            sqlBtn.addEventListener('click', function () {
                showSqlPopup(sqlQuery);
            });
        }
    }

    //  Async follow-up fetcher
    function fetchFollowUp (userQuery, responseText) {
        fetch(FOLLOW_UP_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_query: userQuery,
                response_text: responseText,
            }),
        })
            .then(function (res) {
                return res.json();
            })
            .then(function (data) {
                if (data.follow_up) {
                    // Append follow-up chips to the last bot message
                    const allMessages =
                        dom.messages.querySelectorAll('.message-bot');
                    const lastBotMsg = allMessages[allMessages.length - 1];
                    if (lastBotMsg) {
                        const parsed = parseFollowUp(data.follow_up);
                        if (parsed) {
                            const bubble =
                                lastBotMsg.querySelector('.message-bubble');
                            const followUpDiv = document.createElement('div');
                            followUpDiv.className = 'follow-up-section';

                            const heading = document.createElement('p');
                            heading.className = 'follow-up-heading';
                            heading.textContent = 'Follow up Questions:';
                            followUpDiv.appendChild(heading);

                            const chipWrap = document.createElement('div');
                            chipWrap.className = 'follow-up-chips';

                            parsed.questions.forEach(function (q) {
                                const chip = document.createElement('button');
                                chip.className = 'follow-up-chip';
                                chip.textContent = q;
                                chip.addEventListener('click', function () {
                                    sendMessage(q);
                                });
                                chipWrap.appendChild(chip);
                            });

                            followUpDiv.appendChild(chipWrap);
                            bubble.appendChild(followUpDiv);
                            scrollToBottom();
                        }
                    }
                }
            })
            .catch(function (err) {
                console.error('[fetchFollowUp] Error:', err);
            });
    }

    //  Follow-up Questions
    function parseFollowUp (text) {
        if (!text || typeof text !== 'string') return null;
        const lines = text.split('\n').filter(function (l) {
            return l.trim();
        });
        if (lines.length < 2) return null;
        const heading = lines[0].trim();
        const questions = [];
        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].replace(/^-\s*/, '').trim();
            if (line) questions.push(line);
        }
        return questions.length
            ? { heading: heading, questions: questions }
            : null;
    }

    //  Append new sidebar item after a message is sent
    function addSidebarItem (query, questionId) {
        // Remove "No conversations" empty state if present
        const emptyEl = dom.convList.querySelector('.conv-empty');
        if (emptyEl) emptyEl.remove();

        const item = document.createElement('div');
        item.className = 'conv-item active';
        item.innerHTML =
            '<a href="#" class="conv-item-link">' +
            '<div class="conv-item-icon">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>' +
            '</div>' +
            '<div class="conv-item-text">' +
            '<span class="conv-item-title">' +
            escapeHtml(query.slice(0, 60)) +
            '</span>' +
            '<span class="conv-item-time">Just now</span>' +
            '</div>' +
            '</a>' +
            '<p class="d-none queryId">' +
            escapeHtml(questionId) +
            '</p>';

        // Deactivate others, prepend new item
        dom.convList.querySelectorAll('.conv-item').forEach(function (el) {
            el.classList.remove('active');
        });
        dom.convList.prepend(item);
    }

    //  Disable/enable sidebar during processing
    function setSidebarDisabled (disabled) {
        dom.convList.classList.toggle('conv-list-disabled', disabled);
    }

    //  Agent Status & Thinking Indicator
    function setAgentThinking (thinking) {
        if (thinking) {
            dom.statusDot.classList.add('thinking');
            dom.agentStatus.classList.add('thinking');
            dom.agentStatus.textContent = 'Analyzing...';
            showThinkingIndicator();
        } else {
            dom.statusDot.classList.remove('thinking');
            dom.agentStatus.classList.remove('thinking');
            dom.agentStatus.textContent = 'Online';
            removeThinkingIndicator();
        }
    }

    function showThinkingIndicator () {
        const el = document.createElement('div');
        el.className = 'thinking-indicator';
        el.id = 'thinking-indicator';
        el.innerHTML =
            '<div class="message-avatar">' +
            botAvatarSvg +
            '</div>' +
            '<div class="thinking-bubble">' +
            '<div class="thinking-dots"><span></span><span></span><span></span></div>' +
            '<span class="thinking-text">Querying ClickHouse...</span>' +
            '</div>';
        dom.messages.appendChild(el);
        scrollToBottom();
    }

    function removeThinkingIndicator () {
        const el = document.getElementById('thinking-indicator');
        if (el) el.remove();
    }

    //  Step Timeline (vertical analysis steps)
    function createStepsMessage () {
        if (dom.welcome.style.display !== 'none') {
            dom.welcome.style.display = 'none';
            dom.messages.style.display = 'flex';
        }

        const msg = document.createElement('div');
        msg.className = 'message message--bot steps-message';
        msg.id = 'active-steps-message';
        msg.innerHTML =
            '<div class="message-avatar">' +
            botAvatarSvg +
            '</div>' +
            '<div class="message-content">' +
            '<div class="steps-container">' +
            '<div class="steps-header">' +
            '<div class="steps-header-icon">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>' +
            '</div>' +
            '<span class="steps-header-text">Deep Analysis</span>' +
            '</div>' +
            '<div class="steps-timeline"></div>' +
            '<div class="steps-loading">' +
            '<div class="thinking-dots"><span></span><span></span><span></span></div>' +
            '</div>' +
            '</div>' +
            '</div>';

        dom.messages.appendChild(msg);
        currentStepsContainer = msg;
        scrollToBottom();
    }

    function appendStepToTimeline (stepNum, text) {
        if (!currentStepsContainer) {
            removeThinkingIndicator();
            createStepsMessage();
        }

        const timeline = currentStepsContainer.querySelector('.steps-timeline');
        if (!timeline) return;

        const step = document.createElement('div');
        step.className = 'step-item';
        step.innerHTML =
            '<div class="step-number">' +
            stepNum +
            '</div>' +
            '<div class="step-content">' +
            escapeHtml(text) +
            '</div>';

        timeline.appendChild(step);
        scrollToBottom();
    }

    function finalizeSteps () {
        if (!currentStepsContainer) return;

        const loading = currentStepsContainer.querySelector('.steps-loading');
        if (loading) loading.remove();

        const headerText =
            currentStepsContainer.querySelector('.steps-header-text');
        if (headerText) headerText.textContent = 'Analysis Complete';

        const headerIcon =
            currentStepsContainer.querySelector('.steps-header-icon');
        if (headerIcon) {
            headerIcon.classList.add('steps-header-icon-done');
            headerIcon.innerHTML =
                '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
                '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>' +
                '</svg>';
        }

        currentStepsContainer
            .querySelectorAll('.step-item')
            .forEach(function (s) {
                s.classList.add('step-item-done');
            });

        currentStepsContainer = null;
    }

    //  API Communication
    function sendMessage (text) {
        if (!text || isProcessing) return;

        isProcessing = true;
        const userQuery = text;
        appendMessageDOM(text, true);
        dom.input.value = '';
        autoResizeInput();
        updateSendBtn();
        setAgentThinking(true);
        setSidebarDisabled(true);

        addSidebarItem(userQuery, '');

        fetch(API_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, analysis: analysisMode }),
        })
            .then(function (res) {
                if (!res.ok) {
                    return res.json().then(function (data) {
                        throw new Error(data.error || 'Request failed');
                    });
                }

                const reader = res.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                let lastBotMsgEl = null;

                function injectFollowUpChips (msgEl, text) {
                    if (!msgEl || !text) return;
                    const parsed = parseFollowUp(text);
                    if (!parsed) return;

                    const existing = msgEl.querySelector('.follow-up-section');
                    if (existing) existing.remove();
                    const bubble = msgEl.querySelector('.message-bubble');
                    if (!bubble) return;
                    const followUpDiv = document.createElement('div');
                    followUpDiv.className = 'follow-up-section';
                    const heading = document.createElement('p');
                    heading.className = 'follow-up-heading';
                    heading.textContent = 'Follow up Questions:';
                    followUpDiv.appendChild(heading);
                    const chipWrap = document.createElement('div');
                    chipWrap.className = 'follow-up-chips';
                    parsed.questions.forEach(function (q) {
                        const chip = document.createElement('button');
                        chip.className = 'follow-up-chip';
                        chip.textContent = q;
                        chip.addEventListener('click', function () {
                            sendMessage(q);
                        });
                        chipWrap.appendChild(chip);
                    });
                    followUpDiv.appendChild(chipWrap);
                    bubble.appendChild(followUpDiv);
                    scrollToBottom();
                }
                function processLines (lines) {
                    lines.forEach(function (line) {
                        line = line.trim();
                        if (!line) return;
                        try {
                            const data = JSON.parse(line);
                            if (data.type === 'step') {
                                //appendStepToTimeline(data.step, data.text);
                            } else if (data.type === 'done') {
                                setAgentThinking(false);
                                //finalizeSteps();
                                appendMessageDOM(
                                    data.response || 'No response received.',
                                    false,
                                    true,
                                    '',
                                    data.sql_query || '',
                                );
                                const allBotMsgs =
                                    dom.messages.querySelectorAll(
                                        '.message-bot',
                                    );
                                lastBotMsgEl =
                                    allBotMsgs[allBotMsgs.length - 1] || null;

                                if (data.question_id) {
                                    activeQuestionId = data.question_id;
                                    if (activeQuestionId) {
                                        console.log(activeQuestionId);
                                    }
                                    const pending = dom.convList.querySelector(
                                        '.conv-item.active .queryId',
                                    );
                                    if (pending)
                                        pending.textContent = data.question_id;
                                }
                                if (data.needs_followup_fetch) {
                                    fetchFollowUp(
                                        userQuery,
                                        data.response || '',
                                    );
                                }
                            } else if (data.type === 'followup') {
                                if (lastBotMsgEl && data.text) {
                                    injectFollowUpChips(
                                        lastBotMsgEl,
                                        data.text,
                                    );
                                }
                            } else if (data.type === 'error') {
                                setAgentThinking(false);
                                finalizeSteps();
                                appendMessageDOM('Error: ' + data.error, false);
                            }
                        } catch (e) {
                            console.error(
                                '[sendMessage] Failed to parse stream line:',
                                line,
                                e,
                            );
                        }
                    });
                }

                function processStream () {
                    return reader.read().then(function (result) {
                        if (result.value) {
                            buffer += decoder.decode(result.value, {
                                stream: !result.done,
                            });
                        }

                        const lines = buffer.split('\n');

                        if (result.done) {
                            buffer = '';
                            processLines(lines);
                            return;
                        }

                        buffer = lines.pop();
                        processLines(lines);

                        return processStream();
                    });
                }

                return processStream();
            })
            .catch(function (err) {
                setAgentThinking(false);
                appendMessageDOM(
                    err.message || 'Connection error. Please try again.',
                    false,
                );
            })
            .finally(function () {
                isProcessing = false;
                setSidebarDisabled(false);
                // Reset analysis mode after every query
                analysisMode = false;
                dom.analysisBtn.classList.remove('active');
                dom.analysisBtn.title = 'Enable deep analysis';
            });
    }

    //  Input Handling
    function autoResizeInput () {
        dom.input.style.height = 'auto';
        dom.input.style.height = Math.min(dom.input.scrollHeight, 150) + 'px';
    }

    function updateSendBtn () {
        dom.sendBtn.disabled = !dom.input.value.trim() || isProcessing;
    }

    function scrollToBottom () {
        requestAnimationFrame(function () {
            dom.chat.scrollTop = dom.chat.scrollHeight;
        });
    }

    function scrollToMessage (msgEl) {
        requestAnimationFrame(function () {
            msgEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }

    //  Event Bindings
    dom.sendBtn.addEventListener('click', function () {
        sendMessage(dom.input.value.trim());
    });

    dom.input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(dom.input.value.trim());
        }
    });

    dom.input.addEventListener('input', function () {
        autoResizeInput();
        updateSendBtn();
    });

    dom.analysisBtn.addEventListener('click', function () {
        analysisMode = !analysisMode;
        dom.analysisBtn.classList.toggle('active', analysisMode);
        dom.analysisBtn.title = analysisMode
            ? 'Deep analysis enabled'
            : 'Enable deep analysis';
        if (!analysisMode) {
            dom.analysisBtn.classList.add('no-hover');
            dom.analysisBtn.addEventListener('mouseleave', function handler () {
                dom.analysisBtn.classList.remove('no-hover');
                dom.analysisBtn.removeEventListener('mouseleave', handler);
            });
        }
    });

    dom.sidebarToggle.addEventListener('click', toggleSidebar);
    dom.sidebarOverlay.addEventListener('click', closeSidebar);
    dom.newChatSidebar.addEventListener('click', startNewChat);
    dom.newChatHeader.addEventListener('click', startNewChat);

    dom.convSearch.addEventListener('input', function () {
        filterSidebar(dom.convSearch.value);
    });

    // Suggestion cards
    document.querySelectorAll('.suggestion-card').forEach(function (card) {
        card.addEventListener('click', function () {
            const query = card.getAttribute('data-query');
            if (query) sendMessage(query);
        });
    });

    //  Sidebar lazy-load
    function loadSidebarHistory () {
        fetch(SIDEBAR_HISTORY_ENDPOINT)
            .then(function (res) {
                // console.log('[loadSidebarHistory] Response status:', res.status);
                return res.json();
            })
            .then(function (data) {
                const items = data.history || [];
                // console.log('[loadSidebarHistory] Received', items.length, 'history items');

                // Remove loading / empty state
                const emptyEl = dom.convList.querySelector('.conv-empty');
                if (emptyEl) emptyEl.remove();

                if (!items.length) {
                    // console.log('[loadSidebarHistory] No history found — showing empty state');
                    const empty = document.createElement('div');
                    empty.className = 'conv-empty';
                    empty.innerHTML =
                        '<p>No conversations yet</p><span>Start a new chat to begin</span>';
                    dom.convList.appendChild(empty);
                    return;
                }

                items.forEach(function (item, idx) {
                    // console.log('[loadSidebarHistory] Adding item', idx, ':', item.question_id, '-', (item.query || '').slice(0, 40));
                    const div = document.createElement('div');
                    div.className = 'conv-item';
                    div.innerHTML =
                        '<a href="#" class="conv-item-link">' +
                        '<div class="conv-item-icon">' +
                        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>' +
                        '</div>' +
                        '<div class="conv-item-text">' +
                        '<span class="conv-item-title">' +
                        escapeHtml((item.query || '').slice(0, 60)) +
                        '</span>' +
                        '<span class="conv-item-time">' +
                        escapeHtml(item.query_time || '') +
                        '</span>' +
                        '</div>' +
                        '</a>' +
                        '<p class="d-none queryId">' +
                        escapeHtml(item.question_id || '') +
                        '</p>';
                    dom.convList.appendChild(div);
                });
                // console.log('[loadSidebarHistory] Sidebar populated with', items.length, 'items');
            })
            .catch(function (err) {
                console.error(
                    '[loadSidebarHistory] ERROR fetching sidebar history:',
                    err,
                );
            });
    }

    //  Initialization
    dom.input.focus();
    loadSidebarHistory();
})();
