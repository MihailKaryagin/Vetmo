(() => {
    'use strict';
    const widget = document.querySelector('.support-widget');
    if (!widget) return;
    const panel = widget.querySelector('.support-panel');
    const toggle = widget.querySelector('.support-toggle');
    const form = widget.querySelector('form');
    const input = widget.querySelector('textarea');
    const status = widget.querySelector('.support-status');
    const log = widget.querySelector('.support-messages');
    let cursor = 0;
    let revision = 0;
    let closed = false;
    let csrf = '';
    let loading = false;
    let sending = false;
    let delivery = '';
    const cookie = () => document.cookie.split('; ').find(value => value.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
    async function refresh() {
        if (loading || panel.hidden || document.hidden) return;
        loading = true;
        try {
            const response = await fetch(`${widget.dataset.endpoint}?after=${cursor}&revision=${revision}`, { credentials: 'same-origin', cache: 'no-store' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Не удалось загрузить чат.');
            csrf = cookie();
            if (data.revision !== revision) {
                log.querySelectorAll('.support-bubble').forEach(node => node.remove());
                cursor = 0;
                revision = data.revision;
            }
            closed = data.is_closed;
            input.disabled = closed;
            form.querySelectorAll('button').forEach(button => { button.disabled = closed || sending; });
            for (const message of data.messages) {
                if (message.id <= cursor) continue;
                const bubble = document.createElement('p');
                bubble.className = `support-bubble${message.from_operator ? ' operator' : ''}`;
                bubble.textContent = message.text;
                if (message.from_operator && /^#[0-9a-f]{6}$/i.test(message.color)) bubble.style.color = message.color;
                log.append(bubble);
                cursor = message.id;
                log.scrollTop = log.scrollHeight;
            }
            status.textContent = closed ? 'Диалог закрыт оператором.' : delivery;
        } catch (error) {
            status.textContent = error.message || 'Нет связи. Попробуем снова.';
        } finally { loading = false; }
    }
    function setOpen(open) {
        panel.hidden = !open;
        toggle.setAttribute('aria-expanded', String(open));
        if (open) { refresh(); input.focus(); }
        else toggle.focus();
    }
    toggle.addEventListener('click', () => setOpen(panel.hidden));
    document.querySelector('[data-order-question]')?.addEventListener('click', event => {
        setOpen(true);
        const prefix = `Вопрос по заказу ${event.currentTarget.dataset.orderQuestion}: `;
        if (!input.value.startsWith(prefix)) input.value = prefix + input.value;
        input.focus();
    });
    widget.querySelector('.support-close').addEventListener('click', () => setOpen(false));
    widget.addEventListener('keydown', event => { if (event.key === 'Escape') setOpen(false); });
    input.addEventListener('keydown', event => {
        if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            if (!form.querySelector('[type="submit"]').disabled) form.requestSubmit();
        }
    });
    form.querySelectorAll('[data-quick]').forEach(button => button.addEventListener('click', () => {
        input.value = button.dataset.quick;
        form.requestSubmit();
    }));
    form.addEventListener('submit', async event => {
        event.preventDefault();
        const text = input.value.trim();
        if (!text || sending || closed) return;
        sending = true;
        const button = form.querySelector('[type="submit"]');
        button.disabled = true;
        status.textContent = delivery = 'Отправляем…';
        try {
            // Initial GET sets Django's CSRF cookie before the first POST.
            if (!csrf) { await refresh(); csrf = cookie(); }
            if (!csrf) throw new Error('Не удалось начать чат. Разрешите cookies и попробуйте снова.');
            const response = await fetch(widget.dataset.endpoint, {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(csrf) },
                body: JSON.stringify({ text }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Не удалось отправить сообщение.');
            if (input.value.trim() === text) input.value = '';
            status.textContent = delivery = 'Доставлено';
            await refresh();
        } catch (error) { status.textContent = delivery = `${error.message || 'Нет связи'}. Текст сохранён. Нажмите «Отправить», чтобы повторить.`; }
        finally { sending = false; form.querySelectorAll('button').forEach(b => b.disabled = closed); }
    });
    window.setInterval(refresh, 3000);
    document.addEventListener('visibilitychange', refresh);
})();
