/**
 * Script de performance optimisé
 * Gestion du lazy loading, des animations et des optimisations
 */

// Configuration des performances
const PERFORMANCE_CONFIG = {
    lazyLoadThreshold: 0.1,
    animationThreshold: 0.15,
    debounceDelay: 150,
    throttleDelay: 100
};

// Classe pour la gestion des performances
class PerformanceManager {
    constructor() {
        this.observers = new Map();
        this.debounceTimers = new Map();
        this.throttleTimers = new Map();
        this.init();
    }

    init() {
        this.setupLazyLoading();
        this.setupScrollAnimations();
        this.setupIntersectionObserver();
        this.setupPerformanceMonitoring();
        this.optimizeImages();
        this.setupServiceWorker();
    }

    // Lazy loading des images
    setupLazyLoading() {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.classList.remove('lazy');
                        imageObserver.unobserve(img);
                    }
                });
            }, { threshold: PERFORMANCE_CONFIG.lazyLoadThreshold });

            document.querySelectorAll('img[data-src]').forEach(img => {
                imageObserver.observe(img);
            });
        }
    }

    // Animations au scroll optimisées
    setupScrollAnimations() {
        const animatedElements = document.querySelectorAll('[data-animate]');
        
        if (animatedElements.length === 0) return;

        const animationObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const element = entry.target;
                    const animation = element.dataset.animate;
                    
                    element.classList.add('animate', animation);
                    animationObserver.unobserve(element);
                }
            });
        }, { threshold: PERFORMANCE_CONFIG.animationThreshold });

        animatedElements.forEach(el => animationObserver.observe(el));
    }

    // Observer d'intersection pour les animations
    setupIntersectionObserver() {
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('revealed');
                }
            });
        }, observerOptions);

        document.querySelectorAll('.scroll-reveal').forEach(el => {
            observer.observe(el);
        });
    }

    // Optimisation des images
    optimizeImages() {
        // Préchargement des images critiques
        const criticalImages = [
            '/static/images/hero.png',
            '/static/images/logo.png'
        ];

        criticalImages.forEach(src => {
            const link = document.createElement('link');
            link.rel = 'preload';
            link.as = 'image';
            link.href = src;
            document.head.appendChild(link);
        });

        // Optimisation des images avec WebP
        if (this.supportsWebP()) {
            document.querySelectorAll('img[data-webp]').forEach(img => {
                img.src = img.dataset.webp;
            });
        }
    }

    // Support WebP
    supportsWebP() {
        const canvas = document.createElement('canvas');
        canvas.width = 1;
        canvas.height = 1;
        return canvas.toDataURL('image/webp').indexOf('data:image/webp') === 0;
    }

    // Monitoring des performances
    setupPerformanceMonitoring() {
        if ('performance' in window) {
            window.addEventListener('load', () => {
                setTimeout(() => {
                    this.logPerformanceMetrics();
                }, 0);
            });
        }
    }

    // Log des métriques de performance
    logPerformanceMetrics() {
        const navigation = performance.getEntriesByType('navigation')[0];
        const paint = performance.getEntriesByType('paint');
        
        const metrics = {
            loadTime: navigation.loadEventEnd - navigation.loadEventStart,
            domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
            firstPaint: paint.find(p => p.name === 'first-paint')?.startTime,
            firstContentfulPaint: paint.find(p => p.name === 'first-contentful-paint')?.startTime
        };

        console.log('Performance Metrics:', metrics);
    }

    // Service Worker pour le cache
    setupServiceWorker() {
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/static/js/sw.js')
                    .then(registration => {
                        console.log('SW registered:', registration);
                    })
                    .catch(error => {
                        console.log('SW registration failed:', error);
                    });
            });
        }
    }

    // Debounce optimisé
    debounce(func, key) {
        if (this.debounceTimers.has(key)) {
            clearTimeout(this.debounceTimers.get(key));
        }
        
        const timer = setTimeout(() => {
            func();
            this.debounceTimers.delete(key);
        }, PERFORMANCE_CONFIG.debounceDelay);
        
        this.debounceTimers.set(key, timer);
    }

    // Throttle optimisé
    throttle(func, key) {
        if (this.throttleTimers.has(key)) {
            return;
        }
        
        func();
        this.throttleTimers.set(key, true);
        
        setTimeout(() => {
            this.throttleTimers.delete(key);
        }, PERFORMANCE_CONFIG.throttleDelay);
    }
}

// Classe pour les animations optimisées
class AnimationManager {
    constructor() {
        this.animations = new Map();
        this.init();
    }

    init() {
        this.setupCounterAnimations();
        this.setupParallaxEffects();
        this.setupSmoothScrolling();
    }

    // Animations des compteurs
    setupCounterAnimations() {
        const counters = document.querySelectorAll('[data-counter]');
        
        const counterObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.animateCounter(entry.target);
                    counterObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });

        counters.forEach(counter => counterObserver.observe(counter));
    }

    // Animation d'un compteur
    animateCounter(element) {
        const target = parseInt(element.dataset.counter);
        const duration = 2000;
        const step = target / (duration / 16);
        let current = 0;

        const timer = setInterval(() => {
            current += step;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            element.textContent = Math.floor(current);
        }, 16);
    }

    // Effets parallax optimisés
    setupParallaxEffects() {
        const parallaxElements = document.querySelectorAll('[data-parallax]');
        
        if (parallaxElements.length === 0) return;

        let ticking = false;

        const updateParallax = () => {
            const scrolled = window.pageYOffset;
            
            parallaxElements.forEach(element => {
                const speed = element.dataset.parallax || 0.5;
                const yPos = -(scrolled * speed);
                element.style.transform = `translateY(${yPos}px)`;
            });
            
            ticking = false;
        };

        const requestTick = () => {
            if (!ticking) {
                requestAnimationFrame(updateParallax);
                ticking = true;
            }
        };

        window.addEventListener('scroll', requestTick, { passive: true });
    }

    // Défilement fluide
    setupSmoothScrolling() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', (e) => {
                e.preventDefault();
                const target = document.querySelector(anchor.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    }
}

// Classe pour la gestion du cache
class CacheManager {
    constructor() {
        this.cache = new Map();
        this.maxSize = 100;
    }

    set(key, value) {
        if (this.cache.size >= this.maxSize) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }
        this.cache.set(key, value);
    }

    get(key) {
        return this.cache.get(key);
    }

    has(key) {
        return this.cache.has(key);
    }

    clear() {
        this.cache.clear();
    }
}

// Initialisation optimisée
document.addEventListener('DOMContentLoaded', () => {
    // Initialisation différée pour améliorer les performances
    requestIdleCallback(() => {
        window.performanceManager = new PerformanceManager();
        window.animationManager = new AnimationManager();
        window.cacheManager = new CacheManager();
    });
});

// Optimisations supplémentaires
if ('requestIdleCallback' in window) {
    // Utilisation de requestIdleCallback pour les tâches non critiques
    requestIdleCallback(() => {
        // Initialisation des composants non critiques
        console.log('Non-critical components initialized');
    });
} else {
    // Fallback pour les navigateurs plus anciens
    setTimeout(() => {
        console.log('Non-critical components initialized (fallback)');
    }, 1000);
}

// Export pour utilisation dans d'autres modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { PerformanceManager, AnimationManager, CacheManager };
}
