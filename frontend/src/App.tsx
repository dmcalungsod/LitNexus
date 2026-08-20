import React, { useState, useEffect, useRef } from 'react'
import { EventsOn, EventsOff } from '../wailsjs/runtime/runtime'
import { 
  BookOpen, Plus, FileUp, Download, Settings as SettingsIcon, 
  Search, ExternalLink, CheckCircle2, AlertCircle, RefreshCw, 
  ChevronRight, ArrowLeftRight, FileText, Check, FolderOpen,
  ArrowLeft, GitBranch, Layers, Copy, Share2, Filter, ArrowUpDown,
  ClipboardCheck, DownloadCloud, Code, FileSpreadsheet, Trash2,
  Info, HelpCircle, Sun, Moon, Monitor, X, AlertTriangle,
  ScrollText, ChevronDown, ChevronUp, XCircle, RotateCcw, Sparkles
} from 'lucide-react'

// ─── Interfaces ───

interface Paper {
  doi: string
  title: string
  authors: string
  year: number
  abstract?: string
  generation: number
  pdf_status: string
  pdf_status_reason?: string
  local_filepath?: string
  external_reference_count?: number
  external_citation_count?: number
  external_counts_source?: string
  external_counts_fetched_at?: string
  references_fetch_status?: string
  citations_fetch_status?: string
}

interface AppSettings {
  unpaywall_email: string
  institutional_proxy: string
  output_directory: string
  verify_ssl: boolean
  ui_mode: string
}

interface NavStep {
  id: string
  label: string
  mode: 'all' | 'references' | 'citations'
  targetDOI?: string
}

interface ToastItem {
  id: number
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
}

interface LogEntry {
  id: number
  timestamp: Date
  level: 'info' | 'success' | 'warning' | 'error'
  category: string
  message: string
  detail?: string
}

type ThemeName = 'dark' | 'light' | 'midnight' | 'warm'

// ─── Constants ───

const THEME_OPTIONS: { value: ThemeName; label: string; icon: React.ReactNode }[] = [
  { value: 'dark', label: 'Dark', icon: <Moon className="w-3.5 h-3.5" /> },
  { value: 'light', label: 'Light', icon: <Sun className="w-3.5 h-3.5" /> },
  { value: 'midnight', label: 'Midnight', icon: <Monitor className="w-3.5 h-3.5" /> },
  { value: 'warm', label: 'Warm', icon: <Sparkles className="w-3.5 h-3.5" /> },
]

// Fallback Wails window bindings check
const wails = (window as any).go?.main?.App

let _toastId = 0
let _logId = 0

const parseErrorDetail = (reason?: string) => {
  const raw = reason || ''
  if (!raw || raw.includes('No open-access') || raw.includes('too small') || raw.includes('invalid file') || raw.includes('no legal')) {
    return {
      why: 'No legal, public open-access PDF URL was found from Crossref, Unpaywall, OpenAlex, or Semantic Scholar.',
      how: 'Set an Institutional Proxy in ⚙ Settings if your university has a subscription, or click "Publisher page" to download manually.'
    }
  }
  if (raw.includes('404')) {
    return {
      why: 'Publisher server returned HTTP 404 (File Not Found) for the PDF link.',
      how: 'The link may be broken or restricted. Click "Publisher page" to open the paper directly on the publisher website.'
    }
  }
  if (raw.includes('403') || raw.includes('401')) {
    return {
      why: 'Publisher access restricted (HTTP 403/401 Forbidden).',
      how: 'This paper is behind a subscription paywall. Configure your university\'s EZProxy prefix in ⚙ Settings.'
    }
  }
  if (raw.includes('timeout') || raw.includes('deadline')) {
    return {
      why: 'Network connection timed out while fetching data.',
      how: 'Check your internet connection and retry the operation.'
    }
  }
  if (raw.includes('invalid DOI')) {
    return {
      why: 'The DOI string is improperly formatted or missing digits.',
      how: 'Ensure the DOI follows standard format (e.g. 10.1038/s41586-020-2649-2) with no invalid characters.'
    }
  }
  return {
    why: raw,
    how: 'Retry the operation, check ⚙ Settings for proxy/email options, or open the publisher page directly.'
  }
}

// ─── App Component ───

