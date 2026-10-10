(function () {
  const button = document.querySelector('[data-menu-button]');
  const nav = document.querySelector('[data-mobile-nav]');
  if (!button || !nav) return;

  const icon = button.querySelector('.material-symbols-rounded');
  const close = () => {
    button.setAttribute('aria-expanded', 'false');
    nav.dataset.open = 'false';
    document.body.classList.remove('menu-open');
    if (icon) icon.textContent = 'menu';
  };

  button.addEventListener('click', () => {
    const opening = button.getAttribute('aria-expanded') !== 'true';
    button.setAttribute('aria-expanded', String(opening));
    nav.dataset.open = String(opening);
    document.body.classList.toggle('menu-open', opening);
    if (icon) icon.textContent = opening ? 'close' : 'menu';
  });

  nav.addEventListener('click', (event) => {
    if (event.target.closest('a')) close();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') {
      close();
      button.focus();
    }
  });

  window.addEventListener('resize', () => {
    if (window.innerWidth >= 720) close();
  });
})();
