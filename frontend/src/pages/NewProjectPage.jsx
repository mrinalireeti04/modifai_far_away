import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    FileText,
    Upload,
    Settings2,
    CheckCircle2,
    ArrowLeft,
    ArrowRight,
    Sparkles,
    Check,
    Target,
    Layers,
    MessageSquare,
    BookOpen,
    Palette,
    Tags,
    Bot,
    Zap,
    Database,
    Rocket,
    Brain,
    AlertCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import FileUploadZone from '@/components/FileUploadZone'
import { apiClient } from '@/api/client'

// ── Mode Definitions ──────────────────────────────────────────────────────────
const MODES = [
    {
        value: 'dataset_only',
        label: 'Dataset Only',
        icon: Database,
        desc: 'Generate a clean JSONL training dataset from your documents. No fine-tuning.',
        steps: ['Intent', 'Upload', 'Evaluate', 'Config', 'Review'],
    },
    {
        value: 'finetune_only',
        label: 'Fine-Tune Only',
        icon: Brain,
        desc: 'Fine-tune a model on your existing JSONL dataset. Skip data generation.',
        steps: ['Upload', 'Config', 'Review'],
    },
    {
        value: 'dataset_and_finetune',
        label: 'Dataset + Fine-Tune',
        icon: Zap,
        desc: 'Generate a dataset from documents and then fine-tune a model on it.',
        steps: ['Intent', 'Upload', 'Evaluate', 'Config', 'Review'],
    },
    {
        value: 'full',
        label: 'Full Pipeline',
        icon: Rocket,
        desc: 'End-to-end: generate dataset → fine-tune → deploy as API endpoint.',
        steps: ['Intent', 'Upload', 'Evaluate', 'Config', 'Review'],
    },
]

// ── Intent Definitions ────────────────────────────────────────────────────────
const INTENTS = [
    {
        value: 'question-answering',
        label: 'Question Answering',
        icon: MessageSquare,
        desc: 'Train a model to answer questions about your domain knowledge.',
    },
    {
        value: 'summarization',
        label: 'Summarization',
        icon: BookOpen,
        desc: 'Train a model to summarize long documents into concise outputs.',
    },
    {
        value: 'tone-rewriting',
        label: 'Tone Rewriting',
        icon: Palette,
        desc: 'Train a model to rewrite text in a specific tone or style.',
    },
    {
        value: 'classification',
        label: 'Classification',
        icon: Tags,
        desc: 'Train a model to categorize text into predefined labels.',
    },
    {
        value: 'general-assistant',
        label: 'General Assistant',
        icon: Bot,
        desc: 'Train a general-purpose assistant for your domain.',
    },
]

// ── Model Definitions ─────────────────────────────────────────────────────────
const MODELS = [
    { value: 'llama-3.1-8b', label: 'Llama 3.1 8B', desc: 'Fast, efficient general-purpose' },
    { value: 'mistral-7b', label: 'Mistral 7B', desc: 'Strong reasoning and instruction' },
    { value: 'gemma-2-9b', label: 'Gemma 2 9B', desc: 'Balanced performance' },
    { value: 'phi-3-mini', label: 'Phi-3 Mini', desc: 'Compact, great for edge' },
]

// ── Dynamic Steps Based on Mode ───────────────────────────────────────────────
function getSteps(mode) {
    const includesDataset = mode !== 'finetune_only'
    const includesFineTune = mode !== 'dataset_only'

    const steps = [
        { id: 'mode', label: 'Pipeline Mode', icon: Layers },
    ]

    if (includesDataset) {
        steps.push({ id: 'intent', label: 'Intent', icon: Target })
    }

    steps.push({ id: 'upload', label: 'Upload Data', icon: Upload })

    if (includesDataset) {
        steps.push({ id: 'evaluate', label: 'Evaluate', icon: Sparkles })
    }

    steps.push({ id: 'config', label: 'Configuration', icon: Settings2 })
    steps.push({ id: 'review', label: 'Review & Start', icon: CheckCircle2 })

    return steps
}

