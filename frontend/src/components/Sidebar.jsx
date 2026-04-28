import { useState } from 'react'

const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { id: 'tree', label: 'Assembly Tree', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
  { id: 'bom', label: 'BOM Editor', icon: 'M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { id: 'drafting', label: '2D Drafting', icon: 'M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z' },
]

export default function Sidebar({ activeTab, onTabChange }) {
  return (
    <aside className="w-64 bg-[#09090b] border-r border-white/5 flex flex-col shrink-0 transition-all duration-300">
      <div className="p-6 flex items-center gap-3">
        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shadow-lg shadow-blue-600/20">
          <div className="w-4 h-4 bg-white rounded-sm rotate-45 flex items-center justify-center">
            <div className="w-2 h-2 bg-blue-600 rounded-full"></div>
          </div>
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-tighter text-white">CADMation</h1>
          <p className="text-[10px] text-white/30 font-mono uppercase tracking-widest">Enterprise v2.3</p>
        </div>
      </div>

      <nav className="flex-1 px-4 py-4 space-y-1">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id)}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 group ${
              activeTab === item.id 
              ? 'bg-blue-600/10 text-blue-400 border border-blue-600/20 shadow-inner' 
              : 'text-white/40 hover:text-white/70 hover:bg-white/5 border border-transparent'
            }`}
          >
            <svg 
              className={`w-5 h-5 transition-colors ${activeTab === item.id ? 'text-blue-400' : 'text-white/20 group-hover:text-white/40'}`} 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24" 
              xmlns="http://www.w3.org/2000/svg"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={item.icon}></path>
            </svg>
            <span className="font-medium">{item.label}</span>
            {activeTab === item.id && (
              <div className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.6)]"></div>
            )}
          </button>
        ))}
      </nav>

      <div className="p-6 mt-auto border-t border-white/5 bg-white/[0.02]">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden">
            <svg className="w-6 h-6 text-white/20" fill="currentColor" viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
          </div>
          <div>
            <p className="text-xs font-bold text-white/80">Engineer One</p>
            <p className="text-[10px] text-white/30 uppercase tracking-wider">Tier 1 Supplier</p>
          </div>
        </div>
        <button className="w-full py-2 rounded-lg bg-white/5 text-[10px] text-white/40 hover:text-white hover:bg-white/10 transition-all font-bold uppercase tracking-widest border border-white/5">
          Sign Out
        </button>
      </div>
    </aside>
  )
}
