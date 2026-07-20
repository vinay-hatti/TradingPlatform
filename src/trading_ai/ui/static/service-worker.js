const CACHE_NAME="trading-platform-ui-v33.10.0";
const APP_SHELL=[
  "/",
  "/static/index.html",
  "/static/ui_hardening.js",
  "/static/strategy_studio.js",
  "/static/operations_command_center.js",
  "/static/security_compliance_center.js",
  "/static/executive_reporting.js"
];

self.addEventListener("install",event=>{
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache=>cache.addAll(APP_SHELL))
      .then(()=>self.skipWaiting())
  );
});

self.addEventListener("activate",event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(k=>k!==CACHE_NAME).map(k=>caches.delete(k))))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener("fetch",event=>{
  const request=event.request;
  if(request.method!=="GET")return;

  const url=new URL(request.url);
  if(url.origin!==self.location.origin)return;

  if(url.pathname.startsWith("/api/")){
    event.respondWith(
      fetch(request)
        .then(response=>{
          const clone=response.clone();
          caches.open(CACHE_NAME).then(cache=>cache.put(request,clone));
          return response;
        })
        .catch(()=>caches.match(request))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then(cached=>{
      return cached||fetch(request).then(response=>{
        const clone=response.clone();
        caches.open(CACHE_NAME).then(cache=>cache.put(request,clone));
        return response;
      }).catch(()=>caches.match("/static/index.html"));
    })
  );
});
