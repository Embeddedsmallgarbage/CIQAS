/**
 * 高校事务智能问答系统 - 前端交互
 * Academic Futurism Interaction Design
 */

let currentConversationId = null;
let conversations = [];
let isKbReady = false;
let isStreaming = false;
let studentCategories = [];
let selectedCategoryId = null;

const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const conversationList = document.getElementById('conversationList');
const settingsModal = document.getElementById('settingsModal');
const loadingOverlay = document.getElementById('loadingOverlay');
const kbWarning = document.getElementById('kbWarning');
const documentList = document.getElementById('documentList');
const welcomeScreen = document.getElementById('welcomeScreen');
const statusIndicator = document.getElementById('statusIndicator');
const conversationCount = document.getElementById('conversationCount');
const docCount = document.getElementById('docCount');
const sendBtn = document.getElementById('sendBtn');
const sidebar = document.getElementById('sidebar');
const studentList = document.getElementById('studentList');
const studentSearchInput = document.getElementById('studentSearchInput');

let allStudents = [];

function logout() {
    window.location.href = '/logout';
}

document.addEventListener('DOMContentLoaded', function() {
    loadConversations();
    checkKbStatus();
    setupDragAndDrop();
    setupTextareaAutoResize();
    setupStudentSearch();
    setupModelParamValidation();
    
    messageInput.focus();
});

function setupStudentSearch() {
    if (studentSearchInput) {
        studentSearchInput.addEventListener('input', function() {
            const keyword = this.value.trim();
            searchStudents(keyword);
        });
    }
}

function toggleSidebar() {
    sidebar.classList.toggle('open');
}

function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

function setupTextareaAutoResize() {
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

async function loadStudentCategories() {
    try {
        const response = await fetch('/api/student-categories');
        studentCategories = await response.json();
        renderStudentTree(studentCategories);
    } catch (error) {
        console.error('加载学生分类失败:', error);
    }
}

function renderStudentTree(categories) {
    const treeContainer = document.getElementById('studentCategoryTree');
    if (!treeContainer) return;

    treeContainer.innerHTML = '';

    // 更新添加学生表单中的分类下拉框
    const categorySelect = document.getElementById('studentCategorySelect');
    if (categorySelect) {
        categorySelect.innerHTML = '<option value="">-- 选择分类 --</option>';
        categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category.id;
            option.textContent = category.name;
            categorySelect.appendChild(option);
        });
    }

    if (categories.length === 0) {
        treeContainer.innerHTML = '<div class="folder-empty">暂无分类</div>';
        return;
    }

    categories.forEach(category => {
        const folder = document.createElement('div');
        folder.className = 'folder-item';

        const isSelected = selectedCategoryId === category.id;

        folder.innerHTML = `
            <div class="folder-header ${isSelected ? 'selected' : ''}" onclick="selectCategory(${category.id})">
                <div class="folder-icon" id="categoryIcon-${category.id}" onclick="event.stopPropagation(); toggleStudentFolder(${category.id})">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="9 18 15 12 9 6"/>
                    </svg>
                </div>
                <div class="folder-category-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                        <circle cx="12" cy="7" r="4"/>
                    </svg>
                </div>
                <span class="folder-name">${category.name}</span>
                <span class="folder-count">${category.student_count || 0}</span>
                <button class="btn-remove-doc" onclick="event.stopPropagation(); deleteCategory(${category.id})" aria-label="删除分类">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            </div>
            <div class="folder-content" id="categoryContent-${category.id}">
                ${category.description ? `<div class="folder-description">${category.description}</div>` : ''}
            </div>
        `;

        treeContainer.appendChild(folder);
    });
}

function toggleStudentFolder(categoryId) {
    const content = document.getElementById(`categoryContent-${categoryId}`);
    const icon = document.getElementById(`categoryIcon-${categoryId}`);

    if (content && icon) {
        content.classList.toggle('expanded');
        icon.classList.toggle('expanded');
    }
}

