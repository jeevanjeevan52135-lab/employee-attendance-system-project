(function () {
  var pad = function (n) { return String(n).padStart(2, '0'); };
  var parse = function (s) { return s ? new Date(s.replace(' ', 'T')) : null; };
  var dur = function (ms) {
    var m = Math.max(0, Math.floor(ms / 60000));
    return Math.floor(m / 60) + 'h ' + pad(m % 60) + 'm';
  };

  // theme toggle (initial theme is set in <head>)
  document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('theme', next); } catch (e) {}
    });
  });

  // long dates
  document.querySelectorAll('time[data-format="long"]').forEach(function (el) {
    var d = new Date(el.getAttribute('datetime') + 'T00:00:00');
    if (!isNaN(d)) el.textContent = d.toLocaleDateString(undefined,
      { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  });

  // greeting
  var h = new Date().getHours();
  var hello = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
  document.querySelectorAll('[data-greeting]').forEach(function (el) { el.textContent = hello; });

  var clocks = document.querySelectorAll('[data-live-clock]');
  var dateEl = document.querySelector('[data-live-date]');
  var hero = document.querySelector('[data-hero]');
  var arc = hero && hero.querySelector('[data-arc]');
  var chip = hero && hero.querySelector('[data-chip]');
  var chipText = hero && hero.querySelector('[data-chip-text]');
  var workedEls = document.querySelectorAll('[data-worked]');
  var TARGET = 8 * 3600 * 1000; // 8-hour day goal

  function update() {
    var now = new Date();
    clocks.forEach(function (el) {
      el.textContent = pad(now.getHours()) + ':' + pad(now.getMinutes()) +
        (el.hasAttribute('data-seconds') ? ':' + pad(now.getSeconds()) : '');
    });
    if (dateEl) dateEl.textContent = now.toLocaleDateString(undefined,
      { weekday: 'long', day: 'numeric', month: 'long' });
    if (!hero) return;
    var ci = parse(hero.dataset.in), co = parse(hero.dataset.out);
    if (!ci) return;
    var elapsed = (co || now) - ci;
    arc.style.strokeDashoffset = 100 * (1 - Math.min(elapsed / TARGET, 1));
    arc.style.opacity = elapsed < 60000 ? 0 : 1;
    chip.classList.toggle('live', !co);
    chip.classList.toggle('done', !!co);
    chipText.textContent = co ? 'Day complete' : 'On the clock';
    workedEls.forEach(function (el) { el.textContent = dur(elapsed); });
  }
  update();
  setInterval(update, 1000);
})();
