export default function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-1 p-2">
      {[0, 150, 300].map((delay) => (
        <div
          key={delay}
          className="w-2 h-2 rounded-full bg-purple-400 animate-bounce"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </div>
  )
}
