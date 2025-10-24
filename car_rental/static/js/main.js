document.addEventListener('DOMContentLoaded', function () {
    // Initialize carousel
    var carouselElement = document.getElementById('carCarousel');
    var carousel = new bootstrap.Carousel(carouselElement, {
        interval: 5000,
        wrap: true,
        keyboard: true
    });

    // Pause carousel when mouse enters and resume when mouse leaves
    carouselElement.addEventListener('mouseenter', function () {
        carousel.pause();
    });

    carouselElement.addEventListener('mouseleave', function () {
        carousel.cycle();
    });
});