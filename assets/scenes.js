/* Отчёт «Анализ личности»: тема, вступительная орбита, сцены.
   Финальный кадр каждой сцены уже нарисован сервером. Без JavaScript, при «уменьшить движение»
   и при печати читатель видит готовую картинку; здесь только переключатель темы, скрытие шагов до показа
   и обратный ход по нажатию на рисунок. */
(function () {
  'use strict';
  window.__personalityScenes = true;
  var root = document.documentElement;

  /* ---------- тема: по умолчанию тёмная, выбор хранится в браузере ---------- */
  var toggle = document.getElementById('pa-theme');
  if (toggle) {
    var calm = function () { return window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches; };
    var setTheme = function (dark) {
      root.setAttribute('data-theme', dark ? 'dark' : 'light');
      toggle.setAttribute('aria-checked', String(dark));
    };
    setTheme(root.getAttribute('data-theme') !== 'light');
    toggle.addEventListener('click', function () {
      var dark = root.getAttribute('data-theme') === 'light';
      if (document.startViewTransition && !calm()) {
        document.startViewTransition(function () { setTheme(dark); });
      } else if (!calm()) {
        root.classList.add('pa-theming');
        setTheme(dark);
        setTimeout(function () { root.classList.remove('pa-theming'); }, 600);
      } else {
        setTheme(dark);
      }
      try { localStorage.setItem('pa-theme', dark ? 'dark' : 'light'); } catch (e) { /* без хранилища выбор не запомнится */ }
    });
  }

  /* ---------- вступительная орбита: один раз за визит; тап пропускает, нажатие на орбиту в шапке — заново ---------- */
  var art = document.querySelector('.pa-art');
  var timers = [];
  function clearTimers() { timers.forEach(clearTimeout); timers = []; }
  function finish() {
    clearTimers();
    root.classList.remove('pa-back', 'pa-intro', 'pa-go', 'pa-up');
    document.removeEventListener('pointerdown', finish);
    document.removeEventListener('keydown', finish);
  }
  // координаты центра экрана относительно места орбиты в шапке
  function measure() {
    var prev = art.style.transition;
    art.style.transition = 'none';
    art.style.transform = 'none';
    var box = art.getBoundingClientRect();
    art.style.transform = '';
    void art.offsetWidth;
    art.style.transition = prev;
    var size = Math.min(window.innerWidth * 0.82, window.innerHeight * 0.52, 420);
    root.style.setProperty('--is', String(size / box.width));
    root.style.setProperty('--ix', (window.innerWidth / 2 - (box.left + box.width / 2)) + 'px');
    root.style.setProperty('--iy', (window.innerHeight / 2 - (box.top + box.height / 2)) + 'px');
  }
  function listenSkip() {
    document.addEventListener('pointerdown', finish);
    document.addEventListener('keydown', finish);
  }
  function play() {
    root.classList.add('pa-intro');
    requestAnimationFrame(function () { requestAnimationFrame(function () { root.classList.add('pa-go'); }); });
    timers.push(setTimeout(function () { root.classList.add('pa-up'); }, 3500));
    timers.push(setTimeout(finish, 5200));
  }
  function replayIntro() {
    if (!root.classList.contains('gm') || root.classList.contains('pa-intro') || root.classList.contains('pa-back')) return;
    window.scrollTo(0, 0);
    measure();
    root.classList.add('pa-back');
    timers.push(setTimeout(function () {
      root.classList.add('pa-intro');
      root.classList.remove('pa-back');
      play();
    }, 900));
    // пропуск тапом — со следующего касания, а не с того, которым запустили повтор
    timers.push(setTimeout(listenSkip, 0));
  }
  if (art) {
    art.addEventListener('click', replayIntro);
    window.addEventListener('beforeprint', finish);
  }
  if (root.classList.contains('pa-intro')) {
    if (!art || window.scrollY > 40) {
      finish();
    } else {
      try { sessionStorage.setItem('pa-intro', '1'); } catch (e) { /* без хранилища заставка повторится — не страшно */ }
      measure();
      play();
      listenSkip();
    }
  }

  /* ---------- сцены ---------- */
  if (!root.classList.contains('gm') || !('IntersectionObserver' in window)) return;

  var scenes = Array.prototype.slice.call(document.querySelectorAll('.scene'));
  var easeOut = function (t) { return 1 - Math.pow(1 - t, 3); };

  function count(el) {
    var to = Number(el.getAttribute('data-to'));
    if (!isFinite(to)) return;
    var t0 = null;
    function step(ts) {
      if (t0 === null) t0 = ts;
      var k = Math.min(1, (ts - t0) / 900);
      el.textContent = String(Math.round(to * easeOut(k)));
      if (k < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  function finalCounts(s) {
    Array.prototype.forEach.call(s.querySelectorAll('.cnt'), function (c) { c.textContent = c.getAttribute('data-to'); });
  }
  function start(s) {
    s.classList.add('in');
    Array.prototype.forEach.call(s.querySelectorAll('.cnt'), count);
  }

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      start(e.target);
      io.unobserve(e.target);
    });
  }, { threshold: 0, rootMargin: '0px 0px -15% 0px' });

  /* Нажатие на рисунок: обратный ход (элементы уходят в обратном порядке, быстрее прямого), затем показ заново. */
  function replay(s) {
    if (!s.classList.contains('in')) return;
    s.classList.add('gs-back');
    s.classList.remove('in');
    var again = function () {
      if (!s.classList.contains('gs-back')) return; // печать или повторное нажатие уже всё решили
      s.classList.remove('gs-back');
      requestAnimationFrame(function () { start(s); });
    };
    var running = s.getAnimations ? s.getAnimations({ subtree: true }).filter(function (a) {
      return a.effect && a.effect.getTiming().iterations !== Infinity;
    }) : [];
    if (!running.length) { again(); return; }
    var guard = setTimeout(again, 3000);
    Promise.all(running.map(function (a) { return a.finished.catch(function () {}); })).then(function () {
      clearTimeout(guard);
      again();
    });
  }

  var interactive = 'a, button, summary, details, input, select, textarea, [tabindex]';
  scenes.forEach(function (s) {
    io.observe(s);
    /* Видимой кнопки нет: она остаётся для клавиатуры и экранных читалок. */
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'replay';
    button.textContent = 'Повторить';
    button.addEventListener('click', function (event) { event.stopPropagation(); replay(s); });
    var caption = s.querySelector(':scope > figcaption');
    s.insertBefore(button, caption || null);
    s.addEventListener('click', function (event) {
      if (event.target.closest(interactive)) return;
      var selection = window.getSelection && window.getSelection();
      if (selection && String(selection).length) return;
      replay(s);
    });
  });

  window.addEventListener('beforeprint', function () {
    scenes.forEach(function (s) { s.classList.remove('gs-back'); s.classList.add('in'); finalCounts(s); });
  });
})();
