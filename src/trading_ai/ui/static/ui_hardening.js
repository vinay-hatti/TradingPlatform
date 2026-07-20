(() => {
  const CACHE_PREFIX="trading-ui-cache:";
  const DEFAULT_TIMEOUT=10000;

  function announce(message){
    let region=document.querySelector("#globalAriaLive");
    if(!region){
      region=document.createElement("div");
      region.id="globalAriaLive";
      region.setAttribute("aria-live","polite");
      region.setAttribute("aria-atomic","true");
      region.className="visually-hidden";
      document.body.appendChild(region);
    }
    region.textContent="";
    setTimeout(()=>{region.textContent=message},20);
  }

  function addSkipLink(){
    if(document.querySelector(".skip-link"))return;
    const link=document.createElement("a");
    link.href="#content";
    link.className="skip-link";
    link.textContent="Skip to main content";
    document.body.insertBefore(link,document.body.firstChild);
  }

  function improveLandmarks(){
    const nav=document.querySelector("#nav")||document.querySelector(".nav");
    if(nav&&!nav.getAttribute("aria-label"))nav.setAttribute("aria-label","Primary navigation");
    const content=document.querySelector("#content");
    if(content){
      content.setAttribute("role","main");
      content.setAttribute("tabindex","-1");
    }
    document.querySelectorAll("button").forEach(button=>{
      if(!button.type)button.type="button";
      if(!button.getAttribute("aria-label")&&!button.textContent.trim()){
        button.setAttribute("aria-label","Action");
      }
    });
    document.querySelectorAll("table").forEach(table=>{
      if(!table.querySelector("caption")){
        const caption=document.createElement("caption");
        caption.className="visually-hidden";
        caption.textContent="Data table";
        table.insertBefore(caption,table.firstChild);
      }
    });
  }

  function enableKeyboardNav(){
    document.addEventListener("keydown",event=>{
      if(event.key==="Escape"){
        const active=document.activeElement;
        if(active&&typeof active.blur==="function")active.blur();
      }
      if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="k"){
        event.preventDefault();
        const first=document.querySelector("#nav button, .nav button");
        if(first)first.focus();
      }
    });
  }

  async function fetchWithResilience(url,options={}){
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),options.timeout||DEFAULT_TIMEOUT);
    const method=(options.method||"GET").toUpperCase();
    const cacheKey=CACHE_PREFIX+url;
    try{
      const response=await fetch(url,{...options,signal:controller.signal,cache:"no-store"});
      clearTimeout(timeout);
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const cloned=response.clone();
      if(method==="GET"){
        cloned.text().then(text=>{
          try{
            localStorage.setItem(cacheKey,JSON.stringify({
              cached_at:new Date().toISOString(),
              body:text,
              content_type:response.headers.get("content-type")||"application/json"
            }));
          }catch(_){}
        });
      }
      return response;
    }catch(error){
      clearTimeout(timeout);
      if(method==="GET"){
        const cached=localStorage.getItem(cacheKey);
        if(cached){
          const payload=JSON.parse(cached);
          announce("Network unavailable. Showing cached data.");
          document.body.dataset.offlineFallback="true";
          return new Response(payload.body,{
            status:200,
            headers:{
              "Content-Type":payload.content_type,
              "X-Offline-Fallback":"true",
              "X-Cached-At":payload.cached_at
            }
          });
        }
      }
      throw error;
    }
  }

  function installGlobalErrorBoundary(){
    window.addEventListener("error",event=>{
      console.error("UI error",event.error||event.message);
      announce("An interface error occurred. Existing data remains unchanged.");
    });
    window.addEventListener("unhandledrejection",event=>{
      console.error("Unhandled promise rejection",event.reason);
      announce("A background request failed. Existing data remains unchanged.");
    });
  }

  function trackPerformance(){
    window.addEventListener("load",()=>{
      const nav=performance.getEntriesByType("navigation")[0];
      const record={
        timestamp:new Date().toISOString(),
        dom_content_loaded_ms:nav?Math.round(nav.domContentLoadedEventEnd):0,
        load_complete_ms:nav?Math.round(nav.loadEventEnd):0,
        resource_count:performance.getEntriesByType("resource").length
      };
      try{localStorage.setItem("trading-ui:last-performance",JSON.stringify(record))}catch(_){}
      if(record.load_complete_ms>3000)announce("The interface loaded more slowly than expected.");
    });
  }

  function registerServiceWorker(){
    if("serviceWorker" in navigator){
      navigator.serviceWorker.register("/static/service-worker.js").catch(error=>{
        console.warn("Service worker registration failed",error);
      });
    }
  }

  function observeDynamicContent(){
    const observer=new MutationObserver(()=>{
      improveLandmarks();
    });
    observer.observe(document.documentElement,{childList:true,subtree:true});
  }

  function exposeHelpers(){
    window.TradingUiResilience={
      fetch:fetchWithResilience,
      announce,
      getLastPerformance:()=>{
        try{return JSON.parse(localStorage.getItem("trading-ui:last-performance")||"null")}catch(_){return null}
      }
    };
  }

  window.addEventListener("DOMContentLoaded",()=>{
    addSkipLink();
    improveLandmarks();
    enableKeyboardNav();
    installGlobalErrorBoundary();
    trackPerformance();
    registerServiceWorker();
    observeDynamicContent();
    exposeHelpers();
    announce("Trading workstation ready.");
  });
})();
