export default function StatusIndicator({ isConnected }) {
    return (
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-zen-surface border border-zen-border">
            <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-zen-success shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-zen-error animate-pulse'}`}></div>
            <span className="text-[9px] text-zen-text-muted uppercase tracking-wider font-bold">
                {isConnected ? 'CATIA Connected' : 'CATIA Disconnected'}
            </span>
        </div>
    )
}
