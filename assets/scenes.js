/* Сцены отчёта «Личная карта»: появление по прокрутке и повтор.
   Финальный кадр каждой сцены уже нарисован сервером. Без JavaScript, при «уменьшить движение»
   и при печати читатель видит готовую картинку; здесь только скрытие шагов до показа и повтор. */
(function () {
  'use strict';
  window.__personalityScenes = true;
  var root = document.documentElement;
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

  function replay(s) {
    if (!s.classList.contains('in')) return;
    s.classList.add('reset');
    s.classList.remove('in');
    void s.offsetWidth;
    s.classList.remove('reset');
    requestAnimationFrame(function () { start(s); });
  }

  var interactive = 'a, button, summary, details, input, select, textarea, [tabindex]';
  scenes.forEach(function (s) {
    io.observe(s);
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'replay';
    button.textContent = 'Повторить';
    button.setAttribute('aria-label', 'Повторить анимацию рисунка');
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
    scenes.forEach(function (s) { s.classList.add('in'); finalCounts(s); });
  });
})();
