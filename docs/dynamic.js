document.querySelectorAll('pre[data-copy]').forEach(pre => {
    const btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.textContent = 'copy';
    btn.addEventListener('click', () => {
        const code = pre.querySelector('code').innerText;
        navigator.clipboard.writeText(code).then(() => {
            btn.textContent = 'Copied!';
            setTimeout(() => btn.textContent = 'Copy', 1500);
        });
    });
    pre.appendChild(btn);
});
document.querySelectorAll('#top-bar a').forEach(a => {
    a.addEventListener('click', e => {
        e.preventDefault();
        const target = document.querySelector(a.getAttribute('href'));
        target.scrollIntoView({behavior:'smooth'});
        const elementPosition = target.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - 100;
        window.scrollTo({
            top: offsetPosition,
            behavior: "smooth"
        });
    });
});
document.querySelectorAll('.drop-btn').forEach(btn => {
    btn.addEventListener('click', e => {
        e.preventDefault();                 // keep #docs from scrolling
        const menu = btn.nextElementSibling;
        menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
    });
    document.addEventListener('click', e => {
        if (!btn.closest('.dropdown').contains(e.target)) {
            btn.nextElementSibling.style.display = 'none';
        }
    });
});
