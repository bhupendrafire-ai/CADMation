export default function StatusIndicator({ isConnected }) {
    return (
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/5">
            <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-red-500 animate-pulse'}`}></div>
            <span className="text-[9px] text-muted-foreground uppercase tracking-wider font-bold">
                {isConnected ? 'CATIA Connected' : 'CATIA Disconnected'}
            </span>
        </div>
    )
}
