/**
 * UpScrolled Video Downloader - Navigation Component
 * Injects navbar and footer into all pages
 */

(function() {
    'use strict';

    // Navbar HTML
    const navbarHTML = `
        <div class="container">
            <a href="/" class="navbar-logo">UpScrolled Downloader</a>
            <button class="navbar-toggle" aria-label="Toggle navigation" aria-expanded="false">
                <span></span>
                <span></span>
                <span></span>
            </button>
            <ul class="navbar-links">
                <li><a href="/">Home</a></li>
                <li><a href="how-it-works.html">How It Works</a></li>
                <li><a href="about.html">About</a></li>
                <li><a href="contact.html">Contact</a></li>
            </ul>
        </div>
    `;

    // Footer HTML
    const footerHTML = `
        <div class="container">
            <ul class="footer-links">
                <li><a href="terms.html">Terms of Service</a></li>
                <li><a href="privacy.html">Privacy Policy</a></li>
                <li><a href="dmca.html">DMCA</a></li>
                <li><a href="contact.html">Contact</a></li>
            </ul>
            <p class="footer-text">© 2026 UpScrolled Video Downloader — Not affiliated with UpScrolled</p>
        </div>
    `;

    // Inject navbar
    const navbar = document.getElementById('navbar');
    if (navbar) {
        navbar.innerHTML = navbarHTML;
        
        // Mobile menu toggle
        const toggle = navbar.querySelector('.navbar-toggle');
        const links = navbar.querySelector('.navbar-links');
        
        if (toggle && links) {
            toggle.addEventListener('click', function() {
                const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
                toggle.setAttribute('aria-expanded', !isExpanded);
                links.classList.toggle('active');
            });

            // Close menu when clicking a link
            links.querySelectorAll('a').forEach(link => {
                link.addEventListener('click', function() {
                    links.classList.remove('active');
                    toggle.setAttribute('aria-expanded', 'false');
                });
            });

            // Close menu when clicking outside
            document.addEventListener('click', function(e) {
                if (!navbar.contains(e.target)) {
                    links.classList.remove('active');
                    toggle.setAttribute('aria-expanded', 'false');
                }
            });
        }
    }

    // Inject footer
    const footer = document.getElementById('footer');
    if (footer) {
        footer.innerHTML = footerHTML;
    }

    // Highlight current page in nav
    const currentPage = window.location.pathname.split('/').pop() || 'index.html';
    const navLinks = document.querySelectorAll('.navbar-links a');
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (href === currentPage || (href === '/' && currentPage === 'index.html')) {
            link.style.opacity = '0.6';
        }
    });

})();
