document.addEventListener("DOMContentLoaded", function () {
    // --- Preloader ---
    const preloader = document.querySelector('.preloader');
    if (preloader) {
        window.addEventListener('load', function () {
            // Hide preloader after a slight delay for a smoother transition
            setTimeout(function () {
                preloader.classList.add('hidden');
            }, 500);
        });
    }

    // --- Navbar scroll effect ---
    const navbar = document.getElementById("mainNavbar");

    window.addEventListener("scroll", function () {
        if (window.scrollY > 50) {
            navbar.classList.add("navbar-scrolled");
        } else {
            navbar.classList.remove("navbar-scrolled");
        }
    });

    // --- Back to top button ---
    const backToTopButton = document.getElementById("backToTop");

    window.addEventListener("scroll", function () {
        if (window.scrollY > 300) {
            backToTopButton.classList.add("show");
        } else {
            backToTopButton.classList.remove("show");
        }
    });

    backToTopButton.addEventListener("click", function (e) {
        e.preventDefault();
        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });
    });

    // --- Skip to main content accessibility focus management ---
    const skipLink = document.querySelector('.sr-only-focusable');
    if (skipLink) {
        skipLink.addEventListener('click', function (e) {
            e.preventDefault();
            const mainContent = document.getElementById('main-content');
            if (mainContent) {
                // Setting tabindex="-1" makes the element focusable, and .focus() moves focus to it.
                mainContent.setAttribute('tabindex', '-1');
                mainContent.focus();
            }
        });
    }
});