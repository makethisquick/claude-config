/* Lead attribution — first-party, 90-day cookie `elm_attr` (JSON): Google click ids (gclid/gbraid/wbraid),
   UTMs, first landing page + referrer + first-seen, captured on the FIRST page of the visit, written into
   the form's hidden fields, plus the GA4 client id from _ga at submit time. No third-party calls, no PII. */
(function(){try{
  var d=document,KEY='elm_attr',DAYS=90;
  function getCookie(n){var m=d.cookie.match('(?:^|; )'+n.replace(/[.$?*|{}()\[\]\\\/+^]/g,'\\$&')+'=([^;]*)');return m?decodeURIComponent(m[1]):'';}
  function setCookie(n,v){var dt=new Date();dt.setTime(dt.getTime()+DAYS*864e5);d.cookie=n+'='+encodeURIComponent(v)+'; expires='+dt.toUTCString()+'; path=/; SameSite=Lax; Secure';}
  var q=new URLSearchParams(location.search),a={};try{a=JSON.parse(getCookie(KEY)||'{}')||{};}catch(e){a={};}
  var keys=['gclid','gbraid','wbraid','utm_source','utm_medium','utm_campaign','utm_term','utm_content'],touched=false;
  keys.forEach(function(k){var v=q.get(k);if(v){a[k]=v.slice(0,200);touched=true;}});
  if(!a.landing_page){a.landing_page=location.pathname+location.search.slice(0,300);a.referrer=(d.referrer||'').slice(0,300);a.first_seen=new Date().toISOString();touched=true;}
  if(touched)setCookie(KEY,JSON.stringify(a));
  function gaClientId(){var g=getCookie('_ga'),p=g.split('.');return p.length>=4?p[2]+'.'+p[3]:'';}
  function fill(){var forms=d.querySelectorAll('form.frm-fluent-form');if(!forms.length)return;
    forms.forEach(function(f){function set(n,v){var el=f.querySelector('input[name="'+n+'"]');if(el&&v&&!el.value)el.value=v;}
      keys.concat(['landing_page','referrer','first_seen']).forEach(function(k){set(k,a[k]||'');});set('page_url',location.href.slice(0,300));set('ga_client_id',gaClientId());});}
  if(d.readyState!=='loading')fill();else d.addEventListener('DOMContentLoaded',fill);
  d.addEventListener('submit',function(e){if(e.target&&e.target.matches&&e.target.matches('form.frm-fluent-form')){var el=e.target.querySelector('input[name="ga_client_id"]');if(el&&!el.value)el.value=gaClientId();}},true);
}catch(e){}})();
