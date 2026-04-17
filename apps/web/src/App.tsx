import { SearchBar } from '@/components/SearchBar'

function App() {
  const handleSearch = (query: string) => {
    console.log('Search query:', query)
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header with Search Bar */}
      <header className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center justify-center px-4 py-3">
          <SearchBar
            onSearch={handleSearch}
            placeholder="Search research..."
          />
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex flex-col items-center justify-center px-4 py-16">
        <p className="text-muted-foreground text-sm">
          Enter a search query above to get started
        </p>
      </main>
    </div>
  )
}

export default App
