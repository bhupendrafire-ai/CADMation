import { CADMationLogo } from './Logo'

const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { id: 'sessions', label: 'Drafts', icon: 'M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z' },
  { id: 'tree', label: 'Assembly Tree', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
  { id: 'bom', label: 'BOM Editor', icon: 'M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { id: 'drafting', label: '2D Drafting', icon: 'M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z' },
]

export default function Sidebar({ activeTab, onTabChange, user, onOpenGuide }) {
  return (
    <aside className="w-64 bg-zen-surface border-r border-zen-border flex flex-col shrink-0 transition-all duration-300">
      <div className="p-6">
        <CADMationLogo version="3.6.7" />
      </div>

      <nav className="flex-1 px-4 py-4 space-y-1">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id)}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200 group ${
              activeTab === item.id 
              ? 'bg-zen-primary/[0.06] text-zen-primary border border-zen-primary/10 shadow-sm' 
              : 'text-zen-text-dim hover:text-zen-text-main hover:bg-zen-surface-alt border border-transparent'
            }`}
          >
            <svg 
              className={`w-5 h-5 transition-colors ${activeTab === item.id ? 'text-zen-primary' : 'text-zen-text-muted group-hover:text-zen-text-dim'}`} 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24" 
              xmlns="http://www.w3.org/2000/svg"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={item.icon}></path>
            </svg>
            <span className="font-medium">{item.label}</span>
            {activeTab === item.id && (
              <div className="ml-auto w-1.5 h-1.5 rounded-full bg-zen-primary"></div>
            )}
          </button>
        ))}
      </nav>

      <div className="p-6 mt-auto border-t border-zen-border">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-zen-surface-alt border border-zen-border flex items-center justify-center overflow-hidden">
            <svg className="w-6 h-6 text-zen-text-muted" fill="currentColor" viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67-0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
          </div>
          <div className="min-w-0">
            <p className="text-xs font-bold text-zen-text-main truncate">{user?.name || 'Loading...'}</p>
            <p className="text-[10px] text-zen-text-muted uppercase tracking-wider truncate">{user?.role || 'Guest'}</p>
          </div>
        </div>
        <button 
          onClick={onOpenGuide}
          className="w-full py-2 mb-2 rounded-full bg-zen-surface-alt text-[10px] text-zen-text-dim hover:text-zen-text-main hover:bg-zen-info/[0.1] transition-all font-bold uppercase tracking-widest border border-zen-border flex items-center justify-center gap-2"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
          Quick Guide
        </button>
        <button className="w-full py-2 rounded-full bg-zen-surface-alt text-[10px] text-zen-text-dim hover:text-zen-text-main hover:bg-zen-primary hover:text-white transition-all font-bold uppercase tracking-widest border border-zen-border hover:border-zen-primary">
          Sign Out
        </button>
      </div>
    </aside>
  )
}
