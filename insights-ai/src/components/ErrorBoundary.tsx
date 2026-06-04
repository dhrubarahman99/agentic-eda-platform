import { Component, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error) {
    console.error(error)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#0A0A0A] flex flex-col items-center justify-center px-4">
          <AlertTriangle size={48} className="text-red-400" />
          <h2 className="text-white text-2xl font-bold mt-4">Something went wrong</h2>
          {this.state.error?.message && (
            <p className="text-[#52525B] text-sm mt-2 max-w-sm text-center">
              {this.state.error.message}
            </p>
          )}
          <button
            onClick={() => window.location.reload()}
            className="mt-6 bg-[#1A1A1A] border border-[#2A2A2A] rounded-xl px-6 py-2.5 text-white text-sm hover:bg-[#2A2A2A] cursor-pointer transition-colors"
          >
            Refresh the page
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
