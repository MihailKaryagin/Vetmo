(() => {
    'use strict';
    const chat = document.querySelector('.operator-chat');
    if (document.querySelector('[data-support-list]')) {
        window.setInterval(() => {
            if (!document.hidden && !document.querySelector('#searchbar:focus')) window.location.reload();
        }, 15000);
    }
    if (!chat) return;
    const log = chat.querySelector('.operator-log');
    const status = chat.querySelector('.operator-status');
    let cursor = 0;
    let revision = 0;
    let loading = false;
    async function refresh() {
        if (loading || document.hidden) return;
        loading = true;
        try {
            const response = await fetch(`${chat.dataset.endpoint}?after=${cursor}&revision=${revision}`, { credentials: 'same-origin', cache: 'no-store' });
            if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Не удалось загрузить сообщения. Проверьте соединение и вход в админку.');
            const data = await response.json();
            if (data.revision !== revision) {
                log.replaceChildren();
                cursor = 0;
                revision = data.revision;
            }
            chat.querySelectorAll('.operator-form textarea, .operator-form button, .operator-form select').forEach(node => { node.disabled = data.is_closed; });
            const close = chat.querySelector('[data-close-chat]');
            const reopen = chat.querySelector('[data-reopen-chat]');
            if (close) close.hidden = data.is_closed;
            if (reopen) reopen.hidden = !data.is_closed;
            const stickToBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 60;
            for (const message of data.messages) {
                if (message.id <= cursor) continue;
                const bubble = document.createElement('div');
                bubble.className = `operator-message${message.from_operator ? ' is-operator' : ''}`;
                const author = document.createElement('strong');
                author.textContent = message.from_operator ? 'Поддержка' : 'Посетитель';
                const text = document.createElement('p');
                text.textContent = message.text;
                if (message.from_operator && /^#[0-9a-f]{6}$/i.test(message.color)) text.style.color = message.color;
                const time = document.createElement('time');
                time.dateTime = message.created_at;
                time.textContent = new Date(message.created_at).toLocaleString('ru-RU');
                bubble.append(author, text, time);
                log.append(bubble);
                cursor = message.id;
            }
            if (stickToBottom) log.scrollTop = log.scrollHeight;
            status.textContent = data.is_closed ? 'Диалог закрыт. Откройте его, чтобы продолжить.' : (cursor ? '' : 'Пока нет сообщений.');
        } catch (error) { status.textContent = error.message; }
        finally { loading = false; }
    }
    refresh();
    window.setInterval(refresh, 3000);
    document.addEventListener('visibilitychange', refresh);
    const form = chat.querySelector('.operator-form');
    if (form) {
        const input = form.querySelector('textarea');
        input.addEventListener('keydown', event => {
            if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
                event.preventDefault();
                if (!input.disabled && input.value.trim()) form.requestSubmit();
            }
        });
        form.querySelectorAll('[data-quick]').forEach(button => button.addEventListener('click', () => {
            input.value = button.dataset.quick;
            input.focus();
        }));
    }
})();
