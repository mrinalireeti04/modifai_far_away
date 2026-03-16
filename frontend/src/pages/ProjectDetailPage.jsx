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
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
    DialogClose,
} from '@/components/ui/dialog'
import PipelineTracker from '@/components/PipelineTracker'
import { getStepsForMode } from '@/data/mockData'
import { apiClient } from '@/api/client'

const stepIconMap = { Upload, ScanText, Layers, Database, ShieldCheck, Brain, Rocket }

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

// Build human-readable summary lines for each step's result data
function buildStepSummary(stepName, data) {
    if (!data || typeof data !== 'object') return []
    const lines = []

    switch (stepName) {
        case 'upload':
            if (data.raw_file_keys?.length) lines.push(`📁 ${data.raw_file_keys.length} file(s) uploaded`)
            break
        case 'ocr':
            if (data.files_processed != null) lines.push(`📄 ${data.files_processed} file(s) processed`)
            if (data.total_characters != null) lines.push(`✏️ ${data.total_characters.toLocaleString()} characters extracted`)
            if (data.files_failed > 0) lines.push(`⚠️ ${data.files_failed} file(s) failed`)
            if (data.errors?.length) {
                data.errors.forEach(e => lines.push(`❌ ${e.file}: ${e.error}`))
            }
            break
        case 'chunking':
            if (data.chunk_count != null) lines.push(`🧩 ${data.chunk_count} chunks created`)
            if (data.total_words != null) lines.push(`📝 ${data.total_words.toLocaleString()} total words`)
            break
        case 'generation':
            if (data.example_count != null) lines.push(`🤖 ${data.example_count} training examples generated`)
            if (data.chunks_processed != null) lines.push(`✅ ${data.chunks_processed} chunks processed`)
            if (data.chunks_failed > 0) lines.push(`⚠️ ${data.chunks_failed} chunks failed`)
            break
        case 'quality_control':
            if (data.total_input != null) lines.push(`📊 ${data.total_input} examples evaluated`)
            if (data.kept != null) lines.push(`✅ ${data.kept} kept (above ${(data.threshold || 0.7) * 100}% threshold)`)
            if (data.discarded > 0) lines.push(`🗑️ ${data.discarded} discarded`)
            if (data.duplicates_removed > 0) lines.push(`♻️ ${data.duplicates_removed} duplicates removed`)
            break
        case 'fine_tuning':
            if (data.job_name) lines.push(`🔧 Job: ${data.job_name}`)
            if (data.duration_min) lines.push(`⏱️ ${data.duration_min} minutes`)
            if (data.final_loss != null) lines.push(`📉 Final loss: ${data.final_loss}`)
            break
        case 'deployment':
            if (data.endpoint_url) lines.push(`🚀 Endpoint: ${data.endpoint_url}`)
            break
        default:
            // Generic: show any keys with values
            Object.entries(data).forEach(([k, v]) => {
                if (v != null && typeof v !== 'object') lines.push(`${k}: ${v}`)
            })
    }
    return lines
}