function showAddCategoryForm() {
    const form = document.getElementById('addCategoryForm');
    if (form) {
        form.style.display = 'block';
        document.getElementById('categoryName').focus();
    }
}

function hideAddCategoryForm() {
    const form = document.getElementById('addCategoryForm');
    if (form) {
        form.style.display = 'none';
        document.getElementById('categoryName').value = '';
        document.getElementById('categoryDescription').value = '';
    }
}

async function addCategory() {
    const name = document.getElementById('categoryName').value.trim();
    const description = document.getElementById('categoryDescription').value.trim();

    if (!name) {
        alert('请输入分类名称');
        return;
    }

    try {
        const response = await fetch('/api/student-categories', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name, description })
        });

        const data = await response.json();

        if (data.success) {
            hideAddCategoryForm();
            await loadStudentCategories();
        } else {
            alert('添加失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        console.error('添加分类失败:', error);
        alert('添加失败，请重试');
    }
}

async function deleteCategory(categoryId) {
    const category = studentCategories.find(c => c.id === categoryId);
    const categoryName = category ? category.name : '该分类';

    if (!confirm(`确定要删除分类 "${categoryName}" 吗？该分类下的学生将被移出此分类。`)) {
        return;
    }

    try {
        const response = await fetch(`/api/student-categories/${categoryId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            if (selectedCategoryId === categoryId) {
                selectedCategoryId = null;
            }
            await loadStudentCategories();
            await loadStudentList();
        } else {
            alert('删除失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        console.error('删除分类失败:', error);
        alert('删除失败，请重试');
    }
}

function selectCategory(categoryId) {
    selectedCategoryId = categoryId;
    renderStudentTree(studentCategories);
    loadStudentList(categoryId);
}

async function loadStudentList(categoryId = null) {
    try {
        let url = '/api/students';
        if (categoryId) {
            url = `/api/students?category_id=${categoryId}`;
        }
        const response = await fetch(url);
        const students = await response.json();
        allStudents = students;
        
        const keyword = studentSearchInput ? studentSearchInput.value.trim() : '';
        if (keyword) {
            searchStudents(keyword);
        } else {
            renderStudentList([]);
        }
    } catch (error) {
        console.error('加载学生列表失败:', error);
    }
}

function searchStudents(keyword) {
    if (!keyword || keyword.trim() === '') {
        renderStudentList([]);
        return;
    }
    
    const lowerKeyword = keyword.toLowerCase().trim();
    const filteredStudents = allStudents.filter(student => {
        const usernameMatch = student.username.toLowerCase().includes(lowerKeyword);
        const nameMatch = student.name.toLowerCase().includes(lowerKeyword);
        return usernameMatch || nameMatch;
    });
    
    renderStudentList(filteredStudents, true);
}

function renderStudentList(students, isSearchResult = false) {
    if (!studentList) return;
    
    studentList.innerHTML = '';
    
    if (!isSearchResult && students.length === 0) {
        studentList.innerHTML = '<div class="empty-state"><span>请输入学号或姓名进行搜索</span></div>';
        return;
    }
    
    if (isSearchResult && students.length === 0) {
        studentList.innerHTML = '<div class="empty-state"><span>未找到匹配的学生</span></div>';
        return;
    }
    
    students.forEach(student => {
        const item = document.createElement('div');
        item.className = 'student-item';
        item.dataset.username = student.username;
        
        item.innerHTML = `
            <div class="student-info">
                <div class="student-avatar">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                        <circle cx="12" cy="7" r="4"/>
                    </svg>
                </div>
                <div class="student-details">
                    <span class="student-name">${student.name}</span>
                    <span class="student-id">${student.username}</span>
                </div>
            </div>
            <button class="btn-remove-student" onclick="deleteStudent('${student.username}')" aria-label="删除学生">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
            </button>
        `;
        
        studentList.appendChild(item);
    });
}

function showAddStudentForm() {
    const form = document.getElementById('addStudentForm');
    if (form) {
        form.style.display = 'block';
        document.getElementById('studentUsername').focus();
    }
}

function hideAddStudentForm() {
    const form = document.getElementById('addStudentForm');
    if (form) {
        form.style.display = 'none';
        document.getElementById('studentUsername').value = '';
        document.getElementById('studentName').value = '';
        document.getElementById('studentPassword').value = '';
    }
}

async function addStudent() {
    const username = document.getElementById('studentUsername').value.trim();
    const name = document.getElementById('studentName').value.trim();
    const password = document.getElementById('studentPassword').value;
    const categoryId = document.getElementById('studentCategorySelect')?.value;

    if (!username || !name || !password) {
        alert('请填写所有字段');
        return;
    }

    try {
        const body = { username, name, password };
        if (categoryId && categoryId !== '') {
            body.category_id = parseInt(categoryId);
        }

        const response = await fetch('/api/students', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(body)
        });

        const data = await response.json();

        if (data.success) {
            hideAddStudentForm();
            await loadStudentList(selectedCategoryId);
            await loadStudentCategories();
        } else {
            alert('添加失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        console.error('添加学生失败:', error);
        alert('添加失败，请重试');
    }
}

async function deleteStudent(username) {
    if (!confirm(`确定要删除学生账号 "${username}" 吗？`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/students/${encodeURIComponent(username)}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            await loadStudentList();
        } else {
            alert('删除失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        console.error('删除学生失败:', error);
        alert('删除失败，请重试');
    }
}

function setupDragAndDrop() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.style.borderColor = 'var(--color-bronze)';
            uploadArea.style.background = 'var(--color-parchment)';
        });
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.style.borderColor = 'var(--color-sand)';
            uploadArea.style.background = 'var(--color-cream)';
        });
    });
    
    uploadArea.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFiles(files);
        }
    });
}

async function loadConversations() {
    try {
        const response = await fetch('/api/conversations');
        conversations = await response.json();
        renderConversationList();
        updateConversationCount();
    } catch (error) {
        console.error('加载对话列表失败:', error);
    }
}

function updateConversationCount() {
    if (conversationCount) {
        conversationCount.textContent = conversations.length;
    }
}

function renderConversationList() {
    conversationList.innerHTML = '';

    if (conversations.length === 0) {
        conversationList.innerHTML = `
            <div class="empty-state">
                <svg class="empty-icon" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                </svg>
                <span>暂无对话记录</span>
            </div>
        `;
        return;
    }

    conversations.forEach((conv, index) => {
        const item = document.createElement('div');
        item.className = `conversation-item ${conv.id === currentConversationId ? 'active' : ''}`;
        item.style.animationDelay = `${index * 30}ms`;
        item.onclick = () => switchConversation(conv.id);
        item.oncontextmenu = (e) => showContextMenu(e, conv.id);

        const icon = document.createElement('span');
        icon.className = 'icon';
        icon.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;

        const title = document.createElement('span');
        title.className = 'title';
        title.textContent = conv.title;

        item.appendChild(icon);
        item.appendChild(title);
        conversationList.appendChild(item);
    });
}

async function createNewConversation() {
    try {
        const response = await fetch('/api/conversations', {
            method: 'POST'
        });
        const newConv = await response.json();

        currentConversationId = newConv.id;
        conversations.unshift(newConv);

        renderConversationList();
        updateConversationCount();
        clearChatMessages();
        showWelcomeScreen();
        
        messageInput.focus();
    } catch (error) {
        console.error('创建对话失败:', error);
    }
}

function showWelcomeScreen() {
    if (welcomeScreen) {
        welcomeScreen.style.display = 'flex';
    }
}

function hideWelcomeScreen() {
    if (welcomeScreen) {
        welcomeScreen.style.display = 'none';
    }
}

async function switchConversation(convId) {
    if (convId === currentConversationId) return;

    currentConversationId = convId;
    renderConversationList();

    try {
        const response = await fetch(`/api/conversations/${convId}`);
        const conv = await response.json();
        
        hideWelcomeScreen();
        renderMessages(conv.messages);
    } catch (error) {
        console.error('加载对话失败:', error);
    }
}

function renderMessages(messages) {
    const existingMessages = chatMessages.querySelectorAll('.message');
    existingMessages.forEach(m => m.remove());

    if (messages.length === 0) {
        showWelcomeScreen();
        return;
    }

    hideWelcomeScreen();
    messages.forEach(msg => {
        appendMessage(msg.role, msg.content, []);
    });

    scrollToBottom();
}

function clearChatMessages() {
    const existingMessages = chatMessages.querySelectorAll('.message');
    existingMessages.forEach(m => m.remove());
    showWelcomeScreen();
}

function askQuestion(question) {
    messageInput.value = question;
    messageInput.focus();
    sendMessage();
}

async function sendMessage() {
    if (isStreaming) return;

    const question = messageInput.value.trim();
    if (!question) return;

    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    hideWelcomeScreen();
    appendMessage('user', question, []);

    isStreaming = true;
    sendBtn.disabled = true;
    showLoading();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: question,
                conversation_id: currentConversationId,
                stream: true
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantDiv = null;
        let fullContent = '';
        let sources = [];

        hideLoading();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));

                        if (data.type === 'chunk') {
                            fullContent += data.content;

                            if (!assistantDiv) {
                                assistantDiv = createMessageElement('assistant');
                                chatMessages.appendChild(assistantDiv);
                            }

                            const contentDiv = assistantDiv.querySelector('.message-content');
                            contentDiv.innerHTML = renderMarkdown(fullContent) + '<span class="typing-cursor"></span>';
                            scrollToBottom();
                        } else if (data.type === 'done') {
                            sources = data.sources;

                            if (assistantDiv) {
                                const contentDiv = assistantDiv.querySelector('.message-content');
                                contentDiv.innerHTML = renderMarkdown(fullContent);
                                
                                if (sources.length > 0) {
                                    addSourcesToMessage(assistantDiv, sources);
                                }
                            }

                            if (data.conversation_id !== currentConversationId) {
                                currentConversationId = data.conversation_id;
                                loadConversations();
                            }
                        } else if (data.type === 'error') {
                            appendMessage('assistant', `错误: ${data.message}`, []);
                        }
                    } catch (e) {
                        console.error('解析响应失败:', e);
                    }
                }
            }
        }

        if (!assistantDiv) {
            appendMessage('assistant', '抱歉，未能获取回复。', []);
        }

    } catch (error) {
        console.error('发送消息失败:', error);
        hideLoading();
        appendMessage('assistant', '抱歉，发送消息时出现错误，请稍后重试。', []);
    } finally {
        isStreaming = false;
        sendBtn.disabled = false;
        scrollToBottom();
    }
}

function createMessageElement(role) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    if (role === 'user') {
        avatar.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
    } else {
        avatar.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>`;
    }

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);

    return messageDiv;
}

