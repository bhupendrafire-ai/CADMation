import { useState } from 'react'

const steps = [
  {
    title: 'Welcome to CADMation Enterprise',
    description: 'We have upgraded your experience to a professional engineering suite. The tool is now organized into specialized workspaces.',
    icon: 'M13 10V3L4 14h7v7l9-11h-7z',
  },
  {
    title: 'Modular Workspaces',
    description: 'Use the new sidebar to switch between the Assembly Tree, BOM Command Center, and Drafting Tools. Each workspace is optimized for its specific task.',
    icon: 'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z',
  },
  {
    title: 'AI Copilot',
    description: 'The chat is now your Copilot. It lives in the side drawer and can assist you with complex modifications, measurements, and CAD automation while you work.',
    icon: 'M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z',
  },
  {
    title: 'Full-Screen Power',
    description: 'The BOM Editor now fills the entire screen, giving you a high-density grid for faster reviewing and seamless Excel exports.',
    icon: 'M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4',
  }
]

export default function HowToUseModal({ onClose }) {
  const [currentStep, setCurrentStep] = useState(0)
  const [dontShowAgain, setDontShowAgain] = useState(false)

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1)
    } else {
      handleClose()
    }
  }

  const handleClose = () => {
    if (dontShowAgain) {
      localStorage.setItem('cadmation_hide_guide', 'true')
    }
    onClose()
  }

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/90 backdrop-blur-xl animate-in fade-in duration-500">
      <div className="bg-[#121214] border border-white/10 rounded-[2.5rem] w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[80vh]">
        <div className="flex-1 overflow-y-auto p-12 text-center">
          <div className="w-20 h-20 bg-blue-600/20 rounded-3xl flex items-center justify-center mx-auto mb-8 shadow-lg shadow-blue-600/10 transition-transform hover:scale-110 duration-500">
             <svg className="w-10 h-10 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
               <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={steps[currentStep].icon}></path>
             </svg>
          </div>
          
          <h2 className="text-3xl font-bold text-white mb-4 tracking-tight animate-in slide-in-from-bottom-2 duration-300">
            {steps[currentStep].title}
          </h2>
          <p className="text-white/40 text-lg leading-relaxed max-w-md mx-auto animate-in slide-in-from-bottom-4 duration-500">
            {steps[currentStep].description}
          </p>

          <div className="flex justify-center gap-2 mt-12">
            {steps.map((_, i) => (
              <div 
                key={i} 
                className={`h-1 rounded-full transition-all duration-300 ${i === currentStep ? 'w-8 bg-blue-500' : 'w-2 bg-white/10'}`}
              ></div>
            ))}
          </div>
        </div>

        <div className="p-8 border-t border-white/5 bg-white/[0.02] flex items-center justify-between">
          <label className="flex items-center gap-3 cursor-pointer group">
            <input 
              type="checkbox" 
              checked={dontShowAgain}
              onChange={(e) => setDontShowAgain(e.target.checked)}
              className="w-5 h-5 rounded-lg border-white/10 bg-black/40 text-blue-600 focus:ring-blue-500/20 transition-all cursor-pointer"
            />
            <span className="text-sm text-white/40 group-hover:text-white/60 transition-all font-medium">Don't show this again</span>
          </label>

          <div className="flex gap-4">
             {currentStep > 0 && (
               <button 
                 onClick={() => setCurrentStep(currentStep - 1)}
                 className="px-6 py-3 rounded-2xl bg-white/5 text-white/60 hover:bg-white/10 hover:text-white transition-all font-bold text-sm"
               >
                 Back
               </button>
             )}
             <button 
               onClick={handleNext}
               className="px-10 py-3 rounded-2xl bg-blue-600 text-white font-bold text-sm hover:bg-blue-500 hover:shadow-lg hover:shadow-blue-600/20 active:scale-95 transition-all"
             >
               {currentStep === steps.length - 1 ? 'Get Started' : 'Next'}
             </button>
          </div>
        </div>
      </div>
    </div>
  )
}
