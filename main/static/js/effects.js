(() => {
    // Замыкание изолирует служебные переменные от глобального window.
    'use strict';

    // Системное уменьшение движения и наличие мыши определяют доступные эффекты.
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
    const header = document.querySelector('.main-header');
    const progress = document.querySelector('.scroll-progress');
    const topButton = document.querySelector('.back-to-top');
    const runningAnimations = new Set();
    const scene = document.querySelector('.ambient-scene');
    const scrollHeadings = document.querySelectorAll('.section-heading');
    const trackAnimation = (animation) => {
        // Реестр позволяет остановить Web Animations при смене настроек доступности.
        runningAnimations.add(animation);
        animation.finished.finally(() => runningAnimations.delete(animation)).catch(() => {});
        return animation;
    };

    let logoClicks = 0;
    // Каждый десятый клик по логотипу запускает старую декоративную пасхалку.
    // Отдельный счётчик нужен, чтобы новая игра запускалась ровно на 30-м клике.
    let runnerClicks = 0;
    let secretPlaying = false;
    let runnerPlaying = false;
    const playLogoSecret = () => {
        secretPlaying = true;
        const overlay = document.createElement('div');
        overlay.className = 'noir-secret';
        overlay.setAttribute('role', 'status');
        overlay.setAttribute('aria-live', 'polite');
        const ring = document.createElement('span');
        ring.className = 'noir-secret-ring';
        ring.setAttribute('aria-hidden', 'true');
        const title = document.createElement('span');
        title.className = 'noir-secret-title';
        title.textContent = 'vetmo';
        const caption = document.createElement('span');
        caption.className = 'noir-secret-caption';
        caption.textContent = 'Секретный бафф гильдии открыт. GG WP.';
        overlay.append(ring, title, caption);
        document.body.append(overlay);
        let timeout;
        const cleanup = () => {
            window.clearTimeout(timeout);
            overlay.remove();
            secretPlaying = false;
        };
        // Резервная очистка также работает без Web Animations.
        timeout = window.setTimeout(cleanup, 3000);
        if (motion.matches || !Element.prototype.animate) return;
        const animation = trackAnimation(overlay.animate([
            { opacity: 0 },
            { opacity: 1, offset: 0.15 },
            { opacity: 1, offset: 0.78 },
            { opacity: 0 },
        ], { duration: 2600, easing: 'ease-in-out' }));
        animation.finished.finally(cleanup).catch(() => {});
    };

    // Мини-игра-раннер: логотип перепрыгивает препятствия, как герой Google Dinosaur.
    const playLogoRunner = () => {
        if (runnerPlaying) return;
        runnerPlaying = true;

        const overlay = document.createElement('div');
        overlay.className = 'vetmo-runner';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.setAttribute('aria-label', 'Мини-игра vetmo runner');
        // Сохраняем фокус и прокрутку, чтобы после закрытия вернуть пользователя на сайт.
        const previousFocus = document.activeElement;
        const previousOverflow = document.body.style.overflow;
        const backgroundElements = [...document.body.children];
        const inertStates = backgroundElements.map((element) => element.inert);
        backgroundElements.forEach((element) => { element.inert = true; });
        document.body.style.overflow = 'hidden';

        const top = document.createElement('div');
        top.className = 'vetmo-runner-top';
        const title = document.createElement('strong');
        title.textContent = 'VETMO RUNNER';
        const score = document.createElement('span');
        score.className = 'vetmo-runner-score';
        score.textContent = '00000';
        const close = document.createElement('button');
        close.className = 'vetmo-runner-close';
        close.type = 'button';
        close.textContent = '×';
        close.setAttribute('aria-label', 'Закрыть мини-игру');
        top.append(title, score, close);

        const stage = document.createElement('div');
        stage.className = 'vetmo-runner-stage';
        const hint = document.createElement('p');
        hint.className = 'vetmo-runner-hint';
        hint.textContent = 'SPACE / ↑ / КЛИК — прыжок · ESC — выйти';
        const player = document.createElement('div');
        player.className = 'vetmo-runner-player';
        const sourceLogo = document.querySelector('.brand-image');
        if (sourceLogo) {
            const image = sourceLogo.cloneNode(true);
            image.alt = '';
            player.append(image);
        } else {
            player.textContent = 'V';
        }
        const ground = document.createElement('div');
        ground.className = 'vetmo-runner-ground';
        stage.append(hint, player, ground);
        overlay.append(top, stage);
        document.body.append(overlay);
        close.focus();

        let frame = 0;
        let lastTime = performance.now();
        let obstacleTimer = 0;
        let scoreValue = 0;
        let speed = 0.32;
        let playerY = 0;
        let playerVelocity = 0;
        let jumping = false;
        let gameOver = false;
        const obstacles = new Set();
        const gravity = 0.00165;
        const jumpVelocity = 0.72;

        const finish = () => {
            if (frame) window.cancelAnimationFrame(frame);
            document.removeEventListener('keydown', onKeyDown);
            overlay.removeEventListener('pointerdown', onStagePointerDown);
            close.removeEventListener('click', finish);
            document.removeEventListener('visibilitychange', pauseWhenHidden);
            window.removeEventListener('blur', pauseWhenHidden);
            window.removeEventListener('focus', resume);
            backgroundElements.forEach((element, index) => { element.inert = inertStates[index]; });
            document.body.style.overflow = previousOverflow;
            runnerPlaying = false;
            overlay.remove();
            previousFocus?.focus();
        };

        const jump = () => {
            if (gameOver) return;
            if (!jumping) {
                playerVelocity = jumpVelocity;
                jumping = true;
            }
        };

        const restart = () => {
            paused = false;
            gameOver = false;
            scoreValue = 0;
            speed = 0.32;
            playerY = 0;
            playerVelocity = 0;
            jumping = false;
            obstacleTimer = 0;
            nextObstacle = 1100;
            player.style.transform = 'translateY(0)';
            score.textContent = '00000';
            hint.textContent = 'SPACE / ↑ / КЛИК — прыжок · ESC — выйти';
            overlay.querySelector('.vetmo-runner-restart')?.remove();
            obstacles.forEach((obstacle) => obstacle.remove());
            obstacles.clear();
            lastTime = performance.now();
            frame = window.requestAnimationFrame(tick);
        };

        const endGame = () => {
            if (gameOver) return;
            gameOver = true;
            hint.textContent = `Игра окончена · счёт ${String(Math.floor(scoreValue)).padStart(5, '0')}`;
            const restartButton = document.createElement('button');
            restartButton.className = 'vetmo-runner-restart';
            restartButton.type = 'button';
            restartButton.textContent = 'Играть снова';
            restartButton.addEventListener('click', restart, { once: true });
            stage.append(restartButton);
            restartButton.focus();
        };

        const addObstacle = () => {
            if (gameOver) return;
            const obstacle = document.createElement('span');
            obstacle.className = 'vetmo-runner-obstacle';
            obstacle.style.height = `${28 + Math.random() * 24}px`;
            obstacle.style.setProperty('--obstacle-width', `${14 + Math.random() * 10}px`);
            // Движение измеряется в пикселях сцены, одинаково на телефоне и мониторе.
            obstacle.dataset.x = String(stage.clientWidth + 24);
            obstacle.style.transform = `translateX(${obstacle.dataset.x}px)`;
            stage.append(obstacle);
            obstacles.add(obstacle);
        };

        const onKeyDown = (event) => {
            if (event.key === 'Tab') {
                // Фокус остаётся между кнопками открытого диалога.
                const buttons = [...overlay.querySelectorAll('button')];
                const index = buttons.indexOf(document.activeElement);
                const next = (index + (event.shiftKey ? -1 : 1) + buttons.length) % buttons.length;
                event.preventDefault();
                buttons[next].focus();
                return;
            }
            if (event.key === 'Escape') {
                finish();
                return;
            }
            if (event.code === 'Space' || event.key === 'ArrowUp') {
                if (event.target === close || event.target.closest('.vetmo-runner-restart')) return;
                event.preventDefault();
                if (event.repeat) return;
                if (gameOver) restart();
                else jump();
            }
        };
        const onStagePointerDown = (event) => {
            if (event.target.closest('button')) return;
            if (gameOver) restart();
            else jump();
        };

        // Один случайный интервал на препятствие; не пересчитываем его каждый кадр.
        let nextObstacle = 1100;
        let paused = false;
        const pauseWhenHidden = () => {
            paused = true;
            window.cancelAnimationFrame(frame);
            frame = 0;
            if (!gameOver) hint.textContent = 'ПАУЗА · вернись в окно, чтобы продолжить';
            if (!document.hidden && document.hasFocus()) resume();
        };
        const resume = () => {
            if (!paused || document.hidden || gameOver) return;
            paused = false;
            lastTime = performance.now();
            hint.textContent = 'SPACE / ↑ / КЛИК — прыжок · ESC — выйти';
            frame = window.requestAnimationFrame(tick);
        };
        const tick = (time) => {
            frame = 0;
            if (gameOver) return;
            // Ограничение шага исключает резкий скачок физики после задержки кадра.
            const delta = Math.min(32, time - lastTime);
            lastTime = time;
            obstacleTimer += delta;
            scoreValue += delta * 0.012;
            speed = Math.min(0.58, speed + delta * 0.000002);
            score.textContent = String(Math.floor(scoreValue)).padStart(5, '0');

            if (obstacleTimer > nextObstacle) {
                obstacleTimer = 0;
                nextObstacle = 1150 + Math.random() * 550;
                addObstacle();
            }
            if (jumping) {
                playerY += playerVelocity * delta;
                playerVelocity -= gravity * delta;
                if (playerY <= 0) {
                    playerY = 0;
                    playerVelocity = 0;
                    jumping = false;
                }
            }
            player.style.transform = `translateY(${-playerY}px)`;
            const playerRect = player.getBoundingClientRect();
            obstacles.forEach((obstacle) => {
                const x = Number(obstacle.dataset.x) - speed * delta;
                obstacle.dataset.x = String(x);
                obstacle.style.transform = `translateX(${x}px)`;
                if (x < -40) {
                    obstacle.remove();
                    obstacles.delete(obstacle);
                    return;
                }
                const obstacleRect = obstacle.getBoundingClientRect();
                if (playerRect.left < obstacleRect.right - 4 && playerRect.right > obstacleRect.left + 4
                    && playerRect.top < obstacleRect.bottom && playerRect.bottom > obstacleRect.top + 4) {
                    endGame();
                }
            });
            if (!gameOver) frame = window.requestAnimationFrame(tick);
        };

        close.addEventListener('click', finish);
        document.addEventListener('keydown', onKeyDown);
        overlay.addEventListener('pointerdown', onStagePointerDown);
        document.addEventListener('visibilitychange', pauseWhenHidden);
        window.addEventListener('blur', pauseWhenHidden);
        window.addEventListener('focus', resume);
        frame = window.requestAnimationFrame(tick);
    };

    document.querySelectorAll('.logo-play').forEach((logo) => {
        // Повторный клик отменяет предыдущий поворот, не накапливая анимации.
        let spin;
        logo.addEventListener('click', () => {
            if (secretPlaying || runnerPlaying) return;
            logoClicks += 1;
            runnerClicks += 1;
            if (runnerClicks === 30) {
                // На 30-м клике игра имеет приоритет; старый эффект остаётся на 10-м и 20-м.
                runnerClicks = 0;
                logoClicks = 0;
                spin?.cancel();
                playLogoRunner();
                return;
            }
            if (logoClicks === 10) {
                logoClicks = 0;
                spin?.cancel();
                playLogoSecret();
                return;
            }
            if (motion.matches || !Element.prototype.animate) return;
            spin?.cancel();
            spin = trackAnimation(logo.animate([
                { transform: 'rotate(0deg) scale(1)' },
                { transform: 'rotate(160deg) scale(1.22)', offset: 0.35 },
                { transform: 'rotate(385deg) scale(0.94)', offset: 0.8 },
                { transform: 'rotate(360deg) scale(1)' },
            ], { duration: 950, easing: 'cubic-bezier(0.2, 0.7, 0.3, 1)' }));
            const rect = logo.getBoundingClientRect();
            for (let i = 0; i < 10; i += 1) {
                const spark = document.createElement('span');
                spark.className = 'logo-spark';
                spark.setAttribute('aria-hidden', 'true');
                spark.style.left = `${rect.left + rect.width / 2}px`;
                spark.style.top = `${rect.top + rect.height / 2}px`;
                spark.style.background = ['#d2d3d7', '#ffffff', '#777b87'][i % 3];
                document.body.append(spark);
                const angle = (i / 10) * Math.PI * 2;
                const radius = 35 + (i % 3) * 12;
                const burst = trackAnimation(spark.animate([
                    { transform: 'translate(-50%, -50%) scale(0.2)', opacity: 1 },
                    { transform: `translate(calc(-50% + ${Math.cos(angle) * radius}px), calc(-50% + ${Math.sin(angle) * radius}px)) rotate(140deg) scale(0)`, opacity: 0 },
                ], { duration: 700, easing: 'ease-out' }));
                burst.finished.finally(() => spark.remove()).catch(() => {});
            }
        });
    });

    // Один кадр на обновление прокрутки, даже при частых событиях.
    let scrollPending = false;
    const updateScroll = () => {
        // Прогресс, фон и заголовки обновляются вместе, максимум один раз за кадр.
        const distance = document.documentElement.scrollHeight - window.innerHeight;
        if (progress) progress.style.transform = `scaleX(${distance > 0 ? Math.min(1, Math.max(0, window.scrollY / distance)) : 0})`;
        header?.classList.toggle('is-scrolled', window.scrollY > 24);
        if (topButton) topButton.hidden = window.scrollY < 450;
        if (scene) {
            const fraction = distance > 0 ? Math.min(1, Math.max(0, window.scrollY / distance)) : 0;
            scene.style.setProperty('--scene-shift', motion.matches ? '0px' : `${fraction * -100}px`);
            scene.style.setProperty('--scene-turn', motion.matches ? '0deg' : `${fraction * 16}deg`);
        }
        scrollHeadings.forEach((heading) => {
            if (motion.matches) {
                heading.style.removeProperty('--scroll-lift');
                return;
            }
            const rect = heading.getBoundingClientRect();
            if (rect.bottom > 0 && rect.top < window.innerHeight) {
                const offset = (rect.top + rect.height / 2 - window.innerHeight / 2) / window.innerHeight;
                heading.style.setProperty('--scroll-lift', `${offset * -22}px`);
            }
        });
        scrollPending = false;
    };
    const queueScroll = () => {
        if (!scrollPending) {
            scrollPending = true;
            window.requestAnimationFrame(updateScroll);
        }
    };
    window.addEventListener('scroll', queueScroll, { passive: true });
    window.addEventListener('resize', queueScroll, { passive: true });
    // Высота документа меняется и после загрузки изображений или шрифтов.
    if ('ResizeObserver' in window) new ResizeObserver(queueScroll).observe(document.body);
    updateScroll();
    topButton?.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: motion.matches ? 'instant' : 'smooth' });
    });

    // Web Animations не прячут контент при отключённом или неподдерживаемом JS.
    const revealTargets = document.querySelectorAll('.hero-content, .page-heading, .section-heading, .feature-card, .empty-state, .data-form, .result-card');
    let revealObserver;
    if ('IntersectionObserver' in window && Element.prototype.animate && !motion.matches) {
        revealObserver = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                revealObserver.unobserve(entry.target);
                if (motion.matches) return;
                const siblings = entry.target.parentElement.children;
                const index = Array.prototype.indexOf.call(siblings, entry.target);
                const animation = entry.target.animate([
                    { opacity: 0, translate: '0 24px' },
                    { opacity: 1, translate: '0 0' },
                ], { duration: 650, delay: Math.min(index * 80, 240), easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)', fill: 'backwards' });
                runningAnimations.add(animation);
                animation.finished.then(() => runningAnimations.delete(animation)).catch(() => runningAnimations.delete(animation));
            });
        }, { threshold: 0.08 });
        revealTargets.forEach((element) => revealObserver.observe(element));
    }

    let activeCard = null;
    // Отслеживается одна карточка; CSS-переменные управляют наклоном и бликом.
    let pointerFrame = 0;
    let pointerX = 0;
    let pointerY = 0;
    const resetCard = () => {
        if (!activeCard) return;
        activeCard.classList.remove('is-hovered');
        ['--tilt-x', '--tilt-y', '--shine-x', '--shine-y'].forEach((name) => activeCard.style.removeProperty(name));
        activeCard = null;
    };
    document.querySelectorAll('.feature-card').forEach((card) => {
        card.addEventListener('pointermove', (event) => {
            if (motion.matches || !finePointer.matches) return;
            if (activeCard !== card) {
                resetCard();
                activeCard = card;
                card.classList.add('is-hovered');
            }
            pointerX = event.clientX;
            pointerY = event.clientY;
            if (pointerFrame) return;
            pointerFrame = window.requestAnimationFrame(() => {
                pointerFrame = 0;
                if (!activeCard) return;
                const rect = activeCard.getBoundingClientRect();
                // Координаты приводятся к диапазону 0..1 и ограничиваются у краёв.
                const x = Math.min(1, Math.max(0, (pointerX - rect.left) / rect.width));
                const y = Math.min(1, Math.max(0, (pointerY - rect.top) / rect.height));
                activeCard.style.setProperty('--tilt-x', `${(0.5 - y) * 7}deg`);
                activeCard.style.setProperty('--tilt-y', `${(x - 0.5) * 7}deg`);
                activeCard.style.setProperty('--shine-x', `${x * 100}%`);
                activeCard.style.setProperty('--shine-y', `${y * 100}%`);
            });
        });
        card.addEventListener('pointerleave', resetCard);
        card.addEventListener('pointercancel', resetCard);
    });

    // Фото и его содержимое используют одни смещения с разными коэффициентами:
    // CSS создаёт два слоя глубины без изменения размеров блока в раскладке.
    const hero = document.querySelector('.sport-hero');
    const art = document.querySelector('.hero-photo');
    let heroFrame = 0;
    let heroEvent;
    const resetArt = () => {
        if (heroFrame) window.cancelAnimationFrame(heroFrame);
        heroFrame = 0;
        art?.style.removeProperty('--parallax-x');
        art?.style.removeProperty('--parallax-y');
    };
    hero?.addEventListener('pointermove', (event) => {
        if (motion.matches || !finePointer.matches || !art) return;
        heroEvent = event;
        if (heroFrame) return;
        heroFrame = window.requestAnimationFrame(() => {
            heroFrame = 0;
            const rect = hero.getBoundingClientRect();
            art.style.setProperty('--parallax-x', `${((heroEvent.clientX - rect.left) / rect.width - 0.5) * 16}px`);
            art.style.setProperty('--parallax-y', `${((heroEvent.clientY - rect.top) / rect.height - 0.5) * 12}px`);
        });
    });
    hero?.addEventListener('pointerleave', resetArt);

    // Курсор слегка сдвигает атмосферные пятна — эффект остаётся почти незаметным.
    const ambientScene = document.querySelector('.ambient-scene');
    let ambientFrame = 0;
    let ambientEvent;
    const resetAmbient = () => {
        if (ambientFrame) window.cancelAnimationFrame(ambientFrame);
        ambientFrame = 0;
        ambientScene?.style.setProperty('--cursor-x', '0px');
        ambientScene?.style.setProperty('--cursor-y', '0px');
    };
    document.addEventListener('pointermove', (event) => {
        if (motion.matches || !finePointer.matches || !ambientScene) return;
        ambientEvent = event;
        if (ambientFrame) return;
        ambientFrame = window.requestAnimationFrame(() => {
            ambientFrame = 0;
            ambientScene.style.setProperty('--cursor-x', `${(ambientEvent.clientX / window.innerWidth - 0.5) * 18}px`);
            ambientScene.style.setProperty('--cursor-y', `${(ambientEvent.clientY / window.innerHeight - 0.5) * 14}px`);
        });
    }, { passive: true });
    document.addEventListener('pointerleave', resetAmbient);
    const resetPointerEffects = () => {
        // Убираем застывшие смещения после потери фокуса или отключения мыши.
        resetCard();
        resetArt();
        resetAmbient();
    };
    window.addEventListener('blur', resetPointerEffects);
    finePointer.addEventListener('change', resetPointerEffects);

    document.querySelectorAll('.button-primary, .header-button').forEach((button) => {
        // Волна идёт от клика мыши, а при активации клавиатурой — из центра.
        button.addEventListener('click', (event) => {
            if (motion.matches) return;
            const rect = button.getBoundingClientRect();
            const ripple = document.createElement('span');
            ripple.className = 'click-ripple';
            ripple.setAttribute('aria-hidden', 'true');
            ripple.style.setProperty('--ripple-size', `${Math.max(rect.width, rect.height) * 2}px`);
            ripple.style.setProperty('--ripple-x', `${event.detail ? event.clientX - rect.left : rect.width / 2}px`);
            ripple.style.setProperty('--ripple-y', `${event.detail ? event.clientY - rect.top : rect.height / 2}px`);
            button.append(ripple);
            window.setTimeout(() => ripple.remove(), 700);
        });
    });

    motion.addEventListener('change', () => {
        // Новая настройка доступности применяется без перезагрузки страницы.
        if (!motion.matches) return;
        resetCard();
        resetArt();
        resetAmbient();
        revealObserver?.disconnect();
        runningAnimations.forEach((animation) => animation.cancel());
        queueScroll();
        document.querySelectorAll('.click-ripple').forEach((element) => element.remove());
    });
})();