function appendMessage(role, content, sources) {
    const messageDiv = createMessageElement(role);
    const contentDiv = messageDiv.querySelector('.message-content');

    contentDiv.innerHTML = renderMarkdown(content);

    if (sources && sources.length > 0) {
        addSourcesToMessage(messageDiv, sources);
    }

    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

function addSourcesToMessage(messageDiv, sources) {
    const contentDiv = messageDiv.querySelector('.message-content');

    const sourcesDetails = document.createElement('details');
    sourcesDetails.className = 'message-sources';

    const summary = document.createElement('summary');
    summary.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 6px;" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>查看参考来源`;
    sourcesDetails.appendChild(summary);

    sources.forEach((source, index) => {
        const sourceItem = document.createElement('div');
        sourceItem.className = 'source-item';

        const sourceName = document.createElement('div');
        sourceName.className = 'source-name';
        sourceName.textContent = `来源 ${index + 1}: ${source.source}`;

        const sourceContent = document.createElement('div');
        sourceContent.className = 'source-content';
        sourceContent.textContent = source.content;

        sourceItem.appendChild(sourceName);
        sourceItem.appendChild(sourceContent);
        sourcesDetails.appendChild(sourceItem);
    });

    contentDiv.appendChild(sourcesDetails);
}

function renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
        return marked.parse(text);
    }

    let html = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>');
    html = html.replace(/\n/g, '<br>');

    return html;
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });
}

