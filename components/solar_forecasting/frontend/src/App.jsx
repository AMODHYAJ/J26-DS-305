import React, { useState } from 'react';
import {
  Search, Bell, ArrowUpRight, Filter, Calendar, Download, Plus
} from 'lucide-react';
import { BarChart, Bar, XAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

// Embilipitiya GSS cluster telemetry & BESS headroom mock data
const generationData = [
  { month: 'Jan', power: 310 },
  { month: 'Feb', power: 340 },
  { month: 'Mar', power: 300 },
  { month: 'Apr', power: 379.502, active: true },
  { month: 'May', power: 350 },
  { month: 'Jun', power: 330 },
];

const matrixGrid = Array.from({ length: 6 }, (_, row) =>
  Array.from({ length: 12 }, (_, col) => ({
    id: `${row}-${col}`,
    intensity: Math.random()
  }))
);

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState('Overview');

  return (
    <div className="min-h-screen bg-[#121214] text-white font-sans p-6">
      {/* Top Navigation Bar */}
      <header className="flex items-center justify-between mb-8 bg-[#1a1a1e] px-6 py-4 rounded-2xl border border-white/5 shadow-xl">
        <div className="flex items-center space-x-8">
          <div className="bg-[#d4ff32] text-black font-black p-2 rounded-xl text-xl tracking-tighter">
            ⚡ GSS
          </div>
          <nav className="flex space-x-2">
            {['Overview', 'Insights', 'Analytics', 'Audiences', 'Reports'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                  activeTab === tab
                    ? 'bg-[#d4ff32] text-black font-semibold shadow-md'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`}
              >
                {tab} {tab === 'Analytics' && '🔥'}
              </button>
            ))}
          </nav>
        </div>

        <div className="flex items-center space-x-4">
          <button className="p-2.5 rounded-full bg-white/5 hover:bg-white/10 text-gray-300">
            <Search size={18} />
          </button>
          <button className="p-2.5 rounded-full bg-white/5 hover:bg-white/10 text-gray-300">
            <Bell size={18} />
          </button>
          <div className="w-10 h-10 rounded-full overflow-hidden border-2 border-[#d4ff32]">
            <img src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100" alt="Operator" className="w-full h-full object-cover" />
          </div>
        </div>
      </header>

      {/* Welcome Banner & KPI Header */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
        <div className="lg:col-span-1 flex flex-col justify-center">
          <p className="text-gray-400 text-sm mb-1">Welcome back,</p>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Darlene Robertson</h1>
          <span className="inline-block bg-purple-900/50 text-purple-300 border border-purple-500/30 text-xs px-3 py-1 rounded-full font-medium w-fit">
            Senior Grid Operator
          </span>
        </div>

        {/* KPI Card 1 */}
        <div className="bg-[#1a1a1e] p-5 rounded-2xl border border-white/5 flex flex-col justify-between relative group hover:border-[#d4ff32]/30 transition-all">
          <div className="flex justify-between items-start">
            <span className="text-xs text-gray-400 font-medium">Cluster Generation (kW)</span>
            <button className="p-2 bg-white/5 rounded-full group-hover:bg-[#d4ff32] group-hover:text-black transition-all">
              <ArrowUpRight size={16} />
            </button>
          </div>
          <div>
            <div className="text-3xl font-bold text-white mb-1">975,124</div>
            <p className="text-xs text-emerald-400 font-medium">+42.8% from previous week</p>
          </div>
        </div>

        {/* KPI Card 2 */}
        <div className="bg-[#1a1a1e] p-5 rounded-2xl border border-white/5 flex flex-col justify-between relative group hover:border-[#d4ff32]/30 transition-all">
          <div className="flex justify-between items-start">
            <span className="text-xs text-gray-400 font-medium">BESS Headroom (kWh)</span>
            <button className="p-2 bg-white/5 rounded-full group-hover:bg-[#d4ff32] group-hover:text-black transition-all">
              <ArrowUpRight size={16} />
            </button>
          </div>
          <div>
            <div className="text-3xl font-bold text-white mb-1">296,241</div>
            <p className="text-xs text-emerald-400 font-medium">+26.3% from previous week</p>
          </div>
        </div>

        {/* KPI Card 3 (Lime Highlighted Card) */}
        <div className="bg-[#d4ff32] text-black p-5 rounded-2xl flex flex-col justify-between shadow-xl">
          <div className="flex justify-between items-start">
            <span className="text-xs font-bold text-black/70">Embilipitiya GSS Load</span>
            <button className="p-2 bg-black/10 rounded-full hover:bg-black/20 transition-all">
              <ArrowUpRight size={16} />
            </button>
          </div>
          <div>
            <div className="text-3xl font-black mb-1">76,314</div>
            <p className="text-xs font-semibold text-black/70">-18.4% from previous week</p>
          </div>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex space-x-2">
          {['All', 'Engagement', 'Visit', 'Post'].map((filter, idx) => (
            <button key={filter} className={`px-4 py-2 rounded-full text-xs font-semibold ${idx === 0 ? 'bg-[#d4ff32] text-black' : 'bg-[#1a1a1e] text-gray-400 hover:text-white'}`}>
              {filter}
            </button>
          ))}
        </div>
        <div className="flex space-x-3">
          <button className="p-2.5 bg-[#1a1a1e] text-gray-300 rounded-xl hover:bg-white/5"><Filter size={16} /></button>
          <button className="p-2.5 bg-[#1a1a1e] text-gray-300 rounded-xl hover:bg-white/5"><Calendar size={16} /></button>
          <button className="flex items-center space-x-2 px-4 py-2.5 bg-[#1a1a1e] text-white text-xs font-medium rounded-xl hover:bg-white/5">
            <Download size={14} />
            <span>Download reports</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Charts & Feeder Matrix */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Chart Widget */}
        <div className="bg-[#1a1a1e] p-6 rounded-2xl border border-white/5 lg:col-span-1">
          <div className="flex justify-between items-center mb-6">
            <div className="flex items-center space-x-2 text-sm font-semibold text-gray-300">
              <span>📊 Generation Profile</span>
            </div>
            <div className="flex bg-black/30 p-1 rounded-full text-xs">
              <span className="px-3 py-1 rounded-full text-gray-400">Monthly</span>
              <span className="px-3 py-1 rounded-full bg-[#d4ff32] text-black font-bold">Annually</span>
            </div>
          </div>

          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={generationData}>
                <XAxis dataKey="month" stroke="#8e8e93" fontSize={12} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: '#121214', borderColor: '#333', borderRadius: '12px' }} />
                <Bar dataKey="power" fill="#6c5dd3" radius={[8, 8, 0, 0]}>
                  {generationData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.active ? '#d4ff32' : '#6c5dd3'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Matrix Volatility Heatmap Widget */}
        <div className="bg-[#1a1a1e] p-6 rounded-2xl border border-white/5 lg:col-span-1">
          <div className="flex justify-between items-center mb-6">
            <span className="text-sm font-semibold text-gray-300">⚡ Feeder Ramp Volatility Matrix</span>
            <span className="text-xs bg-white/5 px-3 py-1 rounded-full text-gray-400">Live ▾</span>
          </div>

          <div className="grid grid-cols-6 gap-2 h-60 content-center">
            {matrixGrid.flat().map((cell) => {
              const isHigh = cell.intensity > 0.7;
              const isMid = cell.intensity > 0.4 && cell.intensity <= 0.7;
              return (
                <div
                  key={cell.id}
                  className={`rounded-lg transition-all ${
                    isHigh ? 'bg-[#d4ff32]' : isMid ? 'bg-[#8be9fd]' : 'bg-[#6c5dd3]/40'
                  } hover:scale-110 cursor-pointer shadow-inner`}
                  title={`Feeder Node ${cell.id}`}
                />
              );
            })}
          </div>
        </div>

        {/* Live Feed / Messages Widget */}
        <div className="bg-[#1a1a1e] p-6 rounded-2xl border border-white/5 lg:col-span-1 flex flex-col justify-between">
          <div className="flex justify-between items-center mb-4">
            <span className="text-sm font-semibold text-gray-300">💬 Operator Alerts & Logs</span>
            <button className="p-2 bg-white/5 rounded-full hover:bg-white/10"><Plus size={16} /></button>
          </div>

          <div className="space-y-4">
            {[
              { name: 'Theresa Webb', msg: 'Ramp-Down event detected on Feeder 3.', time: '3m', img: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100' },
              { name: 'Marvin McKinney', msg: 'BESS headroom score stable at 84%.', time: '12m', img: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100' },
              { name: 'Jenny Wilson', msg: 'CAMS weather sync completed successfully.', time: '29m', img: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=100' },
            ].map((item, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-white/5 hover:bg-white/10 transition-all">
                <div className="flex items-center space-x-3">
                  <img src={item.img} alt={item.name} className="w-10 h-10 rounded-full object-cover" />
                  <div>
                    <h4 className="text-xs font-bold text-white">{item.name}</h4>
                    <p className="text-xs text-gray-400 truncate max-w-[160px]">{item.msg}</p>
                  </div>
                </div>
                <span className="text-[10px] text-gray-500">{item.time}</span>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}