import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
    ArrowLeft,
    Clock,
    FileText,
    Brain,
    Upload,
    ScanText,
    Layers,
    Database,
    ShieldCheck,
    Rocket,
    RotateCcw,
    Trash2,
    CheckCircle2,
    AlertCircle,
    Loader2,
    Pause,
    Download,
    Circle,
    ExternalLink,
    BarChart3,
    Timer,
    Settings2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Progress } from '@/components/ui/progress'
import PipelineTracker from '@/components/PipelineTracker'
import { PIPELINE_STEPS } from '@/data/mockData'
import { apiClient } from '@/api/client'

const stepIcons = [Upload, ScanText, Layers, Database, ShieldCheck, Brain, Rocket]

const statusConfig = {
    running: { label: 'Running', className: 'bg-blue-500/15 text-blue-400 border-blue-500/30', icon: Loader2 },
    completed: { label: 'Complete', className: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30', icon: CheckCircle2 },
    complete: { label: 'Complete', className: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30', icon: CheckCircle2 },
    failed: { label: 'Error', className: 'bg-red-500/15 text-red-400 border-red-500/30', icon: AlertCircle },
    error: { label: 'Error', className: 'bg-red-500/15 text-red-400 border-red-500/30', icon: AlertCircle },
    pending: { label: 'Pending', className: 'bg-amber-500/15 text-amber-400 border-amber-500/30', icon: Pause },
}

const stepDetails = {
    complete: { duration: '2m 34s', output: 'Completed successfully' },
    running: { duration: 'In progress...', output: 'Processing data...' },
    error: { duration: '1m 12s', output: 'Failed: Check logs for details.' },
    pending: { duration: '—', output: 'Waiting for previous steps to complete' },
}

export default function ProjectDetailPage() {
    const { id } = useParams()
    const navigate = useNavigate()
    const [project, setProject] = useState(null)
    const [pipelineStatus, setPipelineStatus] = useState('NOT_STARTED')
    const [pipelineLogs, setPipelineLogs] = useState([])
    const [results, setResults] = useState(null)
    const [activeStep, setActiveStep] = useState(null)
    const [loading, setLoading] = useState(true)
    const [deleting, setDeleting] = useState(false)

    // ── Fetch project metadata ────────────────────────────────────────────────
    useEffect(() => {
        const fetchProject = async () => {
            try {
                const data = await apiClient.get(`projects/${id}`)
                setProject({
                    id: data.id,
                    name: data.name,
                    description: data.description,
                    status: data.status,
                    mode: data.mode,
                    createdAt: data.created_at,
                    model: data.base_model || 'Unknown',
                    intent: data.intent,
                })
            } catch (err) {
                console.error(err)
            } finally {
                setLoading(false)
            }
        }
        fetchProject()
    }, [id])

    // ── Poll status & logs ────────────────────────────────────────────────────
    useEffect(() => {
        if (!project) return

        const checkStatusAndLogs = async () => {
            try {
                const statusData = await apiClient.get(`projects/${id}/status`)
                setPipelineStatus(statusData.pipeline_status || 'NOT_STARTED')
                setProject(prev => ({ ...prev, status: statusData.project_status || prev.status }))

                const logsData = await apiClient.get(`projects/${id}/logs`)
                setPipelineLogs(logsData.logs || [])
            } catch (err) {
                console.error("Status/logs error", err)
            }
        }

        checkStatusAndLogs()

        let interval
        if (pipelineStatus === 'RUNNING') {
            interval = setInterval(checkStatusAndLogs, 5000)
        }

        return () => clearInterval(interval)
    }, [id, project?.id, pipelineStatus])

    // ── Fetch results when pipeline succeeds ──────────────────────────────────
    useEffect(() => {
        if (pipelineStatus !== 'SUCCEEDED') return

        const fetchResults = async () => {
            try {
                const data = await apiClient.get(`projects/${id}/results`)
                setResults(data)
            } catch (err) {
                console.error("Results fetch error", err)
            }
        }
        fetchResults()
    }, [id, pipelineStatus])

    // ── Delete project ────────────────────────────────────────────────────────
    const handleDelete = async () => {
        if (!confirm('Are you sure you want to delete this project? This cannot be undone.')) return
        try {
            setDeleting(true)
            await apiClient.delete(`projects/${id}`)
            navigate('/projects')
        } catch (err) {
            console.error('Delete error:', err)
            alert('Failed to delete project')
        } finally {
            setDeleting(false)
        }
    }

    // ── Derive pipeline progress array ────────────────────────────────────────
    const derivePipelineArr = () => {
        const arr = []
        const isRun = pipelineStatus === 'RUNNING'
        const isSuc = pipelineStatus === 'SUCCEEDED'
        const isErr = pipelineStatus === 'FAILED'

        for (let i = 0; i < 7; i++) {
            if (isSuc) {
                arr.push({ step: i + 1, status: 'complete', progress: 100 })
            } else if (isErr) {
                if (i === 3) arr.push({ step: i + 1, status: 'error', progress: 50 })
                else if (i < 3) arr.push({ step: i + 1, status: 'complete', progress: 100 })
                else arr.push({ step: i + 1, status: 'pending', progress: 0 })
            } else if (isRun) {
                if (i < 3) arr.push({ step: i + 1, status: 'complete', progress: 100 })
                else if (i === 3) arr.push({ step: i + 1, status: 'running', progress: 65 })
                else arr.push({ step: i + 1, status: 'pending', progress: 0 })
            } else {
                arr.push({ step: i + 1, status: 'pending', progress: 0 })
            }
        }
        return arr
    }

    // ── Loading / NotFound ────────────────────────────────────────────────────
    if (loading) {
        return <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>
    }

    if (!project) {
        return (
            <div className="flex flex-col items-center justify-center h-full py-20">
                <p className="text-lg font-medium">Project not found</p>
                <p className="text-sm text-muted-foreground mt-1 mb-4">The project you're looking for doesn't exist</p>
                <Button variant="outline" onClick={() => navigate('/projects')}>← Back to Projects</Button>
            </div>
        )
    }

    const pipelineArr = derivePipelineArr()
    const uiStatusKey = pipelineStatus === 'SUCCEEDED' ? 'completed' : pipelineStatus === 'FAILED' ? 'failed' : pipelineStatus === 'RUNNING' ? 'running' : 'pending'
    const status = statusConfig[uiStatusKey] || statusConfig.pending
    const StatusIcon = status?.icon || Clock
    const completedSteps = pipelineArr.filter(s => s.status === 'complete').length
    const overallProgress = Math.round((completedSteps / 7) * 100)
    const displayStep = activeStep !== null ? activeStep : Math.min(completedSteps, 6)
    const currentPipelineStep = pipelineArr[displayStep] || { status: 'pending', progress: 0 }
    const currentStepDef = PIPELINE_STEPS[displayStep]
    const StepIcon = stepIcons[displayStep] || Circle
    const detail = stepDetails[currentPipelineStep.status] || stepDetails.pending

    const timeAgo = (dateStr) => {
        if (!dateStr) return 'Just now'
        const diff = Date.now() - new Date(dateStr).getTime()
        const days = Math.floor(diff / (1000 * 60 * 60 * 24))
        if (days === 0) return 'Today'
        if (days === 1) return 'Yesterday'
        return `${days} days ago`
    }

    return (
        <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                <div className="flex items-start gap-3">
                    <Button variant="ghost" size="icon" className="h-8 w-8 mt-0.5" onClick={() => navigate('/projects')}>
                        <ArrowLeft className="w-4 h-4" />
                    </Button>
                    <div>
                        <div className="flex items-center gap-3">
                            <h1 className="text-2xl font-bold">{project.name}</h1>
                            <Badge variant="outline" className={`${status.className}`}>
                                <StatusIcon className={`w-3 h-3 mr-1 ${uiStatusKey === 'running' ? 'animate-spin' : ''}`} />
                                {status.label}
                            </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">{project.description}</p>
                    </div>
                </div>

                <div className="flex items-center gap-2 sm:shrink-0">
                    {uiStatusKey === 'failed' && (
                        <Button variant="outline" size="sm" className="gap-1.5">
                            <RotateCcw className="w-3.5 h-3.5" />
                            Retry
                        </Button>
                    )}
                    {results?.dataset_download_url && (
                        <Button
                            size="sm"
                            className="gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground"
                            onClick={() => window.open(results.dataset_download_url, '_blank')}
                        >
                            <Download className="w-3.5 h-3.5" />
                            Download Dataset
                        </Button>
                    )}
                    {uiStatusKey === 'completed' && (
                        <Button
                            variant="outline"
                            size="sm"
                            className="gap-1.5"
                            onClick={() => navigate(`/projects/${id}/dataset`)}
                        >
                            <Database className="w-3.5 h-3.5" />
                            Review Dataset
                        </Button>
                    )}
                    {uiStatusKey === 'completed' && (
                        <Button
                            size="sm"
                            className="gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground"
                            onClick={() => navigate(`/projects/${id}/compare`)}
                        >
                            <BarChart3 className="w-3.5 h-3.5" />
                            Compare Models
                        </Button>
                    )}
                    <Button
                        variant="outline"
                        size="sm"
                        className="gap-1.5 text-destructive hover:text-destructive"
                        onClick={handleDelete}
                        disabled={deleting}
                    >
                        {deleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                        Delete
                    </Button>
                </div>
            </div>

            {/* Project meta cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="rounded-lg border border-border bg-card px-4 py-3">
                    <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Model</p>
                    <p className="text-sm font-semibold mt-1 flex items-center gap-1.5">
                        <Brain className="w-3.5 h-3.5 text-primary" />
                        {project.model}
                    </p>
                </div>
                <div className="rounded-lg border border-border bg-card px-4 py-3">
                    <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Mode</p>
                    <p className="text-sm font-semibold mt-1 flex items-center gap-1.5">
                        <Settings2 className="w-3.5 h-3.5 text-primary" />
                        {project.mode?.replace(/_/g, ' ')}
                    </p>
                </div>
                <div className="rounded-lg border border-border bg-card px-4 py-3">
                    <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Created</p>
                    <p className="text-sm font-semibold mt-1 flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-primary" />
                        {timeAgo(project.createdAt)}
                    </p>
                </div>
                <div className="rounded-lg border border-border bg-card px-4 py-3">
                    <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Progress</p>
                    <p className="text-sm font-semibold mt-1">{completedSteps}/7 steps ({overallProgress}%)</p>
                </div>
            </div>

            {/* Pipeline Tracker */}
            <Card className="border-border bg-card">
                <CardHeader className="pb-4">
                    <CardTitle className="text-base">Pipeline Progress</CardTitle>
                </CardHeader>
                <CardContent>
                    <PipelineTracker
                        pipeline={pipelineArr}
                        activeStep={displayStep}
                        onStepClick={setActiveStep}
                    />
                </CardContent>
            </Card>

            {/* Step Detail Panel */}
            <Card className="border-border bg-card">
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${currentPipelineStep.status === 'complete'
                                ? 'bg-emerald-500/15' : currentPipelineStep.status === 'running'
                                    ? 'bg-primary/15' : currentPipelineStep.status === 'error'
                                        ? 'bg-red-500/15' : 'bg-muted'
                                }`}>
                                <StepIcon className={`w-4 h-4 ${currentPipelineStep.status === 'complete'
                                    ? 'text-emerald-400' : currentPipelineStep.status === 'running'
                                        ? 'text-primary' : currentPipelineStep.status === 'error'
                                            ? 'text-red-400' : 'text-muted-foreground'
                                    }`} />
                            </div>
                            <div>
                                <CardTitle className="text-base">Step {displayStep + 1}: {currentStepDef.name}</CardTitle>
                                <p className="text-xs text-muted-foreground mt-0.5">{currentStepDef.description}</p>
                            </div>
                        </div>
                        <Badge variant="outline" className={`text-[11px] ${(statusConfig[currentPipelineStep.status] || statusConfig.pending).className}`}>
                            {(statusConfig[currentPipelineStep.status] || statusConfig.pending).label}
                        </Badge>
                    </div>
                </CardHeader>
                <CardContent className="space-y-4">
                    {currentPipelineStep.status === 'running' && (
                        <div className="space-y-2">
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-muted-foreground">Progress</span>
                                <span className="font-mono text-primary">{currentPipelineStep.progress}%</span>
                            </div>
                            <Progress value={currentPipelineStep.progress} className="h-2" />
                        </div>
                    )}
                    <Separator />
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                        <div>
                            <p className="text-muted-foreground text-xs mb-1">Duration</p>
                            <p className="font-medium">{detail.duration}</p>
                        </div>
                        <div>
                            <p className="text-muted-foreground text-xs mb-1">Status</p>
                            <p className={`font-medium ${currentPipelineStep.status === 'error' ? 'text-red-400' : ''}`}>{detail.output}</p>
                        </div>
                    </div>
                    {currentPipelineStep.status === 'error' && (
                        <>
                            <Separator />
                            <div className="flex items-center gap-2">
                                <Button variant="outline" size="sm" className="gap-1.5">
                                    <RotateCcw className="w-3.5 h-3.5" />
                                    Retry This Step
                                </Button>
                            </div>
                        </>
                    )}
                </CardContent>
            </Card>

            {/* ── Results Panel ─────────────────────────────────────────────── */}
            {results && pipelineStatus === 'SUCCEEDED' && (
                <Card className="border-emerald-500/20 bg-card">
                    <CardHeader className="pb-3 border-b border-border">
                        <CardTitle className="text-base flex items-center gap-2">
                            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                            Pipeline Results
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-6 space-y-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                            {/* Dataset Download */}
                            {results.dataset_download_url && (
                                <div className="rounded-lg border border-border bg-background p-4 space-y-3">
                                    <div className="flex items-center gap-2 text-sm font-medium">
                                        <Database className="w-4 h-4 text-primary" />
                                        Training Dataset
                                    </div>
                                    <p className="text-xs text-muted-foreground">Clean JSONL file ready for fine-tuning</p>
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        className="w-full gap-1.5"
                                        onClick={() => window.open(results.dataset_download_url, '_blank')}
                                    >
                                        <Download className="w-3.5 h-3.5" />
                                        Download JSONL
                                    </Button>
                                </div>
                            )}

                            {/* Model Endpoint */}
                            {results.model_endpoint_url && (
                                <div className="rounded-lg border border-border bg-background p-4 space-y-3">
                                    <div className="flex items-center gap-2 text-sm font-medium">
                                        <Rocket className="w-4 h-4 text-primary" />
                                        Model Endpoint
                                    </div>
                                    <p className="text-xs text-muted-foreground font-mono break-all">{results.model_endpoint_url}</p>
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        className="w-full gap-1.5"
                                        onClick={() => navigator.clipboard.writeText(results.model_endpoint_url)}
                                    >
                                        <ExternalLink className="w-3.5 h-3.5" />
                                        Copy Endpoint
                                    </Button>
                                </div>
                            )}

                            {/* Training Metrics */}
                            {results.training_metrics && (
                                <div className="rounded-lg border border-border bg-background p-4 space-y-3">
                                    <div className="flex items-center gap-2 text-sm font-medium">
                                        <BarChart3 className="w-4 h-4 text-primary" />
                                        Training Metrics
                                    </div>
                                    <div className="space-y-2">
                                        {results.training_metrics.duration_min && (
                                            <div className="flex items-center justify-between text-xs">
                                                <span className="text-muted-foreground flex items-center gap-1"><Timer className="w-3 h-3" /> Duration</span>
                                                <span className="font-medium">{results.training_metrics.duration_min} min</span>
                                            </div>
                                        )}
                                        {results.training_metrics.final_loss != null && (
                                            <div className="flex items-center justify-between text-xs">
                                                <span className="text-muted-foreground">Final Loss</span>
                                                <span className="font-medium">{results.training_metrics.final_loss}</span>
                                            </div>
                                        )}
                                        {results.training_metrics.job_name && (
                                            <div className="flex items-center justify-between text-xs">
                                                <span className="text-muted-foreground">Job</span>
                                                <span className="font-medium truncate max-w-[150px]">{results.training_metrics.job_name}</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Execution Logs Viewer */}
            {pipelineStatus !== 'NOT_STARTED' && (
                <Card className="border-border bg-card mt-6">
                    <CardHeader className="pb-3 border-b border-border bg-muted/20">
                        <CardTitle className="text-sm font-semibold flex items-center gap-2 text-muted-foreground uppercase tracking-wider">
                            <Layers className="w-4 h-4" />
                            AWS Step Functions Execution Logs
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="max-h-80 overflow-y-auto bg-[#0d1117] text-[#c9d1d9] p-4 font-mono text-xs rounded-b-lg">
                            {pipelineLogs.length === 0 ? (
                                <div className="text-center text-muted-foreground italic py-10">No logs yet or waiting for pipeline to start...</div>
                            ) : (
                                pipelineLogs.map(log => (
                                    <div key={log.id} className="mb-2.5 last:mb-0 pb-2.5 border-b border-white/5 last:border-0 border-dashed">
                                        <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-3 mb-1">
                                            <span className="text-[#8b949e] shrink-0">
                                                {new Date(log.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date(log.timestamp).getMilliseconds().toString().padStart(3, '0')}
                                            </span>
                                            <span className={`font-semibold shrink-0 ${log.type.includes('Failed') ? 'text-[#ff7b72]' :
                                                log.type.includes('Succeeded') ? 'text-[#3fb950]' :
                                                    log.type.includes('Entered') ? 'text-[#58a6ff]' :
                                                        log.type.includes('Started') ? 'text-[#a5d6ff]' :
                                                            'text-[#d2a8ff]'
                                                }`}>
                                                [{log.type}]
                                            </span>
                                            <span className="text-[#79c0ff] truncate">
                                                {log.details?.name || log.details?.stateName || log.details?.resourceType || log.type}
                                            </span>
                                        </div>
                                        {(log.details?.error || log.details?.cause) && (
                                            <div className="mt-1 pl-4 border-l-2 border-[#ff7b72]/50 text-[#ff7b72] whitespace-pre-wrap">
                                                {log.details.error}
                                                {log.details.cause && `\n${log.details.cause}`}
                                            </div>
                                        )}
                                    </div>
                                ))
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    )
}
