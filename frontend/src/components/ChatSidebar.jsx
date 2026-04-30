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
                fixed top-14 bottom-0 right-0 z-40 flex flex-col glass border-l border-zen-border transition-all duration-300 ease-in-out
                ${isOpen ? 'w-64' : 'w-0 border-l-0'}
            `}
        >
            {/* Toggle Tab (Floats left of sidebar) */}
            <button
                onClick={onToggle}
                className={`
                    absolute top-4 -left-8 w-8 h-8 flex items-center justify-center bg-zen-surface border border-zen-border rounded-l-lg hover:bg-zen-surface-alt transition-colors
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
                    className={`transition-transform duration-300 text-zen-text-dim ${isOpen ? '' : 'rotate-180'}`}
                >
                    <polyline points="9 18 15 12 9 6" />
                </svg>
            </button>

            {isOpen && (
                <div className="flex flex-col h-full overflow-hidden animate-in">
                    <div className="p-4 border-b border-zen-border flex items-center justify-between">
                        <span className="zen-label">History</span>
                        <button 
                            onClick={onNewChat}
                            className="p-1.5 rounded-lg bg-zen-surface-alt hover:bg-zen-primary text-zen-text-dim hover:text-white transition-all border border-zen-border hover:border-zen-primary"
                            title="New Conversation"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="12" y1="5" x2="12" y2="19" />
                                <line x1="5" y1="12" x2="19" y2="12" />
                            </svg>
                        </button>
                    </div>

                    <div className="flex-1 overflow-y-auto p-2 space-y-2">
                        {sessions.length === 0 ? (
                            <div className="p-4 text-[11px] text-zen-text-muted text-center italic">
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
                                            ? 'bg-zen-primary/[0.05] border-zen-primary/20 text-zen-text-main' 
                                            : 'border-transparent text-zen-text-dim hover:bg-zen-surface-alt hover:text-zen-text-main'
                                        }
                                    `}
                                >
                                    <div className="text-xs font-medium truncate mb-1">
                                        {s.name || 'Untitled Chat'}
                                    </div>
                                    <div className="text-[9px] text-zen-text-muted font-mono">
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
