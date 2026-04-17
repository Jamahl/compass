import { useState, type FormEvent } from 'react'
import { Search } from 'lucide-react'

interface SearchBarProps {
  onSearch?: (query: string) => void
  placeholder?: string
}

export function SearchBar({ onSearch, placeholder = 'Search...' }: SearchBarProps) {
  const [query, setQuery] = useState('')
  const [isFocused, setIsFocused] = useState(false)

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (query.trim() && onSearch) {
      onSearch(query.trim())
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-[584px]">
      <div
        className={`
          flex items-center gap-3 px-4 py-3
          bg-card border rounded-full
          transition-shadow duration-200
          ${isFocused ? 'shadow-lg border-transparent' : 'border-border hover:shadow-md'}
        `}
      >
        <Search className="h-5 w-5 text-muted-foreground flex-shrink-0" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          className="flex-1 bg-transparent text-foreground text-base outline-none placeholder:text-muted-foreground"
        />
        {query && (
          <button
            type="button"
            onClick={() => setQuery('')}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Clear search"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
      </div>
    </form>
  )
}