function showLoading() {
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
}

async function checkKbStatus() {
    try {
        const response = await fetch('/api/kb/status');
        const data = await response.json();

        isKbReady = data.ready;
        
        if (kbWarning) {
            kbWarning.style.display = isKbReady ? 'none' : 'block';
        }
        
        if (statusIndicator) {
            const statusText = statusIndicator.querySelector('.status-text');
            if (isKbReady) {
                statusIndicator.classList.remove('warning', 'error');
                if (statusText) statusText.textContent = '知识库就绪';
            } else {
                statusIndicator.classList.add('warning');
                if (statusText) statusText.textContent = '知识库未初始化';
            }
        }

        if (settingsModal.classList.contains('show')) {
            renderDocumentList(data.documents);
        }
    } catch (error) {
        console.error('检查知识库状态失败:', error);
    }
}

async function toggleSettingsPanel() {
    const isShowing = settingsModal.classList.contains('show');

    if (isShowing) {
        settingsModal.classList.remove('show');
    } else {
        settingsModal.classList.add('show');
        await loadDocumentTree();
        await loadModelSettings();
        if (window.currentUser && window.currentUser.role === 'admin') {
            await loadStudentCategories();
            await loadStudentList();
        }
    }
}

function switchSettingsTab(tabName) {
    document.querySelectorAll('.settings-nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.tab === tabName) {
            item.classList.add('active');
        }
    });
    
    document.querySelectorAll('.settings-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    
    const targetPanel = document.getElementById(`panel-${tabName}`);
    if (targetPanel) {
        targetPanel.classList.add('active');
    }
}

