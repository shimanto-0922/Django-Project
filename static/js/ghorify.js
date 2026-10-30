// Auto-hide flash messages after a few seconds.
document.querySelectorAll('.gh-toast').forEach((toast, i) => {
  setTimeout(() => {
    toast.style.transition = 'opacity .4s, transform .4s';
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(30px)';
    setTimeout(() => toast.remove(), 400);
  }, 5000 + i * 600);
});

// Ask before destructive actions: <form data-confirm="Are you sure?">
document.addEventListener('submit', (event) => {
  const message = event.target.dataset.confirm;
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});

// Live preview for image file inputs: <input data-preview="#imgId">
document.querySelectorAll('input[type=file][data-preview]').forEach((input) => {
  input.addEventListener('change', () => {
    const target = document.querySelector(input.dataset.preview);
    if (!target || !input.files.length) return;
    target.innerHTML = '';
    Array.from(input.files).slice(0, 10).forEach((file) => {
      const img = document.createElement('img');
      img.src = URL.createObjectURL(file);
      img.className = 'rounded-3 me-2 mb-2';
      img.style.cssText = 'width:96px;height:72px;object-fit:cover';
      target.appendChild(img);
    });
  });
});

// Property gallery lightbox.
const lightbox = document.getElementById('lightbox');
if (lightbox) {
  const img = lightbox.querySelector('img');
  const links = Array.from(document.querySelectorAll('[data-lightbox]'));
  let index = 0;
  const show = (i) => {
    index = (i + links.length) % links.length;
    img.src = links[index].getAttribute('href');
  };
  links.forEach((link, i) => link.addEventListener('click', (e) => {
    e.preventDefault();
    show(i);
    bootstrap.Modal.getOrCreateInstance(lightbox).show();
  }));
  lightbox.querySelector('[data-prev]')?.addEventListener('click', () => show(index - 1));
  lightbox.querySelector('[data-next]')?.addEventListener('click', () => show(index + 1));
  document.addEventListener('keydown', (e) => {
    if (!lightbox.classList.contains('show')) return;
    if (e.key === 'ArrowLeft') show(index - 1);
    if (e.key === 'ArrowRight') show(index + 1);
  });
}
