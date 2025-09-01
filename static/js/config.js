/**
 * Configuration des performances
 * Paramètres optimisés pour le site du Club Municipal de Tennis Chihia
 */

const PERFORMANCE_CONFIG = {
    // Seuils pour les animations
    animationThreshold: 0.15,
    lazyLoadThreshold: 0.1,
    counterThreshold: 0.5,
    
    // Délais pour les optimisations
    debounceDelay: 150,
    throttleDelay: 100,
    animationDelay: 300,
    
    // Configuration du cache
    cacheMaxSize: 100,
    cacheExpiry: 24 * 60 * 60 * 1000, // 24 heures
    
    // Configuration des images
    imageQuality: 0.8,
    imageMaxWidth: 1920,
    imageFormats: ['webp', 'avif', 'jpg'],
    
    // Configuration du Service Worker
    swVersion: '1.0.0',
    swCacheName: 'cmtch-v1.0.0',
    
    // Ressources critiques
    criticalResources: [
        '/static/css/critical.css',
        '/static/js/performance.js',
        '/static/images/hero.png',
        'https://www.cmtch.online/photos/logo.jpg'
    ],
    
    // Ressources à précharger
    preloadResources: [
        '/static/fonts/montserrat.woff2',
        '/static/fonts/montserrat-bold.woff2'
    ],
    
    // Configuration des animations
    animations: {
        duration: 400,
        easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
        stagger: 100
    },
    
    // Configuration du monitoring
    monitoring: {
        enabled: true,
        logLevel: 'info',
        metrics: ['fcp', 'lcp', 'fid', 'cls']
    }
};

// Configuration des breakpoints
const BREAKPOINTS = {
    mobile: 576,
    tablet: 768,
    desktop: 992,
    large: 1200
};

// Configuration des polices
const FONT_CONFIG = {
    primary: 'Montserrat',
    fallback: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    weights: [400, 500, 600, 700, 800],
    display: 'swap'
};

// Configuration des couleurs
const COLOR_CONFIG = {
    primary: '#1e3a8a',
    primaryDark: '#1e40af',
    accent: '#f59e0b',
    accentHover: '#d97706',
    secondary: '#ffffff',
    lightBg: '#f8fafc',
    text: '#1f2937',
    textMuted: '#6b7280'
};

// Configuration des API
const API_CONFIG = {
    baseUrl: '/api',
    timeout: 10000,
    retries: 3,
    cacheTime: 5 * 60 * 1000 // 5 minutes
};

// Configuration des routes
const ROUTE_CONFIG = {
    home: '/',
    articles: '/articles',
    reservations: '/reservations',
    login: '/connexion',
    register: '/inscription',
    admin: {
        members: '/admin/membres',
        reservations: '/admin/reservations',
        articles: '/admin/articles'
    }
};

// Configuration des erreurs
const ERROR_CONFIG = {
    networkTimeout: 'La requête a pris trop de temps',
    networkError: 'Erreur de connexion réseau',
    serverError: 'Erreur du serveur',
    notFound: 'Page non trouvée',
    unauthorized: 'Accès non autorisé'
};

// Configuration des messages
const MESSAGE_CONFIG = {
    loading: 'Chargement...',
    saving: 'Sauvegarde...',
    success: 'Opération réussie',
    error: 'Une erreur est survenue',
    confirm: 'Êtes-vous sûr ?',
    cancel: 'Annuler'
};

// Configuration des validations
const VALIDATION_CONFIG = {
    email: {
        pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
        message: 'Adresse email invalide'
    },
    password: {
        minLength: 8,
        pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/,
        message: 'Le mot de passe doit contenir au moins 8 caractères, une majuscule, une minuscule et un chiffre'
    },
    phone: {
        pattern: /^(\+33|0)[1-9](\d{8})$/,
        message: 'Numéro de téléphone invalide'
    }
};

// Configuration des notifications
const NOTIFICATION_CONFIG = {
    position: 'top-right',
    duration: 5000,
    animation: 'slide',
    types: {
        success: { icon: 'fas fa-check', color: '#10b981' },
        error: { icon: 'fas fa-times', color: '#ef4444' },
        warning: { icon: 'fas fa-exclamation-triangle', color: '#f59e0b' },
        info: { icon: 'fas fa-info-circle', color: '#3b82f6' }
    }
};

// Configuration des graphiques
const CHART_CONFIG = {
    colors: ['#1e3a8a', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6'],
    animation: {
        duration: 1000,
        easing: 'easeOutQuart'
    },
    responsive: true,
    maintainAspectRatio: false
};

// Configuration des exports
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        PERFORMANCE_CONFIG,
        BREAKPOINTS,
        FONT_CONFIG,
        COLOR_CONFIG,
        API_CONFIG,
        ROUTE_CONFIG,
        ERROR_CONFIG,
        MESSAGE_CONFIG,
        VALIDATION_CONFIG,
        NOTIFICATION_CONFIG,
        CHART_CONFIG
    };
}

// Export global pour utilisation dans le navigateur
if (typeof window !== 'undefined') {
    window.CONFIG = {
        PERFORMANCE_CONFIG,
        BREAKPOINTS,
        FONT_CONFIG,
        COLOR_CONFIG,
        API_CONFIG,
        ROUTE_CONFIG,
        ERROR_CONFIG,
        MESSAGE_CONFIG,
        VALIDATION_CONFIG,
        NOTIFICATION_CONFIG,
        CHART_CONFIG
    };
}