settingsModal.addEventListener('click', function(event) {
    if (event.target === settingsModal) {
        toggleSettingsPanel();
    }
});

document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape' && settingsModal.classList.contains('show')) {
        toggleSettingsPanel();
    }
});

async function loadDocumentList() {
    try {
        const response = await fetch('/api/kb/status');
        const data = await response.json();
        renderDocumentList(data.documents);
    } catch (error) {
        console.error('加载文档列表失败:', error);
    }
}

async function loadDocumentTree() {
    try {
        const response = await fetch('/api/kb/documents');
        const categories = await response.json();
        renderDocumentTree(categories);
    } catch (error) {
        console.error('加载文档树失败:', error);
    }
}

function renderDocumentTree(categories) {
    const documentTree = document.getElementById('documentTree');
    if (!documentTree) return;
    
    documentTree.innerHTML = '';
    
    const categoryIcons = {
        'regulations': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
        'procedures': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M9 15l2 2 4-4"/></svg>',
        'campus_life': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
        'teaching': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>',
        'other': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>'
    };
    
    let hasDocuments = false;
    
    Object.entries(categories).forEach(([catId, catData]) => {
        if (catData.count > 0) {
            hasDocuments = true;
        }
        
        const folder = document.createElement('div');
        folder.className = 'folder-item';
        
        folder.innerHTML = `
            <div class="folder-header" onclick="toggleFolder('${catId}')">
                <div class="folder-icon" id="folderIcon-${catId}">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="9 18 15 12 9 6"/>
                    </svg>
                </div>
                <div class="folder-category-icon">${categoryIcons[catId] || categoryIcons['other']}</div>
                <span class="folder-name">${catData.name}</span>
                <span class="folder-count">${catData.count}</span>
            </div>
            <div class="folder-content" id="folderContent-${catId}">
                ${catData.documents.length === 0 ? '<div class="folder-empty">暂无文档</div>' : ''}
            </div>
        `;
        
        documentTree.appendChild(folder);
        
        if (catData.documents.length > 0) {
            const content = folder.querySelector('.folder-content');
            catData.documents.forEach(doc => {
                const docItem = document.createElement('div');
                docItem.className = 'doc-item';
                docItem.innerHTML = `
                    <div class="doc-info">
                        <svg class="doc-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                        </svg>
                        <span class="doc-name" title="${doc.name}">${doc.name}</span>
                        <span class="doc-chunks">${doc.chunks} 片段</span>
                    </div>
                    <button class="btn-remove-doc" onclick="deleteDocument('${doc.name}')" aria-label="删除文档">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                    </button>
                `;
                content.appendChild(docItem);
            });
        }
    });
    
    if (!hasDocuments) {
        documentTree.innerHTML = '<div class="empty-state"><span>暂无文档，请上传</span></div>';
    }
}

