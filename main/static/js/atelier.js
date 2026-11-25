(() => {
    // Дополнительный модуль для разметки со скульптурой и переключателями атмосферы.
    // В текущем base.html подключён effects.js; этот файл автоматически не запускается.
    'use strict';
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    const root = document.documentElement;
    const panel = document.querySelector('.atmosphere');
    const switches = [...document.querySelectorAll('[data-mood]')];
    const moods = ['copper', 'olive', 'wine'];
    const animations = new Set();
    const track = (animation) => {
        animations.add(animation);
        animation.finished.finally(() => animations.delete(animation)).catch(() => {});
        return animation;
    };
    const setMood = (mood) => {
        // Принимаем только известные темы и обновляем доступное состояние кнопок.
        if (!moods.includes(mood)) return;
        root.dataset.mood = mood;
        switches.forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.mood === mood)));
        try { localStorage.setItem('vetmo-atmosphere', mood); } catch { /* Приватный режим не мешает переключению. */ }
    };
    // Хранилище запоминает выбор; его недоступность не мешает работе интерфейса.
    try { setMood(localStorage.getItem('vetmo-atmosphere') || 'copper'); } catch { setMood('copper'); }
    switches.forEach((button) => button.addEventListener('click', () => setMood(button.dataset.mood)));
    if (panel) panel.hidden = false;

    const scene = document.querySelector('.sculpture-scene');
    const core = document.querySelector('.sculpture-core');
    const trigger = document.querySelector('.scene-trigger');
    let spinning = false;
    if (trigger && Element.prototype.animate) {
        // Показываем кнопку только при наличии разметки и поддержки Web Animations.
        trigger.hidden = false;
        trigger.addEventListener('click', () => {
            const current = moods.indexOf(root.dataset.mood);
            setMood(moods[(current + 1) % moods.length]);
            if (reduced.matches || spinning || !core || !scene) return;
            spinning = true;
            const spin = track(core.animate([
                { transform: 'rotateX(-8deg) rotateY(-18deg) rotateZ(-12deg) scale(1)' },
                { transform: 'rotateX(90deg) rotateY(160deg) rotateZ(25deg) scale(1.15)', offset: 0.45 },
                { transform: 'rotateX(352deg) rotateY(342deg) rotateZ(348deg) scale(1)' },
            ], { duration: 1700, easing: 'cubic-bezier(0.2, 0.7, 0.25, 1)' }));
            spin.finished.finally(() => { spinning = false; }).catch(() => {});
            for (let i = 0; i < 3; i += 1) {
                // Кольца стартуют с задержкой и удаляются после завершения анимации.
                const wave = document.createElement('span');
                wave.className = 'scene-shockwave';
                wave.setAttribute('aria-hidden', 'true');
                scene.append(wave);
                const burst = track(wave.animate([
                    { transform: 'scale(0.5)', opacity: 0 },
                    { opacity: 0.6, offset: 0.15 },
                    { transform: 'scale(2.6)', opacity: 0 },
                ], { duration: 1400, delay: i * 160, easing: 'ease-out', fill: 'backwards' }));
                burst.finished.finally(() => wave.remove()).catch(() => {});
            }
        });
    }
    // Останавливаем декоративные циклы, когда вкладка не видна.
    const loops = document.querySelectorAll('.sculpture-core, .sculpture-orbit, .scene-star, .ticker-track, .ambient-orb');
    document.addEventListener('visibilitychange', () => {
        loops.forEach((element) => { element.style.animationPlayState = document.hidden ? 'paused' : ''; });
    });
    reduced.addEventListener('change', () => {
        if (reduced.matches) animations.forEach((animation) => animation.cancel());
    });
})();