export default function ProjectDetailPage() {
    const { id } = useParams()
    const navigate = useNavigate()
    const [project, setProject] = useState(null)
    const [pipelineStatus, setPipelineStatus] = useState('NOT_STARTED')
    const [results, setResults] = useState(null)
    const [activeStep, setActiveStep] = useState(null)
    const [loading, setLoading] = useState(true)
    const [deleting, setDeleting] = useState(false)
    const [showDeleteDialog, setShowDeleteDialog] = useState(false)

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

        const checkStatus = async () => {
            try {
                const statusData = await apiClient.get(`projects/${id}/status`)
                const rawStatus = statusData.pipeline_status || 'NOT_STARTED'
                const normalizedStatus = rawStatus === 'COMPLETE' ? 'SUCCEEDED' : rawStatus
                setPipelineStatus(normalizedStatus)
                setProject(prev => ({ ...prev, status: statusData.project_status || prev.status }))
            } catch (err) {
                console.error("Status error", err)
            }
        }

        checkStatus()

        let interval
        if (pipelineStatus === 'RUNNING') {
            interval = setInterval(checkStatus, 5000)
        }

        return () => clearInterval(interval)
    }, [id, project?.id, pipelineStatus])

    // ── Fetch results when pipeline finishes ──────────────────────────────────
    useEffect(() => {
        if (pipelineStatus !== 'SUCCEEDED' && pipelineStatus !== 'FAILED') return

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
        try {
            setDeleting(true)
            await apiClient.delete(`projects/${id}`)
            setShowDeleteDialog(false)
            navigate('/projects')
        } catch (err) {
            console.error('Delete error:', err)
        } finally {
            setDeleting(false)
        }
    }

    // ── Mode-based steps ────────────────────────────────────────────────────────
    const modeSteps = getStepsForMode(project?.mode)
    const stepCount = modeSteps.length

    // ── Derive pipeline progress array ────────────────────────────────────────
    const derivePipelineArr = () => {
        const arr = []
        const isRun = pipelineStatus === 'RUNNING'
        const isSuc = pipelineStatus === 'SUCCEEDED'
        const isErr = pipelineStatus === 'FAILED'

        for (let i = 0; i < stepCount; i++) {
            if (isSuc) {
                arr.push({ step: i + 1, status: 'complete', progress: 100 })
            } else if (isErr) {
                // Mark the last step as error, previous as complete
                if (i === stepCount - 1) arr.push({ step: i + 1, status: 'error', progress: 50 })
                else arr.push({ step: i + 1, status: 'complete', progress: 100 })
            } else if (isRun) {
                // Estimate: first half complete, middle running, rest pending
                const mid = Math.floor(stepCount / 2)
                if (i < mid) arr.push({ step: i + 1, status: 'complete', progress: 100 })
                else if (i === mid) arr.push({ step: i + 1, status: 'running', progress: 65 })
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
    const overallProgress = Math.round((completedSteps / stepCount) * 100)
    const displayStep = activeStep !== null ? activeStep : Math.min(completedSteps, stepCount - 1)
    const currentPipelineStep = pipelineArr[displayStep] || { status: 'pending', progress: 0 }
    const currentStepDef = modeSteps[displayStep]
    const StepIcon = stepIconMap[currentStepDef?.icon] || Circle
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
                    <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
                        <DialogTrigger asChild>
                            <Button
                                variant="outline"
                                size="sm"
                                className="gap-1.5 text-destructive hover:text-destructive"
                            >
                                <Trash2 className="w-3.5 h-3.5" />
                                Delete
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-md">
                            <DialogHeader>
                                <DialogTitle>Delete Project</DialogTitle>
                                <DialogDescription>
                                    Are you sure you want to delete <span className="font-semibold text-foreground">{project.name}</span>? This will permanently remove the project, all uploaded files, and generated datasets. This action cannot be undone.
                                </DialogDescription>
                            </DialogHeader>
                            <DialogFooter className="gap-2 sm:gap-0">
                                <DialogClose asChild>
                                    <Button variant="outline" size="sm" disabled={deleting}>
                                        Cancel
                                    </Button>
                                </DialogClose>
                                <Button
                                    variant="destructive"
                                    size="sm"
                                    className="gap-1.5"
                                    onClick={handleDelete}
                                    disabled={deleting}
                                >
                                    {deleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                                    {deleting ? 'Deleting...' : 'Delete Project'}
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
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
                    <p className="text-sm font-semibold mt-1">{completedSteps}/{stepCount} steps ({overallProgress}%)</p>
                </div>
            </div>

            {/* Pipeline Tracker */}
            <Card className="border-border bg-card">
                <CardHeader className="pb-4">
                    <CardTitle className="text-base">Pipeline Progress</CardTitle>
                </CardHeader>
                <CardContent>
                    <PipelineTracker
                        steps={modeSteps}
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

            {/* Step Results Panel */}
            {results?.step_results && Object.keys(results.step_results).length > 0 && (
                <Card className="border-border bg-card mt-6">
                    <CardHeader className="pb-3 border-b border-border bg-muted/20">
                        <CardTitle className="text-sm font-semibold flex items-center gap-2 text-muted-foreground uppercase tracking-wider">
                            <Layers className="w-4 h-4" />
                            Pipeline Step Results
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="divide-y divide-border">
                            {Object.entries(results.step_results).map(([stepName, data]) => {
                                const summaryLines = buildStepSummary(stepName, data)
                                if (!summaryLines.length) return null
                                const hasError = data?.errors?.length > 0 || data?.files_failed > 0
                                return (
                                    <div key={stepName} className="px-4 py-3 flex flex-col sm:flex-row sm:items-start gap-2">
                                        <div className="flex items-center gap-2 min-w-[140px] shrink-0">
                                            <div className={`w-2 h-2 rounded-full ${hasError ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                                            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                                {stepName.replace(/_/g, ' ')}
                                            </span>
                                        </div>
                                        <div className="text-xs text-foreground space-y-0.5">
                                            {summaryLines.map((line, i) => (
                                                <p key={i} className={line.startsWith('⚠') || line.startsWith('❌') ? 'text-amber-400' : ''}>
                                                    {line}
                                                </p>
                                            ))}
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    )
}