function toggleFolder(catId) {
    const content = document.getElementById(`folderContent-${catId}`);
    const icon = document.getElementById(`folderIcon-${catId}`);
    
    if (content && icon) {
        content.classList.toggle('expanded');
        icon.classList.toggle('expanded');
    }
}

function renderDocumentList(documents) {
    documentList.innerHTML = '';
    
    if (docCount) {
        docCount.textContent = documents.length;
    }

    if (documents.length === 0) {
        documentList.innerHTML = `
            <div class="empty-state">
                <span>暂无文档</span>
            </div>
        `;
        return;
    }

    documents.forEach((docName, index) => {
        const item = document.createElement('div');
        item.className = 'document-item';
        item.style.animationDelay = `${index * 50}ms`;

        const name = document.createElement('span');
        name.className = 'document-name';
        name.textContent = docName;

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn-delete';
        deleteBtn.textContent = '删除';
        deleteBtn.onclick = () => deleteDocument(docName);

        item.appendChild(name);
        item.appendChild(deleteBtn);
        documentList.appendChild(item);
    });
}

async function handleFileSelect(event) {
    const files = event.target.files;
    if (files.length > 0) {
        handleFiles(files);
    }
}

async function handleFiles(files) {
    const uploadStatus = document.getElementById('uploadStatus');
    const categorySelect = document.getElementById('categorySelect');
    const category = categorySelect ? categorySelect.value : 'other';
    
    const validFiles = Array.from(files).filter(file => {
        const ext = file.name.split('.').pop().toLowerCase();
        return ['txt', 'pdf'].includes(ext);
    });

    if (validFiles.length === 0) {
        uploadStatus.innerHTML = '<div class="status-message error">请选择 .txt 或 .pdf 格式的文件</div>';
        setTimeout(() => uploadStatus.innerHTML = '', 3000);
        return;
    }

    uploadStatus.innerHTML = `<div class="status-message">正在上传 ${validFiles.length} 个文件...</div>`;

    let successCount = 0;
    let errorMessages = [];

    for (const file of validFiles) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('category', category);

        try {
            const response = await fetch('/api/kb/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                successCount++;
            } else {
                errorMessages.push(`${file.name}: ${data.error}`);
            }
        } catch (error) {
            errorMessages.push(`${file.name}: 上传失败`);
        }
    }

    if (successCount > 0) {
        uploadStatus.innerHTML = `<div class="status-message success">成功上传 ${successCount} 个文件</div>`;
        await loadDocumentTree();
        await checkKbStatus();
    }
    
    if (errorMessages.length > 0) {
        uploadStatus.innerHTML = `<div class="status-message error">${errorMessages.join('<br>')}</div>`;
    }

    document.getElementById('fileInput').value = '';
    
    setTimeout(() => {
        uploadStatus.innerHTML = '';
    }, 5000);
}

