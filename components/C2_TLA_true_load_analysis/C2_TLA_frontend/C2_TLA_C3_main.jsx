import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './C2_TLA_C3_App.jsx';
import './C2_TLA_C3_index.css';

// Keep main's C3 UI intact; forward the shared local-session token for its data fetch.
const originalFetch=window.fetch.bind(window);
window.fetch=(url,options={})=>{
  if(url==='/data/transformer_risk.json'){
    const headers=new Headers(options.headers);
    const token=sessionStorage.getItem('C2_TLA_API_TOKEN');
    if(token)headers.set('Authorization',`Bearer ${token}`);
    return originalFetch(url,{...options,headers});
  }
  return originalFetch(url,options);
};
createRoot(document.getElementById('root')).render(<App/>);
