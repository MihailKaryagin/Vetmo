const navToggle = document.querySelector('.nav-toggle');
const navigation = document.querySelector('#main-navigation');
if (navToggle && navigation) {
    navToggle.hidden = false;
    document.documentElement.classList.add('has-mobile-nav');
    const closeMenu = () => {
        navToggle.setAttribute('aria-expanded', 'false');
        navigation.classList.remove('is-open');
        navigation.querySelectorAll('details[open]').forEach(group => { group.open = false; });
    };
    navToggle.addEventListener('click', () => {
        const open = navToggle.getAttribute('aria-expanded') !== 'true';
        navToggle.setAttribute('aria-expanded', String(open));
        navigation.classList.toggle('is-open', open);
    });
    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape' || !event.target.closest('.main-header')) return;
        const group = event.target.closest('details[open]');
        if (group) {
            group.open = false;
            group.querySelector('summary').focus();
        } else if (navToggle.getAttribute('aria-expanded') === 'true') {
            closeMenu();
            navToggle.focus();
        }
    });
    document.addEventListener('pointerdown', event => {
        if (!event.target.closest('.main-header')) closeMenu();
    });
    navigation.querySelectorAll('details').forEach(group => {
        group.addEventListener('focusout', event => {
            if (!group.contains(event.relatedTarget)) group.open = false;
        });
    });
    navigation.querySelectorAll('a').forEach((link) => {
        if (link.pathname === window.location.pathname) link.setAttribute('aria-current', 'page');
        link.addEventListener('click', closeMenu);
    });
}

// Отправка временно отключает кнопку. Не даём клавиатурному фокусу упасть на body.
const chatPanel = document.querySelector('.support-panel');
chatPanel?.addEventListener('submit', event => {
    if (event.submitter === document.activeElement) chatPanel.querySelector('textarea').focus();
}, true);
// В кабинете тот же чат может открыться по вопросу о конкретном заказе.
let orderOpener;
document.addEventListener('click', event => {
    const button = event.target.closest('[data-order-question]');
    if (button) orderOpener = button;
}, true);
if (chatPanel) new MutationObserver(() => {
    if (chatPanel.hidden && orderOpener) {
        orderOpener.focus();
        orderOpener = null;
    }
}).observe(chatPanel, {attributes: true, attributeFilter: ['hidden']});

// Keep readable captions when an external portrait cannot load.
function productFallback(img) {
    if (!img.matches('.merch-product-image,.product-detail-photo,.product-gallery img')) return;
    const caption = document.createElement('span');
    caption.className = `photo-fallback ${img.className}`;
    caption.textContent = img.alt || 'Фото товара недоступно';
    img.replaceWith(caption);
}
document.querySelectorAll('img').forEach(img => { if (img.complete && !img.naturalWidth) productFallback(img); });
document.addEventListener('error', (event) => {
    if (event.target instanceof HTMLImageElement) productFallback(event.target);
    if (event.target instanceof HTMLImageElement && event.target.closest('.hero-chip')) event.target.hidden = true;
}, true);

// перед важным действием спрашиваем подтверждение
document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== 'post') return;
    const message = form.dataset.confirm;
    if (message && !window.confirm(message)) {
        event.preventDefault();
        return;
    }
    if (event.defaultPrevented) return;
    if (form.dataset.submitting === 'true') {
        event.preventDefault();
        return;
    }
    form.dataset.submitting = 'true';
    form.setAttribute('aria-busy', 'true');
    form.querySelectorAll('button:not([type="button"]), input[type="submit"]').forEach((button) => {
        button.disabled = true;
    });
});

// Back/forward cache restores the page with its previous DOM state.
window.addEventListener('pageshow', () => {
    document.querySelectorAll('form[data-submitting]').forEach((form) => {
        delete form.dataset.submitting;
        form.removeAttribute('aria-busy');
        form.querySelectorAll('button:not([type="button"]), input[type="submit"]').forEach((button) => { button.disabled = false; });
    });
});

// счетчик обновляем только пока вкладка открыта
const notificationLink = document.querySelector('[data-notification-url]');
if (notificationLink) {
    const update = async () => {
        if (document.hidden) return;
        try {
            const response = await fetch(notificationLink.dataset.notificationUrl, {headers: {'Accept': 'application/json'}});
            if (response.ok && response.headers.get('content-type')?.includes('application/json')) {
                const data = await response.json();
                notificationLink.querySelector('[data-notification-count]').textContent = data.count;
            }
        } catch { /* повторим при следующем обновлении */ }
    };
    setInterval(update, 30000);
    document.addEventListener('visibilitychange', update);
}