export default function App() {
  const [allPapers, setAllPapers] = useState<Paper[]>([])
  const [displayedPapers, setDisplayedPapers] = useState<Paper[]>([])
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null)
  const [selectedDOIs, setSelectedDOIs] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [sortBy, setSortBy] = useState<string>('default')
  
  const [addDOIInput, setAddDOIInput] = useState('')
  const [isAdding, setIsAdding] = useState(false)
  const [isFetchingSnowball, setIsFetchingSnowball] = useState<'references' | 'citations' | null>(null)
  const [isDownloadingBatch, setIsDownloadingBatch] = useState(false)
  const [isDownloadingSingle, setIsDownloadingSingle] = useState<string | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [showAppInfo, setShowAppInfo] = useState(false)
  const [showClearConfirm, setShowClearConfirm] = useState(false)
  const [selectedCitationStyle, setSelectedCitationStyle] = useState<string>('APA')
  const [theme, setTheme] = useState<ThemeName>(() => {
    return (localStorage.getItem('litnexus_theme') as ThemeName) || 'dark'
  })

  // Download progress tracking
  const [batchProgress, setBatchProgress] = useState<{
    active: boolean; completed: number; total: number; percent: number; currentDOI: string;
    failures: Array<{doi: string; error: string}>;
  }>({ active: false, completed: 0, total: 0, percent: 0, currentDOI: '', failures: [] })
  const [showBatchSummary, setShowBatchSummary] = useState(false)
  
  // QoL States
  const [clipboardDOI, setClipboardDOI] = useState<string | null>(null)

  // Toast system (typed)
  const [toasts, setToasts] = useState<ToastItem[]>([])

  // Activity log
  const [logEntries, setLogEntries] = useState<LogEntry[]>([])
  const [showLog, setShowLog] = useState(false)
  const logEndRef = useRef<HTMLDivElement>(null)

  // Onboarding
  const [showOnboarding, setShowOnboarding] = useState(false)

  // Navigation stack for breadcrumbs
  const [navStack, setNavStack] = useState<NavStep[]>([
    { id: 'root', label: 'Root Workspace', mode: 'all' }
  ])

  // Current paper's local references & citations count
  const [refCount, setRefCount] = useState<number>(0)
  const [citCount, setCitCount] = useState<number>(0)

  const [settings, setSettings] = useState<AppSettings>({
    unpaywall_email: '',
    institutional_proxy: '',
    output_directory: 'C:\\Users\\User\\Downloads\\LitNexus_PDFs',
    verify_ssl: true,
    ui_mode: 'research'
  })

  // ─── Toast System ───

  const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info' = 'success') => {
    const id = ++_toastId
    setToasts(prev => [...prev.slice(-4), { id, message, type }]) // Keep max 5
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, type === 'error' ? 5000 : 3000) // Errors stay longer
  }

  // ─── Activity Log ───

  const addLog = (level: LogEntry['level'], category: string, message: string, detail?: string) => {
    const entry: LogEntry = {
      id: ++_logId,
      timestamp: new Date(),
      level,
      category,
      message,
      detail,
    }
    setLogEntries(prev => [...prev.slice(-499), entry]) // Keep max 500
  }

  // ─── Theme System ───

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('litnexus_theme', theme)
  }, [theme])

  // ─── Loading Cursor ───

  useEffect(() => {
    const isBusy = isAdding || !!isFetchingSnowball || isDownloadingBatch || !!isDownloadingSingle
    if (isBusy) {
      document.documentElement.classList.add('app-busy')
    } else {
      document.documentElement.classList.remove('app-busy')
    }
    return () => document.documentElement.classList.remove('app-busy')
  }, [isAdding, isFetchingSnowball, isDownloadingBatch, isDownloadingSingle])

  // ─── Onboarding check ───

  useEffect(() => {
    const onboarded = localStorage.getItem('litnexus_onboarded')
    if (!onboarded) {
      setShowOnboarding(true)
    }
  }, [])

  // ─── Initial Load (Mount Only) ───

  useEffect(() => {
    loadWorkspace()
    loadSettings()
    addLog('info', 'System', 'LitNexus started')
  }, [])

  // ─── Window Focus Clipboard DOI Check ───

  const allPapersRef = useRef<Paper[]>([])
  useEffect(() => {
    allPapersRef.current = allPapers
  }, [allPapers])

  useEffect(() => {
    const checkClipboard = async () => {
      if (wails?.ReadClipboard) {
        try {
          const text: string = await wails.ReadClipboard()
          if (text && text.trim()) {
            const match = text.match(/\b(10\.\d{4,9}\/[-._;()/:A-Z0-9]+)\b/i)
            if (match && match[1]) {
              const detected = match[1]
              if (!allPapersRef.current.some(p => p.doi.toLowerCase() === detected.toLowerCase())) {
                setClipboardDOI(detected)
              }
            }
          }
        } catch (e) {}
      }
    }

    window.addEventListener('focus', checkClipboard)
    return () => window.removeEventListener('focus', checkClipboard)
  }, [])

  // ─── Wails Download Event Listeners ───

  useEffect(() => {
    const cancelBatchStart = EventsOn('batch-download-start', (data: any) => {
      setBatchProgress({ active: true, completed: 0, total: data.total || 0, percent: 0, currentDOI: '', failures: [] })
      addLog('info', 'Download', `Batch download started: ${data.total || 0} papers`)
    })
    const cancelBatchProgress = EventsOn('batch-download-progress', (data: any) => {
      setBatchProgress(prev => {
        const failures = data.status === 'failed' && data.error
          ? [...prev.failures, { doi: data.doi, error: data.error }]
          : prev.failures
        return {
          ...prev, completed: data.completed, total: data.total, percent: data.percent || 0,
          currentDOI: data.doi, failures,
        }
      })
      // Update individual paper status in list
      if (data.doi && data.status) {
        setAllPapers(prev => prev.map(p => p.doi === data.doi
          ? { ...p, pdf_status: data.status === 'downloaded' ? 'downloaded' : data.status, pdf_status_reason: data.error || '' } : p
        ))
        if (data.status === 'downloaded') {
          addLog('success', 'Download', `Downloaded: ${data.doi}`, data.filename)
        } else if (data.status === 'failed') {
          addLog('error', 'Download', `Failed: ${data.doi}`, data.error)
        }
      }
    })
    const cancelBatchComplete = EventsOn('batch-download-complete', (_data: any) => {
      setBatchProgress(prev => {
        const failCount = prev.failures.length
        const successCount = prev.total - failCount
        addLog(failCount > 0 ? 'warning' : 'success', 'Download', 
          `Batch complete: ${successCount} downloaded, ${failCount} failed out of ${prev.total}`)
        if (failCount > 0) {
          setShowBatchSummary(true)
        }
        return { ...prev, active: false }
      })
      loadWorkspace() // Refresh full list
    })
    const cancelSingleStart = EventsOn('download-start', (data: any) => {
      if (data?.doi) setIsDownloadingSingle(data.doi)
    })
    const cancelSingleComplete = EventsOn('download-complete', (data: any) => {
      setIsDownloadingSingle(null)
      if (data?.doi) {
        setAllPapers(prev => prev.map(p => p.doi === data.doi
          ? { ...p, pdf_status: data.status || p.pdf_status, pdf_status_reason: data.error || '' } : p
        ))
      }
    })
    return () => {
      cancelBatchStart(); cancelBatchProgress(); cancelBatchComplete();
      cancelSingleStart(); cancelSingleComplete();
    }
  }, [])

  // ─── Update Displayed Papers ───

  useEffect(() => {
    applyCurrentNavStep(navStack[navStack.length - 1])
  }, [navStack, allPapers, searchQuery, filterStatus, sortBy])

  // ─── Update Counts ───

  useEffect(() => {
    if (selectedPaper) {
      updatePaperCounts(selectedPaper.doi)
    } else {
      setRefCount(0)
      setCitCount(0)
    }
  }, [selectedPaper, allPapers])

  // Auto-scroll log
  useEffect(() => {
    if (showLog && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logEntries, showLog])

  // ─── Data Loading ───

  const loadWorkspace = async () => {
    if (wails?.GetAllPapers) {
      try {
        const res: Paper[] = await wails.GetAllPapers()
        const papersList = res || []
        setAllPapers(papersList)
        if (papersList.length > 0 && !selectedPaper) {
          setSelectedPaper(papersList[0])
        }
      } catch (err) {
        addLog('error', 'System', 'Failed to load workspace papers', String(err))
      }
    }
  }

  const loadSettings = async () => {
    if (wails?.GetSettings) {
      try {
        const res: AppSettings = await wails.GetSettings()
        setSettings(res)
        addLog('info', 'System', 'Settings loaded')
      } catch (err) {
        addLog('error', 'System', 'Failed to load settings', String(err))
      }
    }
  }

  const updatePaperCounts = async (doi: string) => {
    if (wails?.GetPastReferences && wails?.GetFutureCitations) {
      try {
        const refs: Paper[] = await wails.GetPastReferences(doi)
        const cits: Paper[] = await wails.GetFutureCitations(doi)
        setRefCount(refs ? refs.length : 0)
        setCitCount(cits ? cits.length : 0)
      } catch (err) {
        console.error('Failed to update counts:', err)
      }
    }
  }

  const applyCurrentNavStep = async (step: NavStep) => {
    if (!step) return
    let baseList: Paper[] = []

    if (step.mode === 'all') {
      baseList = [...allPapers]
    } else if (step.mode === 'references' && step.targetDOI && wails?.GetPastReferences) {
      try {
        const refs: Paper[] = await wails.GetPastReferences(step.targetDOI)
        baseList = refs || []
      } catch (err) {
        console.error(err)
      }
    } else if (step.mode === 'citations' && step.targetDOI && wails?.GetFutureCitations) {
      try {
        const cits: Paper[] = await wails.GetFutureCitations(step.targetDOI)
        baseList = cits || []
      } catch (err) {
        console.error(err)
      }
    }

    // Filter Status
    if (filterStatus === 'downloaded') {
      baseList = baseList.filter(p => p.pdf_status === 'downloaded')
    } else if (filterStatus === 'failed') {
      baseList = baseList.filter(p => p.pdf_status === 'failed')
    } else if (filterStatus === 'abstract') {
      baseList = baseList.filter(p => p.abstract && p.abstract.trim().length > 0)
    } else if (filterStatus === 'root') {
      baseList = baseList.filter(p => p.generation === 0)
    }

    // Filter Search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      baseList = baseList.filter(p => 
        p.title.toLowerCase().includes(q) ||
        p.doi.toLowerCase().includes(q) ||
        p.authors.toLowerCase().includes(q)
      )
    }

    // Sorting
    if (sortBy === 'year_desc') {
      baseList.sort((a, b) => b.year - a.year)
    } else if (sortBy === 'year_asc') {
      baseList.sort((a, b) => a.year - b.year)
    } else if (sortBy === 'title') {
      baseList.sort((a, b) => a.title.localeCompare(b.title))
    }

    setDisplayedPapers(baseList)
  }

  // ─── Navigation ───

  const pushNavStep = (step: NavStep) => {
    setNavStack(prev => [...prev, step])
  }

  const popNavStep = () => {
    if (navStack.length > 1) {
      setNavStack(prev => prev.slice(0, prev.length - 1))
    }
  }

  const jumpToNavStep = (index: number) => {
    if (index >= 0 && index < navStack.length) {
      setNavStack(prev => prev.slice(0, index + 1))
    }
  }

  // ─── Clipboard ───

  const copyText = async (text: string, label: string) => {
    if (wails?.CopyToClipboard) {
      await wails.CopyToClipboard(text)
      showToast(`Copied ${label} to clipboard!`, 'success')
    } else {
      navigator.clipboard.writeText(text)
      showToast(`Copied ${label} to clipboard!`, 'success')
    }
  }

  // ─── Core Actions ───

  const handleAddDOI = async (rawDOI: string) => {
    if (!rawDOI.trim()) return
    setIsAdding(true)
    addLog('info', 'Paper', `Adding DOI: ${rawDOI.trim()}`)
    try {
      if (wails?.AddDOI) {
        const newPaper: Paper = await wails.AddDOI(rawDOI.trim())
        setAddDOIInput('')
        setClipboardDOI(null)
        await loadWorkspace()
        setSelectedPaper(newPaper)
        showToast(`Added paper: ${newPaper.title || newPaper.doi}`, 'success')
        addLog('success', 'Paper', `Added: ${newPaper.doi}`, newPaper.title)
      } else {
        const mock: Paper = {
          doi: rawDOI.trim(),
          title: `Paper for DOI ${rawDOI.trim()}`,
          authors: 'Smith et al.',
          year: 2024,
          abstract: 'This is a mock paper loaded in browser mode.',
          generation: 0,
          pdf_status: 'pending'
        }
        setAllPapers(prev => [mock, ...prev])
        setSelectedPaper(mock)
        setAddDOIInput('')
        setClipboardDOI(null)
      }
    } catch (err: any) {
      const errMsg = typeof err === 'string' ? err : err?.message || 'Unknown error'
      showToast(`Failed to add DOI: ${errMsg}`, 'error')
      addLog('error', 'Paper', `Failed to add DOI: ${rawDOI}`, errMsg)
    } finally {
      setIsAdding(false)
    }
  }

  const handleDownloadSingle = async (doi: string) => {
    setIsDownloadingSingle(doi)
    setAllPapers(prev => prev.map(p => p.doi === doi ? { ...p, pdf_status: 'downloading' } : p))
    addLog('info', 'Download', `Starting download: ${doi}`)
    try {
      if (wails?.DownloadPDF) {
        const result = await wails.DownloadPDF(doi)
        const reason = result?.error || result?.Error || ''
        const status = result?.status || result?.Status || 'failed'
        setAllPapers(prev => prev.map(p => p.doi === doi ? { ...p, pdf_status: status, pdf_status_reason: reason } : p))
        if (status === 'downloaded') {
          showToast(`Downloaded PDF for ${doi}`, 'success')
          addLog('success', 'Download', `Downloaded: ${doi}`, result?.filename)
        } else if (status === 'skipped') {
          showToast('PDF already exists locally', 'info')
          addLog('info', 'Download', `Skipped (already exists): ${doi}`)
        } else if (status === 'failed') {
          showToast(`Download failed: ${reason || 'No open-access PDF found'}`, 'error')
          addLog('error', 'Download', `Failed: ${doi}`, reason)
        }
        await loadWorkspace()
      } else {
        setTimeout(() => {
          setAllPapers(prev => prev.map(p => p.doi === doi ? { ...p, pdf_status: 'downloaded' } : p))
        }, 1500)
      }
    } catch (err: any) {
      const errMsg = typeof err === 'string' ? err : err?.message || 'Unknown error'
      setAllPapers(prev => prev.map(p => p.doi === doi ? { ...p, pdf_status: 'failed', pdf_status_reason: errMsg } : p))
      showToast(`Download failed: ${errMsg}`, 'error')
      addLog('error', 'Download', `Exception downloading ${doi}`, errMsg)
    } finally {
      setIsDownloadingSingle(null)
    }
  }

  const handleRowDoubleClick = (paper: Paper) => {
    setSelectedPaper(paper)
    if (paper.pdf_status === 'downloaded') {
      showToast('Opening PDF in default viewer...', 'info')
      if (wails?.OpenPDFFile) {
        wails.OpenPDFFile(paper.local_filepath || paper.doi)
      }
    } else if (paper.pdf_status === 'pending') {
      showToast(`Downloading PDF for ${paper.doi}...`, 'info')
      handleDownloadSingle(paper.doi)
    } else {
      showToast('Opening publisher page in browser...', 'info')
      if (wails?.OpenPDFFile) {
        wails.OpenPDFFile(paper.doi)
      } else {
        window.open(`https://doi.org/${paper.doi}`, '_blank')
      }
    }
  }

  const handleDownloadSelected = async () => {
    if (selectedDOIs.size === 0) return
    setIsDownloadingBatch(true)
    const doiArray = Array.from(selectedDOIs)
    addLog('info', 'Download', `Starting batch download: ${doiArray.length} papers`)
    try {
      if (wails?.DownloadBatchPDFs) {
        await wails.DownloadBatchPDFs(doiArray)
        await loadWorkspace()
      } else {
        setAllPapers(prev => prev.map(p => selectedDOIs.has(p.doi) ? { ...p, pdf_status: 'downloaded' } : p))
      }
      setSelectedDOIs(new Set())
    } catch (err: any) {
      const errMsg = typeof err === 'string' ? err : err?.message || 'Unknown error'
      showToast(`Batch download error: ${errMsg}`, 'error')
      addLog('error', 'Download', 'Batch download exception', errMsg)
    } finally {
      setIsDownloadingBatch(false)
    }
  }

  const handleFetchReferences = async () => {
    if (!selectedPaper) return
    const seed = selectedPaper
    setIsFetchingSnowball('references')
    addLog('info', 'Snowball', `Fetching references for: ${seed.doi}`)
    try {
      if (wails?.FetchPastReferences) {
        await wails.FetchPastReferences(seed.doi, seed.generation)
        await loadWorkspace()
        showToast('Fetched references from OpenAlex!', 'success')
        addLog('success', 'Snowball', `References fetched for: ${seed.doi}`)
        // Automatically switch view to fetched references
        pushNavStep({
          id: `ref-${seed.doi}`,
          label: `References of "${seed.title.slice(0, 24)}..."`,
          mode: 'references',
          targetDOI: seed.doi
        })
      }
    } catch (err: any) {
      const errMsg = typeof err === 'string' ? err : err?.message || 'Unknown error'
      showToast(`Failed to fetch references: ${errMsg}`, 'error')
      addLog('error', 'Snowball', `Failed to fetch references for: ${seed.doi}`, errMsg)
    } finally {
      setIsFetchingSnowball(null)
    }
  }

  const handleFetchCitations = async () => {
    if (!selectedPaper) return
    const seed = selectedPaper
    setIsFetchingSnowball('citations')
    addLog('info', 'Snowball', `Fetching citations for: ${seed.doi}`)
    try {
      if (wails?.FetchFutureCitations) {
        await wails.FetchFutureCitations(seed.doi, seed.generation)
        await loadWorkspace()
        showToast('Fetched citations from OpenAlex!', 'success')
        addLog('success', 'Snowball', `Citations fetched for: ${seed.doi}`)
        // Automatically switch view to fetched citations
        pushNavStep({
          id: `cit-${seed.doi}`,
          label: `Citations of "${seed.title.slice(0, 24)}..."`,
          mode: 'citations',
          targetDOI: seed.doi
        })
      }
    } catch (err: any) {
      const errMsg = typeof err === 'string' ? err : err?.message || 'Unknown error'
      showToast(`Failed to fetch citations: ${errMsg}`, 'error')
      addLog('error', 'Snowball', `Failed to fetch citations for: ${seed.doi}`, errMsg)
    } finally {
      setIsFetchingSnowball(null)
    }
  }

  const handleViewReferences = (paper: Paper) => {
    pushNavStep({
      id: `ref-${paper.doi}`,
      label: `References of "${paper.title.slice(0, 24)}..."`,
      mode: 'references',
      targetDOI: paper.doi
    })
  }

  const handleViewCitations = (paper: Paper) => {
    pushNavStep({
      id: `cit-${paper.doi}`,
      label: `Citations of "${paper.title.slice(0, 24)}..."`,
      mode: 'citations',
      targetDOI: paper.doi
    })
  }

  const handleCopyFormattedCitation = async (styleName?: string) => {
    if (!selectedPaper) return
    const style = styleName || selectedCitationStyle
    if (wails?.GenerateFormattedCitation) {
      try {
        const cite: string = await wails.GenerateFormattedCitation(
          selectedPaper.doi, selectedPaper.title, selectedPaper.authors, selectedPaper.year, style
        )
        copyText(cite, `${style} Citation`)
        return
      } catch (err) {
        console.error(err)
      }
    }
    if (style === 'BibTeX' && wails?.GenerateBibTeX) {
      const bib: string = await wails.GenerateBibTeX(
        selectedPaper.doi, selectedPaper.title, selectedPaper.authors, selectedPaper.year
      )
      copyText(bib, 'BibTeX Entry')
    } else if (style === 'RIS' && wails?.GenerateRIS) {
      const ris: string = await wails.GenerateRIS(
        selectedPaper.doi, selectedPaper.title, selectedPaper.authors, selectedPaper.year
      )
      copyText(ris, 'RIS Entry')
    } else {
      const cite = `${selectedPaper.authors} (${selectedPaper.year}). ${selectedPaper.title}. https://doi.org/${selectedPaper.doi}`
      copyText(cite, `${style} Citation`)
    }
  }

  const handleCopyAPA = () => handleCopyFormattedCitation('APA')
  const handleCopyBibTeX = () => handleCopyFormattedCitation('BibTeX')

  const handleExportWorkspaceBibTeX = async () => {
    if (wails?.ExportWorkspaceBibTeX) {
      const fullBib: string = await wails.ExportWorkspaceBibTeX()
      copyText(fullBib, `BibTeX for all ${allPapers.length} papers`)
      addLog('success', 'Export', `Exported BibTeX for ${allPapers.length} papers`)
    }
  }

  const handleImportFile = async () => {
    try {
      if (wails?.SelectAndImportFile) {
        const imported: string[] = await wails.SelectAndImportFile()
        if (imported && imported.length > 0) {
          showToast(`Successfully imported ${imported.length} DOI(s)!`, 'success')
          addLog('success', 'Import', `Imported ${imported.length} paper DOIs from citation file`)
          await loadWorkspace()
        }
      }
    } catch (err: any) {
      const errMsg = typeof err === 'string' ? err : err?.message || 'Failed to import file'
      showToast(errMsg, 'error')
      addLog('error', 'Import', 'File import failed', errMsg)
    }
  }

  const handleClearWorkspace = () => {
    setShowClearConfirm(true)
  }

  const confirmClearWorkspace = async () => {
    setShowClearConfirm(false)
    try {
      if (wails?.ClearWorkspace) {
        await wails.ClearWorkspace()
        setAllPapers([])
        setDisplayedPapers([])
        setSelectedPaper(null)
        setSelectedDOIs(new Set())
        setNavStack([{ id: 'root', label: 'Root Workspace', mode: 'all' }])
        showToast('Workspace cleared successfully!', 'success')
        addLog('warning', 'System', 'Workspace cleared — all papers and edges removed')
      }
    } catch (err: any) {
      const errMsg = typeof err === 'string' ? err : err?.message || 'Unknown error'
      showToast(`Failed to clear workspace: ${errMsg}`, 'error')
      addLog('error', 'System', 'Failed to clear workspace', errMsg)
    }
  }

  const handleDeletePaper = async (paper: Paper) => {
    try {
      if (wails?.DeletePaper) {
        await wails.DeletePaper(paper.doi)
        showToast(`Deleted paper: ${paper.title || paper.doi}`, 'success')
        addLog('info', 'Workspace', `Deleted paper ${paper.doi}`, paper.title)
        
        if (selectedPaper?.doi === paper.doi) {
          setSelectedPaper(null)
        }
        setSelectedDOIs(prev => {
          const next = new Set(prev)
          next.delete(paper.doi)
          return next
        })
        loadWorkspace()
      }
    } catch (err: any) {
      const errMsg = typeof err === 'string' ? err : err?.message || 'Failed to delete paper'
      showToast(`Delete failed: ${errMsg}`, 'error')
      addLog('error', 'Workspace', `Failed to delete paper ${paper.doi}`, errMsg)
    }
  }

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      if (wails?.SaveSettings) {
        await wails.SaveSettings(settings)
      }
      setShowSettings(false)
      showToast('Settings saved!', 'success')
      addLog('info', 'Settings', 'Application settings saved')
    } catch (err: any) {
      showToast(`Failed to save settings: ${err}`, 'error')
      addLog('error', 'Settings', 'Failed to save settings', String(err))
    }
  }

  const toggleSelectDOI = (doi: string) => {
    const next = new Set(selectedDOIs)
    if (next.has(doi)) next.delete(doi)
    else next.add(doi)
    setSelectedDOIs(next)
  }

  const dismissOnboarding = () => {
    setShowOnboarding(false)
    localStorage.setItem('litnexus_onboarded', 'true')
    addLog('info', 'System', 'Onboarding completed')
  }

  const clearLogs = () => {
    setLogEntries([])
    showToast('Activity log cleared', 'info')
  }

  // ─── Toast Rendering Helper ───

  const toastConfig = {
    success: { bg: 'bg-emerald-600 border-emerald-400/40', icon: <CheckCircle2 className="w-4 h-4 shrink-0" /> },
    error:   { bg: 'bg-rose-600 border-rose-400/40', icon: <XCircle className="w-4 h-4 shrink-0" /> },
    warning: { bg: 'bg-amber-600 border-amber-400/40', icon: <AlertTriangle className="w-4 h-4 shrink-0" /> },
    info:    { bg: 'bg-indigo-600 border-indigo-400/40', icon: <Info className="w-4 h-4 shrink-0" /> },
  }

  const logLevelConfig = {
    info:    { color: 'text-blue-400', bg: 'bg-blue-950/30', icon: <Info className="w-3 h-3" /> },
    success: { color: 'text-emerald-400', bg: 'bg-emerald-950/30', icon: <CheckCircle2 className="w-3 h-3" /> },
    warning: { color: 'text-amber-400', bg: 'bg-amber-950/30', icon: <AlertTriangle className="w-3 h-3" /> },
    error:   { color: 'text-rose-400', bg: 'bg-rose-950/30', icon: <XCircle className="w-3 h-3" /> },
  }

  // ─── Render ───

  return (
    <div className="flex flex-col h-screen overflow-hidden relative"
      style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)' }}
    >
      {/* ─── Toast Notifications ─── */}
      <div className="fixed top-16 left-1/2 z-[60] flex flex-col items-center space-y-2 pointer-events-none" style={{ transform: 'translateX(-50%)' }}>
        {toasts.map(toast => {
          const cfg = toastConfig[toast.type]
          return (
            <div key={toast.id}
              className={`toast-enter ${cfg.bg} text-white px-4 py-2 rounded-xl shadow-2xl font-medium text-xs flex items-center space-x-2 border pointer-events-auto`}
            >
              {cfg.icon}
              <span>{toast.message}</span>
              <button onClick={() => setToasts(prev => prev.filter(t => t.id !== toast.id))} className="ml-1 opacity-60 hover:opacity-100">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )
        })}
      </div>

      {/* ─── Auto Clipboard DOI Detection Banner ─── */}
      {clipboardDOI && (
        <div className="border-b px-6 py-2 flex items-center justify-between z-20 text-xs shadow-lg"
          style={{ background: 'linear-gradient(to right, rgba(79, 70, 229, 0.15), rgba(139, 92, 246, 0.15))', borderColor: 'var(--border-secondary)' }}
        >
          <div className="flex items-center space-x-2">
            <ClipboardCheck className="w-4 h-4 text-indigo-300 animate-pulse" />
            <span className="font-medium" style={{ color: 'var(--text-primary)' }}>Detected DOI in clipboard:</span>
            <span className="font-mono text-indigo-300 font-semibold">{clipboardDOI}</span>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handleAddDOI(clipboardDOI)}
              className="bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-semibold px-3 py-1 rounded-md shadow transition-all"
            >
              + Click to Import DOI
            </button>
            <button
              onClick={() => setClipboardDOI(null)}
              className="text-[var(--text-muted)] hover:text-[var(--text-primary)] text-[11px] px-2"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* ─── Top Header ─── */}
      <header className="h-16 border-b backdrop-blur-md flex items-center justify-between px-6 z-10"
        style={{ backgroundColor: 'var(--header-bg)', borderColor: 'var(--border-primary)' }}
      >
        <div className="flex items-center space-x-3" title="LitNexus Academic Literature Hub">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <BookOpen className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-indigo-300 bg-clip-text text-transparent">LitNexus</h1>
            <p className="text-[10px] font-medium" style={{ color: 'var(--text-muted)' }}>Open Access Literature Hub</p>
          </div>
        </div>

        {/* Add DOI & Quick Controls */}
        <div className="flex items-center space-x-3">
          <form onSubmit={(e) => { e.preventDefault(); handleAddDOI(addDOIInput); }} className="flex items-center rounded-lg p-1 border focus-within:border-indigo-500 transition-colors"
            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-secondary)' }}
          >
            <input 
              type="text"
              placeholder="Paste DOI (e.g., 10.1038/s41586-020-2649-2)"
              title="Enter a DOI (e.g. 10.1038/s41586-020-2649-2) to fetch metadata and add paper"
              value={addDOIInput}
              onChange={(e) => setAddDOIInput(e.target.value)}
              className="bg-transparent text-xs placeholder-[var(--text-muted)] px-3 py-1.5 focus:outline-none w-72"
              style={{ color: 'var(--text-primary)' }}
            />
            <button 
              type="submit"
              disabled={isAdding}
              title="Fetch paper metadata online and add to workspace"
              className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-3 py-1.5 rounded-md font-medium flex items-center space-x-1 transition-all disabled:opacity-50"
            >
              {isAdding ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
              <span>Add DOI</span>
            </button>
          </form>

          {/* Import File Button */}
          <button
            onClick={handleImportFile}
            title="Bulk-import DOIs from BibTeX, RIS, XML, JSON, CSV, or TXT files"
            className="border text-xs px-3 py-2 rounded-lg font-medium flex items-center space-x-1.5 transition-all hover:opacity-80"
            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-secondary)', color: 'var(--text-primary)' }}
          >
            <FileUp className="w-4 h-4 text-emerald-400" />
            <span>Import File</span>
          </button>

          {/* Export BibTeX Button */}
          <button
            onClick={handleExportWorkspaceBibTeX}
            title="Export all workspace papers to a single BibTeX reference file"
            className="border text-xs px-3 py-2 rounded-lg font-medium flex items-center space-x-1.5 transition-all hover:opacity-80"
            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-secondary)', color: 'var(--text-primary)' }}
          >
            <Code className="w-4 h-4 text-indigo-400" />
            <span>Export BibTeX</span>
          </button>

          {/* Clear Workspace Button */}
          {allPapers.length > 0 && (
            <button
              onClick={handleClearWorkspace}
              title="Clear all papers and citation edges from local database"
              className="border text-xs px-3 py-2 rounded-lg font-medium flex items-center space-x-1.5 transition-all hover:bg-rose-950/60 hover:text-rose-300"
              style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-secondary)', color: 'var(--text-muted)' }}
            >
              <Trash2 className="w-4 h-4" />
              <span>Clear Grid</span>
            </button>
          )}

          {selectedDOIs.size > 0 && (
            <button
              onClick={handleDownloadSelected}
              disabled={isDownloadingBatch}
              title="Download open-access PDFs concurrently for all checked papers"
              className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs px-3.5 py-2 rounded-lg font-medium flex items-center space-x-1.5 shadow-lg shadow-emerald-600/20 transition-all"
            >
              {isDownloadingBatch ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              <span>Download Selected ({selectedDOIs.size})</span>
            </button>
          )}

          {/* Theme Switcher */}
          <div className="flex items-center rounded-lg border overflow-hidden"
            style={{ borderColor: 'var(--border-secondary)' }}
          >
            {THEME_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setTheme(opt.value)}
                title={`Switch to ${opt.label} theme`}
                className={`p-2 transition-all ${
                  theme === opt.value
                    ? 'bg-indigo-600 text-white'
                    : 'hover:opacity-80'
                }`}
                style={theme !== opt.value ? { backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-muted)' } : {}}
              >
                {opt.icon}
              </button>
            ))}
          </div>

          {/* Activity Log Toggle */}
          <button 
            onClick={() => setShowLog(!showLog)}
            title="Toggle activity log panel"
            className={`p-2 border rounded-lg transition-colors relative ${showLog ? 'bg-indigo-600 text-white border-indigo-500' : ''}`}
            style={!showLog ? { backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-secondary)', color: 'var(--text-muted)' } : {}}
          >
            <ScrollText className="w-4 h-4" />
            {logEntries.some(e => e.level === 'error') && !showLog && (
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-rose-500 rounded-full border-2" style={{ borderColor: 'var(--bg-primary)' }} />
            )}
          </button>

          {/* Help / Onboarding Button */}
          <button 
            onClick={() => setShowOnboarding(true)}
            title="Show quick start guide"
            className="p-2 border rounded-lg transition-colors hover:opacity-80"
            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-secondary)', color: 'var(--text-muted)' }}
          >
            <HelpCircle className="w-4 h-4" />
          </button>

          <button 
            onClick={() => setShowSettings(true)}
            title="Open application settings (Unpaywall email, library proxy, download path)"
            className="p-2 border rounded-lg transition-colors hover:opacity-80"
            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-secondary)', color: 'var(--text-muted)' }}
          >
            <SettingsIcon className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* ─── Main Split-Pane Workspace ─── */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Data Grid Pane */}
        <div className="flex-1 flex flex-col border-r overflow-hidden"
          style={{ borderColor: 'var(--border-primary)', backgroundColor: 'var(--bg-secondary)' }}
        >
          
          {/* Breadcrumb Navigation Trail Bar */}
          <div className="px-4 py-2.5 border-b flex items-center justify-between text-xs"
            style={{ borderColor: 'var(--border-secondary)', backgroundColor: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}
          >
            <div className="flex items-center space-x-2 overflow-x-auto">
              {navStack.length > 1 && (
                <button
                  onClick={popNavStep}
                  title="Navigate back to previous discovery tree level"
                  className="p-1 text-indigo-400 hover:text-indigo-300 rounded transition-colors flex items-center space-x-1 text-[11px] font-semibold pr-2"
                  style={{ backgroundColor: 'transparent' }}
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Back</span>
                </button>
              )}

              <div className="flex items-center space-x-1 font-medium text-[11px]">
                {navStack.map((step, idx) => (
                  <React.Fragment key={step.id}>
                    {idx > 0 && <ChevronRight className="w-3 h-3" style={{ color: 'var(--text-muted)' }} />}
                    <button
                      onClick={() => jumpToNavStep(idx)}
                      title={`Jump directly to ${step.label}`}
                      className={`px-2 py-0.5 rounded transition-colors ${
                        idx === navStack.length - 1 
                          ? 'bg-indigo-950/80 text-indigo-300 font-semibold border border-indigo-800/40' 
                          : 'hover:opacity-80'
                      }`}
                      style={idx !== navStack.length - 1 ? { color: 'var(--text-muted)' } : {}}
                    >
                      {step.label}
                    </button>
                  </React.Fragment>
                ))}
              </div>
            </div>

            <div className="text-[11px] font-mono" style={{ color: 'var(--text-muted)' }} title="Total paper count vs currently filtered papers">
              Showing {displayedPapers.length} of {allPapers.length} total
            </div>
          </div>

          {/* Search, Filter & Sort Bar */}
          <div className="p-3 border-b flex items-center justify-between gap-3"
            style={{ borderColor: 'var(--border-secondary)', backgroundColor: 'var(--bg-primary)' }}
          >
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-2.5" style={{ color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Search papers by title, DOI, author..."
                title="Filter papers by title keywords, DOI, or author name"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full border rounded-lg pl-9 pr-4 py-1.5 text-xs focus:outline-none focus:border-indigo-500"
                style={{ backgroundColor: 'var(--bg-input)', borderColor: 'var(--border-primary)', color: 'var(--text-primary)' }}
              />
            </div>

            {/* Filter Dropdown */}
            <div className="flex items-center space-x-1 text-xs" title="Filter grid by PDF download status or seed generation">
              <Filter className="w-3.5 h-3.5" style={{ color: 'var(--text-muted)' }} />
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="border rounded-lg px-2 py-1.5 text-xs focus:outline-none"
                style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-primary)', color: 'var(--text-secondary)' }}
              >
                <option value="all">All Papers</option>
                <option value="downloaded">Downloaded Only</option>
                <option value="failed">Failed Only</option>
                <option value="abstract">Has Abstract</option>
                <option value="root">Gen 0 (Seed) Only</option>
              </select>
            </div>

            {/* Sort Dropdown */}
            <div className="flex items-center space-x-1 text-xs" title="Sort papers by publication year or title">
              <ArrowUpDown className="w-3.5 h-3.5" style={{ color: 'var(--text-muted)' }} />
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="border rounded-lg px-2 py-1.5 text-xs focus:outline-none"
                style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-primary)', color: 'var(--text-secondary)' }}
              >
                <option value="default">Default Order</option>
                <option value="year_desc">Year (Newest First)</option>
                <option value="year_asc">Year (Oldest First)</option>
                <option value="title">Title (A-Z)</option>
              </select>
            </div>
          </div>

          {/* Data Table */}
          <div className="flex-1 overflow-y-auto">
            {displayedPapers.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center p-8 text-center" style={{ color: 'var(--text-muted)' }}>
                <BookOpen className="w-12 h-12 mb-3 stroke-1" />
                <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>No papers match current filters</p>
                <p className="text-xs max-w-xs mt-1">Paste a DOI above or fetch references/citations for any paper to expand the graph.</p>
              </div>
            ) : (
              <table className="w-full text-left border-collapse table-fixed">
                <thead>
                  <tr className="border-b text-[11px] font-semibold uppercase tracking-wider"
                    style={{ borderColor: 'var(--border-primary)', color: 'var(--text-muted)', backgroundColor: 'var(--bg-secondary)' }}
                  >
                    <th className="p-3 w-10 text-center">
                      <input 
                        type="checkbox"
                        checked={selectedDOIs.size === displayedPapers.length && displayedPapers.length > 0}
                        onChange={(e) => {
                          if (e.target.checked) setSelectedDOIs(new Set(displayedPapers.map(p => p.doi)))
                          else setSelectedDOIs(new Set())
                        }}
                        className="rounded border-slate-700 bg-slate-800 text-indigo-600 focus:ring-0"
                      />
                    </th>
                    <th className="p-3">Title / DOI</th>
                    <th className="p-3 w-36">Authors</th>
                    <th className="p-3 w-16 text-center">Year</th>
                    <th className="p-3 w-20 text-center">Gen</th>
                    <th className="p-3 w-28 text-center">Status</th>
                    <th className="p-3 w-16 text-center">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y text-xs" style={{ '--tw-divide-opacity': '0.4', borderColor: 'var(--border-secondary)' } as any}>
                  {displayedPapers.map((paper) => {
                    const isSelected = selectedPaper?.doi === paper.doi
                    return (
                      <tr
                        key={paper.doi}
                        onClick={() => setSelectedPaper(paper)}
                        onDoubleClick={() => handleRowDoubleClick(paper)}
                        title="Double-click to open PDF (or download if pending)"
                        className={`group cursor-pointer transition-colors ${
                          isSelected ? 'bg-indigo-950/40 border-l-2 border-indigo-500' : 'hover:opacity-90'
                        }`}
                      >
                        <td className="p-3 text-center" onClick={(e) => e.stopPropagation()}>
                          <input 
                            type="checkbox"
                            checked={selectedDOIs.has(paper.doi)}
                            onChange={() => toggleSelectDOI(paper.doi)}
                            className="rounded border-slate-700 bg-slate-800 text-indigo-600 focus:ring-0"
                          />
                        </td>
                        <td className="p-3 pr-4 min-w-0">
                          <div className="font-medium flex items-center space-x-1.5 min-w-0" style={{ color: 'var(--text-primary)' }}>
                            {paper.abstract && paper.abstract.trim().length > 0 && (
                              <span title="Abstract Available" className="inline-flex items-center justify-center text-amber-400 bg-amber-950/60 p-0.5 rounded border border-amber-800/40 shrink-0">
                                <FileText className="w-3 h-3" />
                              </span>
                            )}
                            <span className="truncate min-w-0">{paper.title || 'Unknown Title'}</span>
                          </div>
                          <div 
                            onClick={(e) => { e.stopPropagation(); copyText(paper.doi, 'DOI'); }}
                            title="Click to copy DOI"
                            className="text-[11px] text-indigo-400/80 hover:text-indigo-300 font-mono mt-0.5 truncate flex items-center space-x-1 w-fit group/doi"
                          >
                            <span>{paper.doi}</span>
                            <Copy className="w-3 h-3 opacity-0 group-hover/doi:opacity-100 transition-opacity" />
                          </div>
                        </td>
                        <td className="p-3 truncate" style={{ color: 'var(--text-muted)' }}>
                          {paper.authors || 'Unknown'}
                        </td>
                        <td className="p-3 text-center font-mono" style={{ color: 'var(--text-muted)' }}>
                          {paper.year > 0 ? paper.year : '—'}
                        </td>
                        <td className="p-3 text-center">
                          <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border ${
                            paper.generation < 0 
                              ? 'bg-amber-950/40 text-amber-300 border-amber-800/40' 
                              : paper.generation > 0 
                                ? 'bg-indigo-950/40 text-indigo-300 border-indigo-800/40'
                                : 'text-slate-300 border-slate-700'
                          }`}
                          style={paper.generation === 0 ? { backgroundColor: 'var(--bg-tertiary)' } : {}}
                          >
                            Gen {paper.generation}
                          </span>
                        </td>
                        <td className="p-3 text-center">
                          {paper.pdf_status === 'downloaded' && (
                            <span className="inline-flex items-center space-x-1 text-emerald-400 bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-800/40 text-[10px]">
                              <CheckCircle2 className="w-3 h-3" />
                              <span>Downloaded</span>
                            </span>
                          )}
                          {paper.pdf_status === 'downloading' && (
                            <span className="inline-flex items-center space-x-1 text-amber-400 bg-amber-950/50 px-2 py-0.5 rounded border border-amber-800/40 text-[10px]">
                              <RefreshCw className="w-3 h-3 animate-spin" />
                              <span>Downloading</span>
                            </span>
                          )}
                          {paper.pdf_status === 'pending' && (
                            <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Pending</span>
                          )}
                          {paper.pdf_status === 'failed' && (() => {
                            const info = parseErrorDetail(paper.pdf_status_reason)
                            return (
                              <span 
                                title={`Reason: ${info.why}\nResolution: ${info.how}`}
                                className="inline-flex items-center space-x-1 text-rose-400 bg-rose-950/50 px-2 py-0.5 rounded border border-rose-800/40 text-[10px] cursor-help"
                              >
                                <AlertCircle className="w-3 h-3" />
                                <span>Failed</span>
                              </span>
                            )
                          })()}
                          {paper.pdf_status === 'skipped' && (
                            <span className="inline-flex items-center space-x-1 text-blue-400 bg-blue-950/50 px-2 py-0.5 rounded border border-blue-800/40 text-[10px]">
                              <Check className="w-3 h-3" />
                              <span>Exists</span>
                            </span>
                          )}
                        </td>
                        <td className="p-3 text-center" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-center space-x-1">
                            {paper.pdf_status === 'failed' ? (
                              <button
                                onClick={() => handleDownloadSingle(paper.doi)}
                                title={`Retry download — ${paper.pdf_status_reason || 'previous attempt failed'}`}
                                className="p-1.5 text-amber-400 hover:text-amber-300 hover:bg-amber-950/60 rounded transition-colors"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                              </button>
                            ) : paper.pdf_status === 'downloading' ? (
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" style={{ color: 'var(--text-muted)' }} />
                            ) : (
                              <button
                                onClick={() => handleDownloadSingle(paper.doi)}
                                title="Download open-access PDF"
                                className="p-1.5 hover:text-indigo-400 hover:bg-indigo-950/60 rounded transition-colors"
                                style={{ color: 'var(--text-muted)' }}
                              >
                                <Download className="w-3.5 h-3.5" />
                              </button>
                            )}
                            <button
                              onClick={() => handleDeletePaper(paper)}
                              title="Delete paper from workspace"
                              className="p-1.5 hover:text-rose-400 hover:bg-rose-950/60 rounded transition-colors"
                              style={{ color: 'var(--text-muted)' }}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* ─── Right Selected Paper Preview Panel ─── */}
        <div className="w-[440px] border-l flex flex-col overflow-hidden"
          style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-primary)' }}
        >
          {selectedPaper ? (
            <div className="flex-1 flex flex-col p-6 overflow-y-auto space-y-6">
              <div>
                <div className="flex items-center justify-between text-xs text-indigo-400 font-semibold mb-2">
                  <span className="flex items-center space-x-1">
                    <GitBranch className="w-3.5 h-3.5" />
                    <span>Gen {selectedPaper.generation} Node</span>
                  </span>
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-[11px] px-2 py-0.5 rounded" style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>{selectedPaper.year || 'N/A'}</span>
                    <button
                      onClick={() => handleDeletePaper(selectedPaper)}
                      title="Delete paper from workspace"
                      className="p-1 text-slate-400 hover:text-rose-400 hover:bg-rose-950/60 rounded transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
                <h2 className="text-lg font-bold leading-snug" style={{ color: 'var(--text-primary)' }}>{selectedPaper.title || 'Unknown Title'}</h2>
                <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>{selectedPaper.authors}</p>
                
                {/* Clickable DOI pill with copy */}
                <div 
                  onClick={() => copyText(selectedPaper.doi, 'DOI')}
                  title="Click to copy DOI"
                  className="mt-3 inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg border cursor-pointer font-mono text-xs text-indigo-300 transition-colors group hover:opacity-80"
                  style={{ backgroundColor: 'var(--bg-input)', borderColor: 'var(--border-primary)' }}
                >
                  <span style={{ color: 'var(--text-muted)' }}>DOI:</span>
                  <span>{selectedPaper.doi}</span>
                  <Copy className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-400 transition-colors" />
                </div>
              </div>

              {/* ─── Download Failure Banner ─── */}
              {selectedPaper.pdf_status === 'failed' && (() => {
                const info = parseErrorDetail(selectedPaper.pdf_status_reason)
                return (
                  <div className="bg-rose-950/40 border border-rose-800/50 rounded-xl p-4 space-y-3">
                    <div className="flex items-start space-x-2.5">
                      <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                      <div className="space-y-1.5 min-w-0">
                        <p className="text-xs font-bold text-rose-300">Download Failed</p>
                        <p className="text-[11px] text-rose-200/90 leading-normal">
                          <strong className="text-rose-300">Why: </strong>{info.why}
                        </p>
                        <p className="text-[11px] text-rose-300/90 leading-normal bg-rose-900/40 p-2 rounded-lg border border-rose-700/40">
                          <strong>💡 How to resolve: </strong>{info.how}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2 pt-1">
                      <button
                        onClick={() => handleDownloadSingle(selectedPaper.doi)}
                        className="bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold py-2 px-3 rounded-lg flex items-center space-x-1.5 transition-all shadow-md shadow-rose-600/20"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>Retry</span>
                      </button>
                      <button
                        onClick={() => setShowSettings(true)}
                        className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium py-2 px-3 rounded-lg flex items-center space-x-1.5 transition-all border border-slate-700"
                      >
                        <SettingsIcon className="w-3.5 h-3.5 text-indigo-400" />
                        <span>Settings</span>
                      </button>
                      <a
                        href={`https://doi.org/${selectedPaper.doi}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-medium text-rose-300 hover:text-rose-200 underline underline-offset-2 ml-auto"
                      >
                        Publisher page →
                      </a>
                    </div>
                  </div>
                )
              })()}

              {/* Action Hero Buttons */}
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => handleDownloadSingle(selectedPaper.doi)}
                  disabled={isDownloadingSingle === selectedPaper.doi}
                  title="Download open-access PDF file for this paper"
                  className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold py-2.5 px-3 rounded-lg flex items-center justify-center space-x-2 shadow-lg shadow-indigo-600/20 transition-all disabled:opacity-50"
                >
                  {isDownloadingSingle === selectedPaper.doi ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Download className="w-4 h-4" />
                  )}
                  <span>{isDownloadingSingle === selectedPaper.doi ? 'Downloading...' : 'Download PDF'}</span>
                </button>

                {selectedPaper.local_filepath ? (
                  <button
                    onClick={() => wails?.OpenPDFFile(selectedPaper.local_filepath)}
                    title="Open downloaded PDF file in default OS application"
                    className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold py-2.5 px-3 rounded-lg flex items-center justify-center space-x-2 shadow-lg shadow-emerald-600/20 transition-all"
                  >
                    <FolderOpen className="w-4 h-4" />
                    <span>Open PDF</span>
                  </button>
                ) : (
                  <a
                    href={`https://doi.org/${selectedPaper.doi}`}
                    target="_blank"
                    rel="noreferrer"
                    title="Open publisher's official article webpage in default browser"
                    className="border text-xs font-semibold py-2.5 px-3 rounded-lg flex items-center justify-center space-x-2 transition-all hover:opacity-80"
                    style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-secondary)', color: 'var(--text-primary)' }}
                  >
                    <ExternalLink className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                    <span>View Publisher</span>
                  </a>
                )}
              </div>

              {/* Multi-Format Citation Manager Widget */}
              <div className="rounded-xl p-4 border space-y-3"
                style={{ backgroundColor: 'var(--bg-input)', borderColor: 'var(--border-primary)' }}
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold tracking-wider uppercase flex items-center space-x-1.5" style={{ color: 'var(--text-primary)' }}>
                    <Share2 className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Citation Generator</span>
                  </h3>
                  <select
                    value={selectedCitationStyle}
                    onChange={(e) => setSelectedCitationStyle(e.target.value)}
                    title="Select academic citation style format"
                    className="border rounded-lg text-xs px-2.5 py-1 focus:outline-none focus:border-indigo-500 font-medium"
                    style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-secondary)', color: 'var(--text-primary)' }}
                  >
                    <option value="APA">APA 7th</option>
                    <option value="MLA">MLA 9th</option>
                    <option value="Chicago">Chicago 17th</option>
                    <option value="Harvard">Harvard</option>
                    <option value="IEEE">IEEE</option>
                    <option value="Vancouver">Vancouver</option>
                    <option value="BibTeX">BibTeX (.bib)</option>
                    <option value="RIS">RIS (.ris)</option>
                  </select>
                </div>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handleCopyFormattedCitation(selectedCitationStyle)}
                    title={`Copy formatted reference in ${selectedCitationStyle} format to system clipboard`}
                    className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs py-2 px-3 rounded-lg flex items-center justify-center space-x-1.5 transition-all shadow-md shadow-indigo-600/20"
                  >
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copy {selectedCitationStyle} Reference</span>
                  </button>
                </div>

                {/* Quick Format Chips */}
                <div className="flex flex-wrap gap-1.5 pt-1 border-t" style={{ borderColor: 'var(--border-secondary)' }}>
                  {['APA', 'MLA', 'Chicago', 'IEEE', 'BibTeX', 'RIS'].map((st) => (
                    <button
                      key={st}
                      onClick={() => {
                        setSelectedCitationStyle(st)
                        handleCopyFormattedCitation(st)
                      }}
                      title={`Switch to ${st} format and copy citation to clipboard`}
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium transition-colors border ${
                        selectedCitationStyle === st
                          ? 'bg-indigo-950 text-indigo-300 border-indigo-700/60'
                          : 'hover:opacity-80'
                      }`}
                      style={selectedCitationStyle !== st ? { backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-secondary)', color: 'var(--text-muted)' } : {}}
                    >
                      {st}
                    </button>
                  ))}
                </div>
              </div>

              {/* Literature Graph Traversal Controls */}
              <div className="rounded-xl p-4 border space-y-4"
                style={{ backgroundColor: 'var(--bg-input)', borderColor: 'var(--border-primary)' }}
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold tracking-wider uppercase flex items-center space-x-1.5" style={{ color: 'var(--text-primary)' }}>
                    <Layers className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Literature Graph Navigation</span>
                  </h3>
                </div>

                {/* Section 1: References */}
                <div className="rounded-lg p-3 border space-y-2"
                  style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-primary)' }}
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-amber-300">References</span>
                    <span className="text-[11px] font-mono" style={{ color: 'var(--text-muted)' }} title="Number of reference papers stored locally vs total online citations">
                      {refCount} local{selectedPaper.external_reference_count ? ` • ${selectedPaper.external_reference_count} online` : ''}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <button
                      onClick={handleFetchReferences}
                      disabled={isFetchingSnowball !== null}
                      title="Fetch past references cited by this paper online via OpenAlex (Generation - 1)"
                      className="bg-amber-950/50 hover:bg-amber-900/60 border border-amber-800/50 text-amber-200 text-[11px] font-medium py-1.5 px-2 rounded-md flex items-center justify-center space-x-1 transition-colors disabled:opacity-50"
                    >
                      {isFetchingSnowball === 'references' ? <RefreshCw className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                      <span>Fetch Online</span>
                    </button>
                    <button
                      onClick={() => handleViewReferences(selectedPaper)}
                      disabled={refCount === 0}
                      title="Filter workspace grid to display local past references"
                      className="border text-[11px] font-medium py-1.5 px-2 rounded-md flex items-center justify-center space-x-1 transition-colors disabled:opacity-40 hover:opacity-80"
                      style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-secondary)', color: 'var(--text-primary)' }}
                    >
                      <ArrowLeft className="w-3 h-3 text-amber-400" />
                      <span>View Grid ({refCount})</span>
                    </button>
                  </div>
                </div>

                {/* Section 2: Citations */}
                <div className="rounded-lg p-3 border space-y-2"
                  style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-primary)' }}
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-indigo-300">Citations</span>
                    <span className="text-[11px] font-mono" style={{ color: 'var(--text-muted)' }} title="Number of citing papers stored locally vs total online citations">
                      {citCount} local{selectedPaper.external_citation_count ? ` • ${selectedPaper.external_citation_count} online` : ''}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <button
                      onClick={handleFetchCitations}
                      disabled={isFetchingSnowball !== null}
                      title="Fetch future citations citing this paper online via OpenAlex (Generation + 1)"
                      className="bg-indigo-950/50 hover:bg-indigo-900/60 border border-indigo-800/50 text-indigo-200 text-[11px] font-medium py-1.5 px-2 rounded-md flex items-center justify-center space-x-1 transition-colors disabled:opacity-50"
                    >
                      {isFetchingSnowball === 'citations' ? <RefreshCw className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                      <span>Fetch Online</span>
                    </button>
                    <button
                      onClick={() => handleViewCitations(selectedPaper)}
                      disabled={citCount === 0}
                      title="Filter workspace grid to display local future citations"
                      className="border text-[11px] font-medium py-1.5 px-2 rounded-md flex items-center justify-center space-x-1 transition-colors disabled:opacity-40 hover:opacity-80"
                      style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-secondary)', color: 'var(--text-primary)' }}
                    >
                      <ChevronRight className="w-3 h-3 text-indigo-400" />
                      <span>View Grid ({citCount})</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Abstract */}
              <div className="space-y-2">
                <h3 className="text-xs font-bold tracking-wider uppercase" style={{ color: 'var(--text-secondary)' }}>Abstract</h3>
                <p className="text-xs leading-relaxed p-4 rounded-xl border max-h-60 overflow-y-auto select-text"
                  style={{ backgroundColor: 'var(--bg-input)', borderColor: 'var(--border-secondary)', color: 'var(--text-muted)' }}
                >
                  {selectedPaper.abstract || 'No abstract available for this publication.'}
                </p>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center p-8 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
              Select a paper from the list to view metadata, download options, and citation graph.
            </div>
          )}
        </div>
      </div>

      {/* ─── Batch Download Progress Bar ─── */}
      {batchProgress.active && (
        <div className="border-t px-6 py-3 z-30"
          style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-primary)' }}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2 text-xs">
              <RefreshCw className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
              <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                Downloading {batchProgress.completed} of {batchProgress.total} ({batchProgress.percent}%)
              </span>
            </div>
            <div className="flex items-center space-x-3 text-[11px]">
              {batchProgress.failures.length > 0 && (
                <span className="text-rose-400 font-medium">{batchProgress.failures.length} failed</span>
              )}
              <span className="font-mono" style={{ color: 'var(--text-muted)' }}>
                {batchProgress.currentDOI && `Current: ${batchProgress.currentDOI.slice(0, 30)}...`}
              </span>
            </div>
          </div>
          <div className="w-full h-2 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--bg-tertiary)' }}>
            <div
              className="h-full rounded-full bg-gradient-to-r from-indigo-600 to-violet-500 progress-bar-fill"
              style={{ width: `${batchProgress.percent}%` }}
            />
          </div>
        </div>
      )}

      {/* ─── Batch Summary Modal ─── */}
      {showBatchSummary && batchProgress.failures.length > 0 && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="border rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4"
            style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-primary)' }}
          >
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold flex items-center space-x-2" style={{ color: 'var(--text-primary)' }}>
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                <span>Batch Download Summary</span>
              </h2>
              <button onClick={() => setShowBatchSummary(false)} className="p-1 rounded hover:opacity-80" style={{ color: 'var(--text-muted)' }}>
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="flex items-center space-x-4 text-sm">
              <span className="text-emerald-400 font-semibold">{batchProgress.total - batchProgress.failures.length} downloaded</span>
              <span className="text-rose-400 font-semibold">{batchProgress.failures.length} failed</span>
            </div>

            <div className="border rounded-lg overflow-hidden max-h-64 overflow-y-auto" style={{ borderColor: 'var(--border-secondary)' }}>
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-muted)' }}>
                    <th className="p-2 text-left font-semibold w-1/3">DOI</th>
                    <th className="p-2 text-left font-semibold w-1/3">Reason</th>
                    <th className="p-2 text-left font-semibold w-1/3">Suggested Resolution</th>
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: 'var(--border-secondary)' }}>
                  {batchProgress.failures.map((f, i) => {
                    const info = parseErrorDetail(f.error)
                    return (
                      <tr key={i} className="hover:bg-rose-950/20">
                        <td className="p-2 font-mono text-indigo-400 truncate max-w-[140px]" title={f.doi}>{f.doi}</td>
                        <td className="p-2 text-rose-300 text-[11px] leading-tight">{info.why}</td>
                        <td className="p-2 text-amber-300 text-[11px] leading-tight">{info.how}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <button
              onClick={() => setShowBatchSummary(false)}
              className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2 rounded-lg transition-all"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* ─── Activity Log Panel ─── */}
      {showLog && (
        <div className="border-t flex flex-col max-h-64 z-20"
          style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-primary)' }}
        >
          <div className="flex items-center justify-between px-4 py-2 border-b"
            style={{ borderColor: 'var(--border-secondary)', backgroundColor: 'var(--bg-secondary)' }}
          >
            <div className="flex items-center space-x-2 text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
              <ScrollText className="w-3.5 h-3.5 text-indigo-400" />
              <span>Activity Log</span>
              <span className="font-mono text-[10px] px-1.5 py-0.5 rounded" style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-muted)' }}>{logEntries.length}</span>
            </div>
            <div className="flex items-center space-x-2">
              <button onClick={clearLogs} className="text-[11px] font-medium px-2 py-1 rounded hover:opacity-80 transition-colors" style={{ color: 'var(--text-muted)' }}>
                Clear
              </button>
              <button onClick={() => setShowLog(false)} className="p-1 rounded hover:opacity-80" style={{ color: 'var(--text-muted)' }}>
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto px-2 py-1 text-xs font-mono space-y-0.5">
            {logEntries.length === 0 ? (
              <div className="flex items-center justify-center h-full" style={{ color: 'var(--text-muted)' }}>
                No activity recorded yet.
              </div>
            ) : (
              logEntries.map(entry => {
                const cfg = logLevelConfig[entry.level]
                return (
                  <div key={entry.id} className={`flex items-start space-x-2 px-2 py-1 rounded ${cfg.bg}`}>
                    <span className="text-[10px] shrink-0 w-[60px]" style={{ color: 'var(--text-muted)' }}>
                      {entry.timestamp.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                    <span className={`shrink-0 mt-0.5 ${cfg.color}`}>{cfg.icon}</span>
                    <span className="text-[10px] shrink-0 font-semibold w-[60px] uppercase" style={{ color: 'var(--text-muted)' }}>
                      {entry.category}
                    </span>
                    <span className={`${cfg.color} text-[11px]`}>{entry.message}</span>
                    {entry.detail && (
                      <span className="text-[10px] truncate" style={{ color: 'var(--text-muted)' }}>— {entry.detail}</span>
                    )}
                  </div>
                )
              })
            )}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

      {/* ─── Settings Modal ─── */}
      {showSettings && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="border rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-5"
            style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-primary)' }}
          >
            <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>Application Settings</h2>
            <form onSubmit={handleSaveSettings} className="space-y-4 text-xs">
              <div>
                <label className="block font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Institutional Email</label>
                <input
                  type="email"
                  value={settings.unpaywall_email || ''}
                  onChange={(e) => setSettings({ ...settings, unpaywall_email: e.target.value })}
                  placeholder="your.name@university.edu"
                  className="w-full border rounded-lg p-2.5 focus:outline-none focus:border-indigo-500"
                  style={{ backgroundColor: 'var(--bg-input)', borderColor: 'var(--border-primary)', color: 'var(--text-primary)' }}
                />
                <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>Used for Unpaywall Open Access API & Crossref Polite API pool.</p>
              </div>

              <div>
                <label className="block font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Institutional EZProxy Gateway Prefix (Optional)</label>
                <input
                  type="text"
                  value={settings.institutional_proxy || ''}
                  onChange={(e) => setSettings({ ...settings, institutional_proxy: e.target.value })}
                  placeholder="https://ezproxy.lib.university.edu/login?url="
                  className="w-full border rounded-lg p-2.5 focus:outline-none focus:border-indigo-500 font-mono text-[11px]"
                  style={{ backgroundColor: 'var(--bg-input)', borderColor: 'var(--border-primary)', color: 'var(--text-primary)' }}
                />
                <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>Routes paywalled journal downloads through your university library proxy gateway.</p>
              </div>

              <div>
                <label className="block font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>PDF Download Output Directory</label>
                <input
                  type="text"
                  value={settings.output_directory || ''}
                  onChange={(e) => setSettings({ ...settings, output_directory: e.target.value })}
                  className="w-full border rounded-lg p-2.5 focus:outline-none focus:border-indigo-500 font-mono text-[11px]"
                  style={{ backgroundColor: 'var(--bg-input)', borderColor: 'var(--border-primary)', color: 'var(--text-primary)' }}
                />
              </div>
              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={() => setShowSettings(false)}
                  className="px-4 py-2 rounded-lg font-medium transition-colors hover:opacity-80"
                  style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold shadow-lg shadow-indigo-600/20"
                >
                  Save Settings
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── Onboarding / Welcome Guide Modal ─── */}
      {showOnboarding && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md flex items-center justify-center z-[70] p-4">
          <div className="border rounded-2xl w-full max-w-lg p-8 shadow-2xl space-y-6"
            style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-primary)' }}
          >
            {/* Header */}
            <div className="text-center space-y-2">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/30 mx-auto">
                <BookOpen className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Welcome to LitNexus</h2>
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Your open-access academic literature hub</p>
            </div>

            {/* Steps */}
            <div className="space-y-3">
              {[
                { step: '1', title: 'Add a Seed Paper', desc: 'Paste a DOI into the search bar at the top and click "Add DOI" to fetch its metadata.', icon: <Plus className="w-4 h-4" /> },
                { step: '2', title: 'Explore via Snowballing', desc: 'Select a paper and use "Fetch Online" to discover its references (backward) and citations (forward).', icon: <Layers className="w-4 h-4" /> },
                { step: '3', title: 'Select & Download', desc: 'Use checkboxes to select papers, then click "Download Selected" for batch PDF downloads.', icon: <Download className="w-4 h-4" /> },
                { step: '4', title: 'Cite & Export', desc: 'Generate citations in APA, MLA, BibTeX, and more. Export your entire workspace as BibTeX.', icon: <Share2 className="w-4 h-4" /> },
                { step: '5', title: 'Configure Settings', desc: 'Set your institutional email for API access and optionally configure an EZProxy gateway.', icon: <SettingsIcon className="w-4 h-4" /> },
              ].map(item => (
                <div key={item.step} className="flex items-start space-x-3 p-3 rounded-lg border"
                  style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-secondary)' }}
                >
                  <div className="w-8 h-8 rounded-lg bg-indigo-600/20 flex items-center justify-center text-indigo-400 shrink-0">
                    {item.icon}
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                      <span className="text-indigo-400 mr-1">{item.step}.</span>{item.title}
                    </p>
                    <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-muted)' }}>{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between pt-2">
              <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                You can reopen this guide anytime via the <HelpCircle className="w-3 h-3 inline" /> button.
              </p>
              <button
                onClick={dismissOnboarding}
                className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-6 py-2.5 rounded-lg shadow-lg shadow-indigo-600/20 transition-all text-sm"
              >
                Get Started
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Clear Workspace Confirmation Modal ─── */}
      {showClearConfirm && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-[70] flex items-center justify-center p-4">
          <div 
            className="w-full max-w-md border rounded-2xl p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in duration-150"
            style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-primary)', color: 'var(--text-primary)' }}
          >
            <div className="flex items-center space-x-3 text-rose-500">
              <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-semibold text-base">Clear Workspace?</h3>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>This action cannot be undone.</p>
              </div>
            </div>
            
            <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Are you sure you want to clear the workspace? This will permanently remove all <strong>{allPapers.length} paper(s)</strong> and citation relationships from the local database.
            </p>

            <div className="flex items-center justify-end space-x-3 pt-2">
              <button
                onClick={() => setShowClearConfirm(false)}
                className="px-4 py-2 text-xs rounded-lg font-medium border transition-colors hover:opacity-80"
                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-secondary)', color: 'var(--text-muted)' }}
              >
                Cancel
              </button>
              <button
                onClick={confirmClearWorkspace}
                className="px-4 py-2 text-xs rounded-lg font-medium bg-rose-600 hover:bg-rose-500 text-white transition-colors shadow-lg shadow-rose-600/20 flex items-center space-x-1.5"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Clear All Papers</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
