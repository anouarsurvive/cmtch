/**
 * Service Worker pour le cache et les performances
 * Version: 1.0.0
 */

const CACHE_NAME = 'cmtch-pwa-v1.1.0';
const STATIC_CACHE = 'cmtch-static-pwa-v1.1.0';
const DYNAMIC_CACHE = 'cmtch-dynamic-pwa-v1.1.0';
const OFFLINE_CACHE = 'cmtch-offline-pwa-v1.1.0';

// Ressources à mettre en cache immédiatement
const STATIC_ASSETS = [
    '/',
    '/static/css/critical.css',
    '/static/css/style.css',
    '/static/css/custom.css',
    '/static/css/rtl.css',
    '/static/js/performance.js',
    '/static/js/config.js',
    '/static/images/hero.png',
    '/static/images/logo.jpg',
    '/static/favicon-192x192.png',
    '/static/favicon-512x512.png',
    '/static/manifest.json'
];

// Ressources à mettre en cache dynamiquement
const DYNAMIC_ASSETS = [
    '/articles',
    '/reservations',
    '/login',
    '/register'
];

// Installation du Service Worker
self.addEventListener('install', (event) => {
    console.log('Service Worker installing...');
    
    event.waitUntil(
        Promise.all([
            // Cache des ressources statiques
            caches.open(STATIC_CACHE).then((cache) => {
                console.log('Caching static assets...');
                return cache.addAll(STATIC_ASSETS).catch((error) => {
                    console.warn('Some static assets failed to cache:', error);
                    // Continuer même si certaines ressources échouent
                    return Promise.resolve();
                });
            }),
            // Cache des ressources dynamiques
            caches.open(DYNAMIC_CACHE).then((cache) => {
                console.log('Caching dynamic assets...');
                return cache.addAll(DYNAMIC_ASSETS).catch((error) => {
                    console.warn('Some dynamic assets failed to cache:', error);
                    // Continuer même si certaines ressources échouent
                    return Promise.resolve();
                });
            })
        ]).then(() => {
            console.log('Service Worker installed successfully');
            return self.skipWaiting();
        }).catch((error) => {
            console.error('Service Worker installation failed:', error);
        })
    );
});

// Activation du Service Worker
self.addEventListener('activate', (event) => {
    console.log('Service Worker activating...');
    
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    // Suppression des anciens caches
                    if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
                        console.log('Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('Service Worker activated successfully');
            return self.clients.claim();
        })
    );
});

// Interception des requêtes
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Stratégie de cache selon le type de ressource
    if (request.method === 'GET') {
        // Ressources statiques (CSS, JS, images, fonts)
        if (isStaticAsset(url.pathname)) {
            event.respondWith(cacheFirst(request, STATIC_CACHE));
        }
        // Pages HTML
        else if (isHTMLRequest(request)) {
            event.respondWith(networkFirst(request, DYNAMIC_CACHE));
        }
        // API et autres ressources
        else {
            event.respondWith(networkFirst(request, DYNAMIC_CACHE));
        }
    }
});

// Stratégie Cache First pour les ressources statiques
async function cacheFirst(request, cacheName) {
    try {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        console.log('Cache first strategy failed:', error);
        return new Response('Offline content not available', {
            status: 503,
            statusText: 'Service Unavailable'
        });
    }
}

// Stratégie Network First pour les pages dynamiques
async function networkFirst(request, cacheName) {
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        console.log('Network first strategy failed, trying cache:', error);
        
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // Page d'erreur offline
        return caches.match('/offline.html').then((response) => {
            return response || new Response('Offline content not available', {
                status: 503,
                statusText: 'Service Unavailable'
            });
        });
    }
}

// Vérification si c'est une ressource statique
function isStaticAsset(pathname) {
    const staticExtensions = ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.woff', '.woff2', '.ttf', '.eot'];
    return staticExtensions.some(ext => pathname.includes(ext));
}

// Vérification si c'est une requête HTML
function isHTMLRequest(request) {
    return request.headers.get('accept').includes('text/html');
}

// Gestion des messages du client
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data && event.data.type === 'GET_VERSION') {
        event.ports[0].postMessage({ version: CACHE_NAME });
    }
    
    // Gestion des notifications push
    if (event.data && event.data.type === 'PUSH_NOTIFICATION') {
        showNotification(event.data.title, event.data.body, event.data.icon);
    }
});

// Gestion des notifications push
self.addEventListener('push', (event) => {
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.body || 'Nouvelle notification du CMTCH',
            icon: '/static/favicon-192x192.png',
            badge: '/static/favicon-192x192.png',
            vibrate: [200, 100, 200],
            data: data.data || {},
            actions: [
                {
                    action: 'open',
                    title: 'Ouvrir',
                    icon: '/static/favicon-192x192.png'
                },
                {
                    action: 'close',
                    title: 'Fermer'
                }
            ]
        };
        
        event.waitUntil(
            self.registration.showNotification(data.title || 'CMTCH', options)
        );
    }
});

// Gestion des clics sur les notifications
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    
    if (event.action === 'open' || !event.action) {
        event.waitUntil(
            clients.openWindow('/')
        );
    }
});

// Fonction pour afficher une notification
function showNotification(title, body, icon) {
    const options = {
        body: body,
        icon: icon || '/static/favicon-192x192.png',
        badge: '/static/favicon-192x192.png',
        vibrate: [200, 100, 200],
        tag: 'cmtch-notification'
    };
    
    return self.registration.showNotification(title, options);
}

// Gestion des erreurs
self.addEventListener('error', (event) => {
    console.error('Service Worker error:', event.error);
});

// Gestion des rejets de promesses non gérés
self.addEventListener('unhandledrejection', (event) => {
    console.error('Service Worker unhandled rejection:', event.reason);
});

// Nettoyage périodique du cache
self.addEventListener('periodicsync', (event) => {
    if (event.tag === 'cleanup-cache') {
        event.waitUntil(cleanupCache());
    }
});

// Fonction de nettoyage du cache
async function cleanupCache() {
    try {
        const cacheNames = await caches.keys();
        const currentCaches = [STATIC_CACHE, DYNAMIC_CACHE];
        
        for (const cacheName of cacheNames) {
            if (!currentCaches.includes(cacheName)) {
                await caches.delete(cacheName);
                console.log('Cleaned up old cache:', cacheName);
            }
        }
    } catch (error) {
        console.error('Cache cleanup failed:', error);
    }
}

// Optimisations pour les performances
const PERFORMANCE_OPTIMIZATIONS = {
    // Compression des réponses
    compressResponse: async (response) => {
        if (response.headers.get('content-type')?.includes('text/')) {
            const text = await response.text();
            const compressed = new Response(text, {
                headers: {
                    'content-type': response.headers.get('content-type'),
                    'content-encoding': 'gzip'
                }
            });
            return compressed;
        }
        return response;
    },
    
    // Préchargement intelligent
    preloadCriticalResources: async () => {
        const criticalResources = [
            '/static/css/critical.css',
            '/static/js/performance.js'
        ];
        
        for (const resource of criticalResources) {
            try {
                await fetch(resource, { cache: 'force-cache' });
            } catch (error) {
                console.log('Preload failed for:', resource);
            }
        }
    }
};

// Initialisation des optimisations
self.addEventListener('install', (event) => {
    event.waitUntil(PERFORMANCE_OPTIMIZATIONS.preloadCriticalResources());
});
