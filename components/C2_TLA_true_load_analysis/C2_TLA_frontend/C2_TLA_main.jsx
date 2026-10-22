import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import App from './C2_TLA_App.jsx';
import './C2_TLA_styles.css';
function Workspace(){
  const [workspace,setWorkspace]=useState('c2');
  return <><nav className="workspace-nav" aria-label="Component workspace"><span>SOLAVERA WORKSPACE</span><div><button className={workspace==='c2'?'selected':''} onClick={()=>setWorkspace('c2')}>Demand intelligence · C2</button><button className={workspace==='c3'?'selected':''} onClick={()=>setWorkspace('c3')}>Grid intelligence · C3</button></div><small>Connected to current-main components</small></nav><div hidden={workspace!=='c2'}><App onOpenGrid={()=>setWorkspace('c3')}/></div>{workspace==='c3'&&<iframe className="c3-frame" title="C3 grid intelligence dashboard" src="/c3/"/>}</>;
}
createRoot(document.getElementById('root')).render(<Workspace />);