async function deleteDocument(docName) {
    if (!confirm(`确定要删除文档 "${docName}" 吗？`)) {
        return;
    }

    try {
        const response = await fetch(`/api/kb/documents/${encodeURIComponent(docName)}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            await loadDocumentTree();
            await checkKbStatus();
        } else {
            alert('删除失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        console.error('删除文档失败:', error);
        alert('删除失败，请重试');
    }
}

let contextMenu = null;

function showContextMenu(event, convId) {
    event.preventDefault();

    if (contextMenu) {
        contextMenu.remove();
    }

    contextMenu = document.createElement('div');
    contextMenu.className = 'context-menu';
    contextMenu.style.cssText = `
        position: fixed;
        left: ${event.clientX}px;
        top: ${event.clientY}px;
    `;

    const deleteItem = document.createElement('div');
    deleteItem.className = 'context-menu-item';
    deleteItem.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 8px;" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>删除对话`;
    deleteItem.onclick = () => {
        deleteConversation(convId);
        contextMenu.remove();
        contextMenu = null;
    };

    contextMenu.appendChild(deleteItem);
    document.body.appendChild(contextMenu);

    const closeMenu = () => {
        if (contextMenu) {
            contextMenu.remove();
            contextMenu = null;
        }
        document.removeEventListener('click', closeMenu);
    };

    setTimeout(() => {
        document.addEventListener('click', closeMenu);
    }, 0);
}

async function deleteConversation(convId) {
    if (!confirm('确定要删除这个对话吗？')) {
        return;
    }

    try {
        const response = await fetch(`/api/conversations/${convId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            conversations = conversations.filter(c => c.id !== convId);
            updateConversationCount();

            if (convId === currentConversationId) {
                if (data.new_current_id) {
                    currentConversationId = data.new_current_id;
                    const conv = conversations.find(c => c.id === currentConversationId);
                    if (conv) {
                        const convDetail = await fetch(`/api/conversations/${currentConversationId}`);
                        const convData = await convDetail.json();
                        renderMessages(convData.messages);
                    }
                } else {
                    await createNewConversation();
                    return;
                }
            }

            renderConversationList();
        }
    } catch (error) {
        console.error('删除对话失败:', error);
        alert('删除失败，请重试');
    }
}

// 模型参数设置相关函数
const MODEL_PARAM_RANGES = {
    temperature: { min: 0, max: 2, default: 0.7 },
    max_tokens: { min: 1, max: 8192, default: 2048 },
    top_p: { min: 0, max: 1, default: 0.9 },
    frequency_penalty: { min: -2, max: 2, default: 0 },
    presence_penalty: { min: -2, max: 2, default: 0 },
    chunk_size: { min: 100, max: 4000, default: 1000 },
    chunk_overlap: { min: 0, max: 1000, default: 200 },
    retrieval_k: { min: 1, max: 20, default: 5 }
};

let currentModelSettings = {};

async function loadModelSettings() {
    try {
        const response = await fetch('/api/settings');
        if (!response.ok) {
            throw new Error('加载设置失败');
        }
        const data = await response.json();
        // 后端返回格式: {success: true, settings: [...]}
        const settings = data.settings || data;
        currentModelSettings = settings;
        renderModelSettings(settings);
    } catch (error) {
        console.error('加载模型设置失败:', error);
        showModelSettingsError('加载设置失败，请重试');
    }
}

function renderModelSettings(settings) {
    const llmParams = ['temperature', 'max_tokens', 'top_p', 'frequency_penalty', 'presence_penalty'];
    const embeddingParams = ['chunk_size', 'chunk_overlap', 'retrieval_k'];
    
    // 将数组格式转换为对象格式
    // 后端返回格式: [{setting_key: 'temperature', value: 0.7, ...}, ...]
    let settingsObj = settings;
    if (Array.isArray(settings)) {
        settingsObj = {};
        settings.forEach(item => {
            // 使用 setting_key 作为键，value 作为值
            const key = item.setting_key || item.key;
            const value = item.value !== undefined ? item.value : item.setting_value;
            if (key) {
                settingsObj[key] = value;
            }
        });
    }
    
    llmParams.forEach(param => {
        const input = document.getElementById(`param-${param}`);
        if (input && settingsObj[param] !== undefined) {
            input.value = settingsObj[param];
            input.classList.remove('error');
        }
    });
    
    embeddingParams.forEach(param => {
        const input = document.getElementById(`param-${param}`);
        if (input && settingsObj[param] !== undefined) {
            input.value = settingsObj[param];
            input.classList.remove('error');
        }
    });
}

function validateSetting(key, value, min, max) {
    const numValue = parseFloat(value);
    
    if (isNaN(numValue)) {
        return { valid: false, message: '请输入有效的数字' };
    }
    
    if (numValue < min) {
        return { valid: false, message: `值不能小于 ${min}` };
    }
    
    if (numValue > max) {
        return { valid: false, message: `值不能大于 ${max}` };
    }
    
    return { valid: true, value: numValue };
}

function setupModelParamValidation() {
    const paramIds = ['temperature', 'max_tokens', 'top_p', 'frequency_penalty', 'presence_penalty', 'chunk_size', 'chunk_overlap', 'retrieval_k'];
    
    paramIds.forEach(param => {
        const input = document.getElementById(`param-${param}`);
        if (input) {
            input.addEventListener('change', function() {
                const range = MODEL_PARAM_RANGES[param];
                const result = validateSetting(param, this.value, range.min, range.max);
                
                if (!result.valid) {
                    this.classList.add('error');
                    showModelSettingsError(result.message);
                } else {
                    this.classList.remove('error');
                    clearModelSettingsError();
                }
            });
            
            input.addEventListener('input', function() {
                if (this.classList.contains('error')) {
                    const range = MODEL_PARAM_RANGES[param];
                    const result = validateSetting(param, this.value, range.min, range.max);
                    if (result.valid) {
                        this.classList.remove('error');
                        clearModelSettingsError();
                    }
                }
            });
        }
    });
}

async function saveModelSettings() {
    const settings = {};
    const paramIds = ['temperature', 'max_tokens', 'top_p', 'frequency_penalty', 'presence_penalty', 'chunk_size', 'chunk_overlap', 'retrieval_k'];
    
    for (const param of paramIds) {
        const input = document.getElementById(`param-${param}`);
        if (!input) continue;
        
        const range = MODEL_PARAM_RANGES[param];
        const result = validateSetting(param, input.value, range.min, range.max);
        
        if (!result.valid) {
            input.classList.add('error');
            showModelSettingsError(`${param}: ${result.message}`);
            return;
        }
        
        settings[param] = result.value;
    }
    
    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentModelSettings = settings;
            showModelSettingsSuccess('设置已保存');
        } else {
            showModelSettingsError('保存失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        console.error('保存模型设置失败:', error);
        showModelSettingsError('保存失败，请重试');
    }
}

async function resetModelSettings() {
    if (!confirm('确定要恢复默认设置吗？')) {
        return;
    }
    
    const defaultSettings = {};
    for (const [key, config] of Object.entries(MODEL_PARAM_RANGES)) {
        defaultSettings[key] = config.default;
    }
    
    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(defaultSettings)
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentModelSettings = defaultSettings;
            renderModelSettings(defaultSettings);
            showModelSettingsSuccess('已恢复默认设置');
        } else {
            showModelSettingsError('恢复默认设置失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        console.error('恢复默认设置失败:', error);
        showModelSettingsError('恢复默认设置失败，请重试');
    }
}

function showModelSettingsError(message) {
    let errorDiv = document.getElementById('modelSettingsError');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.id = 'modelSettingsError';
        errorDiv.className = 'status-message error';
        const panel = document.getElementById('panel-model');
        if (panel) {
            panel.insertBefore(errorDiv, panel.firstChild);
        }
    }
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    
    setTimeout(() => {
        errorDiv.style.display = 'none';
    }, 5000);
}

function clearModelSettingsError() {
    const errorDiv = document.getElementById('modelSettingsError');
    if (errorDiv) {
        errorDiv.style.display = 'none';
    }
}

function showModelSettingsSuccess(message) {
    let successDiv = document.getElementById('modelSettingsSuccess');
    if (!successDiv) {
        successDiv = document.createElement('div');
        successDiv.id = 'modelSettingsSuccess';
        successDiv.className = 'status-message success';
        const panel = document.getElementById('panel-model');
        if (panel) {
            panel.insertBefore(successDiv, panel.firstChild);
        }
    }
    successDiv.textContent = message;
    successDiv.style.display = 'block';
    
    setTimeout(() => {
        successDiv.style.display = 'none';
    }, 3000);
}
