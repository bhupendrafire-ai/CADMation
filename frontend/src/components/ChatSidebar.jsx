import { useState, useEffect } from 'react'

export default function ChatSidebar({ 
    isOpen, 
    onToggle, 
    sessions, 
    currentSessionId, 
    onSelectSession, 
    onNewChat 
}) {
    return (
        <aside 
            className={`
                fixed top-14 bottom-0 right-0 z-40 flex flex-col glass border-l border-white/5 transition-all duration-300 ease-in-out
                ${isOpen ? 'w-64' : 'w-0 border-l-0'}
            `}
        >
            {/* Toggle Tab (Floats left of sidebar) */}
            <button
                onClick={onToggle}
                className={`
                    absolute top-4 -left-8 w-8 h-8 flex items-center justify-center bg-white/5 border border-white/10 rounded-l-lg hover:bg-white/10 transition-colors
                    ${isOpen ? 'opacity-100' : 'opacity-100 -left-8'}
                `}
                title={isOpen ? "Close History" : "Open History"}
            >
                <svg 
                    xmlns="http://www.w3.org/2000/svg" 
                    width="14" 
                    height="14" 
                    viewBox="0 0 24 24" 
                    fill="none" 
                    stroke="currentColor" 
                    strokeWidth="2" 
                    strokeLinecap="round" 
                    strokeLinejoin="round"
                    className={`transition-transform duration-300 ${isOpen ? '' : 'rotate-180'}`}
                >
                    <polyline points="9 18 15 12 9 6" />
                </svg>
            </button>

            {isOpen && (
                <div className="flex flex-col h-full overflow-hidden animate-in fade-in duration-300">
                    <div className="p-4 border-b border-white/5 flex items-center justify-between">
                        <span className="text-[10px] uppercase tracking-widest font-bold text-white/40">History</span>
                        <button 
                            onClick={onNewChat}
                            className="p-1.5 rounded-lg bg-white/10 hover:bg-white text-white hover:text-black transition-all"
                            title="New Conversation"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="12" y1="5" x2="12" y2="19" />
                                <line x1="5" y1="12" x2="19" y2="12" />
                            </svg>
                        </button>
                    </div>

                    <div className="flex-1 overflow-y-auto p-2 space-y-2 custom-scrollbar">
                        {sessions.length === 0 ? (
                            <div className="p-4 text-[11px] text-white/20 text-center italic">
                                No previous sessions
                            </div>
                        ) : (
                            sessions.map((s) => (
                                <button
                                    key={s.id}
                                    onClick={() => onSelectSession(s.id)}
                                    className={`
                                        w-full text-left p-3 rounded-xl transition-all border group
                                        ${s.id === currentSessionId 
                                            ? 'bg-white/10 border-white/20 text-white' 
                                            : 'border-transparent text-white/50 hover:bg-white/5 hover:text-white'
                                        }
                                    `}
                                >
                                    <div className="text-xs font-medium truncate mb-1">
                                        {s.name || 'Untitled Chat'}
                                    </div>
                                    <div className="text-[9px] opacity-40 font-mono">
                                        {s.updated_at ? new Date(s.updated_at).toLocaleDateString() : 'Unknown date'}
                                    </div>
                                </button>
                            ))
                        )}
                    </div>
                </div>
            )}
        </aside>
    )
}