export default function NewProjectPage() {
    const navigate = useNavigate()
    const [currentStep, setCurrentStep] = useState(0)

    // Form state
    const [name, setName] = useState('')
    const [description, setDescription] = useState('')
    const [mode, setMode] = useState('dataset_only')
    const [intent, setIntent] = useState('')
    const [useCase, setUseCase] = useState('')
    const [files, setFiles] = useState([])
    const [model, setModel] = useState('llama-3.1-8b')
    const [samplesPerChunk, setSamplesPerChunk] = useState([5])
    const [qualityThreshold, setQualityThreshold] = useState([70])

    // Evaluate Data Phase
    const [evaluating, setEvaluating] = useState(false)
    const [evalScore, setEvalScore] = useState(null)
    const [evalExplanation, setEvalExplanation] = useState(null)
    const [extractedText, setExtractedText] = useState('')

    // Submission state
    const [submitting, setSubmitting] = useState(false)
    const [submitError, setSubmitError] = useState(null)

    const steps = getSteps(mode)
    const currentStepId = steps[currentStep]?.id

    const includesDataset = mode !== 'finetune_only'
    const includesFineTune = mode !== 'dataset_only'

    const canProceed = () => {
        switch (currentStepId) {
            case 'mode': return name.trim().length >= 3
            case 'intent': return intent && useCase.trim().length >= 10
            case 'upload': return files.length > 0
            case 'evaluate': return evalScore !== null
            case 'config': return !!model
            case 'review': return true
            default: return false
        }
    }

    // Reset dependent state when mode changes
    const handleModeChange = (newMode) => {
        setMode(newMode)
        setCurrentStep(0) // Always go back to step 0 when mode changes
        // Reset evaluation
        setEvalScore(null)
        setEvalExplanation(null)
        setExtractedText('')
        // Reset intent if switching to finetune_only
        if (newMode === 'finetune_only') {
            setIntent('')
            setUseCase('')
        }
    }

    const handleEvaluate = async () => {
        if (!files.length) return

        setEvaluating(true)
        setEvalScore(null)
        setEvalExplanation(null)

        try {
            const file = files[0].file
            const text = await new Promise((resolve, reject) => {
                const reader = new FileReader()
                reader.onload = (e) => resolve(e.target.result.substring(0, 2000))
                reader.onerror = reject
                reader.readAsText(file)
            })

            setExtractedText(text.substring(0, 300) + '...')

            const result = await apiClient.post('evaluate/', {
                text_sample: text,
                intent: `${intent}: ${useCase}`,
            })

            setEvalScore(result.score)
            setEvalExplanation(result.explanation)
        } catch (error) {
            console.error("Evaluation error:", error)
            setEvalExplanation("Failed to evaluate the dataset. You can proceed anyway.")
            setEvalScore(0.5)
        } finally {
            setEvaluating(false)
        }
    }

    const handleSubmit = async () => {
        try {
            setSubmitting(true)
            setSubmitError(null)

            // 1. Create the project
            const project = await apiClient.post('projects/', {
                name,
                description,
                mode,
                intent: includesDataset ? intent : null,
                base_model: model,
                config: {
                    samples_per_chunk: samplesPerChunk[0],
                    quality_threshold: qualityThreshold[0] / 100,
                },
            })

            // 2. Upload files via presigned URLs
            for (const fileObj of files) {
                const urlData = await apiClient.post(
                    `projects/${project.id}/upload-url?filename=${encodeURIComponent(fileObj.name)}`
                )

                const uploadResponse = await fetch(urlData.presigned_url, {
                    method: 'PUT',
                    body: fileObj.file,
                    headers: { 'Content-Type': fileObj.type || 'application/octet-stream' },
                })
                if (!uploadResponse.ok) throw new Error(`Failed to upload ${fileObj.name} to S3`)
            }

            // 3. Start the pipeline
            await apiClient.post(`projects/${project.id}/start`, {
                config: {
                    intent: includesDataset ? `${intent}: ${useCase}` : undefined,
                    samples_per_chunk: samplesPerChunk[0],
                    quality_threshold: qualityThreshold[0] / 100,
                },
            })

            // 4. Navigate to the detail page
            navigate(`/projects/${project.id}`)

        } catch (error) {
            console.error("Submission error:", error)
            setSubmitError(error.message || 'Failed to create project')
        } finally {
            setSubmitting(false)
        }
    }

    // ── Render ─────────────────────────────────────────────────────────────────
    return (
        <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-8">
            {/* Header */}
            <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => navigate(-1)}>
                    <ArrowLeft className="w-4 h-4" />
                </Button>
                <div>
                    <h1 className="text-2xl font-bold">Create New Project</h1>
                    <p className="text-sm text-muted-foreground">Set up your data-to-model pipeline</p>
                </div>
            </div>

            {/* Stepper */}
            <div className="flex items-center gap-0 overflow-x-auto pb-2 -mx-4 px-4 sm:mx-0 sm:px-0">
                {steps.map((step, i) => {
                    const Icon = step.icon
                    const isCompleted = i < currentStep
                    const isActive = i === currentStep
                    const isFuture = i > currentStep

                    return (
                        <React.Fragment key={step.id}>
                            <button
                                onClick={() => i < currentStep && setCurrentStep(i)}
                                disabled={isFuture}
                                className={`
                                    flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium
                                    transition-all duration-200 shrink-0
                                    ${isActive
                                        ? 'bg-primary/15 text-primary'
                                        : isCompleted
                                            ? 'text-primary/70 hover:bg-primary/10 cursor-pointer'
                                            : 'text-muted-foreground cursor-default'
                                    }
                                `}
                            >
                                <div className={`w-7 h-7 shrink-0 rounded-full flex items-center justify-center text-xs font-semibold border transition-all duration-200 ${isActive
                                    ? 'bg-primary text-primary-foreground border-primary'
                                    : isCompleted
                                        ? 'bg-primary/20 text-primary border-primary/30'
                                        : 'border-border text-muted-foreground'
                                    }`}>
                                    {isCompleted ? <Check className="w-3.5 h-3.5" /> : i + 1}
                                </div>
                                <span className={isActive ? 'inline' : 'hidden md:inline'}>{step.label}</span>
                            </button>
                            {i < steps.length - 1 && (
                                <div className={`w-8 sm:flex-1 h-px mx-1 transition-colors duration-300 ${i < currentStep ? 'bg-primary/40' : 'bg-border'
                                    }`} />
                            )}
                        </React.Fragment>
                    )
                })}
            </div>

            {/* Step Content */}
            <Card className="border-border bg-card">
                <CardContent className="p-6 overflow-hidden">

                    {/* ── Step: Mode Selection ───────────────────────────────── */}
                    {currentStepId === 'mode' && (
                        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <div className="space-y-1">
                                <h2 className="text-lg font-semibold">Pipeline Mode & Project Info</h2>
                                <p className="text-sm text-muted-foreground">Choose what the platform should do and give your project a name</p>
                            </div>

                            {/* Project name */}
                            <div className="space-y-2">
                                <Label htmlFor="name">Project Name *</Label>
                                <Input
                                    id="name"
                                    placeholder="e.g. Customer Support Bot"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    className="bg-background"
                                />
                                {name.length > 0 && name.length < 3 && (
                                    <p className="text-xs text-destructive">Name must be at least 3 characters</p>
                                )}
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="desc">Description</Label>
                                <Textarea
                                    id="desc"
                                    placeholder="Briefly describe your project"
                                    value={description}
                                    onChange={(e) => setDescription(e.target.value)}
                                    rows={2}
                                    className="bg-background resize-none"
                                />
                            </div>

                            <Separator className="my-2" />

                            {/* Mode cards */}
                            <div className="space-y-3">
                                <Label>Pipeline Mode</Label>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {MODES.map((m) => {
                                        const ModeIcon = m.icon
                                        return (
                                            <label
                                                key={m.value}
                                                className={`
                                                    relative flex cursor-pointer rounded-lg border p-4 shadow-sm
                                                    hover:border-primary focus:outline-none transition-all
                                                    ${mode === m.value
                                                        ? 'border-primary bg-primary/5 ring-1 ring-primary'
                                                        : 'border-border bg-card'
                                                    }
                                                `}
                                            >
                                                <input
                                                    type="radio"
                                                    name="mode"
                                                    value={m.value}
                                                    className="sr-only"
                                                    onChange={() => handleModeChange(m.value)}
                                                    checked={mode === m.value}
                                                />
                                                <div className="flex items-start gap-3">
                                                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${mode === m.value ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground'
                                                        }`}>
                                                        <ModeIcon className="w-4.5 h-4.5" />
                                                    </div>
                                                    <div className="flex flex-col">
                                                        <span className="block text-sm font-medium">{m.label}</span>
                                                        <span className="block text-xs text-muted-foreground mt-1">{m.desc}</span>
                                                    </div>
                                                </div>
                                            </label>
                                        )
                                    })}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* ── Step: Intent Selection ─────────────────────────────── */}
                    {currentStepId === 'intent' && (
                        <div className="space-y-6 animate-in slide-in-from-right-8 duration-500">
                            <div className="space-y-1">
                                <h2 className="text-lg font-semibold">Intent & Use Case</h2>
                                <p className="text-sm text-muted-foreground">Select what task your model should perform and describe your use case</p>
                            </div>

                            {/* Intent cards */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                                {INTENTS.map((item) => {
                                    const IntentIcon = item.icon
                                    return (
                                        <label
                                            key={item.value}
                                            className={`
                                                relative flex cursor-pointer rounded-lg border p-4 shadow-sm
                                                hover:border-primary focus:outline-none transition-all
                                                ${intent === item.value
                                                    ? 'border-primary bg-primary/5 ring-1 ring-primary'
                                                    : 'border-border bg-card'
                                                }
                                            `}
                                        >
                                            <input
                                                type="radio"
                                                name="intent"
                                                value={item.value}
                                                className="sr-only"
                                                onChange={() => setIntent(item.value)}
                                                checked={intent === item.value}
                                            />
                                            <div className="flex flex-col items-center text-center gap-2">
                                                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${intent === item.value ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground'
                                                    }`}>
                                                    <IntentIcon className="w-5 h-5" />
                                                </div>
                                                <span className="text-sm font-medium">{item.label}</span>
                                                <span className="text-xs text-muted-foreground">{item.desc}</span>
                                            </div>
                                        </label>
                                    )
                                })}
                            </div>

                            <Separator />

                            {/* Use-case description */}
                            <div className="space-y-2">
                                <Label htmlFor="usecase">Use-Case Description *</Label>
                                <Textarea
                                    id="usecase"
                                    placeholder="Describe how you intend to use the fine-tuned model. This guides the LLM to generate relevant training examples."
                                    value={useCase}
                                    onChange={(e) => setUseCase(e.target.value)}
                                    rows={3}
                                    className="bg-background resize-none"
                                />
                                {useCase.length > 0 && useCase.length < 10 && (
                                    <p className="text-xs text-destructive">Description must be at least 10 characters</p>
                                )}
                            </div>
                        </div>
                    )}

                    {/* ── Step: Upload Files ──────────────────────────────────── */}
                    {currentStepId === 'upload' && (
                        <div className="space-y-6 animate-in slide-in-from-right-8 duration-500">
                            <div className="space-y-1">
                                <h2 className="text-lg font-semibold">Upload Your Data</h2>
                                <p className="text-sm text-muted-foreground">
                                    {mode === 'finetune_only'
                                        ? 'Upload your JSONL training dataset file'
                                        : 'Upload the documents you want to use for training data generation'
                                    }
                                </p>
                            </div>
                            <FileUploadZone files={files} onFilesChange={setFiles} />
                        </div>
                    )}

                    {/* ── Step: Data Evaluation ───────────────────────────────── */}
                    {currentStepId === 'evaluate' && (
                        <div className="space-y-6 animate-in slide-in-from-right-8 duration-500">
                            <div className="space-y-1">
                                <h2 className="text-lg font-semibold flex items-center gap-2">
                                    <Sparkles className="w-5 h-5 text-primary" />
                                    Data Quality Check
                                </h2>
                                <p className="text-sm text-muted-foreground">
                                    We'll extract a sample from your files and evaluate if it's suitable for <span className="font-medium text-foreground">"{intent}"</span>
                                </p>
                            </div>

                            {!evalScore && !evaluating && (
                                <div className="rounded-lg border border-dashed border-border p-8 text-center bg-muted/20">
                                    <div className="mx-auto w-12 h-12 bg-primary/10 text-primary rounded-full flex items-center justify-center mb-4">
                                        <FileText className="w-6 h-6" />
                                    </div>
                                    <h3 className="font-semibold mb-1">Ready to Test</h3>
                                    <p className="text-sm text-muted-foreground mb-6 max-w-sm mx-auto">
                                        We'll extract ~2000 characters from {files[0]?.name} and ask Nova Micro to evaluate it.
                                    </p>
                                    <Button onClick={handleEvaluate} className="w-full sm:w-auto gap-2">
                                        <Sparkles className="w-4 h-4" />
                                        Run Automated Evaluation
                                    </Button>
                                </div>
                            )}

                            {evaluating && (
                                <div className="rounded-lg border border-border p-8 text-center bg-card shadow-sm">
                                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-4" />
                                    <p className="text-sm font-medium animate-pulse">Analyzing sample against intent...</p>
                                </div>
                            )}

                            {evalScore !== null && !evaluating && (
                                <div className="space-y-4">
                                    <div className={`rounded-lg border p-6 transition-all shadow-sm ${evalScore > 0.6 ? 'border-emerald-500/30 bg-emerald-500/5' :
                                        evalScore > 0.4 ? 'border-amber-500/30 bg-amber-500/5' :
                                            'border-red-500/30 bg-red-500/5'
                                        }`}>
                                        <div className="flex flex-col sm:flex-row items-center gap-6">
                                            <div className="relative shrink-0">
                                                <svg className="w-24 h-24 transform -rotate-90">
                                                    <circle cx="48" cy="48" r="40" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-muted/30" />
                                                    <circle cx="48" cy="48" r="40" stroke="currentColor" strokeWidth="8" fill="transparent"
                                                        strokeDasharray={40 * 2 * Math.PI}
                                                        strokeDashoffset={40 * 2 * Math.PI * (1 - evalScore)}
                                                        className={`transition-all duration-1000 ease-out ${evalScore > 0.6 ? 'text-emerald-500' :
                                                            evalScore > 0.4 ? 'text-amber-500' : 'text-red-500'
                                                            }`}
                                                    />
                                                </svg>
                                                <div className="absolute inset-0 flex items-center justify-center">
                                                    <span className="text-xl font-bold">{Math.round(evalScore * 100)}%</span>
                                                </div>
                                            </div>
                                            <div className="space-y-2 text-center sm:text-left">
                                                <h3 className="font-semibold text-lg flex items-center justify-center sm:justify-start gap-2">
                                                    {evalScore > 0.6 ? <CheckCircle2 className="w-5 h-5 text-emerald-500" /> : null}
                                                    {evalScore > 0.6 ? 'High Quality' : evalScore > 0.4 ? 'Acceptable Quality' : 'Low Quality'}
                                                </h3>
                                                <p className="text-sm text-muted-foreground leading-relaxed">
                                                    {evalExplanation}
                                                </p>
                                                {evalScore < 0.6 && (
                                                    <Button variant="outline" size="sm" onClick={handleEvaluate} className="mt-2 text-xs h-8">
                                                        Retest another sample
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    <div className="rounded-lg border border-border bg-muted/30 p-4">
                                        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-2">Sample Extracted & Tested</p>
                                        <p className="text-xs text-muted-foreground font-mono leading-relaxed bg-background/50 p-3 rounded border border-border/50">
                                            "{extractedText}"
                                        </p>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* ── Step: Configuration ─────────────────────────────────── */}
                    {currentStepId === 'config' && (
                        <div className="space-y-6 animate-in slide-in-from-right-8 duration-500">
                            <div className="space-y-1">
                                <h2 className="text-lg font-semibold">Pipeline Configuration</h2>
                                <p className="text-sm text-muted-foreground">Configure how the pipeline processes your data</p>
                            </div>

                            <div className="space-y-6">
                                {/* Model selection — show for modes that include fine-tuning */}
                                {includesFineTune && (
                                    <>
                                        <div className="space-y-2">
                                            <Label>Base Model</Label>
                                            <Select value={model} onValueChange={setModel}>
                                                <SelectTrigger className="bg-background">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {MODELS.map(m => (
                                                        <SelectItem key={m.value} value={m.value}>
                                                            <div className="flex items-center gap-2">
                                                                <span className="font-medium">{m.label}</span>
                                                                <span className="text-xs text-muted-foreground">— {m.desc}</span>
                                                            </div>
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <Separator />
                                    </>
                                )}

                                {/* Dataset config — show for modes that include dataset generation */}
                                {includesDataset && (
                                    <>
                                        <div className="space-y-3">
                                            <div className="flex items-center justify-between">
                                                <Label>Samples per Chunk</Label>
                                                <Badge variant="secondary" className="text-xs font-mono">{samplesPerChunk[0]}</Badge>
                                            </div>
                                            <Slider
                                                value={samplesPerChunk}
                                                onValueChange={setSamplesPerChunk}
                                                min={1} max={20} step={1}
                                                className="w-full"
                                            />
                                            <p className="text-xs text-muted-foreground">
                                                Number of synthetic training samples generated per text chunk.
                                            </p>
                                        </div>

                                        <Separator />

                                        <div className="space-y-3">
                                            <div className="flex items-center justify-between">
                                                <Label>Quality Threshold</Label>
                                                <Badge variant="secondary" className="text-xs font-mono">{qualityThreshold[0]}%</Badge>
                                            </div>
                                            <Slider
                                                value={qualityThreshold}
                                                onValueChange={setQualityThreshold}
                                                min={0} max={100} step={5}
                                                className="w-full"
                                            />
                                            <p className="text-xs text-muted-foreground">
                                                Minimum confidence score. Higher = stricter quality, fewer samples.
                                            </p>
                                        </div>
                                    </>
                                )}
                            </div>
                        </div>
                    )}

                    {/* ── Step: Review & Start ────────────────────────────────── */}
                    {currentStepId === 'review' && (
                        <div className="space-y-6 animate-in slide-in-from-right-8 duration-500">
                            <div className="space-y-1">
                                <h2 className="text-lg font-semibold">Review & Start Pipeline</h2>
                                <p className="text-sm text-muted-foreground">Verify your project settings before kicking off the pipeline</p>
                            </div>

                            <div className="space-y-4">
                                {/* Project summary */}
                                <div className="rounded-lg border border-border bg-background p-4 space-y-2">
                                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Project</p>
                                    <p className="font-semibold">{name}</p>
                                    {description && <p className="text-sm text-muted-foreground">{description}</p>}
                                    <Badge variant="outline" className="mt-1">
                                        {MODES.find(m => m.value === mode)?.label}
                                    </Badge>
                                </div>

                                {/* Intent summary — if applicable */}
                                {includesDataset && intent && (
                                    <div className="rounded-lg border border-border bg-background p-4 space-y-2">
                                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Intent</p>
                                        <p className="font-semibold">{INTENTS.find(i => i.value === intent)?.label}</p>
                                        <p className="text-sm text-muted-foreground">{useCase}</p>
                                    </div>
                                )}

                                {/* Files summary */}
                                <div className="rounded-lg border border-border bg-background p-4 space-y-2">
                                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Files</p>
                                    <p className="font-semibold">{files.length} file{files.length !== 1 ? 's' : ''}</p>
                                    <div className="flex flex-wrap gap-1.5">
                                        {files.slice(0, 5).map(f => (
                                            <Badge key={f.id} variant="outline" className="text-xs">{f.name}</Badge>
                                        ))}
                                        {files.length > 5 && <Badge variant="outline" className="text-xs">+{files.length - 5} more</Badge>}
                                    </div>
                                </div>

                                {/* Config summary */}
                                <div className="rounded-lg border border-border bg-background p-4 space-y-3">
                                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Configuration</p>
                                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
                                        {includesFineTune && (
                                            <div>
                                                <p className="text-muted-foreground text-xs">Base Model</p>
                                                <p className="font-medium">{MODELS.find(m => m.value === model)?.label}</p>
                                            </div>
                                        )}
                                        {includesDataset && (
                                            <>
                                                <div>
                                                    <p className="text-muted-foreground text-xs">Samples/Chunk</p>
                                                    <p className="font-medium">{samplesPerChunk[0]}</p>
                                                </div>
                                                <div>
                                                    <p className="text-muted-foreground text-xs">Quality Threshold</p>
                                                    <p className="font-medium">{qualityThreshold[0]}%</p>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                </div>

                                {/* Evaluation summary */}
                                {includesDataset && evalScore !== null && (
                                    <div className="rounded-lg border border-border bg-background p-4 space-y-2">
                                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Data Quality</p>
                                        <p className="font-semibold">{Math.round(evalScore * 100)}% — {evalScore > 0.6 ? 'High Quality' : evalScore > 0.4 ? 'Acceptable' : 'Low Quality'}</p>
                                    </div>
                                )}

                                {/* Error */}
                                {submitError && (
                                    <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 flex items-start gap-3">
                                        <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                                        <div>
                                            <p className="text-sm font-medium text-red-500">Failed to start pipeline</p>
                                            <p className="text-xs text-muted-foreground mt-1">{submitError}</p>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Navigation buttons */}
            <div className="flex items-center justify-between">
                <Button
                    variant="outline"
                    className="gap-2"
                    onClick={() => currentStep === 0 ? navigate(-1) : setCurrentStep(currentStep - 1)}
                >
                    <ArrowLeft className="w-4 h-4" />
                    {currentStep === 0 ? 'Cancel' : 'Back'}
                </Button>

                {currentStepId !== 'review' ? (
                    <Button
                        className="gap-2 bg-primary hover:bg-primary/90 text-primary-foreground"
                        disabled={!canProceed()}
                        onClick={() => setCurrentStep(currentStep + 1)}
                    >
                        Continue
                        <ArrowRight className="w-4 h-4" />
                    </Button>
                ) : (
                    <Button
                        className="gap-2 bg-primary hover:bg-primary/90 text-primary-foreground glow"
                        onClick={handleSubmit}
                        disabled={submitting}
                    >
                        {submitting ? (
                            <div className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                        ) : (
                            <Sparkles className="w-4 h-4" />
                        )}
                        {submitting ? 'Creating Project...' : 'Start Pipeline'}
                    </Button>
                )}
            </div>
        </div>
    )
}
