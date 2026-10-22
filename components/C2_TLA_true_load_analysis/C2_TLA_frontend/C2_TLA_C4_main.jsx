import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './C2_TLA_C4_App.jsx';
import './C2_TLA_C4_index.css';

// Forward the shared session token to the mounted C4 API.
const originalFetch=window.fetch.bind(window);
window.fetch=(url,options={})=>{
  if(typeof url==='string' && url.startsWith('/api/')){
    const headers=new Headers(options.headers);
    const token=sessionStorage.getItem('C2_TLA_API_TOKEN');
    if(token)headers.set('Authorization',`Bearer ${token}`);
    return originalFetch(url,{...options,headers});
  }
  return originalFetch(url,options);
};
createRoot(document.getElementById('root')).render(<App/>);
